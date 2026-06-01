
import os
from avre.config import ARTIFACTS_DIR, VULN_PORT, FIXED_PORT
from avre.database import update_verdict, add_artifact, get_logs
from avre.utils.logger import get_logger

class ReportAgent:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = get_logger("ReportAgent", session_id)

    def _get_screenshot_html(self, port):
        # Check for triggered first, then standard
        trigger_path = ARTIFACTS_DIR / f"triggered_{self.session_id}_{port}.png"
        std_path = ARTIFACTS_DIR / f"screenshot_{self.session_id}_{port}.png"
        
        if trigger_path.exists():
            return f'<img src="{trigger_path.name}" style="max-width: 400px; border: 2px solid red;">'
        elif std_path.exists():
            return f'<img src="{std_path.name}" style="max-width: 400px; border: 1px solid #555;">'
        else:
            return "<p>No screenshot available</p>"

    def determine_verdict(self, vuln_exploitable: bool, fixed_exploitable: bool) -> str:
        # Differential Logic
        if vuln_exploitable and not fixed_exploitable:
            verdict = "FIXED"
        elif vuln_exploitable and fixed_exploitable:
            verdict = "NOT FIXED"
        elif not vuln_exploitable and fixed_exploitable:
            verdict = "REGRESSION"
        elif not vuln_exploitable and not fixed_exploitable:
            verdict = "INVESTIGATE" # Could verify the exploit wasn't working to begin with
        else:
            verdict = "UNKNOWN"
            
        self.logger.info(f"Verdict Calculated: {verdict} (Vuln: {vuln_exploitable}, Fixed: {fixed_exploitable})")
        update_verdict(self.session_id, verdict)
        return verdict

    def generate_html_report(self, verdict: str, vuln_result: dict, fixed_result: dict, diff_content: str = None):
        self.logger.info("Generating HTML report...")
        
        logs = get_logs(self.session_id, limit=50)
        log_html = "".join([f"<li>[{row[0]}] {row[1]}: {row[2]}</li>" for row in logs])
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; background-color: #1e1e1e; color: #fff; padding: 20px; }}
                h1 {{ color: #00d4ff; }}
                .verdict {{ font-size: 2em; font-weight: bold; padding: 10px; border-radius: 5px; display: inline-block; }}
                .FIXED {{ background-color: #4caf50; color: white; }}
                .NOT_FIXED {{ background-color: #ff9800; color: black; }}
                .REGRESSION {{ background-color: #f44336; color: white; }}
                .INVESTIGATE {{ background-color: #9e9e9e; color: white; }}
                .section {{ margin-top: 20px; border: 1px solid #444; padding: 15px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <h1>AVRE Security Report</h1>
            <div class="verdict {verdict}">{verdict}</div>
            
            <div class="section">
                <h2>Analysis Details</h2>
                <p><strong>Session ID:</strong> {self.session_id}</p>
                <ul>
                    <li><strong>Vulnerable Container (Port {VULN_PORT}):</strong> Exploitable? {vuln_result.get('exploitable')}</li>
                    <li><strong>Fixed Container (Port {FIXED_PORT}):</strong> Exploitable? {fixed_result.get('exploitable')}</li>
                </ul>
                
                <h3>Verification Screenshots</h3>
                <div style="display: flex; gap: 20px;">
                    <div>
                        <h4>Vulnerable (Port {VULN_PORT})</h4>
                        {self._get_screenshot_html(VULN_PORT)}
                    </div>
                    <div>
                        <h4>Fixed (Port {FIXED_PORT})</h4>
                        {self._get_screenshot_html(FIXED_PORT)}
                    </div>
                </div>

                <div class="section">
                    <h2>Code Difference (Fix Patch)</h2>
                    <p>The following changes were applied to fix the vulnerability:</p>
                    <pre style="background: #2d2d2d; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: monospace;"><code>{diff_content if diff_content else "No diff available."}</code></pre>
                </div>
            </div>

            <div class="section">
                <h2>Recent Logs</h2>
                <ul style="font-size: 0.9em; color: #ccc;">
                    {log_html}
                </ul>
            </div>
        </body>
        </html>
        """
        
        report_path = ARTIFACTS_DIR / f"report_{self.session_id}.html"
        with open(report_path, "w") as f:
            f.write(html_content)
            
        add_artifact(self.session_id, "html_report", str(report_path))
        self.logger.info(f"Report saved to {report_path}")
        return str(report_path)
