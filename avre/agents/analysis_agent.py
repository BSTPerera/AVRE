
import subprocess
import asyncio
from typing import List, Dict
from pathlib import Path
from playwright.async_api import async_playwright
from avre.config import SEMGREP_RULES, ARTIFACTS_DIR
from avre.utils.logger import get_logger
from avre.database import add_artifact

class AnalysisAgent:
    def __init__(self, session_id: str, custom_payload: str = None):
        self.session_id = session_id
        self.logger = get_logger("AnalysisAgent", session_id)
        # Basic Polyglots
        self.payloads = [
            "<script>alert(1)</script>",
            "\"><script>alert(1)</script>",
            "\"><img src=x onerror=alert(1)>",
            "javascript:alert(1)"
        ]
        
        if custom_payload:
            self.logger.info(f"Adding custom payload: {custom_payload}")
            self.payloads.insert(0, custom_payload)

    def run_static_analysis(self, workspace_path: Path) -> Dict:
        self.logger.info(f"Running Semgrep on {workspace_path}...")
        try:
            cmd = ["semgrep", "--config", SEMGREP_RULES, "--json", str(workspace_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            output_path = ARTIFACTS_DIR / f"semgrep_{self.session_id}_{workspace_path.name}.json"
            
            with open(output_path, "w") as f:
                f.write(result.stdout)
                
            add_artifact(self.session_id, "semgrep_report", str(output_path))
            
            # Simple check: did we find anything?
            import json
            data = json.loads(result.stdout)
            match_count = len(data.get("results", []))
            self.logger.info(f"Semgrep found {match_count} issues.")
            
            return {"matches": match_count, "report": str(output_path)}
        except Exception as e:
            self.logger.error(f"Semgrep failed: {e}")
            return {"matches": 0, "error": str(e)}

    async def verify_xss(self, url: str) -> bool:
        self.logger.info(f"Starting Dynamic Analysis on {url}...")
        is_vulnerable = False
        
        async with async_playwright() as p:
            # Launch with headless=True for speed, or False for debugging
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Wrapper to safely extract port from URL
            from urllib.parse import urlparse
            def get_port(u):
                try:
                    return str(urlparse(u).port)
                except:
                    return "unknown"

            # Listener for dialogs (alert/confirm/prompt)
            async def handle_dialog(dialog):
                nonlocal is_vulnerable
                self.logger.warning(f"Dialog triggered! Type: {dialog.type}, Message: {dialog.message}")
                if "1" in dialog.message: # Our payload triggers alert(1)
                    is_vulnerable = True
                    
                    # We MUST dismiss the dialog first, otherwise page.screenshot will hang waiting for fonts/renderer which are blocked by the alert.
                    await dialog.dismiss()

                    # Capture screenshot immediately upon trigger
                    try:
                        port = get_port(url)
                        # Ensure artifacts dir exists (it should)
                        trigger_path = ARTIFACTS_DIR / f"triggered_{self.session_id}_{port}.png"
                        await page.screenshot(path=str(trigger_path))
                        add_artifact(self.session_id, "triggered_screenshot", str(trigger_path))
                        self.logger.info(f"Captured trigger screenshot: {trigger_path}")
                    except Exception as e:
                        self.logger.error(f"Failed to capture trigger screenshot: {e}")
                    return # Exit handler

                # If not our target dialog, just dismiss
                await dialog.dismiss()

            page.on("dialog", handle_dialog)

            try:
                # Basic navigation
                await page.goto(url, wait_until="networkidle")
                
                # 1. Baseline Screenshot (Hosted State)
                try:
                    port = get_port(url)
                    baseline_path = ARTIFACTS_DIR / f"screenshot_{self.session_id}_{port}.png"
                    await page.screenshot(path=str(baseline_path))
                    add_artifact(self.session_id, "screenshot", str(baseline_path))
                    self.logger.info(f"Captured baseline screenshot: {baseline_path}")
                except Exception as e:
                    self.logger.error(f"Failed to capture baseline screenshot: {e}")
                
                # Fuzzing Loop
                # Locate inputs - simple heuristic: match 'input' or 'textarea'
                inputs = await page.locator("input, textarea").all()
                self.logger.info(f"Found {len(inputs)} inputs.")
                
                for input_el in inputs:
                    if is_vulnerable: break
                    for payload in self.payloads:
                        if is_vulnerable: break
                        try:
                            # Clear and type
                            await input_el.fill(payload)
                            await input_el.press("Enter")
                            # Give it a moment to trigger
                            await page.wait_for_timeout(1000)
                        except Exception as e:
                            self.logger.debug(f"Input interaction failed: {e}")

                # (Optional) Post-fuzzing screenshot? 
                # We already have baseline. If triggered, we have that too.


            except Exception as e:
                self.logger.error(f"Playwright error: {e}")
            finally:
                await browser.close()
                
        return is_vulnerable

    def run_dynamic_analysis(self, url: str) -> bool:
        return asyncio.run(self.verify_xss(url))
