import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import parse_show_inventory
from archive_utils import extract_logs
from lookup import classify_network, lookup_site_zone
from zone_db_manager import render_zone_db_selector, get_active_mapping
from exporter import export_sheet_bytes

st.set_page_config(page_title="Inventory | NT Report", page_icon="📦", layout="wide")

for key, default in [('inventory_rows', []), ('inv_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

# Sidebar Zone DB
render_zone_db_selector(location="sidebar")

st.title("📦 Inventory")
st.caption("Upload ไฟล์ `show inventory` และ `admin show inventory` **รวมในไฟล์เดียวกัน** (.zip / .7z)")

# ── Upload ─────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("**Archive รวม: show inventory + admin show inventory**")
    st.caption("App จะ auto-detect ประเภทจากเนื้อหาของแต่ละไฟล์โดยอัตโนมัติ")
    inv_file = st.file_uploader(
        "Upload archive (.zip / .7z)",
        type=['zip', '7z'],
        key="inv_upload",
    )
    if inv_file:
        st.success(f"📁 {inv_file.name}  ({inv_file.size/1024/1024:.1f} MB)")

# ── Process ────────────────────────────────────────────────────────────────────
if st.button("🔍 Process Inventory", type="primary", use_container_width=True):
    if not inv_file:
        st.warning("กรุณา upload ไฟล์ก่อน")
        st.stop()
    try:
        files = extract_logs(inv_file)
    except Exception as e:
        st.error(f"❌ Extract ล้มเหลว: {e}")
        st.stop()

    mapping    = get_active_mapping()
    version_map = st.session_state.get('version_map', {})
    all_rows   = []
    errors     = []
    n          = len(files)
    prog       = st.progress(0, text="กำลัง parse...")

    for i, (fname, content) in enumerate(files):
        prog.progress((i + 1) / max(n, 1), text=f"{i+1}/{n}: {fname}")
        # Auto-detect: admin show inventory หรือ show inventory
        is_admin = 'admin show inventory' in content.lower()
        try:
            rows = parse_show_inventory(content, is_admin=is_admin)
            for r in rows:
                hn = r.get('Hostname', '')
                site, zone = lookup_site_zone(hn, mapping)
                r['Network']    = classify_network(hn)
                r['Site Name']  = site
                r['Zone']       = zone
                r['SW Version'] = version_map.get(hn, '')
            all_rows.extend(rows)
        except Exception as e:
            errors.append(f"{fname}: {e}")

    prog.empty()
    if errors:
        with st.expander(f"⚠️ {len(errors)} ไฟล์ parse ไม่ได้"):
            for e in errors: st.text(e)

    st.session_state.inventory_rows = all_rows
    st.session_state.inv_file_count = n

    admin_n  = sum(1 for r in all_rows if r.get('_is_admin'))
    normal_n = len(all_rows) - admin_n
    st.success(
        f"✅ **{len(all_rows):,} records** จาก **{n:,} ไฟล์** "
        f"(show inventory: {normal_n:,} | admin: {admin_n:,})"
    )
    st.rerun()

# ── Preview + Per-sheet Export ─────────────────────────────────────────────────
if st.session_state.inventory_rows:
    rows = st.session_state.inventory_rows
    df   = pd.DataFrame(rows)

    st.divider()

    col_title, col_export = st.columns([3, 1])
    col_title.subheader(f"📊 Preview — {len(rows):,} records")

    # Per-page export button
    with col_export:
        report_date = datetime.now().strftime('%d-%m-%Y')
        export_rows = [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]
        excel_bytes = export_sheet_bytes('NT Overall', export_rows, report_date)
        st.download_button(
            label="⬇️ Export sheet นี้",
            data=excel_bytes,
            file_name=f"NT_Overall_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records",    f"{len(df):,}")
    m2.metric("Unique Devices",   f"{df['Hostname'].nunique():,}")
    m3.metric("show inventory",   f"{len(df[~df['_is_admin']]):,}")
    m4.metric("admin inventory",  f"{len(df[df['_is_admin']]):,}")

    tab1, tab2, tab3 = st.tabs(["📋 By Type", "📋 By Platform", "📋 By Zone"])
    with tab1:
        tc = df['Type'].value_counts().reset_index(); tc.columns = ['Type','Count']
        st.dataframe(tc, use_container_width=True, height=220)
    with tab2:
        pc = df['Platform'].value_counts().reset_index(); pc.columns = ['Platform','Count']
        st.dataframe(pc, use_container_width=True, height=220)
    with tab3:
        zc = df['Zone'].value_counts().reset_index(); zc.columns = ['Zone','Count']
        st.dataframe(zc, use_container_width=True, height=220)

    display_cols = [c for c in ['Hostname','Network','Site Name','Zone','Platform','Type','ProductID','CollectedSN','SW Version'] if c in df.columns]
    st.dataframe(df[display_cols].head(200), use_container_width=True, height=350)
    if len(df) > 200:
        st.caption(f"แสดง 200 จาก {len(df):,} แถว")

    if st.button("🗑️ Clear ข้อมูล Inventory", type="secondary"):
        st.session_state.inventory_rows = []
        st.session_state.inv_file_count = 0
        st.rerun()
