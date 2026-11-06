# -*- coding: utf-8 -*-
"""Delete files through the Windows recycle bin only.

There is deliberately no permanent-delete primitive. ``press_key`` also rejects
Shift+Delete, which is the shell shortcut that bypasses the recycle bin.
"""
from __future__ import annotations

import ctypes
from pathlib import Path

FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_SILENT = 0x0004
FOF_NOERRORUI = 0x0400
FO_DELETE = 0x0003


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("wFunc", ctypes.c_uint),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", ctypes.c_bool),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p),
    ]


def recycle(paths: list[str]) -> list[str]:
    """Move existing paths to the recycle bin; return the paths that were sent."""
    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"path does not exist: {raw}")
        resolved.append(path.resolve())
    if not resolved:
        raise ValueError("paths is empty")

    source = "\0".join(str(path) for path in resolved) + "\0\0"
    operation = SHFILEOPSTRUCTW()
    operation.wFunc = FO_DELETE
    operation.pFrom = source
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0:
        raise OSError(f"SHFileOperationW failed with code {result}")
    if operation.fAnyOperationsAborted:
        raise OSError("recycle operation was aborted")
    return [str(path) for path in resolved]
