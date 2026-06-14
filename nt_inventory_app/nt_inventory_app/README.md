# NT Inventory Report Generator

ระบบสร้างรายงาน NT Inventory Report จาก log files อัตโนมัติ
พัฒนาโดยทีม AIT Managed Services

---

## โครงสร้างไฟล์

```
nt_inventory_app/
├── Home.py                  ← หน้าหลัก (Dashboard)
├── parsers.py               ← Parse log ทุกประเภท
├── exporter.py              ← สร้าง Excel output
├── archive_utils.py         ← Extract .zip / .7z
├── requirements.txt         ← Python dependencies
├── packages.txt             ← System packages (Streamlit Cloud)
├── .streamlit/
│   └── config.toml          ← Streamlit config (theme, upload limit)
└── pages/
    ├── 1_Inventory.py       ← show inventory + admin show inventory
    ├── 2_Port_Status.py     ← show interfaces description
    ├── 3_WAN_Link.py        ← show cdp neighbors detail
    └── 4_Export.py          ← Export Excel
```

---

## Deploy บน Streamlit Cloud (GitHub)

### ขั้นตอน

1. **สร้าง GitHub repo** (Public)
   - ไปที่ https://github.com/new
   - ตั้งชื่อ เช่น `nt-inventory-report`
   - เลือก Public → Create repository

2. **Upload ไฟล์ทั้งหมดขึ้น repo**
   ```
   nt-inventory-report/
   ├── Home.py
   ├── parsers.py
   ├── exporter.py
   ├── archive_utils.py
   ├── requirements.txt
   ├── packages.txt
   ├── .streamlit/
   │   └── config.toml
   └── pages/
       ├── 1_Inventory.py
       ├── 2_Port_Status.py
       ├── 3_WAN_Link.py
       └── 4_Export.py
   ```

3. **Deploy บน Streamlit Cloud**
   - ไปที่ https://share.streamlit.io
   - Sign in ด้วย GitHub account
   - คลิก **New app**
   - เลือก repo: `nt-inventory-report`
   - Branch: `main`
   - Main file path: `Home.py`
   - คลิก **Deploy!**

4. **รอ 2-3 นาที** จนแสดง URL เช่น:
   ```
   https://nt-inventory-report-xxxx.streamlit.app
   ```

---

## รองรับ Log Format

| หน้า | Command | Platform |
|------|---------|----------|
| Inventory | `show inventory` | NCS-5K, ASR9K 64-bit, ASR920 |
| Inventory (Admin) | `admin show inventory` | ASR9K 32-bit เท่านั้น |
| Port Status | `show interfaces description` | ทุก platform |
| WAN Link | `show cdp neighbors detail \| include "Device ID\|Interface\|outgoing port"` | IOS XR |
| WAN Link | `show cdp neighbors detail \| include Device ID\|Interface` | IOS XE |

---

## Archive Format ที่รองรับ

| Format | รองรับ |
|--------|--------|
| `.zip` | ✅ แนะนำ |
| `.7z`  | ✅ |
| `.rar` | ❌ ไม่รองรับบน Streamlit Cloud |

### วิธีสร้าง .zip บน Windows
```
เลือกไฟล์ log ทั้งหมด → Right click → Send to → Compressed (zipped) folder
```

### วิธีสร้าง .7z ด้วย 7-Zip
```
เลือกไฟล์ทั้งหมด → Right click → 7-Zip → Add to archive → Format: 7z
```

---

## รันบน Local (สำหรับ test)

```bash
pip install -r requirements.txt
streamlit run Home.py
```

---

## Output Excel

| Sheet | เนื้อหา |
|-------|---------|
| NT Overall | Hardware inventory ทั้งหมด (13 columns) |
| Port Status | สรุป port count per device (100G/40G/10G/1G) |
| WAN Link | CDP neighbor topology (src/dst hostname + interface) |
