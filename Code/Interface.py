import streamlit as st
import sqlite3
import pandas as pd

# Connect to SQLite database
def get_db_connection():
    try:
        conn = sqlite3.connect("proxy_logs.db")
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection failed: {e}")
        return None

# Fetch logs from the database
def get_logs():
    conn = get_db_connection()
    if conn:
        try:
            logs = pd.read_sql_query("SELECT * FROM requests", conn)
            conn.close()
            return logs
        except sqlite3.Error as e:
            st.error(f"Failed to fetch logs: {e}")
    return pd.DataFrame()

# Fetch response logs
def get_response_logs():
    conn = get_db_connection()
    if conn:
        try:
            logs = pd.read_sql_query("SELECT * FROM responses", conn)
            conn.close()
            return logs
        except sqlite3.Error as e:
            st.error(f"Failed to fetch response logs: {e}")
    return pd.DataFrame()

# Fetch filters (blacklist/whitelist)
def get_filters(filter_type):
    conn = get_db_connection()
    if conn:
        try:
            filters = pd.read_sql_query(f"SELECT * FROM filters WHERE type = '{filter_type}'", conn)
            conn.close()
            return filters
        except sqlite3.Error as e:
            st.error(f"Failed to fetch {filter_type} list: {e}")
    return pd.DataFrame()

# Add or remove filters
def modify_filter(domain, filter_type, action):
    conn = get_db_connection()
    if conn:
        try:
            if action == "add":
                conn.execute("INSERT INTO filters (address, type) VALUES (?, ?)", (domain, filter_type))
            elif action == "remove":
                conn.execute("DELETE FROM filters WHERE address = ? AND type = ?", (domain, filter_type))
            conn.commit()
            conn.close()
            st.success(f"{'Added' if action == 'add' else 'Removed'} {domain} from {filter_type}.")
        except sqlite3.Error as e:
            st.error(f"Failed to modify {filter_type}: {e}")

# Clear cache
def clear_cache():
    conn = get_db_connection()
    if conn:
        try:
            conn.execute("DELETE FROM cache")
            conn.commit()
            conn.close()
            st.success("Cache cleared.")
        except sqlite3.Error as e:
            st.error(f"Failed to clear cache: {e}")

# Streamlit UI
st.title("Proxy Server Admin Dashboard")
st.sidebar.header("Navigation")
option = st.sidebar.selectbox("Choose action", ["View Logs", "Manage Blacklist/Whitelist", "Cache Management", "Statistics"])

if option == "View Logs":
    st.header("Request Logs")
    logs = get_logs()
    if not logs.empty:
        st.dataframe(logs)
    else:
        st.info("No logs available.")

    st.header("Response Logs")
    response_logs = get_response_logs()
    if not response_logs.empty:
        st.dataframe(response_logs)
    else:
        st.info("No response logs available.")

elif option == "Manage Blacklist/Whitelist":
    st.header("Blacklist Management")
    blacklist = get_filters("blacklist")
    st.dataframe(blacklist if not blacklist.empty else "No blacklist entries.")

    new_domain = st.text_input("Add to Blacklist:")
    if st.button("Add to Blacklist"):
        modify_filter(new_domain, "blacklist", "add")

    domain_to_remove = st.text_input("Remove from Blacklist:")
    if st.button("Remove from Blacklist"):
        modify_filter(domain_to_remove, "blacklist", "remove")

elif option == "Cache Management":
    st.header("Cache Management")
    if st.button("Clear Cache"):
        clear_cache()

elif option == "Statistics":
    st.header("Statistics")
    logs = get_logs()
    st.metric("Total Requests", len(logs))
