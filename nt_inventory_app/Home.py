import streamlit as st

st.set_page_config(
    page_title="NT Inventory Report",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state init ─────────────────────────────────────────────────────────
for key, default in [
    ('inventory_rows',   []),
    ('port_status_rows', []),
    ('wan_link_rows',    []),
    ('version_map',      {}),
    ('inv_file_count',   0),
    ('ps_file_count',    0),
    ('wan_file_count',   0),
    ('ver_file_count',   0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar: Zone DB selector ──────────────────────────────────────────────────
from zone_db_manager import render_zone_db_selector
render_zone_db_selector(location="sidebar")

# ── Main content ───────────────────────────────────────────────────────────────
st.title("📋 NT Inventory Report Generator")
st.caption("AIT Managed Services — NT Account")
st.divider()

st.subheader("📊 สถานะข้อมูล")
c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Inventory",   f"{len(st.session_state.inventory_rows):,} records",
          delta=f"{st.session_state.inv_file_count:,} files" if st.session_state.inv_file_count else None, delta_color="off")
c2.metric("🔌 Port Status", f"{len(st.session_state.port_status_rows):,} devices",
          delta=f"{st.session_state.ps_file_count:,} files" if st.session_state.ps_file_count else None, delta_color="off")
c3.metric("🔗 WAN Link",    f"{len(st.session_state.wan_link_rows):,} links",
          delta=f"{st.session_state.wan_file_count:,} files" if st.session_state.wan_file_count else None, delta_color="off")
c4.metric("🖥️ SW Version",  f"{len(st.session_state.version_map):,} devices",
          delta=f"{st.session_state.ver_file_count:,} files" if st.session_state.ver_file_count else None, delta_color="off")

st.divider()
st.subheader("📖 วิธีใช้งาน")
for step, desc in [
    ("1️⃣ Inventory",   "Upload ไฟล์ `show inventory` + `admin show inventory` รวมใน archive เดียว"),
    ("2️⃣ Port Status", "Upload ไฟล์ `show interfaces description`"),
    ("3️⃣ WAN Link",    "Upload ไฟล์ `show cdp neighbors detail`"),
    ("4️⃣ SW Version",  "Upload ไฟล์ `show version` ของทุกอุปกรณ์"),
    ("5️⃣ Export",      "ตรวจสอบข้อมูล แล้วกด **Export Excel** (ทั้ง report หรือแยก sheet)"),
]:
    with st.container(border=True):
        a, b = st.columns([1, 5])
        a.markdown(f"**{step}**")
        b.markdown(desc)

with st.expander("ℹ️ Archive format ที่รองรับ"):
    st.markdown("""
| Format | รองรับ | หมายเหตุ |
|--------|--------|----------|
| `.zip` | ✅ | แนะนำ |
| `.7z`  | ✅ | บีบอัดดีกว่า |
| `.rar` | ❌ | ไม่รองรับบน Streamlit Cloud |
""")
