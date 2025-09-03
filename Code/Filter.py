import sqlite3
import logging
import time
DB_NAME = 'proxy_logs.db'
MAX_RETRIES = 5
RETRY_DELAY = 0.1  # 100 ms

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # To return dictionary-like rows
    return conn

# Add filter to list
def add_to_filter_list(address, filter_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO filters (address, type) VALUES (?, ?)", (address, filter_type))
    conn.commit()
    conn.close()

# Remove Filter to list
def remove_from_filter_list(address, filter_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM filters WHERE address = ? AND type = ?", (address, filter_type))
    conn.commit()
    conn.close()

# Function to check if a domain is blacklisted
def is_blacklisted(host):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM filters WHERE address = ? AND type = 'blacklist'", (host,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# Function to check if a domain is whitelisted
def is_whitelisted(host):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM filters WHERE address = ? AND type = 'whitelist'", (host,))
    row = cursor.fetchone()
    conn.close()
    return row is not None


# Send Forbidden response 
def send_forbidden_response(client_socket):
    response = "HTTP/1.1 403 Forbidden\r\n"
    response += "Content-Type: text/html\r\n"
    response += "\r\n"
    response += "<html><body><h1>Forbidden</h1><p>You are not allowed to access this resource.</p></body></html>\r\n"
    client_socket.sendall(response.encode("utf-8"))
    # log response
    client_socket.close()

def isAccepted(host, clientSocket):

     # Check the blacklist and whitelist
        if is_blacklisted(host):
            print(f"Request to {host} is blocked (blacklisted).")
            send_forbidden_response(clientSocket)
            return False
        elif not is_whitelisted(host):
            print(f"Request to {host} is not in the whitelist.")
            send_forbidden_response(clientSocket)
            return False
        else :
            return True
        



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