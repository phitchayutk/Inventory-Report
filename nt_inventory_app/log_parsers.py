"""
NT Inventory Log Parsers
Supports:
  - show inventory        (IOS XR: ASR9K 64-bit, NCS-5K)
  - admin show inventory  (IOS XR: ASR9K 32-bit)
  - show interfaces desc  (IOS XE: ASR920, LPE)
  - show cdp neighbors detail | include ... (IOS XR & IOS XE)
"""

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Terminal / ANSI escape sequence cleaner
# ---------------------------------------------------------------------------

# Matches: ESC[ ... m  (color/SGR), ESC[ ... other, ESC(B, ESC= etc.
_ANSI_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
# Also strip bare control chars except \t \n \r
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

def _clean_ansi(text: str) -> str:
    """Remove ANSI escape codes and stray control characters from log text."""
    text = _ANSI_RE.sub('', text)
    text = _CTRL_RE.sub('', text)
    return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_hostname(text: str) -> str:
    """Pull hostname from prompt line.
    Supports:
      RP/0/RSP0/CPU0:kkm_srw_pe2#
      RP/0/RP0/CPU0:acr_acr_aggpe1#
      atg_atg_lpe1#
    """
    m = re.search(r'(?:CPU0:|^)([a-zA-Z0-9][a-zA-Z0-9_\-]+)#', text, re.MULTILINE)
    return m.group(1) if m else 'unknown'


