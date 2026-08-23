"""
Agent Trace Auditor dashboard.

Ties together the trace store, bisector, and test debt tracker into
one view. Run with: streamlit run dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from storage.trace_store import TraceStore
from audit.bisector import bisect_session
from audit.test_debt import compute_test_debt

st.set_page_config(page_title="Agent Trace Auditor", layout="wide")
st.title("Agent Trace Auditor")

store = TraceStore()
sessions = store.list_sessions()

if not sessions:
    st.warning("No sessions found. Run `python agent/loop.py` first.")
    st.stop()

tab_trace, tab_bisect, tab_debt = st.tabs(["Trace Explorer", "Bisector", "Test Debt"])

with tab_trace:
    st.subheader("Session trace")
    selected = st.selectbox("Select a session", sessions, key="trace_session")
    events = store.get_session(selected)

    outcome = "unknown"
    for e in events:
        if e["action"] == "success":
            outcome = "success"
        elif e["action"] == "give_up":
            outcome = "gave up"

    col1, col2 = st.columns(2)
    col1.metric("Total steps", len(events))
    col2.metric("Outcome", outcome)

    for e in events:
        icon = {
            "run_tests": "🧪",
            "plan": "🧠",
            "edit_file": "✏️",
            "success": "✅",
            "give_up": "❌",
            "parse_error": "⚠️",
        }.get(e["action"], "•")

        with st.expander(f"{icon} Step {e['step']}: {e['action']}"):
            if e["reasoning"]:
                st.write("**Reasoning:**", e["reasoning"])
            if e["file"]:
                st.write("**File:**", e["file"])
            if e["diff"]:
                st.code(e["diff"], language="diff")
            if e["test_result"]:
                st.write(
                    f"**Test result:** {e['test_result']} "
                    f"({e['tests_passed']} passed, {e['tests_failed']} failed)"
                )
            if e["failing_tests"]:
                st.write("**Failing tests:**", e["failing_tests"])
            if e["test_output"]:
                st.code(e["test_output"], language="text")

with tab_bisect:
    st.subheader("Regression bisector")
    selected_b = st.selectbox("Select a session", sessions, key="bisect_session")

    if st.button("Run bisector"):
        result = bisect_session(selected_b)
        if "error" in result:
            st.error(result["error"])
        elif result["regressions_found"] == 0:
            st.success("No regressions detected in this session.")
        else:
            st.error(f"{result['regressions_found']} regression(s) found")
            for i, reg in enumerate(result["regressions"], start=1):
                st.markdown(f"**Regression #{i}**")
                st.write("Newly failing test(s):", reg["newly_failing_tests"])
                lo, hi = reg["detected_between_steps"]
                st.write(f"Detected between step {lo} and step {hi}")
                for s in reg["suspect_steps"]:
                    st.warning(f"Suspect: step {s['step']} in {s['file']}")
                    st.write("Reasoning at the time:", s["reasoning"])
                    if s["diff"]:
                        st.code(s["diff"], language="diff")

with tab_debt:
    st.subheader("Test debt checker")
    st.write("Compare a 'before' and 'after' file to see what fraction of "
             "changed code statements have no test coverage.")

    col1, col2, col3 = st.columns(3)
    before_path = col1.text_input("Before file", "toy_repo/inventory_no_bulk_discount.py")
    after_path = col2.text_input("After file", "toy_repo/inventory.py")
    test_dir = col3.text_input("Test dir", "toy_repo/tests")

    if st.button("Compute test debt"):
        try:
            result = compute_test_debt(before_path, after_path, test_dir)
            col1, col2, col3 = st.columns(3)
            col1.metric("Changed statements", result["total_changed_statements"])
            col2.metric("Covered", len(result["covered_changed_lines"]))
            col3.metric("Debt ratio", f"{result['debt_ratio']*100:.1f}%")

            if result["uncovered_changed_lines"]:
                st.warning(f"Uncovered lines: {result['uncovered_changed_lines']}")
            else:
                st.success("All changed statements are covered by tests.")
        except Exception as e:
            st.error(f"Error computing test debt: {e}")

store.close()