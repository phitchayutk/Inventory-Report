import streamlit as st
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporter import export_to_bytes_full, write_pivot, write_new_device, write_off_device
from differ import (load_nt_overall_from_excel, compute_new_off, compute_pivot,
                    build_eos_ldos_map, enrich_eos_ldos)
from zone_db_manager import render_zone_db_selector
from report_date_widget import render_report_date, get_report_date
from openpyxl import Workbook
import io

st.set_page_config(page_title="Export | NT Report", page_icon="📥", layout="wide")

for key, default in [
    ('inventory_rows', []), ('port_status_rows', []),
    ('wan_link_rows',  []), ('version_map',      {}),
    ('prev_inv_rows',  []), ('prev_file_name',   ''),
]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")
render_report_date()

st.title("📥 Export Report")
st.divider()

inv_rows  = st.session_state.inventory_rows
ps_rows   = st.session_state.port_status_rows
wan_rows  = st.session_state.wan_link_rows
prev_rows = st.session_state.prev_inv_rows

# ── Status ─────────────────────────────────────────────────────────────────────
c1,c2,c3,c4 = st.columns(4)
c1.metric(f"{'✅' if inv_rows  else '❌'} Inventory",   f"{len(inv_rows):,} records")
c2.metric(f"{'✅' if ps_rows   else '❌'} Port Status", f"{len(ps_rows):,} devices")
c3.metric(f"{'✅' if wan_rows  else '❌'} WAN Link",    f"{len(wan_rows):,} links")
c4.metric(f"{'✅' if prev_rows else '⬜'} Prev Month",
          f"{len(prev_rows):,} rows" if prev_rows else "ยังไม่ upload")

if not any([inv_rows, ps_rows, wan_rows]):
    st.warning("⚠️ ยังไม่มีข้อมูล — กรุณา process จากหน้าก่อนหน้า")
    st.stop()

st.divider()

# ── Settings ───────────────────────────────────────────────────────────────────
st.subheader("⚙️ ตั้งค่า")
report_date, report_date_th = get_report_date()
st.info(f"📅 ข้อมูล ณ วันที่ **{report_date_th}** (เปลี่ยนได้ที่ sidebar)")

from datetime import datetime
filename = st.text_input(
    "📄 ชื่อไฟล์ output",
    value=f"NT_Inventory_Report_{datetime.now().strftime('%Y%m')}.xlsx",
)

st.divider()

# ── Previous month upload ──────────────────────────────────────────────────────
st.subheader("📂 Previous Month Inventory")
st.caption("ใช้สำหรับ EOS/LDOS lookup (by ProductID) และ New/Off Device")

col_up, col_info = st.columns([2,3])
with col_up:
    prev_file = st.file_uploader(
        "Upload NT_Inventory_Report_YYYYMM.xlsx (เดือนก่อน)",
        type=['xlsx'], key="prev_month_upload",
    )
    if prev_file:
        try:
            rows = load_nt_overall_from_excel(prev_file)
            st.session_state.prev_inv_rows  = rows
            st.session_state.prev_file_name = prev_file.name
            st.success(f"✅ '{prev_file.name}' — {len(rows):,} rows")
            prev_rows = rows
        except Exception as e:
            st.error(f"❌ โหลดไม่ได้: {e}")

with col_info:
    if st.session_state.prev_file_name:
        st.info(f"📋 ใช้ไฟล์: **{st.session_state.prev_file_name}** ({len(prev_rows):,} rows)")
        eos_map = build_eos_ldos_map(prev_rows)
        c1,c2 = st.columns(2)
        c1.metric("ProductID มี EOS/LDOS", f"{len(eos_map):,}")
        chassis_prev = sum(1 for r in prev_rows if str(r.get('Type','')).upper()=='CHASSIS')
        chassis_cur  = sum(1 for r in inv_rows  if str(r.get('Type','')).upper()=='CHASSIS')
        c2.metric("CHASSIS เดือนนี้ vs ก่อน", f"{chassis_cur:,} vs {chassis_prev:,}")
    else:
        st.caption("ถ้าไม่ upload — EOS/LDOS จะว่าง และ New/Off Device จะว่างเปล่า")
        eos_map = {}

st.divider()

# ── Compute all derived data ───────────────────────────────────────────────────
clean_inv  = [{k:v for k,v in r.items() if not k.startswith('_')} for r in inv_rows]

