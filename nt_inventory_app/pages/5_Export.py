import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporter import (export_to_bytes_full, export_sheet_bytes,
                      write_pivot, write_new_device, write_off_device)
from differ import load_nt_overall_from_excel, compute_new_off, compute_pivot
from zone_db_manager import render_zone_db_selector

st.set_page_config(page_title="Export | NT Report", page_icon="📥", layout="wide")

for key, default in [
    ('inventory_rows',   []), ('port_status_rows', []),
    ('wan_link_rows',    []), ('version_map',      {}),
    ('prev_inv_rows',    []), ('prev_file_name',   ''),
]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")

st.title("📥 Export Report")
st.divider()

inv_rows  = st.session_state.inventory_rows
ps_rows   = st.session_state.port_status_rows
wan_rows  = st.session_state.wan_link_rows
prev_rows = st.session_state.prev_inv_rows

# ── Status ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{'✅' if inv_rows  else '❌'} Inventory",   f"{len(inv_rows):,} records")
c2.metric(f"{'✅' if ps_rows   else '❌'} Port Status", f"{len(ps_rows):,} devices")
c3.metric(f"{'✅' if wan_rows  else '❌'} WAN Link",    f"{len(wan_rows):,} links")
c4.metric(f"{'✅' if prev_rows else '⬜'} Prev Month",
          f"{len(prev_rows):,} rows" if prev_rows else "ยังไม่ upload")

if not any([inv_rows, ps_rows, wan_rows]):
    st.warning("⚠️ ยังไม่มีข้อมูล — กรุณา process จากหน้าก่อนหน้า")
    st.stop()

st.divider()

# ── Previous month upload ──────────────────────────────────────────────────────
st.subheader("📂 Previous Month Inventory (สำหรับ New/Off Device)")

with st.container():
    col_up, col_info = st.columns([2, 3])
    with col_up:
        prev_file = st.file_uploader(
            "Upload NT_Inventory_Report_YYYYMM.xlsx (เดือนก่อน)",
            type=['xlsx'],
            key="prev_month_upload",
        )
        if prev_file:
            try:
                rows = load_nt_overall_from_excel(prev_file)
                st.session_state.prev_inv_rows  = rows
                st.session_state.prev_file_name = prev_file.name
                st.success(f"✅ โหลด '{prev_file.name}' — {len(rows):,} rows")
                prev_rows = rows
            except Exception as e:
                st.error(f"❌ โหลดไม่ได้: {e}")

    with col_info:
        if st.session_state.prev_file_name:
            st.info(f"📋 ใช้ไฟล์: **{st.session_state.prev_file_name}**  ({len(prev_rows):,} rows)")
            # Show chassis count
            chassis_prev = [r for r in prev_rows if str(r.get('Type','')).upper()=='CHASSIS']
            chassis_cur  = [r for r in inv_rows  if str(r.get('Type','')).upper()=='CHASSIS']
            cc1, cc2 = st.columns(2)
            cc1.metric("CHASSIS เดือนก่อน", f"{len(chassis_prev):,}")
            cc2.metric("CHASSIS เดือนนี้",  f"{len(chassis_cur):,}")
        else:
            st.caption("ถ้าไม่ upload — sheet New Device และ Off Device จะว่างเปล่า")

st.divider()

# ── Settings ───────────────────────────────────────────────────────────────────
st.subheader("⚙️ ตั้งค่า")
col_a, col_b = st.columns(2)
with col_a:
    report_date = st.text_input("📅 วันที่รายงาน",
                                value=datetime.now().strftime('%d-%m-%Y'))
with col_b:
    filename = st.text_input("📄 ชื่อไฟล์ output",
                             value=f"NT_Inventory_Report_{datetime.now().strftime('%Y%m')}.xlsx")

st.divider()

# ── Compute Pivot + New/Off ────────────────────────────────────────────────────
clean_inv = [{k: v for k, v in r.items() if not k.startswith('_')} for r in inv_rows]
pivot_rows = compute_pivot(clean_inv)

if prev_rows:
    new_rows, off_rows = compute_new_off(clean_inv, prev_rows)
else:
    new_rows, off_rows = [], []

# Summary before export
if inv_rows:
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("📊 Pivot rows",       f"{len(pivot_rows):,}")
    sc2.metric("🟢 New Device",        f"{len(new_rows):,}")
    sc3.metric("🔴 Off Device",        f"{len(off_rows):,}")

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
                report_date=report_date,
            )
            kb = len(excel_bytes) / 1024
            st.success(f"✅ สร้าง Excel สำเร็จ — {kb:,.1f} KB | 6 sheets")
            st.download_button(
                f"⬇️ ดาวน์โหลด {filename}",
                data=excel_bytes, file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            with st.expander("📋 รายละเอียด sheets"):
                st.markdown(f"""
| Sheet | Rows | หมายเหตุ |
|-------|------|----------|
| NT Overall   | {len(clean_inv):,} | Hardware inventory ทั้งหมด |
| Port Status  | {len(ps_rows):,} | Port count per device |
| WAN Link     | {len(wan_rows):,} | CDP neighbor links |
| Pivot        | {len(pivot_rows):,} | CHASSIS per Hostname |
| New Device   | {len(new_rows):,} | อุปกรณ์ขึ้นใหม่เดือนนี้ |
| Off Device   | {len(off_rows):,} | อุปกรณ์เลิกใช้งานเดือนนี้ |
""")
        except Exception as e:
            st.error(f"❌ Export ล้มเหลว: {e}")
            import traceback
            with st.expander("Error detail"): st.code(traceback.format_exc())

st.divider()

# ── Per-sheet export ───────────────────────────────────────────────────────────
st.subheader("📄 Export แยก Sheet")
col1, col2, col3 = st.columns(3)

with col1:
    if pivot_rows:
        from openpyxl import Workbook as _WB
        import io as _io
        wb = _WB(); ws = wb.active; ws.title = 'Pivot'
        write_pivot(ws, pivot_rows, report_date)
        buf = _io.BytesIO(); wb.save(buf); buf.seek(0)
        st.download_button("⬇️ Pivot", data=buf.read(),
                           file_name=f"NT_Pivot_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

with col2:
    if new_rows:
        from openpyxl import Workbook as _WB2
        import io as _io2
        wb2 = _WB2(); ws2 = wb2.active; ws2.title = 'New Device'
        write_new_device(ws2, new_rows, report_date)
        buf2 = _io2.BytesIO(); wb2.save(buf2); buf2.seek(0)
        st.download_button("⬇️ New Device", data=buf2.read(),
                           file_name=f"NT_NewDevice_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    else:
        st.button("⬇️ New Device (ไม่มีข้อมูล)", disabled=True, use_container_width=True)

with col3:
    if off_rows:
        from openpyxl import Workbook as _WB3
        import io as _io3
        wb3 = _WB3(); ws3 = wb3.active; ws3.title = 'Off Device'
        write_off_device(ws3, off_rows, report_date)
        buf3 = _io3.BytesIO(); wb3.save(buf3); buf3.seek(0)
        st.download_button("⬇️ Off Device", data=buf3.read(),
                           file_name=f"NT_OffDevice_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    else:
        st.button("⬇️ Off Device (ไม่มีข้อมูล)", disabled=True, use_container_width=True)

st.divider()

# ── Clear all ──────────────────────────────────────────────────────────────────
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
