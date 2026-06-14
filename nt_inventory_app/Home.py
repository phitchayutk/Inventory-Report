import streamlit as st

st.set_page_config(
    page_title="NT Inventory Report",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state initialisation ──────────────────────────────────────────────
for key, default in [
    ('inventory_rows',   []),
    ('port_status_rows', []),
    ('wan_link_rows',    []),
    ('inv_file_count',   0),
    ('ps_file_count',    0),
    ('wan_file_count',   0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Page header ───────────────────────────────────────────────────────────────
st.title("📋 NT Inventory Report Generator")
st.caption("AIT Managed Services — NT Account | พัฒนาโดยทีม AIT")
st.divider()

# ── Status dashboard ──────────────────────────────────────────────────────────
st.subheader("📊 สถานะข้อมูล")

col1, col2, col3 = st.columns(3)

with col1:
    n = len(st.session_state.inventory_rows)
    f = st.session_state.inv_file_count
    status = "✅" if n > 0 else "⬜"
    st.metric(f"{status} Inventory", f"{n:,} records",
              delta=f"{f:,} files" if f > 0 else None,
              delta_color="off")

with col2:
    n = len(st.session_state.port_status_rows)
    f = st.session_state.ps_file_count
    status = "✅" if n > 0 else "⬜"
    st.metric(f"{status} Port Status", f"{n:,} devices",
              delta=f"{f:,} files" if f > 0 else None,
              delta_color="off")

with col3:
    n = len(st.session_state.wan_link_rows)
    f = st.session_state.wan_file_count
    status = "✅" if n > 0 else "⬜"
    st.metric(f"{status} WAN Link", f"{n:,} links",
              delta=f"{f:,} files" if f > 0 else None,
              delta_color="off")

st.divider()

# ── Instructions ──────────────────────────────────────────────────────────────
st.subheader("📖 วิธีใช้งาน")

steps = [
    ("1️⃣ Inventory",    "Upload ไฟล์ `show inventory` (ทุก platform)\nและ `admin show inventory` (เฉพาะ ASR9K 32-bit)"),
    ("2️⃣ Port Status",  "Upload ไฟล์ `show interfaces description`"),
    ("3️⃣ WAN Link",     "Upload ไฟล์ `show cdp neighbors detail`"),
    ("4️⃣ Export",       "ตรวจสอบข้อมูลสรุปแล้วกด **Export Excel**"),
]

for title, desc in steps:
    with st.container(border=True):
        col_t, col_d = st.columns([1, 4])
        col_t.markdown(f"**{title}**")
        col_d.markdown(desc)

st.divider()

# ── Format info ───────────────────────────────────────────────────────────────
with st.expander("ℹ️ รูปแบบ Archive ที่รองรับ"):
    st.markdown("""
| Format | รองรับ | หมายเหตุ |
|--------|--------|----------|
| `.zip` | ✅ | แนะนำ — เร็วที่สุด |
| `.7z`  | ✅ | บีบอัดได้ดีกว่า zip |
| `.rar` | ❌ | ไม่รองรับบน Streamlit Cloud |

**ตัวอย่างการสร้าง .zip บน Windows:**
```
เลือกไฟล์ทั้งหมด → Right click → Send to → Compressed (zipped) folder
```
**หรือใช้ 7-Zip:**
```
เลือกไฟล์ทั้งหมด → Right click → 7-Zip → Add to archive → Format: zip หรือ 7z
```
""")

# ── Quick export shortcut ─────────────────────────────────────────────────────
has_any = any([
    st.session_state.inventory_rows,
    st.session_state.port_status_rows,
    st.session_state.wan_link_rows,
])
if has_any:
    st.page_link("pages/4_Export.py", label="📥 ไปหน้า Export", icon="📥")
