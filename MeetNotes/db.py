from __future__ import annotations
import sqlite3, os
from typing import List, Dict, Any

# Always store the DB next to this file (prevents CWD/OneDrive path issues)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "meetings.db")

def get_db_path() -> str:
    """Absolute DB path (handy to show in UI)."""
    return DB_PATH

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        meeting_date TEXT,
        duration_sec INTEGER,
        transcript TEXT,
        summary TEXT,
        decisions TEXT,
        model_used TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER,
        owner TEXT,
        text TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'open',
        FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
    );
    """)
    conn.commit()

def insert_meeting(title:str, meeting_date:str, duration_sec:int, transcript:str,
                   summary:str, decisions:str, model_used:str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO meetings (title, meeting_date, duration_sec, transcript, summary, decisions, model_used) "
        "VALUES (?, ?, ?, ?, ?, ?, ?);",
        (title, meeting_date, duration_sec, transcript, summary, decisions, model_used)
    )
    conn.commit()
    return cur.lastrowid

def insert_actions(meeting_id:int, actions:List[Dict[str, Any]]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    for a in actions:
        cur.execute(
            "INSERT INTO actions (meeting_id, owner, text, due_date, status) VALUES (?, ?, ?, ?, ?);",
            (meeting_id, a.get("owner"), a.get("text"), a.get("due_date"), a.get("status","open"))
        )
    conn.commit()

def list_meetings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, meeting_date, duration_sec, model_used, created_at FROM meetings ORDER BY created_at DESC;")
    return cur.fetchall()

def get_meeting(meeting_id:int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM meetings WHERE id=?;", (meeting_id,))
    return cur.fetchone()

def get_actions(meeting_id:int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM actions WHERE meeting_id=? ORDER BY id ASC;", (meeting_id,))
    return cur.fetchall()

def update_action_status(action_id:int, status:str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE actions SET status=? WHERE id=?;", (status, action_id))
    conn.commit()

def delete_meeting(meeting_id:int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id=?;", (meeting_id,))
    conn.commit()
