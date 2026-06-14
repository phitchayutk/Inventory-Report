import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from archive_utils import extract_logs
from lookup import build_version_map, build_inv_lookup
from zone_db_manager import render_zone_db_selector
from report_date_widget import render_report_date

st.set_page_config(page_title="SW Version | NT Report", page_icon="🖥️", layout="wide")

for key, default in [('version_map', {}), ('ver_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")
render_report_date()

st.title("🖥️ SW Version")
st.caption("Upload ไฟล์ `show version` ของทุกอุปกรณ์ (.zip / .7z)")
st.info("ℹ️ SW Version จะถูกนำไป merge กับ Inventory โดยอัตโนมัติ — กรุณา Process หน้านี้ก่อนหน้า Inventory")

with st.container():
    ver_file = st.file_uploader("Upload archive (.zip / .7z)", type=['zip','7z'], key="ver_upload")
    if ver_file:
        st.success(f"📁 {ver_file.name}  ({ver_file.size/1024/1024:.1f} MB)")

if st.button("🔍 Process SW Version", type="primary", use_container_width=True):
    if not ver_file:
        st.warning("กรุณา upload ไฟล์ก่อน"); st.stop()
    try:
        files = extract_logs(ver_file)
    except Exception as e:
        st.error(f"❌ Extract ล้มเหลว: {e}"); st.stop()

    prog = st.progress(0, text="กำลัง parse...")
    n = len(files)
    # Build version map with progress
    version_map = {}
    from lookup import parse_show_version
    errors = []
    for i, (fname, content) in enumerate(files):
        prog.progress((i+1)/max(n,1), text=f"{i+1}/{n}: {fname}")
        try:
            hn, ver = parse_show_version(content)
            if hn != 'unknown' and ver:
                version_map[hn] = ver
        except Exception as e:
            errors.append(f"{fname}: {e}")
    prog.empty()

    if errors:
        with st.expander(f"⚠️ {len(errors)} ไฟล์ parse ไม่ได้"):
            for e in errors: st.text(e)

    st.session_state.version_map    = version_map
    st.session_state.ver_file_count = n

    # Also update SW Version in already-loaded inventory_rows
    inv_rows = st.session_state.get('inventory_rows', [])
    updated = 0
    for r in inv_rows:
        hn = r.get('Hostname','')
        if hn in version_map:
            r['SW Version'] = version_map[hn]
            updated += 1
    if updated:
        st.session_state.inventory_rows = inv_rows

    st.success(
        f"✅ **{len(version_map):,} devices** มี version จาก **{n:,} ไฟล์**"
        + (f" | อัปเดต Inventory {updated:,} rows แล้ว" if updated else "")
    )
    st.rerun()

# ── Preview ────────────────────────────────────────────────────────────────────
if st.session_state.version_map:
    vm = st.session_state.version_map
    st.divider()
    st.subheader(f"📊 Preview — {len(vm):,} devices")

    df = pd.DataFrame(list(vm.items()), columns=['Hostname', 'SW Version'])
    ver_counts = df['SW Version'].value_counts().reset_index()
    ver_counts.columns = ['SW Version', 'Devices']

    m1, m2 = st.columns(2)
    m1.metric("Devices มี Version", f"{len(vm):,}")
    m2.metric("Unique Versions",    f"{df['SW Version'].nunique():,}")

    tab1, tab2 = st.tabs(["📋 รายการ Hostname → Version", "📊 Version Summary"])
    with tab1:
        st.dataframe(df.sort_values('Hostname').head(200), use_container_width=True, height=380)
        if len(df) > 200: st.caption(f"แสดง 200 จาก {len(df):,} แถว")
    with tab2:
        st.dataframe(ver_counts, use_container_width=True, height=300)

    if st.button("🗑️ Clear SW Version", type="secondary"):
        st.session_state.version_map    = {}
        st.session_state.ver_file_count = 0
        st.rerun()
