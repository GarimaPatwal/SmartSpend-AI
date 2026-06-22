"""
app.py — SmartSpend AI: Personal Finance Analyst
"""

import streamlit as st
import plotly.express as px
import pandas as pd

from nl_to_sql import generate_validated_sql
from query_runner import run_query, QueryExecutionError
from sql_guard import SQLValidationError
from analyst import generate_narrative

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="SmartSpend AI", page_icon="💰", layout="centered")

# ── Initialise session state ───────────────────────────────────────────────────
defaults = {
    "input_text": "",        # actual question text
    "input_version": 0,      # incrementing = new widget key = fresh input box
    "last_question": None,
    "last_sql": None,
    "last_df": None,
    "last_narrative": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("💰 SmartSpend AI")
st.caption("Ask a question about your finances — get data, a chart, and an analyst summary.")
st.divider()

# ── Starter questions ──────────────────────────────────────────────────────────
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
        st.session_state["input_version"] += 1   # new key → fresh widget
        st.rerun()

# ── Question input ─────────────────────────────────────────────────────────────
# Using input_version as part of the key means each programmatic fill
# creates a brand-new widget — no "modified after instantiation" conflict.
question = st.text_input(
    label="Or type your own question:",
    placeholder="e.g. How much did I spend on Transport last month?",
    value=st.session_state["input_text"],
    key=f"question_box_{st.session_state['input_version']}",
)

run = st.button("Analyse →", type="primary", disabled=not question)
st.divider()

# ── Pipeline ───────────────────────────────────────────────────────────────────
if run and question:

    # Step 1 — NL → SQL
    with st.status("Generating SQL query…", expanded=False) as status:
        try:
            sql = generate_validated_sql(question)
            status.update(label="SQL query generated ✓", state="complete")
        except SQLValidationError as e:
            status.update(label="SQL blocked by safety guard", state="error")
            st.error(f"⛔ Unsafe SQL blocked.\n\n**Reason:** {e}")
            st.stop()
        except Exception as e:
            status.update(label="SQL generation failed", state="error")
            st.error(f"⚠️ Could not generate SQL. Please try rephrasing.\n\n**Error:** {e}")
            st.stop()

    # Step 2 — Execute
    with st.status("Running query on database…", expanded=False) as status:
        try:
            df = run_query(sql)
            status.update(label="Query executed ✓", state="complete")
        except QueryExecutionError as e:
            status.update(label="Query failed", state="error")
            st.error(f"⚠️ Query failed at runtime.\n\n**Error:** {e}")
            st.stop()

    if df.empty:
        st.info("No results found. Try adjusting the time period or category.")
        st.stop()

    # Step 3 — Narrative
    with st.status("Generating analyst summary…", expanded=False) as status:
        narrative = generate_narrative(question, df)
        status.update(label="Summary ready ✓", state="complete")

    # Persist to session state
    st.session_state["last_question"] = question
    st.session_state["last_sql"] = sql
    st.session_state["last_df"] = df
    st.session_state["last_narrative"] = narrative

# ── Render (survives dropdown + follow-up reruns) ──────────────────────────────
if st.session_state["last_df"] is not None:

    df        = st.session_state["last_df"]
    sql       = st.session_state["last_sql"]
    narrative = st.session_state["last_narrative"]

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
                # Same counter trick — set text + bump version → fresh input box
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