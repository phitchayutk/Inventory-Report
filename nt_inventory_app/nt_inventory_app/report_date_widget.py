"""
Shared report date selector — renders in sidebar, stores in session_state['report_date']
Call render_report_date() at top of every page.
"""
import streamlit as st
from datetime import date
from differ import to_thai_date

REPORT_DATE_KEY = 'report_date'


def render_report_date() -> tuple[date, str]:
    """
    Renders date picker in sidebar.
    Returns (date_obj, thai_date_string).
    """
    if REPORT_DATE_KEY not in st.session_state:
        st.session_state[REPORT_DATE_KEY] = date.today()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 วันที่รายงาน")

    selected = st.sidebar.date_input(
        "เลือกวันที่",
        value=st.session_state[REPORT_DATE_KEY],
        key="sidebar_report_date",
        label_visibility="collapsed",
    )
    st.session_state[REPORT_DATE_KEY] = selected

    thai_str = to_thai_date(selected)
    st.sidebar.caption(f"ข้อมูล ณ วันที่ **{thai_str}**")

    return selected, thai_str


def get_report_date() -> tuple[date, str]:
    """Get current report date from session state (no UI render)."""
    d = st.session_state.get(REPORT_DATE_KEY, date.today())
    return d, to_thai_date(d)
