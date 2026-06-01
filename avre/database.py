
import sqlite3
import datetime
from pathlib import Path
from typing import List, Optional, Tuple

DB_PATH = Path("avre.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        repo_url TEXT,
        vuln_sha TEXT,
        fix_sha TEXT,
        status TEXT,
        verdict TEXT
    )''')

    # Logs table
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        timestamp TEXT,
        level TEXT,
        message TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    )''')

    # Artifacts table
    c.execute('''CREATE TABLE IF NOT EXISTS artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        type TEXT,
        path TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    )''')
    
    conn.commit()
    conn.close()

def create_session(session_id: str, repo_url: str, vuln_sha: str, fix_sha: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (id, timestamp, repo_url, vuln_sha, fix_sha, status, verdict) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (session_id, datetime.datetime.now().isoformat(), repo_url, vuln_sha, fix_sha, "INITIALIZED", "PENDING"))
    conn.commit()
    conn.close()

def log_event(session_id: str, level: str, message: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO logs (session_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
              (session_id, datetime.datetime.now().isoformat(), level, message))
    conn.commit()
    conn.close()

def add_artifact(session_id: str, art_type: str, path: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO artifacts (session_id, type, path) VALUES (?, ?, ?)",
              (session_id, art_type, str(path)))
    conn.commit()
    conn.close()

def update_status(session_id: str, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
    conn.commit()
    conn.close()

def update_verdict(session_id: str, verdict: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET verdict = ? WHERE id = ?", (verdict, session_id))
    conn.commit()
    conn.close()

def get_logs(session_id: str, limit: int = 100) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT timestamp, level, message FROM logs WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_status(session_id: str) -> str:
    """Retrieve the current status of a session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status FROM sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "UNKNOWN"

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
