import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from exporter import export_to_bytes

st.set_page_config(page_title="Export | NT Report", page_icon="📥", layout="wide")

for key, default in [
    ('inventory_rows', []), ('port_status_rows', []), ('wan_link_rows', [])
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("📥 Export Report")
st.divider()

# ── Status summary ─────────────────────────────────────────────────────────────
inv_rows = st.session_state.inventory_rows
ps_rows  = st.session_state.port_status_rows
wan_rows = st.session_state.wan_link_rows

col1, col2, col3 = st.columns(3)
with col1:
    ok = len(inv_rows) > 0
    st.metric(
        f"{'✅' if ok else '❌'} Inventory",
        f"{len(inv_rows):,} records",
    )
with col2:
    ok = len(ps_rows) > 0
    st.metric(
        f"{'✅' if ok else '❌'} Port Status",
        f"{len(ps_rows):,} devices",
    )
with col3:
    ok = len(wan_rows) > 0
    st.metric(
        f"{'✅' if ok else '❌'} WAN Link",
        f"{len(wan_rows):,} links",
    )

has_data = any([inv_rows, ps_rows, wan_rows])
all_ready = all([inv_rows, ps_rows, wan_rows])

if not has_data:
    st.warning("⚠️ ยังไม่มีข้อมูล — กรุณา process ข้อมูลจากหน้า Inventory, Port Status, และ WAN Link ก่อน")
    st.stop()

missing = []
if not inv_rows:  missing.append("Inventory")
if not ps_rows:   missing.append("Port Status")
if not wan_rows:  missing.append("WAN Link")
if missing:
    st.info(f"ℹ️ ยังขาดข้อมูล: **{', '.join(missing)}** — sheet ที่ขาดจะว่างเปล่าใน Excel")

st.divider()

# ── Export settings ────────────────────────────────────────────────────────────
st.subheader("⚙️ ตั้งค่า")

col_a, col_b = st.columns(2)
with col_a:
    report_date = st.text_input(
        "📅 วันที่รายงาน",
        value=datetime.now().strftime('%d-%m-%Y'),
        help="แสดงในหัวของแต่ละ sheet เช่น 13-16 พฤษภาคม 2569",
    )
with col_b:
    month_str = datetime.now().strftime('%Y%m')
    filename  = st.text_input(
        "📄 ชื่อไฟล์ output",
        value=f"NT_Inventory_Report_{month_str}.xlsx",
    )

st.divider()

# ── Export button ──────────────────────────────────────────────────────────────
if st.button("📥 Generate & Download Excel", type="primary", use_container_width=True):
    with st.spinner("กำลัง generate Excel..."):
        try:
            excel_bytes = export_to_bytes(
                inventory_rows=inv_rows,
                port_status_rows=ps_rows,
                wan_link_rows=wan_rows,
                report_date=report_date,
            )
            size_kb = len(excel_bytes) / 1024
            st.success(f"✅ สร้าง Excel สำเร็จ — {size_kb:,.1f} KB  |  3 sheets")

            st.download_button(
                label=f"⬇️ ดาวน์โหลด {filename}",
                data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Sheet summary
            with st.expander("📋 รายละเอียด Excel ที่สร้าง"):
                st.markdown(f"""
| Sheet | Rows | หมายเหตุ |
|-------|------|----------|
| NT Overall | {len(inv_rows):,} | Hardware inventory ทั้งหมด |
| Port Status | {len(ps_rows):,} | สรุป port count ต่อ device |
| WAN Link | {len(wan_rows):,} | CDP neighbor topology |
""")

        except Exception as e:
            st.error(f"❌ Export ล้มเหลว: {e}")
            import traceback
            with st.expander("ดู error detail"):
                st.code(traceback.format_exc())

st.divider()

# ── Clear all ──────────────────────────────────────────────────────────────────
with st.expander("🗑️ Clear ข้อมูลทั้งหมด"):
    st.warning("การ clear จะลบข้อมูลทั้งหมดออกจาก session")
    if st.button("ยืนยัน — Clear ทั้งหมด", type="secondary"):
        for key in ['inventory_rows', 'port_status_rows', 'wan_link_rows',
                    'inv_file_count', 'ps_file_count', 'wan_file_count']:
            st.session_state[key] = [] if 'rows' in key else 0
        st.success("ล้างข้อมูลทั้งหมดแล้ว")
        st.rerun()
