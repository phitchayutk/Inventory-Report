import streamlit as st
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import parse_show_inventory
from archive_utils import extract_logs

st.set_page_config(page_title="Inventory | NT Report", page_icon="📦", layout="wide")

# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [('inventory_rows', []), ('inv_file_count', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("📦 Inventory")
st.caption("Upload ไฟล์ `show inventory` และ `admin show inventory` (ASR9K 32-bit) ในรูปแบบ .zip หรือ .7z")

# ── Upload section ─────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2, gap="large")

with col_l:
    with st.container(border=True):
        st.markdown("#### 🔹 show inventory")
        st.caption("ทุก platform: NCS-5K, ASR9K 64-bit, ASR920")
        inv_file = st.file_uploader(
            "เลือก archive",
            type=['zip', '7z'],
            key="inv_normal",
            label_visibility="collapsed",
        )
        if inv_file:
            st.success(f"📁 {inv_file.name}  ({inv_file.size/1024/1024:.1f} MB)")

with col_r:
    with st.container(border=True):
        st.markdown("#### 🔸 admin show inventory")
        st.caption("เฉพาะ ASR9K 32-bit เท่านั้น (optional)")
        inv_admin_file = st.file_uploader(
            "เลือก archive",
            type=['zip', '7z'],
            key="inv_admin",
            label_visibility="collapsed",
        )
        if inv_admin_file:
            st.success(f"📁 {inv_admin_file.name}  ({inv_admin_file.size/1024/1024:.1f} MB)")

# ── Process ────────────────────────────────────────────────────────────────────
if st.button("🔍 Process Inventory", type="primary", use_container_width=True):
    if not inv_file and not inv_admin_file:
        st.warning("กรุณา upload อย่างน้อย 1 ไฟล์ก่อน")
        st.stop()

    all_rows = []
    all_errors = []
    total_files = 0
    _total_files = [0]

    def process_archive(uploaded_file, is_admin: bool):
        label = "admin show inventory" if is_admin else "show inventory"
        try:
            files = extract_logs(uploaded_file)
        except Exception as e:
            st.error(f"❌ Extract ล้มเหลว [{label}]: {e}")
            return

        _total_files[0] += len(files)
        prog = st.progress(0, text=f"กำลัง parse {label}...")
        n = len(files)

        for i, (fname, content) in enumerate(files):
            prog.progress((i + 1) / max(n, 1),
                          text=f"[{label}] {i+1}/{n}: {fname}")
            try:
                rows = parse_show_inventory(content, is_admin=is_admin)
                all_rows.extend(rows)
            except Exception as e:
                all_errors.append(f"{fname}: {e}")

        prog.empty()

    with st.spinner("กำลังประมวลผล..."):
        if inv_file:
            process_archive(inv_file, is_admin=False)
        if inv_admin_file:
            process_archive(inv_admin_file, is_admin=True)

    if all_errors:
        with st.expander(f"⚠️ {len(all_errors)} ไฟล์ที่ parse ไม่ได้ (คลิกดูรายละเอียด)"):
            for e in all_errors:
                st.text(e)

    st.session_state.inventory_rows = all_rows
    st.session_state.inv_file_count = _total_files[0]

    admin_count = sum(1 for r in all_rows if r.get('_is_admin'))
    normal_count = len(all_rows) - admin_count
    st.success(
        f"✅ Parse สำเร็จ — **{len(all_rows):,} records** จาก **{total_files:,} ไฟล์**  "
        f"(show inventory: {normal_count:,} | admin: {admin_count:,})"
    )
    st.rerun()

# ── Preview ────────────────────────────────────────────────────────────────────
if st.session_state.inventory_rows:
    rows = st.session_state.inventory_rows
    df = pd.DataFrame(rows)

    st.divider()
    st.subheader(f"📊 Preview — {len(rows):,} records")

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Records",   f"{len(df):,}")
    m2.metric("Unique Devices",  f"{df['Hostname'].nunique():,}")
    m3.metric("Normal Inventory",f"{len(df[~df['_is_admin']]):,}")
    m4.metric("Admin Inventory", f"{len(df[df['_is_admin']]):,}")

    # Breakdown tabs
    tab1, tab2 = st.tabs(["📋 By Type", "📋 By Platform"])
    with tab1:
        if 'Type' in df.columns:
            tc = df['Type'].value_counts().reset_index()
            tc.columns = ['Type', 'Count']
            st.dataframe(tc, use_container_width=True, height=220)
    with tab2:
        if 'Platform' in df.columns:
            pc = df['Platform'].value_counts().reset_index()
            pc.columns = ['Platform', 'Count']
            st.dataframe(pc, use_container_width=True, height=220)

    # Raw data preview
    st.markdown("**ตัวอย่างข้อมูล (100 แถวแรก)**")
    display_cols = [c for c in ['Hostname', 'Platform', 'Type', 'ProductID', 'CollectedSN', '_is_admin']
                    if c in df.columns]
    st.dataframe(df[display_cols].head(100), use_container_width=True, height=320)
    if len(df) > 100:
        st.caption(f"แสดง 100 จาก {len(df):,} แถว")

    if st.button("🗑️ Clear ข้อมูล Inventory", type="secondary"):
        st.session_state.inventory_rows = []
        st.session_state.inv_file_count = 0
        st.rerun()