# Apply EOS/LDOS + LDOS_Planning
if eos_map:
    clean_inv = enrich_eos_ldos(clean_inv, eos_map, report_date)

pivot_rows             = compute_pivot(clean_inv)
new_rows, off_rows     = compute_new_off(clean_inv, prev_rows) if prev_rows else ([], [])

# Metrics
if inv_rows:
    s1,s2,s3 = st.columns(3)
    s1.metric("📊 Pivot",      f"{len(pivot_rows):,}")
    s2.metric("🟢 New Device", f"{len(new_rows):,}")
    s3.metric("🔴 Off Device", f"{len(off_rows):,}")

# ── Full export ────────────────────────────────────────────────────────────────
st.subheader("📦 Export รายงานรวม (6 sheets)")
if st.button("📥 Generate Full Report", type="primary", use_container_width=True):
    with st.spinner("กำลัง generate Excel..."):
        try:
            excel_bytes = export_to_bytes_full(
                inventory_rows=clean_inv,
                port_status_rows=ps_rows,
                wan_link_rows=wan_rows,
                pivot_rows=pivot_rows,
                new_device_rows=new_rows,
                off_device_rows=off_rows,
                report_date=report_date_th,
            )
            kb = len(excel_bytes) / 1024
            st.success(f"✅ สร้าง Excel สำเร็จ — {kb:,.1f} KB | 6 sheets")
            st.download_button(
                f"⬇️ ดาวน์โหลด {filename}", data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            with st.expander("📋 รายละเอียด sheets"):
                st.markdown(f"""
| Sheet | Rows |
|-------|------|
| NT Overall   | {len(clean_inv):,} |
| Port Status  | {len(ps_rows):,} |
| WAN Link     | {len(wan_rows):,} |
| Pivot        | {len(pivot_rows):,} |
| New Device   | {len(new_rows):,} |
| Off Device   | {len(off_rows):,} |
""")
        except Exception as e:
            st.error(f"❌ Export ล้มเหลว: {e}")
            import traceback
            with st.expander("Error detail"): st.code(traceback.format_exc())

st.divider()

# ── Per-sheet export ───────────────────────────────────────────────────────────
st.subheader("📄 Export แยก Sheet")
c1,c2,c3 = st.columns(3)

def _make_wb(title, writer_fn, rows):
    wb = Workbook(); ws = wb.active; ws.title = title
    writer_fn(ws, rows, report_date_th)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf.read()

with c1:
    if pivot_rows:
        st.download_button("⬇️ Pivot",
            data=_make_wb('Pivot', write_pivot, pivot_rows),
            file_name=f"NT_Pivot_{report_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    else:
        st.button("⬇️ Pivot (ไม่มีข้อมูล)", disabled=True, use_container_width=True)

with c2:
    if new_rows:
        st.download_button("⬇️ New Device",
            data=_make_wb('New Device', write_new_device, new_rows),
            file_name=f"NT_NewDevice_{report_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    else:
        st.button("⬇️ New Device (ไม่มีข้อมูล)", disabled=True, use_container_width=True)

with c3:
    if off_rows:
        st.download_button("⬇️ Off Device",
            data=_make_wb('Off Device', write_off_device, off_rows),
            file_name=f"NT_OffDevice_{report_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    else:
        st.button("⬇️ Off Device (ไม่มีข้อมูล)", disabled=True, use_container_width=True)

st.divider()

# ── Clear ──────────────────────────────────────────────────────────────────────
with st.expander("🗑️ Clear ข้อมูลทั้งหมด"):
    st.warning("การ clear จะลบข้อมูลทั้งหมดออกจาก session")
    if st.button("ยืนยัน — Clear ทั้งหมด", type="secondary"):
        for key in ['inventory_rows','port_status_rows','wan_link_rows','version_map',
                    'inv_file_count','ps_file_count','wan_file_count','ver_file_count',
                    'prev_inv_rows','prev_file_name']:
            if 'rows' in key:   st.session_state[key] = []
            elif 'map' in key:  st.session_state[key] = {}
            elif 'name' in key: st.session_state[key] = ''
            else:               st.session_state[key] = 0
        st.success("ล้างข้อมูลทั้งหมดแล้ว")
        st.rerun()
