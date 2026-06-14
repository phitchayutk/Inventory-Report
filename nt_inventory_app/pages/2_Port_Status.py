import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import parse_show_interfaces_desc
from archive_utils import extract_logs

st.set_page_config(page_title="Port Status | NT Report", page_icon="🔌", layout="wide")

for key, default in [('port_status_rows', []), ('ps_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("🔌 Port Status")
st.caption("Upload ไฟล์ `show interfaces description` ในรูปแบบ .zip หรือ .7z")

# ── Upload ─────────────────────────────────────────────────────────────────────
with st.container(border=True):
    ps_file = st.file_uploader(
        "Upload archive (.zip / .7z)",
        type=['zip', '7z'],
        key="port_status_upload",
    )
    if ps_file:
        st.success(f"📁 {ps_file.name}  ({ps_file.size/1024/1024:.1f} MB)")

# ── Process ────────────────────────────────────────────────────────────────────
if st.button("🔍 Process Port Status", type="primary", use_container_width=True):
    if not ps_file:
        st.warning("กรุณา upload ไฟล์ก่อน")
        st.stop()

    try:
        files = extract_logs(ps_file)
    except Exception as e:
        st.error(f"❌ Extract ล้มเหลว: {e}")
        st.stop()

    rows = []
    errors = []
    n = len(files)
    prog = st.progress(0, text="กำลัง parse...")

    for i, (fname, content) in enumerate(files):
        prog.progress((i + 1) / max(n, 1), text=f"{i+1}/{n}: {fname}")
        try:
            result = parse_show_interfaces_desc(content)
            rows.append({
                'Hostname':    result['hostname'],
                'Network':     'MPLS LPE',
                'Site Name':   '',
                'Zone':        '',
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
    st.success(f"✅ Parse สำเร็จ — **{len(rows):,} devices** จาก **{n:,} ไฟล์**")
    st.rerun()

# ── Preview ────────────────────────────────────────────────────────────────────
if st.session_state.port_status_rows:
    rows = st.session_state.port_status_rows
    st.divider()
    st.subheader(f"📊 Preview — {len(rows):,} devices")

    # Flatten for display
    flat = []
    for r in rows:
        pc  = r.get('port_counts', {})
        row = {'Hostname': r['Hostname']}
        for spd in ['100G', '40G', '10G', '1G']:
            band = pc.get(spd, {})
            up   = band.get('Up', 0)
            dn   = band.get('Down', 0)
            adm  = band.get('Admin Down', 0)
            row[f'{spd} Up']    = up
            row[f'{spd} Down']  = dn
            row[f'{spd} Admin'] = adm
            row[f'{spd} Total'] = up + dn + adm
        flat.append(row)

    df = pd.DataFrame(flat)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Devices", f"{len(df):,}")
    total_up   = sum(r['port_counts'].get(s,{}).get('Up',0) for r in rows for s in ['100G','40G','10G','1G'])
    total_dn   = sum(r['port_counts'].get(s,{}).get('Down',0) for r in rows for s in ['100G','40G','10G','1G'])
    total_adm  = sum(r['port_counts'].get(s,{}).get('Admin Down',0) for r in rows for s in ['100G','40G','10G','1G'])
    m2.metric("Total Up",         f"{total_up:,}")
    m3.metric("Total Down",       f"{total_dn:,}")
    m4.metric("Total Admin Down", f"{total_adm:,}")

    st.dataframe(df.head(100), use_container_width=True, height=350)
    if len(df) > 100:
        st.caption(f"แสดง 100 จาก {len(df):,} แถว")

    if st.button("🗑️ Clear ข้อมูล Port Status", type="secondary"):
        st.session_state.port_status_rows = []
        st.session_state.ps_file_count    = 0
        st.rerun()
