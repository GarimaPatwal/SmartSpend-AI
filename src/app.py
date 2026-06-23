"""
app.py — SmartSpend AI: Personal Finance Analyst
Day 4: added caching indicator, latency display, exponential backoff in nl_to_sql.py
Uses input_version counter pattern to avoid Streamlit widget key conflicts.
"""

import time
import streamlit as st
import plotly.express as px

from nl_to_sql import generate_validated_sql
from query_runner import run_query, QueryExecutionError
from sql_guard import SQLValidationError
from analyst import generate_narrative
import cache as sql_cache

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="SmartSpend AI", page_icon="💰", layout="centered")

# ── Initialise session state ──────────────────────────────────────────────────
defaults = {
    "input_text":     "",
    "input_version":  0,
    "last_question":  None,
    "last_sql":       None,
    "last_df":        None,
    "last_narrative": None,
    "last_latency":   None,
    "last_cached":    False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💰 SmartSpend AI")
st.caption("Ask a question about your finances — get data, a chart, and an analyst summary.")
st.divider()

# ── Starter questions ─────────────────────────────────────────────────────────
STARTER_QUESTIONS = [
    "Which categories are over budget this month and by how much?",
    "Show me the top 5 categories by total spending.",
    "What was my total spend in the last 7 days?",
    "Which merchant appears most frequently in my transactions?",
    "What is the average transaction amount per category?",
    "How much have I spent on Dining vs Groceries this month?",
]

st.markdown("**Try a starter question:**")
cols = st.columns(2)
for i, q in enumerate(STARTER_QUESTIONS):
    if cols[i % 2].button(q, key=f"starter_{i}", use_container_width=True):
        st.session_state["input_text"] = q
        st.session_state["input_version"] += 1
        st.rerun()

# ── Question input ────────────────────────────────────────────────────────────
question = st.text_input(
    label="Or type your own question:",
    placeholder="e.g. How much did I spend on Transport last month?",
    value=st.session_state["input_text"],
    key=f"question_box_{st.session_state['input_version']}",
)

run = st.button("Analyse →", type="primary", disabled=not question)
st.divider()

# ── Pipeline ──────────────────────────────────────────────────────────────────
if run and question:

    t_total = time.time()
    was_cached = sql_cache.get(question) is not None

    with st.status("Generating SQL query…", expanded=False) as status:
        try:
            sql = generate_validated_sql(question)
            sql_time = round(time.time() - t_total, 2)
            label = f"SQL query generated ✓ {'(cache ⚡)' if was_cached else f'({sql_time}s)'}"
            status.update(label=label, state="complete")
        except SQLValidationError as e:
            status.update(label="SQL blocked by safety guard ⛔", state="error")
            st.error(f"⛔ Unsafe SQL blocked.\n\n**Reason:** {e}")
            st.stop()
        except Exception as e:
            status.update(label="SQL generation failed", state="error")
            st.error(f"⚠️ Could not generate SQL. Please try rephrasing.\n\n**Error:** {e}")
            st.stop()

    with st.status("Running query on database…", expanded=False) as status:
        try:
            t0 = time.time()
            df = run_query(sql)
            db_time = round(time.time() - t0, 3)
            status.update(label=f"Query executed ✓ ({db_time}s)", state="complete")
        except QueryExecutionError as e:
            status.update(label="Query failed", state="error")
            st.error(f"⚠️ Query failed at runtime.\n\n**Error:** {e}")
            st.stop()

    if df.empty:
        st.info("No results found. Try adjusting the time period or category.")
        st.stop()

    with st.status("Generating analyst summary…", expanded=False) as status:
        t0 = time.time()
        narrative = generate_narrative(question, df)
        narr_time = round(time.time() - t0, 2)
        status.update(label=f"Summary ready ✓ ({narr_time}s)", state="complete")

    st.session_state["last_question"]  = question
    st.session_state["last_sql"]       = sql
    st.session_state["last_df"]        = df
    st.session_state["last_narrative"] = narrative
    st.session_state["last_latency"]   = round(time.time() - t_total, 2)
    st.session_state["last_cached"]    = was_cached

# ── Render ────────────────────────────────────────────────────────────────────
if st.session_state["last_df"] is not None:

    df        = st.session_state["last_df"]
    sql       = st.session_state["last_sql"]
    narrative = st.session_state["last_narrative"]
    latency   = st.session_state["last_latency"]
    cached    = st.session_state["last_cached"]

    if cached:
        st.success("⚡ Answered from cache — instant!")
    else:
        st.info(f"⏱ Total response time: **{latency}s**")

    with st.expander("🔍 View generated SQL", expanded=False):
        st.code(sql, language="sql")

    st.subheader("📊 Results")
    st.dataframe(df, use_container_width=True, hide_index=True)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    text_cols    = df.select_dtypes(include="object").columns.tolist()

    if numeric_cols and text_cols:
        with st.expander("📈 Chart", expanded=True):
            x_col = text_cols[0]
            y_col = st.selectbox("Value to chart:", numeric_cols, key="y_col")
            fig = px.bar(
                df, x=x_col, y=y_col,
                title=f"{y_col} by {x_col}",
                color=x_col,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title=y_col)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("🧠 Analyst Summary")
    for bullet in narrative["summary"]:
        st.markdown(f"- {bullet}")

    if narrative["follow_ups"]:
        st.subheader("💡 Follow-up Questions")
        for fq in narrative["follow_ups"]:
            if st.button(fq, key=f"fq_{fq[:40]}", use_container_width=False):
                st.session_state["input_text"] = fq
                st.session_state["input_version"] += 1
                st.rerun()

    st.divider()
    st.markdown("**Was this answer helpful?**")
    fb_col1, fb_col2, _ = st.columns([1, 1, 8])
    if fb_col1.button("👍  Yes"):
        st.toast("Thanks for the feedback!", icon="✅")
    if fb_col2.button("👎  No"):
        st.toast("Thanks — we'll use this to improve.", icon="📝")