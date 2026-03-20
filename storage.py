"""Persistence helpers for EvE-Logistics."""

from __future__ import annotations

import sqlite3
from datetime import datetime, UTC

from config import DB_FILE, DOCTRINES


QUOTE_COLUMNS = [
    "timestamp",
    "total",
    "jita_total",
    "jump_fee",
    "volume_fee",
    "risk_fee",
    "jumps",
    "volume_m3",
    "isk_per_jump",
    "isk_per_m3",
    "risk_pct",
    "dst_loads",
    "pricing_mode",
    "note",
]


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
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_history (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            total REAL,
            jita_total REAL,
            jump_fee REAL,
            volume_fee REAL,
            risk_fee REAL,
            jumps INTEGER,
            volume_m3 REAL,
            isk_per_jump REAL,
            isk_per_m3 REAL,
            risk_pct REAL,
            dst_loads INTEGER,
            pricing_mode TEXT,
            note TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS doctrine_fits (
            id TEXT PRIMARY KEY,
            name TEXT,
            fit_name TEXT,
            hull TEXT,
            target INTEGER,
            m3 REAL,
            fit_text TEXT,
            item_count INTEGER,
            notes TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()

    # Seed doctrine fits from config if table is empty.
    count = c.execute("SELECT COUNT(*) FROM doctrine_fits").fetchone()[0]
    if count == 0:
        for doctrine in DOCTRINES:
            c.execute(
                """
                INSERT OR IGNORE INTO doctrine_fits
                (id, name, fit_name, hull, target, m3, fit_text, item_count, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doctrine["id"],
                    doctrine["name"],
                    doctrine.get("name", doctrine["id"]),
                    doctrine["id"],
                    int(doctrine.get("target", 0)),
                    float(doctrine.get("m3", 0)),
                    doctrine.get("fit_text", ""),
                    0,
                    doctrine.get("link", ""),
                    datetime.now(UTC).isoformat(),
                ),
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


def save_quote_history(pricing, note: str = "", pricing_mode: str = "per_m3"):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO quote_history
        (timestamp, total, jita_total, jump_fee, volume_fee, risk_fee, jumps, volume_m3,
         isk_per_jump, isk_per_m3, risk_pct, dst_loads, pricing_mode, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            pricing.final_total,
            pricing.jita_total,
            pricing.jump_fee,
            pricing.volume_fee,
            pricing.risk_fee,
            pricing.jumps,
            pricing.volume_m3,
            pricing.isk_per_jump,
            pricing.isk_per_m3,
            pricing.risk_pct,
            pricing.dst_loads,
            pricing_mode,
            note,
        ),
    )
    conn.commit()
    conn.close()


def load_quote_history(limit=20):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM quote_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def load_history(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT timestamp, total FROM history ORDER BY id DESC LIMIT ?", (limit,))
    res = [{"timestamp": row[0], "total": row[1]} for row in c.fetchall()]
    conn.close()
    return res


def load_doctrine_fits():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM doctrine_fits ORDER BY name COLLATE NOCASE ASC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def save_doctrine_fit(doctrine: dict):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO doctrine_fits
        (id, name, fit_name, hull, target, m3, fit_text, item_count, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM doctrine_fits WHERE id = ?), ?))
        """,
        (
            doctrine["id"],
            doctrine["name"],
            doctrine.get("fit_name", doctrine["name"]),
            doctrine.get("hull", doctrine["id"]),
            int(doctrine.get("target", 0)),
            float(doctrine.get("m3", 0)),
            doctrine.get("fit_text", ""),
            int(doctrine.get("item_count", 0)),
            doctrine.get("notes", ""),
            doctrine["id"],
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
