import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_parsers import parse_show_interfaces_desc
from archive_utils import extract_logs
from lookup import classify_network, lookup_site_zone, build_inv_lookup
from zone_db_manager import render_zone_db_selector, get_active_mapping
from session_manager import render_session_manager, init_session
from report_date_widget import render_report_date, get_report_date
from exporter import export_sheet_bytes

st.set_page_config(page_title="Port Status | NT Report", page_icon="🔌", layout="wide")

for key, default in [('port_status_rows', []), ('ps_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")
render_report_date()
render_session_manager()

st.title("🔌 Port Status")
st.caption("Upload ไฟล์ `show interfaces description` (.zip / .7z)")

with st.container():
    ps_file = st.file_uploader("Upload archive (.zip / .7z)", type=['zip','7z'], key="ps_upload")
    if ps_file:
        st.success(f"📁 {ps_file.name}  ({ps_file.size/1024/1024:.1f} MB)")

if st.button("🔍 Process Port Status", type="primary", use_container_width=True):
    if not ps_file:
        st.warning("กรุณา upload ไฟล์ก่อน"); st.stop()
    try:
        files = extract_logs(ps_file)
    except Exception as e:
        st.error(f"❌ Extract ล้มเหลว: {e}"); st.stop()

    mapping  = get_active_mapping()
    inv_lkp  = build_inv_lookup(st.session_state.get('inventory_rows', []))
    rows, errors = [], []
    n    = len(files)
    prog = st.progress(0, text="กำลัง parse...")

    for i, (fname, content) in enumerate(files):
        prog.progress((i+1)/max(n,1), text=f"{i+1}/{n}: {fname}")
        try:
            result   = parse_show_interfaces_desc(content)
            hn       = result['hostname']
            site, zone = lookup_site_zone(hn, mapping)
            inv_info = inv_lkp.get(hn, {})
            rows.append({
                'Hostname':    hn,
                'IP Address':  inv_info.get('IP Address', ''),
                'Platform':    inv_info.get('Platform', ''),
                'Network':     classify_network(hn),
                'Site Name':   site or inv_info.get('Site Name', ''),
                'Zone':        zone or inv_info.get('Zone', ''),
                'port_counts': result['port_counts'],
            })
        except Exception as e:
            errors.append(f"{fname}: {e}")

    prog.empty()
    if errors:
        with st.expander(f"⚠️ {len(errors)} ไฟล์ parse ไม่ได้"):
            for e in errors: st.text(e)

    st.session_state.port_status_rows = rows
    st.session_state.ps_file_count    = n
    st.success(f"✅ **{len(rows):,} devices** จาก **{n:,} ไฟล์**")
    st.rerun()

if st.session_state.port_status_rows:
    rows = st.session_state.port_status_rows
    st.divider()

    col_title, col_export = st.columns([3, 1])
    col_title.subheader(f"📊 Preview — {len(rows):,} devices")
    with col_export:
        _, report_date = get_report_date()
        excel_bytes = export_sheet_bytes('Port Status', rows, report_date)
        st.download_button("⬇️ Export Port Status", data=excel_bytes,
            file_name=f"NT_PortStatus_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)

    flat = []
    for r in rows:
        pc = r.get('port_counts', {})
        row = {'Hostname': r['Hostname'], 'Network': r['Network'],
               'Site Name': r['Site Name'], 'Zone': r['Zone']}
        for spd in ['100G','40G','10G','1G']:
            b = pc.get(spd, {})
            up, dn, adm = b.get('Up',0), b.get('Down',0), b.get('Admin Down',0)
            row[f'{spd} Up'] = up; row[f'{spd} Down'] = dn
            row[f'{spd} Admin'] = adm; row[f'{spd} Total'] = up+dn+adm
        flat.append(row)
    df = pd.DataFrame(flat)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Devices", f"{len(df):,}")
    total_up  = sum(r['port_counts'].get(s,{}).get('Up',0)         for r in rows for s in ['100G','40G','10G','1G'])
    total_dn  = sum(r['port_counts'].get(s,{}).get('Down',0)       for r in rows for s in ['100G','40G','10G','1G'])
    total_adm = sum(r['port_counts'].get(s,{}).get('Admin Down',0) for r in rows for s in ['100G','40G','10G','1G'])
    m2.metric("Up", f"{total_up:,}")
    m3.metric("Down", f"{total_dn:,}")
    m4.metric("Admin Down", f"{total_adm:,}")

    st.dataframe(df.head(200), use_container_width=True, height=380)
    if len(df) > 200:
        st.caption(f"แสดง 200 จาก {len(df):,} แถว")

    if st.button("🗑️ Clear Port Status", type="secondary"):
        st.session_state.port_status_rows = []
        st.session_state.ps_file_count    = 0
        st.rerun()
