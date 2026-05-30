"""Streamlit admin dashboard.

Fixes: parameterized queries (no SQL injection), a Clear Cache button that
actually clears the file/memory cache instead of a non-existent table, and
management for BOTH blacklist and whitelist plus richer stats.

Run with:  streamlit run interface.py
"""
import pandas as pd
import streamlit as st

import cache as cachelib
import config
import filtering
import logs

cfg = config.load_config()
logs.configure(cfg["db_name"])


def df(sql, params=()):
    rows = logs.query(sql, params)
    return pd.DataFrame([dict(r) for r in rows])


st.title("Proxy Server Admin Dashboard")
option = st.sidebar.selectbox(
    "Choose action",
    ["View Logs", "Manage Filters", "Cache Management", "Statistics"],
)

if option == "View Logs":
    st.header("Request Logs")
    requests = df("SELECT * FROM requests ORDER BY id DESC LIMIT 500")
    st.dataframe(requests if not requests.empty else pd.DataFrame())

    st.header("Response Logs")
    responses = df("SELECT * FROM responses ORDER BY id DESC LIMIT 500")
    st.dataframe(responses if not responses.empty else pd.DataFrame())

elif option == "Manage Filters":
    list_type = st.radio("List", ["blacklist", "whitelist"], horizontal=True)
    st.caption(f"Active filter mode in config: **{cfg['filter_mode']}**")

    current = df("SELECT address FROM filters WHERE type = ?", (list_type,))
    st.dataframe(current if not current.empty else pd.DataFrame())

    domain = st.text_input(f"Domain to add/remove ({list_type})")
    col_add, col_remove = st.columns(2)
    if col_add.button("Add") and domain:
        filtering.add_to_filter_list(domain.strip(), list_type)
        st.success(f"Added {domain} to {list_type}.")
        st.rerun()
    if col_remove.button("Remove") and domain:
        filtering.remove_from_filter_list(domain.strip(), list_type)
        st.success(f"Removed {domain} from {list_type}.")
        st.rerun()

elif option == "Cache Management":
    st.header("Cache Management")
    st.write(f"Backend: **{cfg['cache']['backend']}**")
    if st.button("Clear Cache"):
        cachelib.build_cache(cfg).clear()
        st.success("Cache cleared.")

elif option == "Statistics":
    st.header("Statistics")
    total = df("SELECT COUNT(*) AS n FROM requests")
    hits = df("SELECT COUNT(*) AS n FROM responses WHERE cache_status = 'HIT'")
    misses = df("SELECT COUNT(*) AS n FROM responses WHERE cache_status = 'MISS'")
    n_total = int(total["n"][0]) if not total.empty else 0
    n_hits = int(hits["n"][0]) if not hits.empty else 0
    n_misses = int(misses["n"][0]) if not misses.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Requests", n_total)
    c2.metric("Cache Hits", n_hits)
    served = n_hits + n_misses
    c3.metric("Hit Rate", f"{(100 * n_hits / served):.1f}%" if served else "—")

    top = df(
        """SELECT target_host, COUNT(*) AS requests
           FROM requests GROUP BY target_host
           ORDER BY requests DESC LIMIT 10"""
    )
    if not top.empty:
        st.subheader("Top hosts")
        st.bar_chart(top.set_index("target_host"))