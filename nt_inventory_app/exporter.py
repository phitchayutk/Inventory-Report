"""
NT Inventory Excel Exporter
Generates NT_Inventory_Report.xlsx with sheets:
  NT Overall  — Hardware inventory rows
  Port Status — Per-device port count summary
  WAN Link    — CDP neighbor topology
"""

from __future__ import annotations
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

FONT_NAME  = 'Tahoma'
HDR_FILL   = PatternFill('solid', fgColor='4472C4')
HDR_FONT   = Font(name=FONT_NAME, bold=True, color='FFFFFF', size=10)
TITLE_FONT = Font(name=FONT_NAME, bold=True, size=10)
DATA_FONT  = Font(name=FONT_NAME, size=10)
WRAP_ALIGN = Alignment(wrap_text=True, vertical='center', horizontal='center')
LEFT_ALIGN = Alignment(vertical='center', horizontal='left')
CTR_ALIGN  = Alignment(vertical='center', horizontal='center')
_THIN      = Side(style='thin')
BORDER     = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

SPEED_FILLS = {
    '100G': PatternFill('solid', fgColor='C00000'),
    '40G':  PatternFill('solid', fgColor='FF6600'),
    '10G':  PatternFill('solid', fgColor='0070C0'),
    '1G':   PatternFill('solid', fgColor='00B050'),
}


def _hdr(cell, value, fill=HDR_FILL):
    cell.value     = value
    cell.font      = HDR_FONT
    cell.fill      = fill
    cell.alignment = WRAP_ALIGN
    cell.border    = BORDER


def _data(cell, value, align=LEFT_ALIGN):
    cell.value     = value
    cell.font      = DATA_FONT
    cell.alignment = align
    cell.border    = BORDER


def _title(ws, value: str, ncols: int):
    ws['A1'] = value
    ws['A1'].font      = TITLE_FONT
    ws['A1'].alignment = LEFT_ALIGN
    if ncols > 1:
        ws.merge_cells(f'A1:{get_column_letter(ncols)}1')
    ws.row_dimensions[1].height = 20


# ---------------------------------------------------------------------------
# NT Overall
# ---------------------------------------------------------------------------

NT_COLS = [
    ('Network',        12),
    ('Hostname',       22),
    ('IP Address',     18),
    ('Platform',       12),
    ('Type',           20),
    ('ProductID',      28),
    ('CollectedSN',    20),
    ('Site Name',      22),
    ('Zone',           10),
    ('SW Version',     14),
    ('EOS',            20),
    ('LDOS',           20),
    ('LDOS_Planning',  24),
]


def _write_nt_overall(ws, rows: list[dict], report_date: str):
    _title(ws, f'NT Inventory Report (ข้อมูล ณ วันที่ {report_date})', len(NT_COLS))

    for ci, (hdr, w) in enumerate(NT_COLS, 1):
        _hdr(ws.cell(row=2, column=ci), hdr)
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[2].height = 16

    for ri, row in enumerate(rows, 3):
        ws.row_dimensions[ri].height = 15
        vals = [
            row.get('Network',       'MPLS LPE'),
            row.get('Hostname',      ''),
            row.get('IP Address',    ''),
            row.get('Platform',      ''),
            row.get('Type',          ''),
            row.get('ProductID',     ''),
            row.get('CollectedSN',   ''),
            row.get('Site Name',     ''),
            row.get('Zone',          ''),
            row.get('SW Version',    ''),
            row.get('EOS',           'No Announcement'),
            row.get('LDOS',          'No Announcement'),
            row.get('LDOS_Planning', 'No Announcement'),
        ]
        for ci, v in enumerate(vals, 1):
            _data(ws.cell(row=ri, column=ci), v)

    ws.freeze_panes = 'A3'
    if len(rows) > 0:
        ws.auto_filter.ref = f'A2:{get_column_letter(len(NT_COLS))}{len(rows)+2}'


# ---------------------------------------------------------------------------
# Port Status
# ---------------------------------------------------------------------------

