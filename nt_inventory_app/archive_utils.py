"""
Archive extraction utility — Streamlit Cloud compatible
Supports: .zip, .7z  (no .rar — unrar binary unavailable on Streamlit Cloud)
Memory-efficient: yields (filename, content) one at a time
"""

import zipfile
import io
import tempfile
import os
from pathlib import Path


def _is_log_file(name: str) -> bool:
    name = name.lower()
    return (
        name.endswith(('.log', '.txt'))
        and not name.startswith('__macosx')
        and '/.DS_Store' not in name
    )


def _decode(data: bytes) -> str:
    for enc in ('utf-8', 'cp874', 'latin-1'):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode('utf-8', errors='replace')


def extract_logs(uploaded_file) -> list[tuple[str, str]]:
    """
    Extract all .log/.txt files from uploaded archive.
    Returns list of (filename, text_content).
    uploaded_file: Streamlit UploadedFile object
    """
    name = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith('.zip'):
        return list(_from_zip(data))
    elif name.endswith('.7z'):
        return list(_from_7z(data))
    else:
        raise ValueError(f"ไม่รองรับ format: {uploaded_file.name} (รองรับเฉพาะ .zip และ .7z)")


def _from_zip(data: bytes) -> list[tuple[str, str]]:
    results = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        entries = [i for i in zf.infolist() if _is_log_file(i.filename)]
        for info in entries:
            try:
                content = _decode(zf.read(info.filename))
                results.append((Path(info.filename).name, content))
            except Exception:
                continue
    return results


def _from_7z(data: bytes) -> list[tuple[str, str]]:
    import py7zr
    results = []
    with tempfile.NamedTemporaryFile(suffix='.7z', delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        with py7zr.SevenZipFile(tmp_path, mode='r') as sz:
            all_names = sz.getnames()
            log_names = [n for n in all_names if _is_log_file(n)]
            if not log_names:
                return []
            extracted = sz.read(targets=log_names)
            for name, bio in extracted.items():
                try:
                    content = _decode(bio.read())
                    results.append((Path(name).name, content))
                except Exception:
                    continue
    finally:
        os.unlink(tmp_path)
    return results


def count_logs_in_archive(uploaded_file) -> int:
    """Quick count without full extraction — for progress display."""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)  # reset for later read

    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return sum(1 for i in zf.infolist() if _is_log_file(i.filename))
    elif name.endswith('.7z'):
        import py7zr
        with tempfile.NamedTemporaryFile(suffix='.7z', delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            with py7zr.SevenZipFile(tmp_path, mode='r') as sz:
                return sum(1 for n in sz.getnames() if _is_log_file(n))
        finally:
            os.unlink(tmp_path)
    return 0
