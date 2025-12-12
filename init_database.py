#!/usr/bin/env python3
"""
Initialize the job tracker database with all required tables.
Run this if your database is missing tables.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'job_tracker.db'

def init_db():
    """Initialize all database tables."""
    print(f"Initializing database at: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")

    # Create jobs table
    print("Creating 'jobs' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            source TEXT,
            status TEXT DEFAULT 'new',
            score INTEGER DEFAULT 0,
            baseline_score INTEGER DEFAULT 0,
            analysis TEXT,
            cover_letter TEXT,
            notes TEXT,
            raw_text TEXT,
            created_at TEXT,
            updated_at TEXT,
            email_date TEXT,
            is_filtered INTEGER DEFAULT 0,
            viewed INTEGER DEFAULT 0
        )
    ''')

    # Create external_applications table
    print("Creating 'external_applications' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS external_applications (
            app_id TEXT PRIMARY KEY,
            job_id TEXT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            url TEXT,
            source TEXT NOT NULL,
            application_method TEXT,
            applied_date TEXT NOT NULL,
            contact_name TEXT,
            contact_email TEXT,
            status TEXT DEFAULT 'applied',
            follow_up_date TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            is_linked_to_job INTEGER DEFAULT 0,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        )
    ''')

    # Create scan_history table
    print("Creating 'scan_history' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_scan_date TEXT,
            emails_found INTEGER,
            created_at TEXT
        )
    ''')

    # Create watchlist table
    print("Creating 'watchlist' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            url TEXT,
            notes TEXT,
            created_at TEXT
        )
    ''')

    # Create followups table
    print("Creating 'followups' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            subject TEXT,
            type TEXT,
            snippet TEXT,
            email_date TEXT,
            job_id TEXT,
            created_at TEXT
        )
    ''')

    # Create tracked_companies table
    print("Creating 'tracked_companies' table...")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tracked_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            career_page_url TEXT,
            job_alert_email TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    conn.commit()

    # Verify tables were created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("\n✅ Database initialized successfully!")
    print("Tables created:")
    for table in tables:
        print(f"  ✓ {table[0]}")

    conn.close()
    print(f"\n✅ Database ready at: {DB_PATH}")

if __name__ == '__main__':
    init_db()
