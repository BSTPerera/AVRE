# 🛡️ AVRE: Automated Vulnerability Revalidation Engine

**AVRE** is an architect-level security tool designed to automate the differential revalidation of XSS security patches. It orchestrates Git workspaces, Docker environments, and hybrid security analysis (Static + Dynamic) to provide a definitive verdict on whether a patch fixes a vulnerability without introducing regressions.

## 📋 Prerequisites
Before running AVRE, ensure you have the following installed:
1.  **Docker Desktop**: Must be installed and running. (Crucial for isolated container environments).
2.  **Python 3.10+**: The core engine is built in Python.
3.  **Git**: Required for cloning repositories.

## 🚀 Installation & Setup

We have provided a one-click setup script to prepare your environment.

1.  Open your terminal in the project directory:
    ```powershell
    cd "c:\AVRE Tool"
    ```

2.  Run the setup script:
    ```powershell
    setup_env.bat
    ```
    *This script will create a virtual environment, install all python requirements (Streamlit, Docker SDK, etc.), and install the Playwright browsers.*

    > **Manual Setup (Alternative)**:
    > ```powershell
    > python -m venv venv
    > .\venv\Scripts\activate
    > pip install -r requirements.txt
    > python -m playwright install chromium
    > ```

## 🎮 Usage Guide

1.  **Activate the Environment**:
    ```powershell
    .\venv\Scripts\activate
    ```

2.  **Launch the Dashboard**:
    ```powershell
    streamlit run avre/app.py
    ```

3.  **Access the UI**:
    Open your browser to `http://localhost:8501`.

## 🧪 Verification Scenario (Real-World Test)

To verify the tool works, use this real-world XSS vulnerability from the **OWASP NodeGoat** project.

**Enter these details in the AVRE Sidebar:**

*   **Repository URL**: `https://github.com/OWASP/NodeGoat`
*   **Vulnerable SHA**: `823d27b588807b09a9a100f298c12729bf5d2634`
    *   *(This commit represents the vulnerable state)*
*   **Fixed SHA**: `7c293e721bd1e95be6f82475d295b9b10e3b584e`
    *   *(This commit applies the context-aware escaping fix)*

**Expected Result**:
*   **Status**: `COMPLETED`
*   **Verdict**: `FIXED`
*   **Details**: The tool should detect that the exploit works on the Vulnerable container (Port 3000) but fails on the Fixed container (Port 3001).

## 📂 Artifacts & Output
*   **HTML Reports**: Generated in `artifacts/report_[session_id].html`.
*   **Diffs**: Patch diffs saved in `artifacts/`.
*   **Logs**: Viewable in real-time on the dashboard and stored in `avre.db`.

## 🏗️ Architecture
*   **Orchestrator**: `avre/orchestrator.py` - Manages the lifecycle.
*   **Agents**:
    *   `GitAgent`: Handles repo cloning and switching.
    *   `DockerAgent`: Manages dynamic containers.
    *   `AnalysisAgent`: Runs Semgrep (Static) and Playwright (Dynamic).
    *   `ReportAgent`: Computes verdicts.
