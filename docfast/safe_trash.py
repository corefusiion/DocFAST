"""Safe Recycle Bin / Trash support and conditional compression for DocFAST.
Uses standard Windows SHFileOperationW with FOF_ALLOWUNDO so files can be restored with Ctrl+Z,
without triggering antivirus heuristics.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys

IS_WIN = sys.platform == "win32"


def move_to_trash(file_path: str | Path) -> bool:
    """Moves a file safely to the OS Recycle Bin / Trash.
    Returns True on success, False otherwise.
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return False

    if IS_WIN:
        try:
            # SHFILEOPSTRUCTW with FO_DELETE (3) and FOF_ALLOWUNDO (0x0040)
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p),
                ]

            # Double null-terminated string required by SHFileOperation
            p_from = str(p) + "\0\0"
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            flags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

            op = SHFILEOPSTRUCTW()
            op.wFunc = FO_DELETE
            op.pFrom = p_from
            op.fFlags = flags

            ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            return ret == 0
        except Exception:
            return False

    # Linux / macOS fallback
    try:
        home = Path.home()
        trash_dir = home / ".Trash" if sys.platform == "darwin" else home / ".local" / "share" / "Trash" / "files"
        trash_dir.mkdir(parents=True, exist_ok=True)
        dest = trash_dir / p.name
        counter = 1
        while dest.exists():
            dest = trash_dir / f"{p.stem}_{counter}{p.suffix}"
            counter += 1
        p.rename(dest)
        return True
    except Exception:
        return False


def verify_only_if_smaller(original_path: str | Path, output_paths: list[Path]) -> list[Path]:
    """If 'only_if_smaller' is active and output is larger than original,
    discards output and keeps original.
    """
    orig = Path(original_path)
    if not orig.exists() or not output_paths:
        return output_paths

    orig_size = orig.stat().st_size
    valid_outputs: list[Path] = []
    for out in output_paths:
        if out.exists():
            if out.stat().st_size <= orig_size:
                valid_outputs.append(out)
            else:
                # Discard larger file
                try:
                    out.unlink()
                except Exception:
                    pass
    return valid_outputs if valid_outputs else [orig]
