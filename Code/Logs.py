"""SQLite-backed request/response logging.

Keeps the original schema but adds: a read helper (`query`), a way to fill in
the request's final status, an index on responses.request_id, and a proper
docstring placement. WAL mode + retry handle concurrent writes from threads.
"""
import logging
import sqlite3
import time
from datetime import datetime

DB_NAME = "proxy_logs.db"
MAX_RETRIES = 5
RETRY_DELAY = 0.1  # seconds


def configure(db_name):
    global DB_NAME
    DB_NAME = db_name


def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def execute_with_retry(query_sql, params=()):
    """Run a write query, retrying briefly on transient 'database is locked'."""
    for attempt in range(1, MAX_RETRIES + 1):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query_sql, params)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logging.warning("DB locked, retry %s/%s", attempt, MAX_RETRIES)
                time.sleep(RETRY_DELAY)
                continue
            raise
        finally:
            if conn is not None:
                conn.close()
    logging.error("Max retries reached; write failed.")
    return None


def query(query_sql, params=()):
    """Run a read query and return a list of sqlite3.Row."""
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query_sql, params)
        return cursor.fetchall()
    finally:
        conn.close()


def init_db():
    """Create tables/indexes and enable WAL for concurrent read+write."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                client_ip TEXT NOT NULL,
                client_port INTEGER NOT NULL,
                target_host TEXT NOT NULL,
                target_port INTEGER NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                protocol TEXT NOT NULL,
                status INTEGER,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                timestamp DATETIME NOT NULL,
                cache_status TEXT CHECK(cache_status IN ('HIT', 'MISS')),
                response_status INTEGER,
                response_content_type TEXT,
                response_size INTEGER,
                response_time_ms INTEGER,
                FOREIGN KEY(request_id) REFERENCES requests(id)
            );
            CREATE TABLE IF NOT EXISTS filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('blacklist', 'whitelist'))
            );
            CREATE INDEX IF NOT EXISTS idx_responses_request_id
                ON responses(request_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_filters_unique
                ON filters(address, type);
            """
        )
        conn.commit()
        logging.info("Database initialized.")
    finally:
        conn.close()


def log_request(client_ip, client_port, target_host, target_port,
                method, url, protocol, error_message=None):
    return execute_with_retry(
        """INSERT INTO requests
           (timestamp, client_ip, client_port, target_host, target_port,
            method, url, protocol, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now(), client_ip, client_port, target_host, target_port,
         method, url, protocol, error_message),
    )


def update_request_status(request_id, status):
    if request_id is None:
        return
    execute_with_retry(
        "UPDATE requests SET status = ? WHERE id = ?", (status, request_id)
    )


def log_response(request_id, cache_status, response_status, content_type,
                 response_size, response_time_ms):
    execute_with_retry(
        """INSERT INTO responses
           (request_id, timestamp, cache_status, response_status,
            response_content_type, response_size, response_time_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (request_id, datetime.now(), cache_status, response_status,
         content_type, response_size, int(response_time_ms)),
    )