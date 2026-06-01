
import git
import os
import shutil
import asyncio
import time
import stat
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from avre.config import VULN_DIR, FIXED_DIR, ARTIFACTS_DIR
from avre.utils.logger import get_logger
from avre.database import add_artifact

class GitAgent:
    def __init__(self, session_id: str, repo_url: str):
        self.session_id = session_id
        self.repo_url = repo_url
        self.logger = get_logger("GitAgent", session_id)
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _on_rm_error(self, func, path, exc_info):
        """
        Error handler for shutil.rmtree.
        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.
        If the error is because the file is being used by another process, 
        it waits and retries.
        """
        # 1. Attempt to change permissions
        try:
            os.chmod(path, stat.S_IWRITE)
        except Exception:
            pass
        
        # 2. Retry with delay
        try:
            func(path)
        except Exception as e:
            self.logger.warning(f"Retrying deletion for {path} after error: {e}")
            time.sleep(0.5)
            try:
                func(path)
            except Exception as e2:
                self.logger.error(f"Failed to delete {path}: {e2}")

    def _prepare_directory(self, path: Path):
        start = time.time()
        # Give a small buffer for handles to release
        time.sleep(1) 
        
        while path.exists():
            try:
                shutil.rmtree(path, onerror=self._on_rm_error)
            except Exception as e:
                self.logger.warning(f"Standard cleanup failed, trying forceful cleanup... ({e})")
                
                # Windows Force Delete Fallback
                if os.name == 'nt':
                    try:
                        import subprocess
                        # rmdir /s /q is very aggressive
                        subprocess.run(f'rmdir /s /q "{path}"', shell=True, check=True)
                    except Exception as e2:
                        self.logger.warning(f"Force delete failed: {e2}")
            
            if not path.exists():
                break
            
            if time.time() - start > 10: # 10 seconds timeout
                raise Exception(f"Could not clean directory {path} - PLEASE CLOSE ANY OPEN FILES IN VS CODE.")
            time.sleep(1)
            
        os.makedirs(path, exist_ok=True)

    def _clone_and_checkout(self, path: Path, sha: str, label: str):
        self.logger.info(f"[{label}] Preparing workspace...")
        self._prepare_directory(path)
        
        self.logger.info(f"[{label}] Cloning...")
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                # Clone with some robust options
                # config='core.protectNTFS=false' might help on some Windows setups
                repo = git.Repo.clone_from(self.repo_url, path, config='core.longpaths=true', allow_unsafe_options=True)
                
                self.logger.info(f"[{label}] Checking out {sha}...")
                repo.git.checkout(sha)
                self.logger.info(f"[{label}] Ready.")
                return # Success
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = (attempt + 1) * 2 # 2s, 4s...
                    self.logger.warning(f"[{label}] Clone failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    # Clean up before retry
                    self._prepare_directory(path)
                else:
                    self.logger.error(f"[{label}] Failed after {MAX_RETRIES} attempts: {e}")
                    raise


    def _patch_legacy_crypto(self, workspace_path: Path):
        """
        Replaces 'bcrypt' with 'bcryptjs' to avoid native build issues.
        """
        self.logger.info(f"Patching crypto (bcrypt -> bcryptjs) at {workspace_path}...")
        try:
            # 1. Update package.json
            pkg_path = workspace_path / "package.json"
            if pkg_path.exists():
                with open(pkg_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Simple string replace is risky but effective for this specific task
                # Replace dependency
                if '"bcrypt":' in content:
                     content = content.replace('"bcrypt":', '"bcryptjs":')
                     # Remove version caret since we want * or latest stable usually, or just keep same version constraint (bcryptjs follows bcrypt versioning roughly)
                     # Actually bcryptjs is at 2.4.3. bcrypt was 1.0.3. 
                     # Let's simple replace the line to be safe.
                     # Regex would be better but simple replace:
                     # "bcrypt": "^1.0.3" -> "bcryptjs": "*"
                     
                     # Let's reuse python json to be safe
                     import json
                     data = json.loads(content)
                     if "dependencies" in data and "bcrypt" in data["dependencies"]:
                         del data["dependencies"]["bcrypt"]
                         data["dependencies"]["bcryptjs"] = "*"
                         
                     with open(pkg_path, "w", encoding="utf-8") as f:
                         f.write(json.dumps(data, indent=2))

            # 2. Update source files
            # Recursive walk
            for root, dirs, files in os.walk(workspace_path):
                for file in files:
                    if file.endswith(".js"):
                        fpath = Path(root) / file
                        with open(fpath, "r", encoding="utf-8") as f:
                            src = f.read()
                        
                        if "require('bcrypt')" in src or 'require("bcrypt")' in src:
                            src = src.replace("require('bcrypt')", "require('bcryptjs')")
                            src = src.replace('require("bcrypt")', 'require("bcryptjs")')
                            
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.write(src)
                                
        except Exception as e:
            self.logger.error(f"Failed to patch crypto: {e}")

    async def setup_workspaces(self, vuln_sha: str, fix_sha: str):
        self.logger.info(f"Setting up workspaces for {self.repo_url}")
        
        loop = asyncio.get_running_loop()
        
        def clone_and_patch(path, sha, label):
            self._clone_and_checkout(path, sha, label)
            # Patch all repositories to ensure they work on Alpine
            self._patch_legacy_crypto(path)
        
        # Run clones in parallel threads to avoid blocking the async loop
        t1 = loop.run_in_executor(self._executor, clone_and_patch, VULN_DIR, vuln_sha, "VULN")
        t2 = loop.run_in_executor(self._executor, clone_and_patch, FIXED_DIR, fix_sha, "FIXED")
        
        await asyncio.gather(t1, t2)
        self.logger.info("All Workspaces ready.")

    def generate_patch_diff(self, vuln_sha: str, fix_sha: str) -> str:
        self.logger.info("Generating patch diff artifact...")
        repo = git.Repo(VULN_DIR)
        
        diff_output = repo.git.diff(vuln_sha, fix_sha, "--", "*.js", "*.html", "*.ts", "*.jsx", "*.tsx")
        
        artifact_filename = f"diff_{self.session_id}.diff"
        artifact_path = ARTIFACTS_DIR / artifact_filename
        
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(diff_output)
            
        add_artifact(self.session_id, "diff", str(artifact_path))
        return str(artifact_path)
