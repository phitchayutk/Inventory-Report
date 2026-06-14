import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import parse_cdp_neighbors
from archive_utils import extract_logs
from zone_db_manager import render_zone_db_selector
from exporter import export_sheet_bytes

st.set_page_config(page_title="WAN Link | NT Report", page_icon="🔗", layout="wide")

for key, default in [('wan_link_rows', []), ('wan_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")

st.title("🔗 WAN Link")
st.caption("Upload ไฟล์ `show cdp neighbors detail` (.zip / .7z)")

with st.container():
    wan_file = st.file_uploader("Upload archive (.zip / .7z)", type=['zip','7z'], key="wan_upload")
    if wan_file:
        st.success(f"📁 {wan_file.name}  ({wan_file.size/1024/1024:.1f} MB)")

if st.button("🔍 Process WAN Link", type="primary", use_container_width=True):
    if not wan_file:
        st.warning("กรุณา upload ไฟล์ก่อน"); st.stop()
    try:
        files = extract_logs(wan_file)
    except Exception as e:
        st.error(f"❌ Extract ล้มเหลว: {e}"); st.stop()

    rows, errors = [], []
    n    = len(files)
    prog = st.progress(0, text="กำลัง parse...")
    for i, (fname, content) in enumerate(files):
        prog.progress((i+1)/max(n,1), text=f"{i+1}/{n}: {fname}")
        try:
            rows.extend(parse_cdp_neighbors(content))
        except Exception as e:
            errors.append(f"{fname}: {e}")
    prog.empty()

    if errors:
        with st.expander(f"⚠️ {len(errors)} ไฟล์ parse ไม่ได้"):
            for e in errors: st.text(e)

    st.session_state.wan_link_rows  = rows
    st.session_state.wan_file_count = n
    st.success(f"✅ **{len(rows):,} links** จาก **{n:,} devices**")
    st.rerun()

if st.session_state.wan_link_rows:
    rows = st.session_state.wan_link_rows
    st.divider()

    col_title, col_export = st.columns([3,1])
    col_title.subheader(f"📊 Preview — {len(rows):,} links")
    with col_export:
        report_date = datetime.now().strftime('%d-%m-%Y')
        excel_bytes = export_sheet_bytes('WAN Link', rows, report_date)
        st.download_button("⬇️ Export WAN Link", data=excel_bytes,
            file_name=f"NT_WANLink_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)

    df = pd.DataFrame(rows)

    def speed_label(intf):
        u = intf.upper()
        if 'HUNDRED' in u or u.startswith('HU'): return '100G'
        if 'FORTY'   in u or u.startswith('FO'): return '40G'
        if 'TEN'     in u or u.startswith('TE'): return '10G'
        return '1G/Other'

    m1,m2,m3 = st.columns(3)
    m1.metric("Total Links",    f"{len(df):,}")
    m2.metric("Source Devices", f"{df['Source Hostname'].nunique():,}")
    m3.metric("Dest Devices",   f"{df['Destination Hostname'].nunique():,}")

    df['Speed'] = df['Source Interface'].apply(speed_label)
    tab1,tab2 = st.tabs(["📋 All Links","📊 Speed Breakdown"])
    with tab1:
        st.dataframe(df[['Source Hostname','Source Interface',
                          'Destination Hostname','Destination Interface']].head(200),
                     use_container_width=True, height=380)
    with tab2:
        sc = df['Speed'].value_counts().reset_index(); sc.columns=['Speed','Links']
        st.dataframe(sc, use_container_width=True, height=200)
    if len(df) > 200: st.caption(f"แสดง 200 จาก {len(df):,} แถว")

    if st.button("🗑️ Clear WAN Link", type="secondary"):
        st.session_state.wan_link_rows  = []
        st.session_state.wan_file_count = 0
        st.rerun()
