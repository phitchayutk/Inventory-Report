"""
New Device / Off Device / Pivot logic
- Compare current vs previous month NT Overall (CHASSIS rows only)
- Key: CollectedSN
- New Device  = SN in current but NOT in previous
- Off Device  = SN in previous but NOT in current
- Pivot       = CHASSIS rows of current → Hostname, ProductID, SiteName, Site(prefix)
"""

from __future__ import annotations
import io
import re
from openpyxl import load_workbook


# ---------------------------------------------------------------------------
# Load NT Overall sheet from uploaded Excel (previous month report)
# ---------------------------------------------------------------------------

def load_nt_overall_from_excel(uploaded_file) -> list[dict]:
    """
    Read 'NT Overall' sheet from a previously exported report.
    Returns list of dicts (all rows, header from row 2).
    """
    data = uploaded_file.read() if hasattr(uploaded_file, 'read') else open(uploaded_file, 'rb').read()
    wb   = load_workbook(io.BytesIO(data), read_only=True, data_only=True)

    # Find NT Overall sheet (case-insensitive)
    sheet_name = next(
        (s for s in wb.sheetnames if 'overall' in s.lower() or 'nt overall' in s.lower()),
        wb.sheetnames[0]
    )
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 2:
        return []

    # Row 1 = title, Row 2 = headers
    headers = [str(c).strip() if c else f'col{i}' for i, c in enumerate(rows[1])]
    result  = []
    for row in rows[2:]:
        if not any(row):
            continue
        result.append(dict(zip(headers, row)))
    return result


def _chassis_rows(rows: list[dict]) -> list[dict]:
    """Filter to CHASSIS type rows only."""
    return [r for r in rows if str(r.get('Type', '')).upper() == 'CHASSIS']


# ---------------------------------------------------------------------------
# New Device / Off Device
# ---------------------------------------------------------------------------

def compute_new_off(
    current_rows:  list[dict],
    previous_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Compare CHASSIS rows by CollectedSN.
    Returns (new_device_rows, off_device_rows)
    Each row has keys matching NT Overall columns.
    """
    cur_chassis  = _chassis_rows(current_rows)
    prev_chassis = _chassis_rows(previous_rows)

    cur_sns  = {str(r.get('CollectedSN', '')).strip(): r for r in cur_chassis  if r.get('CollectedSN')}
    prev_sns = {str(r.get('CollectedSN', '')).strip(): r for r in prev_chassis if r.get('CollectedSN')}

    new_sns = set(cur_sns.keys())  - set(prev_sns.keys())
    off_sns = set(prev_sns.keys()) - set(cur_sns.keys())

    new_rows = [cur_sns[sn]  for sn in sorted(new_sns)]
    off_rows = [prev_sns[sn] for sn in sorted(off_sns)]

    return new_rows, off_rows


# ---------------------------------------------------------------------------
# Pivot
# ---------------------------------------------------------------------------

def _site_prefix(hostname: str) -> str:
    """Extract site prefix: first two underscore-segments, e.g. 'acr_acr'."""
    parts = hostname.lower().split('_')
    return '_'.join(parts[:2]) if len(parts) >= 2 else hostname.lower()


def compute_pivot(current_rows: list[dict]) -> list[dict]:
    """
    Build Pivot rows from CHASSIS records of current month.
    Columns: Hostname, ProductID, SiteName, Site
    Sorted by Hostname.
    """
    chassis = _chassis_rows(current_rows)
    pivot   = []
    for r in chassis:
        hn = str(r.get('Hostname', '')).strip()
        pivot.append({
            'Hostname':  hn,
            'ProductID': str(r.get('ProductID', '')).strip(),
            'SiteName':  str(r.get('Site Name', '')).strip(),
            'Site':      _site_prefix(hn),
        })
    return sorted(pivot, key=lambda x: x['Hostname'])