def _clean_device_id(raw: str) -> str:
    """Strip domain suffix and parenthetical serial from CDP device IDs."""
    raw = re.sub(r'\.tot[^.\s]*(?:\.[a-z]+)*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\.totbroadband[^.\s]*(?:\.[a-z]+)*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\([^)]+\)', '', raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Type classification from DESCR + PID
# ---------------------------------------------------------------------------

_TYPE_RULES = [
    # SUPERVISOR — check before generic MODULE
    # IOS XR RSP patterns
    (r'Route Switch Processor|RSP880|RSP440|RSP4|RSP-4|RSP880-LT',  'SUPERVISOR'),
    # ASR9900 Route Processor: A99-RP-F, A99-RP-SE, A99-RP2-TR etc.
    (r'^A99-RP',                                                      'SUPERVISOR'),
    # NCS RP/SC patterns
    (r'NCS-5500-RP|NCS4K-RP',                                        'SUPERVISOR'),

    # FAN
    (r'Fan Tray|FAN-TRAY|FAN TRAY',                                  'FAN'),

    # POWER
    (r'Power Module|Power Supply|PWR-\d|AC-\d+W|DC-\d+W',           'PWR'),

    # CHASSIS — handled separately in _classify_type, but keep as fallback
    (r'\bCHASSIS\b',                                                  'CHASSIS'),

    # LINE CARD / MODULE — ASR9900 specific
    # A99-xxxLC = Line Card
    (r'^A99-.*LC\b|ASR-9903-LC|ASR-9906-LC',                        'MODULE'),
    # A99-xxxSE/FC = Fabric Card
    (r'^A99-.*(?:SE|FC|SIP)\b',                                      'MODULE'),

    # TRANSCEIVERS
    (r'100GBASE|CFP2?|QSFP.*100G|100G.*QSFP',                       '100G Transceiver'),
    (r'40GBASE|QSFP.*40G|40G.*QSFP',                                 '40G Transceiver'),
    (r'10GBASE|XFP|SFP\+.*10G|SFP.*10G|10GBASE',                   '10G Transceiver'),
    (r'1000BASE|GLC|SFP-GE|SFP.*1G|1000BASE',                       '1G Transceiver'),

    # Generic LINE CARD
    (r'Modular Linecard|Line Card|MPA|MOD80|MOD160|MOD400',         'MODULE'),
]

_CHASSIS_PID_RE = re.compile(
    r'^(ASR-9[0-9]{3,}|A9K-RSP|A9K-MOD|NCS-55[0-9]|NCS-54[0-9]|NCS-56[0-9]|N540|N560|ASR-920[^-]|ASR-920$)',
    re.IGNORECASE
)
_CHASSIS_NAME_RE = re.compile(r'^chassis\b', re.IGNORECASE)

def _classify_type(descr: str, pid: str, name: str = '') -> str:
    pid_u   = pid.strip().upper()
    descr_u = descr.strip().upper()
    combined = descr_u + ' ' + pid_u

    # 1. PID-first rules (highest priority — overrides DESCR)
    # A99-RP-xxx = SUPERVISOR (ASR9900 Route Processor)
    if re.match(r'^A99-RP', pid_u):
        return 'SUPERVISOR'
    # ASR9K RSP = SUPERVISOR
    if re.match(r'^A9K-RSP', pid_u):
        return 'SUPERVISOR'
    # PIDs ending in -LC = Line Card (MODULE), even if DESCR says "Chassis"
    if re.search(r'-LC$', pid_u) and re.match(r'^(A99-|ASR-990)', pid_u):
        return 'MODULE'
    # A99-xxx-SE/FC/SIP = Fabric/Service card (MODULE)
    if re.match(r'^A99-', pid_u) and re.search(r'-(SE|FC|SIP)\d*$', pid_u):
        return 'MODULE'

    # 2. NAME starts with "chassis"
    if _CHASSIS_NAME_RE.match(name.strip()):
        return 'CHASSIS'

    # 3. CHASSIS keyword in DESCR — but NOT if PID is a line card
    if re.search(r'\bCHASSIS\b', combined) and not re.search(r'\b(PEM|FAN|POWER|PWR)\b', combined):
        return 'CHASSIS'

    # 4. DESCR-based rules
    for pattern, label in _TYPE_RULES:
        if re.search(pattern, combined, re.IGNORECASE):
            return label

    # 5. Fallback: known chassis PID pattern
    if _CHASSIS_PID_RE.match(pid.strip()):
        return 'CHASSIS'

    return 'MODULE'


def _classify_platform(pid: str) -> str:
    """
    Classify platform from CHASSIS Product ID.
    Rules:
      ASR920   : ASR-920-xxx
      ASR9900  : ASR-990x  (exactly 4 digits after ASR-9 → 990x)
      ASR9000  : ASR-9xxxx (5+ digits after ASR-9, e.g. 9006, 9912, 9922)
      NCS-5K   : NCS-5501, NCS-5502, NCS-55xx, NCS-540x, NCS-560x
    """
    p = pid.upper()

    # ASR920 — must check BEFORE ASR9xxx
    if re.search(r'ASR-920|ASR920', p):
        return 'ASR920'

    # ASR9900 — ASR-990x  (3-digit: 990x)
    if re.search(r'ASR-990[0-9](?!\d)', p):
        return 'ASR9900'

    # ASR9000 — ASR-9xxxx  (4+ digit model number like 9006, 9012, 9906, 9912)
    if re.search(r'^A9K|^ASR9K|ASR-9[0-9]{3,}', p):
        return 'ASR9000'

    # NCS-5K (NCS-5501, NCS-5502, NCS-55xx, NCS-55Ax, N540, N560)
    if re.search(r'NCS-55[0-9A-Z]|NCS-5[56][0-9]|N540|N560', p):
        return 'NCS-5K'

    return ''


# ---------------------------------------------------------------------------
# Parser 1: show inventory / admin show inventory (IOS XR)
# ---------------------------------------------------------------------------

def _ip_from_filename(filename: str) -> str:
    """
    Extract IP address from filename.
    e.g. '118_174_252_251.log' → '118.174.252.251'
         '10_244_248_165.txt'  → '10.244.248.165'
    """
    stem = re.sub(r'\.[^.]+$', '', filename)   # remove extension
    # Try underscore-separated octets
    m = re.match(r'^(\d{1,3})_(\d{1,3})_(\d{1,3})_(\d{1,3})', stem)
    if m:
        return f'{m.group(1)}.{m.group(2)}.{m.group(3)}.{m.group(4)}'
    # Already dotted notation inside filename
    m2 = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', stem)
    if m2:
        return m2.group(1)
    return ''


def parse_show_inventory(text: str, is_admin: bool = False,
                         filename: str = '') -> list[dict]:
    """
    Parse output of `show inventory` or `admin show inventory`.
    - IP Address extracted from filename (e.g. 118_174_252_251.log)
    - Platform determined from CHASSIS PID, then propagated to all rows
    Returns list of dicts.
    """
    text     = _clean_ansi(text)
    hostname = _extract_hostname(text)
    ip_addr  = _ip_from_filename(filename) if filename else ''
    records  = []

    # Valid PID: alphanumeric + dash/dot/slash/plus, min 3 chars
    _PID_VALID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9\-\.\/\+]{2,}$')

    block_re = re.compile(
        # NAME: "..." , DESCR: "..."  — on ONE line (IOS XR & IOS XE)
        r'NAME:\s*"([^"]*)"[^"\n]*DESCR:\s*"([^"]*)"\s*\n'
        # PID: xxx (with possible wide spacing) , VID: xxx , SN: xxx
        r'PID:\s*([^,\n]*?)\s*,\s*VID:[^,\n]*,\s*SN:\s*(\S*)',
    )

    # Alternate: VID might have extra spaces or be empty
    block_re_alt = re.compile(
        r'NAME:\s*"([^"]*)"[^"\n]*DESCR:\s*"([^"]*)"\s*\n'
        r'PID:\s*([^\s,][^,\n]*?)\s*,\s*VID:[^\n]*SN:\s*(\S+)',
    )

    matches = list(block_re.finditer(text))
    if not matches:
        matches = list(block_re_alt.finditer(text))

    for m in matches:
        name  = m.group(1).strip()
        descr = (m.group(2) or '').strip()
        pid   = m.group(3).strip()
        sn    = m.group(4).strip()

        if pid in ('N/A', '', 'MISSING', 'n/a'):
            continue
        if not _PID_VALID.match(pid):
            continue

        item_type = _classify_type(descr, pid, name=name)
        records.append({
            'Hostname':    hostname,
            'IP Address':  ip_addr,
            'Type':        item_type,
            'ProductID':   pid,
            'CollectedSN': sn,
            'Platform':    _classify_platform(pid) if item_type == 'CHASSIS' else '',
            '_is_admin':   is_admin,
        })

    # ── Propagate Platform from CHASSIS row to all rows of same hostname ──
    chassis_platform = next(
        (r['Platform'] for r in records if r['Type'] == 'CHASSIS' and r['Platform']),
        ''
    )
    if chassis_platform:
        for r in records:
            if not r['Platform']:
                r['Platform'] = chassis_platform

    return records


# ---------------------------------------------------------------------------
# Parser 2: show interfaces description (IOS XE / IOS XR)
# ---------------------------------------------------------------------------

_INTF_RE = re.compile(
    r'^(\S+)\s+(up|down|admin\s+down)\s+(up|down)\s*(.*)',
    re.IGNORECASE
)

def _speed_bucket(intf: str) -> str | None:
    u = intf.upper()
    if u.startswith('HU') or 'HUNDREDGIG' in u:  return '100G'
    if u.startswith('FO') or 'FORTYGIG' in u:     return '40G'
    if u.startswith('TE') or 'TENGIG' in u:        return '10G'
    if u.startswith('GI') or 'GIGABIT' in u:       return '1G'
    return None


def parse_show_interfaces_desc(text: str) -> dict:
    """
    Returns {
      'hostname': str,
      'port_counts': { '100G': {'Up':n,'Down':n,'Admin Down':n}, ... },
      'interfaces': [{'Interface','Status','Description'}, ...]
    }
    """
    text = _clean_ansi(text)
    hostname = _extract_hostname(text)
    counts = {s: {'Up': 0, 'Down': 0, 'Admin Down': 0} for s in ['100G', '40G', '10G', '1G']}
    interfaces = []

    for line in text.splitlines():
        m = _INTF_RE.match(line.strip())
        if not m:
            continue
        intf       = m.group(1)
        raw_status = m.group(2).lower().strip()
        desc       = m.group(4).strip()
        speed      = _speed_bucket(intf)
        if speed is None:
            continue

        if 'admin' in raw_status:
            status = 'Admin Down'
        elif raw_status == 'up':
            status = 'Up'
        else:
            status = 'Down'

        counts[speed][status] += 1
        interfaces.append({'Interface': intf, 'Status': status, 'Description': desc})

    return {'hostname': hostname, 'port_counts': counts, 'interfaces': interfaces}


# ---------------------------------------------------------------------------
# Parser 3: show cdp neighbors detail
# ---------------------------------------------------------------------------

def parse_cdp_neighbors(text: str) -> list[dict]:
    """
    Supports two output styles:
    IOS XR:   Device ID / Interface / Port ID on separate lines
    IOS XE:   Interface and Port ID on same line
    """
    text  = _clean_ansi(text)
    hostname = _extract_hostname(text)
    records  = []
    lines    = [l.rstrip() for l in text.splitlines()]

    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.startswith('Device ID:'):
            i += 1
            continue

        raw_dev       = line.split('Device ID:', 1)[1].strip()
        dest_hostname = _clean_device_id(raw_dev)

        # Find next non-empty line
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1

        if j >= len(lines) or not lines[j].strip().startswith('Interface:'):
            i += 1
            continue

        intf_line = lines[j].strip()

        # IOS XE: Interface and Port ID on same line
        if 'Port ID (outgoing port):' in intf_line:
            parts    = intf_line.split('Port ID (outgoing port):', 1)
            src_intf = re.sub(r'^Interface:\s*', '', parts[0]).rstrip(', ').strip()
            dst_intf = parts[1].strip()
            records.append({
                'Source Hostname':       hostname,
                'Source Interface':      src_intf,
                'Destination Hostname':  dest_hostname,
                'Destination Interface': dst_intf,
            })
            i = j + 1
            continue

        # IOS XR: Port ID on next line
        src_intf = re.sub(r'^Interface:\s*', '', intf_line).strip()
        k = j + 1
        while k < len(lines) and not lines[k].strip():
            k += 1
        if k < len(lines) and 'Port ID (outgoing port):' in lines[k]:
            dst_intf = lines[k].split('Port ID (outgoing port):', 1)[1].strip()
            records.append({
                'Source Hostname':       hostname,
                'Source Interface':      src_intf,
                'Destination Hostname':  dest_hostname,
                'Destination Interface': dst_intf,
            })
            i = k + 1
            continue

        i = j + 1

    return records


# ---------------------------------------------------------------------------
# Auto-detect log type
# ---------------------------------------------------------------------------

def detect_log_type(text: str) -> str:
    """Returns 'inventory', 'interfaces', 'cdp', or 'unknown'."""
    text = _clean_ansi(text)
    if re.search(r'admin show inventory', text, re.IGNORECASE):
        return 'admin_inventory'
    if re.search(r'show inventory', text, re.IGNORECASE) or re.search(r'PID:\s*\S+.*\nVID:.*\nSN:', text):
        return 'inventory'
    if re.search(r'show cdp neighbors', text, re.IGNORECASE) or 'Device ID:' in text:
        return 'cdp'
    if re.search(r'show interfaces description', text, re.IGNORECASE) or \
       re.search(r'^\S+\s+(up|down|admin\s+down)\s+(up|down)', text, re.MULTILINE | re.IGNORECASE):
        return 'interfaces'
    return 'unknown'
