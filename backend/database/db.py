import os
import sqlite3
from typing import Dict, Any, List, Optional
from backend.core.config import settings

def get_db_path():
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        return os.path.abspath(db_url.replace("sqlite:///", ""))
    return os.path.abspath("csrgo_video_studio.db")

def get_connection():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        topic TEXT NOT NULL,
        mode TEXT DEFAULT 'topic',
        source_url TEXT,
        target_duration INTEGER DEFAULT 45,
        actual_duration REAL,
        aspect_ratio TEXT DEFAULT '9:16',
        resolution TEXT DEFAULT '1080x1920',
        fps INTEGER DEFAULT 24,
        language TEXT DEFAULT 'en',
        voice TEXT DEFAULT 'af_bella',
        speaking_speed REAL DEFAULT 1.0,
        style_slug TEXT DEFAULT 'swiss-motion',
        music_enabled INTEGER DEFAULT 1,
        sfx_enabled INTEGER DEFAULT 1,
        subtitles_enabled INTEGER DEFAULT 1,
        draft_render INTEGER DEFAULT 0,
        status TEXT DEFAULT 'draft',
        stage TEXT DEFAULT 'created',
        progress INTEGER DEFAULT 0,
        error_message TEXT,
        output_video_path TEXT,
        preview_video_path TEXT,
        thumbnail_path TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS render_jobs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        status TEXT DEFAULT 'queued',
        stage TEXT DEFAULT 'initialized',
        progress INTEGER DEFAULT 0,
        message TEXT,
        error TEXT,
        started_at TEXT,
        finished_at TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()
