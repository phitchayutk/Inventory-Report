"""
Session persistence — Save/Load ข้อมูลทั้งหมดเป็นไฟล์ .pkl
ใช้ในหน้า Sidebar ทุกหน้า
"""
import streamlit as st
import pickle
import io
from datetime import datetime

# Keys ที่ต้องการ save/load
SESSION_KEYS = [
    'inventory_rows',
    'port_status_rows',
    'wan_link_rows',
    'version_map',
    'prev_inv_rows',
    'prev_file_name',
    'inv_file_count',
    'ps_file_count',
    'wan_file_count',
    'ver_file_count',
    'report_date',
]

DEFAULTS = {
    'inventory_rows':   [],
    'port_status_rows': [],
    'wan_link_rows':    [],
    'version_map':      {},
    'prev_inv_rows':    [],
    'prev_file_name':   '',
    'inv_file_count':   0,
    'ps_file_count':    0,
    'wan_file_count':   0,
    'ver_file_count':   0,
}


def init_session():
    """Initialize all session keys with defaults if not present."""
    from datetime import date
    for key, default in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default
    if 'report_date' not in st.session_state:
        st.session_state['report_date'] = date.today()


def render_session_manager():
    """Render Save/Load session UI in sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Session")

    # ── Save ──────────────────────────────────────────────────────────────────
    has_data = any([
        st.session_state.get('inventory_rows'),
        st.session_state.get('port_status_rows'),
        st.session_state.get('wan_link_rows'),
    ])

    if has_data:
        snapshot = {k: st.session_state.get(k) for k in SESSION_KEYS}
        buf = io.BytesIO()
        pickle.dump(snapshot, buf)
        buf.seek(0)
        fname = f"NT_Session_{datetime.now().strftime('%Y%m%d_%H%M')}.pkl"
        st.sidebar.download_button(
            "⬇️ Save Session",
            data=buf.read(),
            file_name=fname,
            mime="application/octet-stream",
            use_container_width=True,
            help="บันทึกข้อมูลทั้งหมดไว้ที่เครื่อง แล้ว Load กลับมาได้ครั้งหน้า",
        )
    else:
        st.sidebar.button("⬇️ Save Session", disabled=True,
                          use_container_width=True,
                          help="ยังไม่มีข้อมูล")

    # ── Load ──────────────────────────────────────────────────────────────────
    loaded = st.sidebar.file_uploader(
        "📂 Load Session (.pkl)",
        type=['pkl'],
        key="session_load_upload",
        label_visibility="collapsed",
    )
    if loaded is not None:
        try:
            snapshot = pickle.load(io.BytesIO(loaded.read()))
            for key in SESSION_KEYS:
                if key in snapshot:
                    st.session_state[key] = snapshot[key]
            inv_n = len(st.session_state.get('inventory_rows', []))
            ps_n  = len(st.session_state.get('port_status_rows', []))
            wan_n = len(st.session_state.get('wan_link_rows', []))
            st.sidebar.success(f"✅ โหลดแล้ว\nInv:{inv_n:,} PS:{ps_n:,} WAN:{wan_n:,}")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ โหลดไม่ได้: {e}")
