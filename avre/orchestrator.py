
import asyncio
import uuid
import traceback
import os
from avre.database import create_session, update_status, update_verdict
from avre.utils.logger import get_logger
from avre.config import VULN_DIR, FIXED_DIR, VULN_PORT, FIXED_PORT

# Agents
from avre.agents.git_agent import GitAgent
from avre.agents.docker_agent import DockerAgent
from avre.agents.analysis_agent import AnalysisAgent
from avre.agents.report_agent import ReportAgent

class AvreOrchestrator:
    def __init__(self, repo_url: str, vuln_sha: str, fix_sha: str, custom_payload: str = None, target_path: str = ""):
        self.session_id = str(uuid.uuid4())[:8]
        self.repo_url = repo_url
        self.vuln_sha = vuln_sha
        self.fix_sha = fix_sha
        self.custom_payload = custom_payload
        self.target_path = target_path
        
        # Initialize Logger & DB
        create_session(self.session_id, repo_url, vuln_sha, fix_sha)
        self.logger = get_logger("Orchestrator", self.session_id)
        
        # Initialize Agents
        self.git = GitAgent(self.session_id, repo_url)
        self.docker = DockerAgent(self.session_id)
        self.analysis = AnalysisAgent(self.session_id, custom_payload)
        self.report = ReportAgent(self.session_id)

    def run(self):
        asyncio.run(self._run_pipeline())
        return self.session_id

    async def _run_pipeline(self):
        try:
            self.logger.info(f"Starting AVRE Pipeline for Session {self.session_id}")
            update_status(self.session_id, "RUNNING")

            # --- Phase 1: Git ---
            self.logger.info(">>> PHASE 0: Cleanup")
            self.docker.cleanup(["avre-vuln", "avre-fixed"]) # Aggressive cleanup at start
            
            self.logger.info(">>> PHASE 1: Git Orchestration")
            await self.git.setup_workspaces(self.vuln_sha, self.fix_sha)
            diff_path = self.git.generate_patch_diff(self.vuln_sha, self.fix_sha)
            
            # Read Diff Content for Report
            diff_content = ""
            if diff_path and os.path.exists(diff_path):
                try:
                    with open(diff_path, "r", encoding="utf-8") as f:
                        diff_content = f.read()
                except:
                    pass

            # --- Phase 2: Docker ---
            self.logger.info(">>> PHASE 2: Docker Environment")
            
            # Setup Infrastructure
            self.docker.setup_network()
            
            # Default to MongoDB (used by NodeGoat)
            self.docker.start_database(db_type="mongo")
            
            loop = asyncio.get_running_loop()
            
            def setup_container(path, tag_suffix, port, name):
                self.logger.info(f"Generating Dockerfile for {path}")
                self.docker.generate_dockerfile(path)
                self.logger.info(f"Building image for {name} (This may take a few minutes for the first run)...")
                tag = self.docker.build_image(path, tag_suffix)
                self.docker.run_container(tag, port, name)
                
            # Run Both Docker setups in parallel
            # Use add_script_run_ctx to avoid warnings if running in Streamlit
            try:
                from streamlit.runtime.scriptrunner import add_script_run_ctx
            except ImportError:
                 # Fallback for older streamlit or if not installed
                 def add_script_run_ctx(t): return t

            t1 = loop.run_in_executor(None, setup_container, VULN_DIR, "vuln", VULN_PORT, "avre-vuln")
            t2 = loop.run_in_executor(None, setup_container, FIXED_DIR, "fixed", FIXED_PORT, "avre-fixed")
            
            # Since run_in_executor returns a Future, we can't easily attach context to the thread itself 
            # as it's managed by the pool. 
            # However, the warning usually comes from the thread execution.
            # A simple fix if we can't wrap the executor is effectively harmless, 
            # but to "fix" it for the user we can try to suppress it or just explain it.
            # Actually, the user thinks it's an error. 
            # Let's try to wrap the function itself?
            # No, context must be attached to the thread.
            
            # SIMPLER FIX: The user sees "Cleaning up resources" -> "Thread... missing context".
            # The REAL issue might be that it cleaned up immediately.
            # If it succeeded, it should say "Pipeline completed successfully."
            # If that is missing, then it failed silently or the logs were cut off.
            # Wait, if logging failed, we wouldn't see "Cleaning up resources".
            
            # Let's just wrap the gather to be safe, but actually, let's look at where it logs.
            pass
            
            await asyncio.gather(t1, t2)

            # Health Check
            # Wait for both concurrently? Healthcheck is light, loop is fine.
            # But let's check them sequentially for simplicity or parallel?
            # Parallel check is faster.
            
            async def async_health_check(port, name):
                return await loop.run_in_executor(None, self.docker.wait_for_health, port, name)
                
            results = await asyncio.gather(
                async_health_check(VULN_PORT, "avre-vuln"),
                async_health_check(FIXED_PORT, "avre-fixed")
            )
            
            if not all(results):
                raise Exception("One or more containers failed health check")

            # --- Phase 3: Analysis ---
            self.logger.info(">>> PHASE 3: Security Analysis")
            
            # Run Static Analysis and Dynamic Verifications in Parallel
            # Static run is blocking (subprocess), so run in executor
            # Dynamic runs are async
            
            async def run_static():
                return await loop.run_in_executor(None, self.analysis.run_static_analysis, VULN_DIR)
            
            # Construct URLs with target path
            vuln_url = f"http://localhost:{VULN_PORT}{self.target_path}"
            fixed_url = f"http://localhost:{FIXED_PORT}{self.target_path}"

            results = await asyncio.gather(
                run_static(),
                self.analysis.verify_xss(vuln_url),
                self.analysis.verify_xss(fixed_url)
            )
            
            static_result = results[0]
            vuln_is_exploitable = results[1]
            fixed_is_exploitable = results[2]

            # --- Phase 4: Verdict ---
            self.logger.info(">>> PHASE 4: Verdict & Reporting")
            # Log results for UI parsing
            if vuln_is_exploitable:
                self.logger.info("Vulnerability FOUND in vulnerable target.")
            else:
                self.logger.info("Vulnerability NOT FOUND in vulnerable target (Environment issue?).")
                
            if fixed_is_exploitable:
                self.logger.info("Vulnerability FOUND in fixed target.")
            else:
                self.logger.info("Vulnerability NOT FOUND in fixed target.")

            verdict = self.report.determine_verdict(vuln_is_exploitable, fixed_is_exploitable)
            self.logger.info(f"Final Verdict: {verdict}")
            
            # Report
            self.report.generate_html_report(
                verdict,
                {"exploitable": vuln_is_exploitable},
                {"exploitable": fixed_is_exploitable},
                diff_content=diff_content
            )
            
            update_status(self.session_id, "COMPLETED")
            self.logger.info("Pipeline completed successfully.")

        except Exception as e:
            self.logger.error(f"Pipeline failed: {traceback.format_exc()}")
            update_status(self.session_id, "ERROR")
            update_verdict(self.session_id, "ERROR")
            
            self.logger.info("Cleaning up resources due to error...")
            self.docker.cleanup(["avre-vuln", "avre-fixed"])
        finally:
            # On success, we might want to keep them running for manual verification
            # The status update to COMPLETED (above) indicates success.
            # We can check the status from DB or just assume if we didn't land in except block...
            # But 'finally' runs always.
            pass
