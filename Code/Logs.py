import sqlite3
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_NAME = 'proxy_logs.db'
MAX_RETRIES = 5
RETRY_DELAY = 0.1  # 100 ms


# Enable Write-Ahead Logging (WAL) mode for SQLite
def enable_wal_mode():
    """
    Enables WAL mode to allow concurrent reads and writes.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    conn.close()
    logging.info("WAL mode enabled for the SQLite database.")


# Get a database connection
def get_db_connection():
    """
    Returns a new database connection.
    """
    return sqlite3.connect(DB_NAME, check_same_thread=False)


# Execute queries with retry logic
def execute_with_retry(query, params=()):
    """
    Executes a database query with retry logic to handle transient database locks.
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            row_id = cursor.lastrowid
            conn.close()
            return row_id
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                retries += 1
                time.sleep(RETRY_DELAY)
                logging.warning(f"Retrying due to database lock... ({retries}/{MAX_RETRIES})")
            else:
                raise
        finally:
            try:
                conn.close()
            except NameError:
                pass
    logging.error("Max retries reached. Operation failed.")
    return None


# Initialize the database and create tables
def init_db():
    # Enable WAL mode during initialization
    enable_wal_mode()
    """
    Creates the required database tables if they do not exist.
    """
    queries = [
        '''
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
        )
        ''',
        '''
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
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('blacklist', 'whitelist'))
        )
        ''',
    ]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for query in queries:
            cursor.execute(query)
        conn.commit()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
    finally:
        conn.close()


# Log a request
def log_request(client_ip, client_port, target_host, target_port, method, url, protocol, error_message=None):
    """
    Logs a client request into the requests table.
    """
    query = """
        INSERT INTO requests (timestamp, client_ip, client_port, target_host, target_port, method, url, protocol, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (datetime.now(), client_ip, client_port, target_host, target_port, method, url, protocol, error_message)
    logging.info("Logging request to database.")
    request_id = execute_with_retry(query, params)
    if request_id:
        logging.info(f"Request logged successfully with ID {request_id}.")
    else:
        logging.error("Failed to log request.")
    return request_id


# Log a response
def log_response(request_id, cache_status, response_status, content_type, response_size, response_time_ms):
    """
    Logs a response associated with a request into the responses table.
    """
    query = """
        INSERT INTO responses (request_id, timestamp, cache_status, response_status, response_content_type, response_size, response_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (request_id, datetime.now(), cache_status, response_status, content_type, response_size, response_time_ms)
    logging.info("Logging response to database.")
    result = execute_with_retry(query, params)
    if result:
        logging.info("Response logged successfully.")
    else:
        logging.error("Failed to log response.")



