"""
SQLite database models for the NDA Markup Tool.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional


DB_PATH = os.environ.get("DATABASE_PATH", "nda_markup.db")


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS guidelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            content_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            markup_path TEXT,
            status TEXT DEFAULT 'uploaded',
            markup_mode TEXT DEFAULT 'balanced',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            original_text TEXT NOT NULL,
            new_text TEXT,
            rationale TEXT,
            section TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            applied INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS markup_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            output_path TEXT,
            summary_json TEXT,
            stats_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            original_path TEXT NOT NULL,
            marked_up_path TEXT,
            final_path TEXT,
            metadata_json TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    """
    )
    conn.commit()
    conn.close()


# --- Project CRUD ---


def create_project(name: str, description: str = "") -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO projects (name, description) VALUES (?, ?)",
        (name, description),
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def get_project(project_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_projects() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Document CRUD ---


def create_document(
    project_id: int, filename: str, original_path: str, markup_mode: str = "balanced"
) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO documents (project_id, filename, original_path, markup_mode) VALUES (?, ?, ?, ?)",
        (project_id, filename, original_path, markup_mode),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    return doc_id


def update_document_status(doc_id: int, status: str, markup_path: str = None):
    conn = get_db()
    if markup_path:
        conn.execute(
            "UPDATE documents SET status = ?, markup_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, markup_path, doc_id),
        )
    else:
        conn.execute(
            "UPDATE documents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, doc_id),
        )
    conn.commit()
    conn.close()


def get_document(doc_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_documents(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Guidelines CRUD ---


def create_guideline(
    project_id: int, filename: str, original_path: str, content_text: str = ""
) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO guidelines (project_id, filename, original_path, content_text) VALUES (?, ?, ?, ?)",
        (project_id, filename, original_path, content_text),
    )
    conn.commit()
    gid = cursor.lastrowid
    conn.close()
    return gid


def get_guidelines_for_project(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM guidelines WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Changes CRUD ---


def save_changes(doc_id: int, changes: list[dict]):
    conn = get_db()
    for c in changes:
        conn.execute(
            """INSERT INTO changes (document_id, change_type, original_text, new_text,
               rationale, section, priority, status, applied) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                c.get("change_type", ""),
                c.get("original_text", ""),
                c.get("new_text", ""),
                c.get("rationale", ""),
                c.get("section", ""),
                c.get("priority", "medium"),
                c.get("status", "pending"),
                c.get("applied", 0),
            ),
        )
    conn.commit()
    conn.close()


def get_changes(doc_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM changes WHERE document_id = ? ORDER BY id",
        (doc_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_change_status(change_id: int, status: str):
    conn = get_db()
    conn.execute("UPDATE changes SET status = ? WHERE id = ?", (status, change_id))
    conn.commit()
    conn.close()


# --- Markup Results ---


def save_markup_result(
    doc_id: int, output_path: str, summary: dict, stats: dict
) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO markup_results (document_id, output_path, summary_json, stats_json) VALUES (?, ?, ?, ?)",
        (doc_id, output_path, json.dumps(summary), json.dumps(stats)),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return rid


def get_markup_result(doc_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM markup_results WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
        (doc_id,),
    ).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["summary"] = json.loads(result["summary_json"]) if result["summary_json"] else {}
        result["stats"] = json.loads(result["stats_json"]) if result["stats_json"] else {}
        return result
    return None
