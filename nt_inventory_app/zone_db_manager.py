"""
Zone DB Manager
Provides Streamlit UI component for:
  - Managing multiple Zone DB files
  - Dropdown to select active DB
  - Upload new DB
  - Returns active mapping for lookup
"""

from __future__ import annotations
import streamlit as st
from pathlib import Path
from lookup import load_zone_db

# Built-in DB files (bundled with app)
_BUILTIN_DBS = {
    'Zone_New.xlsx (ค่าเริ่มต้น)': 'Zone_New.xlsx',
    'Map_Zone.xlsx (เก่า)':        'Map_Zone.xlsx',
}

ZONE_DB_KEY     = 'zone_db_store'    # {name: mapping_dict}
ZONE_ACTIVE_KEY = 'zone_db_active'   # str: active db name


def _init_state():
    if ZONE_DB_KEY not in st.session_state:
        st.session_state[ZONE_DB_KEY] = {}
    if ZONE_ACTIVE_KEY not in st.session_state:
        st.session_state[ZONE_ACTIVE_KEY] = None

    # Load built-in DBs if not yet loaded
    store: dict = st.session_state[ZONE_DB_KEY]
    app_dir = Path(__file__).parent

    for label, filename in _BUILTIN_DBS.items():
        if label not in store:
            fpath = app_dir / filename
            if fpath.exists():
                try:
                    _, mapping = load_zone_db(fpath)
                    store[label] = mapping
                except Exception as e:
                    st.warning(f"โหลด {filename} ไม่ได้: {e}")

    # Set default active
    if st.session_state[ZONE_ACTIVE_KEY] is None and store:
        st.session_state[ZONE_ACTIVE_KEY] = next(iter(store))


def render_zone_db_selector(location: str = "sidebar") -> dict | None:
    """
    Render Zone DB selector UI.
    location: "sidebar" or "inline"
    Returns active mapping dict or None.
    """
    _init_state()
    store: dict = st.session_state[ZONE_DB_KEY]

    if location == "sidebar":
        container = st.sidebar
    else:
        container = st

    container.markdown("---")
    container.markdown("### 🗂️ Zone Database")

    # --- Dropdown ---
    db_names = list(store.keys())
    if not db_names:
        container.warning("ไม่มี Zone DB — กรุณา upload ไฟล์")
        active_mapping = None
    else:
        current = st.session_state[ZONE_ACTIVE_KEY]
        default_idx = db_names.index(current) if current in db_names else 0
        selected = container.selectbox(
            "เลือก Zone DB ที่ใช้งาน",
            options=db_names,
            index=default_idx,
            key=f"zone_db_select_{location}",
            label_visibility="collapsed",
        )
        st.session_state[ZONE_ACTIVE_KEY] = selected
        active_mapping = store.get(selected, {})
        container.caption(f"📍 {len(active_mapping):,} entries")

    # --- Upload new DB ---
    with container.expander("➕ Upload Zone DB ใหม่", ):
        uploaded = st.file_uploader(
            "เลือก .xlsx",
            type=['xlsx'],
            key=f"zone_db_upload_{location}",
        )
        if uploaded is not None:
            try:
                db_name, mapping = load_zone_db(uploaded)
                label = f"{db_name} (uploaded)"
                store[label] = mapping
                st.session_state[ZONE_ACTIVE_KEY] = label
                st.success(f"✅ โหลด '{db_name}' สำเร็จ — {len(mapping):,} entries")
                st.rerun()
            except Exception as e:
                st.error(f"❌ โหลดไม่ได้: {e}")

        st.caption("รองรับ 2 format:\n- **Zone_New.xlsx** (Sitename / ตัวย่อ / Zone New)\n- **Map_Zone.xlsx** (Hostname / Sitename / Zone)")

    # --- Delete custom DB ---
    custom_dbs = [n for n in db_names if '(uploaded)' in n]
    if custom_dbs:
        with container.expander("🗑️ ลบ Zone DB", ):
            to_delete = st.selectbox("เลือก DB ที่จะลบ", custom_dbs, key=f"zone_del_{location}")
            if st.button("ลบ", key=f"zone_del_btn_{location}", type="secondary"):
                del store[to_delete]
                if st.session_state[ZONE_ACTIVE_KEY] == to_delete:
                    st.session_state[ZONE_ACTIVE_KEY] = next(iter(store), None)
                st.rerun()

    return active_mapping


def get_active_mapping() -> dict:
    """Get active zone mapping (call after render_zone_db_selector)."""
    _init_state()
    store = st.session_state.get(ZONE_DB_KEY, {})
    active = st.session_state.get(ZONE_ACTIVE_KEY)
    return store.get(active, {}) if active else {}