PS_COLS = [
    ('Zone', 8), ('Network', 12), ('Hostname', 24), ('Site Name', 20),
    ('100G\nDown', 8), ('100G\nUp', 8), ('100G\nAdmin\nDown', 10), ('100G\nTotal', 8),
    ('10G\nDown', 8),  ('10G\nUp', 8),  ('10G\nAdmin\nDown', 10),  ('10G\nTotal', 8),
    ('1G\nDown', 8),   ('1G\nUp', 8),   ('1G\nAdmin\nDown', 10),   ('1G\nTotal', 8),
    ('40G\nDown', 8),  ('40G\nUp', 8),  ('40G\nAdmin\nDown', 10),  ('40G\nTotal', 8),
]


def _write_port_status(ws, rows: list[dict], report_date: str):
    _title(ws, f'NT Port Status Report ( ข้อมูล ณ วันที่ {report_date})', len(PS_COLS))

    for ci, (hdr, w) in enumerate(PS_COLS, 1):
        speed = next((s for s in ['100G', '40G', '10G', '1G'] if s in hdr), None)
        fill  = SPEED_FILLS.get(speed, HDR_FILL)
        _hdr(ws.cell(row=2, column=ci), hdr, fill=fill)
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[2].height = 36

    speeds = ['100G', '10G', '1G', '40G']

    for ri, row in enumerate(rows, 3):
        ws.row_dimensions[ri].height = 15
        pc   = row.get('port_counts', {})
        vals = [
            row.get('Zone', ''),
            row.get('Network', 'MPLS LPE'),
            row.get('Hostname', ''),
            row.get('Site Name', ''),
        ]
        for speed in speeds:
            band = pc.get(speed, {})
            dn   = band.get('Down', 0)
            up   = band.get('Up', 0)
            adm  = band.get('Admin Down', 0)
            vals += [dn, up, adm, dn + up + adm]

        for ci, v in enumerate(vals, 1):
            _data(ws.cell(row=ri, column=ci), v, align=CTR_ALIGN if ci > 4 else LEFT_ALIGN)

    ws.freeze_panes = 'A3'
    if len(rows) > 0:
        ws.auto_filter.ref = f'A2:{get_column_letter(len(PS_COLS))}{len(rows)+2}'


# ---------------------------------------------------------------------------
# WAN Link
# ---------------------------------------------------------------------------

WAN_COLS = [
    ('Source Hostname',       24),
    ('Source Interface',      32),
    ('Destination Hostname',  24),
    ('Destination Interface', 32),
]


def _write_wan_link(ws, rows: list[dict], report_date: str):
    _title(ws, f'NT WAN Link ( ข้อมูล ณ วันที่ {report_date})', len(WAN_COLS))

    for ci, (hdr, w) in enumerate(WAN_COLS, 1):
        _hdr(ws.cell(row=2, column=ci), hdr)
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[2].height = 16

    for ri, row in enumerate(rows, 3):
        ws.row_dimensions[ri].height = 15
        vals = [
            row.get('Source Hostname',       ''),
            row.get('Source Interface',      ''),
            row.get('Destination Hostname',  ''),
            row.get('Destination Interface', ''),
        ]
        for ci, v in enumerate(vals, 1):
            _data(ws.cell(row=ri, column=ci), v)

    ws.freeze_panes = 'A3'
    if len(rows) > 0:
        ws.auto_filter.ref = f'A2:{get_column_letter(len(WAN_COLS))}{len(rows)+2}'


# ---------------------------------------------------------------------------
# Main export — returns bytes for st.download_button
# ---------------------------------------------------------------------------

def export_to_bytes(
    inventory_rows:   list[dict],
    port_status_rows: list[dict],
    wan_link_rows:    list[dict],
    report_date:      str | None = None,
) -> bytes:
    if not report_date:
        report_date = datetime.now().strftime('%d-%m-%Y')

    wb = Workbook()

    ws1 = wb.active
    ws1.title = 'NT Overall'
    _write_nt_overall(ws1, inventory_rows, report_date)

    ws2 = wb.create_sheet('Port Status')
    _write_port_status(ws2, port_status_rows, report_date)

    ws3 = wb.create_sheet('WAN Link')
    _write_wan_link(ws3, wan_link_rows, report_date)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
