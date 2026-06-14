import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporter import export_to_bytes
from zone_db_manager import render_zone_db_selector

st.set_page_config(page_title="Export | NT Report", page_icon="📥", layout="wide")

for key, default in [
    ('inventory_rows', []), ('port_status_rows', []),
    ('wan_link_rows', []),  ('version_map', {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

render_zone_db_selector(location="sidebar")

st.title("📥 Export Report")
st.divider()

inv_rows = st.session_state.inventory_rows
ps_rows  = st.session_state.port_status_rows
wan_rows = st.session_state.wan_link_rows

# ── Status ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{'✅' if inv_rows else '❌'} Inventory",   f"{len(inv_rows):,} records")
c2.metric(f"{'✅' if ps_rows  else '❌'} Port Status", f"{len(ps_rows):,} devices")
c3.metric(f"{'✅' if wan_rows else '❌'} WAN Link",    f"{len(wan_rows):,} links")
c4.metric(f"{'✅' if st.session_state.version_map else '⬜'} SW Version",
          f"{len(st.session_state.version_map):,} devices")

if not any([inv_rows, ps_rows, wan_rows]):
    st.warning("⚠️ ยังไม่มีข้อมูล — กรุณา process จากหน้าก่อนหน้า")
    st.stop()

missing = [n for n, d in [("Inventory", inv_rows), ("Port Status", ps_rows), ("WAN Link", wan_rows)] if not d]
if missing:
    st.info(f"ℹ️ ยังขาด: **{', '.join(missing)}** — sheet ที่ขาดจะว่างเปล่า")

st.divider()

# ── Settings ───────────────────────────────────────────────────────────────────
st.subheader("⚙️ ตั้งค่า")
col_a, col_b = st.columns(2)
with col_a:
    report_date = st.text_input("📅 วันที่รายงาน", value=datetime.now().strftime('%d-%m-%Y'))
with col_b:
    filename = st.text_input("📄 ชื่อไฟล์ output",
                             value=f"NT_Inventory_Report_{datetime.now().strftime('%Y%m')}.xlsx")

st.divider()

# ── Full report export ─────────────────────────────────────────────────────────
st.subheader("📦 Export รายงานรวม (ทุก sheet)")
if st.button("📥 Generate Full Report", type="primary", use_container_width=True):
    with st.spinner("กำลัง generate Excel..."):
        try:
            # Strip internal keys before export
            clean_inv = [{k: v for k, v in r.items() if not k.startswith('_')} for r in inv_rows]
            excel_bytes = export_to_bytes(clean_inv, ps_rows, wan_rows, report_date)
            kb = len(excel_bytes) / 1024
            st.success(f"✅ สร้าง Excel สำเร็จ — {kb:,.1f} KB | 3 sheets")
            st.download_button(
                f"⬇️ ดาวน์โหลด {filename}", data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            with st.expander("📋 รายละเอียด"):
                st.markdown(f"""
| Sheet | Rows |
|-------|------|
| NT Overall | {len(inv_rows):,} |
| Port Status | {len(ps_rows):,} |
| WAN Link | {len(wan_rows):,} |
""")
        except Exception as e:
            st.error(f"❌ Export ล้มเหลว: {e}")
            import traceback
            with st.expander("Error detail"):
                st.code(traceback.format_exc())

st.divider()

# ── Clear all ──────────────────────────────────────────────────────────────────
with st.expander("🗑️ Clear ข้อมูลทั้งหมด"):
    st.warning("การ clear จะลบข้อมูลทั้งหมดออกจาก session")
    if st.button("ยืนยัน — Clear ทั้งหมด", type="secondary"):
        for key in ['inventory_rows','port_status_rows','wan_link_rows','version_map',
                    'inv_file_count','ps_file_count','wan_file_count','ver_file_count']:
            st.session_state[key] = [] if 'rows' in key else ({} if 'map' in key else 0)
        st.success("ล้างข้อมูลทั้งหมดแล้ว")
        st.rerun()
