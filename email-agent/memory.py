import sqlite3
from datetime import datetime

DB_FILE = 'memory.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_emails (
            id TEXT PRIMARY KEY,
            subject TEXT,
            sender TEXT,
            category TEXT,
            processed_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


def is_processed(email_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM processed_emails WHERE id = ?', (email_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_processed(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO processed_emails (id, subject, sender, category, processed_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        email['id'],
        email['subject'],
        email['sender'],
        email.get('category', ''),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def get_history(limit=50):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT subject, sender, category, processed_at
        FROM processed_emails
        ORDER BY processed_at DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows