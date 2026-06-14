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
    (r'Route Switch Processor|RSP880|RSP440',   'SUPERVISOR'),
    (r'Fan Tray|FAN',                            'FAN'),
    (r'Power Module|Power Supply|PEM|PWR',       'PWR'),
    (r'Chassis|chassis',                         'CHASSIS'),
    (r'100GBASE|CFP|QSFP.*100G',                 '100G Transceiver'),
    (r'40GBASE|QSFP.*40G',                       '40G Transceiver'),
    (r'10GBASE|XFP|SFP.*10G',                   '10G Transceiver'),
    (r'1000BASE|GLC|SFP-GE|SFP.*1G',            '1G Transceiver'),
    (r'Modular Linecard|Line Card|MPA|MOD',      'MODULE'),
]

def _classify_type(descr: str, pid: str) -> str:
    combined = (descr + ' ' + pid).upper()
    for pattern, label in _TYPE_RULES:
        if re.search(pattern.upper(), combined):
            return label
    return 'MODULE'


def _classify_platform(pid: str) -> str:
    p = pid.upper()
    if p.startswith('A9K') or p.startswith('ASR-9'):
        return 'ASR9000'
    if 'NCS-55' in p or 'NCS-5501' in p or 'NCS-5502' in p:
        return 'NCS-5K'
    if 'ASR-920' in p or 'ASR920' in p:
        return 'ASR920'
    return ''


# ---------------------------------------------------------------------------
# Parser 1: show inventory / admin show inventory (IOS XR)
# ---------------------------------------------------------------------------

def parse_show_inventory(text: str, is_admin: bool = False) -> list[dict]:
    """
    Parse output of `show inventory` or `admin show inventory`.
    Returns list of dicts with keys: Hostname, Type, ProductID, CollectedSN, Platform, _is_admin
    """
    text = _clean_ansi(text)
    hostname = _extract_hostname(text)
    records = []

    # Valid PID: alphanumeric + dash/dot/slash/plus, min 3 chars
    _PID_VALID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9\-\.\/\+]{2,}$')

    block_re = re.compile(
        # NAME: "..." , DESCR: "..."  — on ONE line (standard IOS XR format)
        r'NAME:\s*"([^"]*)"[^"\n]*DESCR:\s*"([^"]*)"\s*\n'
        # PID: xxx , VID: xxx , SN: xxx  — all on ONE line
        r'PID:\s*([^,\n]+?)\s*,\s*VID:[^,\n]*,\s*SN:\s*(\S*)',
    )

    for m in block_re.finditer(text):
        name  = m.group(1).strip()
        descr = (m.group(2) or '').strip()
        pid   = m.group(3).strip()
        sn    = m.group(4).strip()

        if pid in ('N/A', '', 'MISSING', 'n/a'):
            continue
        # Skip garbled PIDs (contain ^, $, ], or other non-alphanumeric-dash chars)
        if not _PID_VALID.match(pid):
            continue

        records.append({
            'Hostname':    hostname,
            'Type':        _classify_type(descr, pid),
            'ProductID':   pid,
            'CollectedSN': sn,
            'Platform':    _classify_platform(pid),
            '_is_admin':   is_admin,
        })

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
