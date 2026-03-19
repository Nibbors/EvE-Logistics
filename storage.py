"""Persistence helpers for EvE-Logistics."""

import sqlite3
from config import DB_FILE


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS stock (ship_id TEXT PRIMARY KEY, count INTEGER)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, timestamp TEXT, total REAL)"""
    )
    conn.commit()
    conn.close()


def load_stock():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT ship_id, count FROM stock")
    res = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return res


def save_stock(data):
    conn = get_connection()
    c = conn.cursor()
    for k, v in data.items():
        c.execute(
            "INSERT OR REPLACE INTO stock (ship_id, count) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


def load_history(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT timestamp, total FROM history ORDER BY id DESC LIMIT ?", (limit,))
    res = [{"timestamp": row[0], "total": row[1]} for row in c.fetchall()]
    conn.close()
    return res
