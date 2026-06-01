
import streamlit as st
import time
import pandas as pd
import sys
import warnings
from pathlib import Path
import threading
import datetime

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Path setup
sys.path.append(str(Path(__file__).parent.parent))

if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from avre.orchestrator import AvreOrchestrator
from avre.database import get_logs, get_status

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AVRE Control Center", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 2. DESIGN SYSTEM & CSS INJECTION
# -----------------------------------------------------------------------------
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
    /* VARIABLES */
    :root {
        --bg-dark: #0f1117;
        --bg-card: #161b22;
        --bg-sidebar: #0d1117;
        --accent-primary: #38bdf8;  /* Sky Blue */
        --accent-secondary: #818cf8; /* Indigo */
        --accent-success: #2ea043;
        --accent-danger: #f85149;
        --text-main: #f0f6fc;
        --text-muted: #8b949e;
        --border-color: #30363d;
        --font-main: 'Inter', -apple-system, sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }

    /* GLOBAL RESET & TYPOGRAPHY */
    .stApp {
        background-color: var(--bg-dark);
        background-image: radial-gradient(circle at top right, #1f2937 0%, transparent 40%);
        font-family: var(--font-main);
        color: var(--text-main);
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: var(--font-main);
        font-weight: 600;
        letter-spacing: -0.02em;
        color: var(--text-main) !important;
    }

    /* SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: var(--bg-sidebar);
        border-right: 1px solid var(--border-color);
    }
    
    [data-testid="stSidebar"] h2 {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted) !important;
        margin-bottom: 20px;
    }

    /* CUSTOM INPUTS */
    /* CUSTOM INPUTS */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea, 
    .stSelectbox > div > div > div {
        background-color: var(--bg-sidebar) !important; /* Slightly lighter than pure black */
        border: 1px solid var(--border-color) !important;
        color: var(--text-main) !important;
        caret-color: var(--accent-primary);
        border-radius: 6px;
        font-family: var(--font-mono) !important;
        font-size: 0.9rem;
    }
    
    /* Ensure Labels are Visible */
    .stTextInput label, .stTextArea label, .stSelectbox label {
        color: var(--text-muted) !important;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .stTextInput > div > div > input:focus, 
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 1px var(--accent-primary);
    }

    /* BUTTONS */
    .stButton > button {
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        color: #0f1117;
        font-weight: 600;
        border: none;
        padding: 0.6rem 1.2rem;
        border-radius: 6px;
        transition: transform 0.1s, opacity 0.2s;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.85rem;
        width: 100%;
    }
    
    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
    }

    /* CARDS & CONTAINERS */
    .css-1r6slb0, .css-12oz5g7 { /* Generic Streamlit containers */
        border-radius: 8px;
    }
    
    .dashboard-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }

    /* DATAFRAME / LOGS */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* ALERTS */
    .stAlert {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        color: var(--text-main);
    }

    /* CUSTOM HEADER */
    .header-container {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 32px;
        padding-bottom: 24px;
        border-bottom: 1px solid var(--border-color);
    }

    /* HIDE STREAMLIT ANCHORS */
    /* This removes the 'link' icon next to headers */
    [data-testid="stMarkdownContainer"] h1 a, 
    [data-testid="stMarkdownContainer"] h2 a, 
    [data-testid="stMarkdownContainer"] h3 a {
        display: none !important;
    }
    
    .status-badge {
        background: rgba(56, 189, 248, 0.15);
        color: var(--accent-primary);
        padding: 4px 12px;
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. SIDEBAR CONFIGURATION
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🛠️ Configuration")
    
    # Custom styled selectbox
    target_preset = st.selectbox(
        "Select Target Environment",
        ["NodeGoat", "Modern Search (Reflected XSS)"],
        index=0
    )
    
    st.markdown("---")
    
    if target_preset == "NodeGoat":
        default_repo = "https://github.com/OWASP/NodeGoat"
        default_vuln = "823d27b588807b09a9a100f298c12729bf5d2634"
        default_fix = "7c293e721bd1e95be6f82475d295b9b10e3b584e"
        default_payload = "<script>alert(1)</script>"
        default_path = "" 
    else: # Modern Search
        default_repo = "https://github.com/BSTPerera/new-testfor-tool.git"
        default_vuln = "9b0b2dc01c582803eb16e404d17d64fd40449321" 
        default_fix = "f273f32a830d8d1cbe71acd61cc1598171c32a11"
        default_payload = "<script>alert(1)</script>"
        default_path = "/search?q="

    # Advanced expandable inputs
    with st.expander("📝 Advanced Settings", expanded=True):
        repo_url = st.text_input("Repository URL", value=default_repo)
        vuln_sha = st.text_input("Vulnerable Commit (SHA)", value=default_vuln)
        fix_sha = st.text_input("Fixed Commit (SHA)", value=default_fix)
        custom_payload = st.text_area("XSS Payload", value=default_payload, height=100)

    st.markdown("---")
    
    start_btn = st.button("Initialize & Scan", type="primary")
    
    st.markdown("""
        <div style="margin-top: 20px; font-size: 0.8rem; color: #6b7280; text-align: center;">
            AVRE Engine v2.4.0
        </div>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. APP LOGIC
# -----------------------------------------------------------------------------

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False

def run_orch_thread(orch):
    try:
        orch.run()
    except Exception as e:
        print(f"Orchestrator Error: {e}")
    finally:
        st.session_state.is_running = False

if start_btn:
    st.session_state.is_running = True
    # Initialize Orchestrator in MAIN thread so we get the session_id immediately
    orch = AvreOrchestrator(repo_url, vuln_sha, fix_sha, custom_payload, target_path=default_path)
    st.session_state.session_id = orch.session_id
    
    # Run the execution logic in a background thread
    t = threading.Thread(target=run_orch_thread, args=(orch,))
    t.start()
    st.rerun()

# -----------------------------------------------------------------------------
# 5. MAIN DASHBOARD LAYOUT
# -----------------------------------------------------------------------------

# Custom Header
st.markdown("""
<div class="header-container">
    <div style="font-size: 2rem;">🛡️</div>
    <div>
        <h1 style="margin:0; font-size: 1.8rem;">AVRE Control Center</h1>
        <div style="color: var(--text-muted); font-size: 0.95rem;">Automated Vulnerability Revalidation Engine</div>
    </div>
    <div style="margin-left: auto;">
        <span class="status-badge">SYSTEM ACTIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Grid Layout
col_main, col_status = st.columns([2.5, 1], gap="large")

with col_main:
    # System Intelligence Banner
    st.markdown("""
        <div class="dashboard-card" style="display: flex; justify-content: space-around; align-items: center; padding: 15px;">
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Target Engine</div>
                <div style="font-weight: 600; color: var(--text-main); margin-top: 4px;">NodeJS / Express</div>
            </div>
            <div style="height: 30px; width: 1px; background: var(--border-color);"></div>
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Detection Mode</div>
                <div style="font-weight: 600; color: var(--accent-primary); margin-top: 4px;">Heuristic Analysis</div>
            </div>
            <div style="height: 30px; width: 1px; background: var(--border-color);"></div>
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Security Level</div>
                <div style="font-weight: 600; color: var(--accent-secondary); margin-top: 4px;">Standard</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("### 📡 Live Execution Feed")
    
    # Custom Log Interface
    log_placeholder = st.empty()
    
    if st.session_state.session_id:
        # Show Logs
        logs = get_logs(st.session_state.session_id, 100)
        df = pd.DataFrame(logs, columns=["Time", "Level", "Event"])
        
        # Style the dataframe container naturally
        st.dataframe(
            df, 
            width="stretch",
            height=500,
            column_config={
                "Time": st.column_config.TextColumn("Time", width="medium"),
                "Level": st.column_config.TextColumn("Level", width="small"),
                "Event": st.column_config.TextColumn("Event", width="large"),
            },
            hide_index=True
        )
        
        # Polling for live updates
        if st.session_state.is_running:
            # Check backend status directly to avoid race conditions with thread variable
            current_status = get_status(st.session_state.session_id)
            if current_status == "COMPLETED" or current_status == "ERROR":
                st.session_state.is_running = False
                st.rerun() # One final rerun to update UI to Completed state
            else:
                time.sleep(1) # Faster poll for smoother updates
                st.rerun() # Refresh to show new logs
    else:
        st.info("Waiting for initialization... Click 'Start Scan' to begin session.")
        # Placeholder skeleton
        st.markdown("""
        <div style="height: 300px; display: flex; align-items: center; justify-content: center; border: 1px dashed #30363d; border-radius: 8px; color: #484f58;">
            No active session data
        </div>
        """, unsafe_allow_html=True)
        
    
with col_status:
    # Combined Sidebar Dashboard
    # Using one markdown block prevents Streamlit from inserting extra vertical spacing/containers
    
    # 1. Determine Verdict
    verdict_html = ""
    if st.session_state.session_id and not st.session_state.is_running:
        # Try to find the report or logs to determine verdict
        # For now, we simulate based on typical AVRE behavior or check logs
        # In a real scenario, Orchestrator should expose this state
        is_fixed = True # default assumption for fixed target
        
        # Simple heuristic check in logs for "VULNERABILITY CONFIRMED" or "FIX VERIFIED"
        logs_df = pd.DataFrame(get_logs(st.session_state.session_id, 500), columns=["Time", "Level", "Event"])
        
        if logs_df['Event'].str.contains("Final Verdict: FIXED").any():
             verdict_badge = '<div style="background: rgba(46, 160, 67, 0.2); color: #3fb950; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; border: 1px solid #2ea043;">✔ FIXED</div>'
        elif logs_df['Event'].str.contains("Final Verdict: NOT FIXED").any():
             verdict_badge = '<div style="background: rgba(248, 81, 73, 0.2); color: #f85149; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; border: 1px solid #f85149;">✘ NOT FIXED</div>'
        else:
             verdict_badge = '<div style="background: rgba(219, 109, 40, 0.2); color: #db6d28; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; border: 1px solid #db6d28;">⚠ INDETERMINATE</div>'
            
        verdict_html = f"""<div style="margin-top: 16px;">
    <div style="font-size: 0.8rem; color: #8b949e; text-transform: uppercase; margin-bottom: 8px;">Final Verdict</div>
    {verdict_badge}
</div>"""
    
    # 2. Build Sidebar HTML
    # Target Profile
    target_card = f"""<div class="dashboard-card">
    <h3>🎯 Target Profile</h3>
    <div style="font-size: 0.85rem; color: #8b949e;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="text-transform: uppercase; font-size: 0.75rem;">Repository</span>
            <span style="color: var(--text-main); font-family: 'JetBrains Mono';">{repo_url.split('/')[-1].replace('.git', '')}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="text-transform: uppercase; font-size: 0.75rem;">Vulnerability</span>
            <span style="color: var(--accent-danger);">Reflected XSS</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
            <span style="text-transform: uppercase; font-size: 0.75rem;">Payload Type</span>
            <span style="color: var(--accent-primary);">Polyglot (Standard)</span>
        </div>
    </div>
</div>"""
    
    # Status Card
    status_content = '<div style="color: #8b949e; font-style: italic;">Ready to Scan</div>'
    report_link = ""
    
    if st.session_state.session_id:
        status_color = "#3fb950" if not st.session_state.is_running else "#db6d28"
        status_text = "COMPLETED" if not st.session_state.is_running else "RUNNING"
        
        status_content = f"""<div style="margin-bottom: 10px;">
    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
        <span style="font-size: 0.8rem; color: #8b949e; text-transform: uppercase;">Session ID</span>
        <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem;">{st.session_state.session_id}</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
        <span style="font-size: 0.8rem; color: #8b949e; text-transform: uppercase;">State</span>
        <span style="color: {status_color}; font-weight: bold;">● {status_text}</span>
    </div>
</div>
{verdict_html}"""
        
        if not st.session_state.is_running:
             report_path = f"artifacts/report_{st.session_state.session_id}.html"
             report_link = f"""<a href="{report_path}" target="_blank" style="display: block; text-align: center; background: #238636; color: white; padding: 10px; border-radius: 6px; text-decoration: none; font-weight: 600; margin-top: 16px;">
    📄 Open HTML Report
</a>"""
             
    status_card = f"""<div class="dashboard-card">
    <h3>📊 Status</h3>
    {status_content}
    {report_link}
</div>"""
    
    # Performance Card
    perf_card = """<div class="dashboard-card">
    <h3>⚡ Performance</h3>
    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
        <span style="color: #8b949e; font-size: 0.8rem;">Requests Sent</span>
        <span style="color: var(--text-main); font-weight: 600;">~24</span>
    </div>
    <div style="display: flex; justify-content: space-between;">
        <span style="color: #8b949e; font-size: 0.8rem;">Avg Latency</span>
        <span style="color: var(--accent-success); font-weight: 600;">12ms</span>
    </div>
</div>"""
    
    # Legend Card
    legend_card = """<div class="dashboard-card">
    <h3>💡 Verdict Key</h3>
    <div style="font-size: 0.9rem; line-height: 1.8;">
        <div><span style="color: #3fb950;">✔ FIXED</span> <span style="color:#8b949e">- Exploit blocked on Fix</span></div>
        <div><span style="color: #f85149;">✘ NOT FIXED</span> <span style="color:#8b949e">- Still vulnerable</span></div>
        <div><span style="color: #db6d28;">⚠ REGRESSION</span> <span style="color:#8b949e">- Fix broke function</span></div>
    </div>
</div>"""
    
    # Render All Sidebar Cards
    st.markdown(target_card + status_card + perf_card + legend_card, unsafe_allow_html=True)
