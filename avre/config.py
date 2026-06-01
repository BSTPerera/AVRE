
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent
WORKSPACES_DIR = BASE_DIR / "workspaces"
# Updated to point to the new test targets
VULN_DIR = WORKSPACES_DIR / "new testfor tool" / "vulnerable"
FIXED_DIR = WORKSPACES_DIR / "new testfor tool" / "fixed"

# Docker Configuration
DOCKER_IMAGE_TAG = "avre-target"
VULN_PORT = 4000
FIXED_PORT = 4001

# Analysis Configuration
SEMGREP_RULES = "p/xss"

# Reporting
ARTIFACTS_DIR = BASE_DIR.parent / "artifacts"
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
