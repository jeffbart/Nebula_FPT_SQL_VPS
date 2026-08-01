"""Liberação progressiva de espaço do staging no Windows."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


FSCTL_SET_SPARSE = 0x000900C4
FSCTL_SET_ZERO_DATA = 0x000980C8
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080


class FileZeroDataInformation(ctypes.Structure):
    _fields_ = [
        ("file_offset", ctypes.c_longlong),
        ("beyond_final_zero", ctypes.c_longlong),
    ]


def release_uploaded_range(path: Path, offset: int, length: int) -> bool:
    """Desaloca um trecho confirmado sem mudar o tamanho lógico do arquivo.

    Retorna ``False`` quando o sistema de arquivos não oferece a operação. O
    chamador deve continuar normalmente e apagar o arquivo inteiro ao final.
    """
    if os.name != "nt" or offset < 0 or length <= 0:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.CreateFileW(
        str(path),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle == invalid_handle:
        return False

    returned = wintypes.DWORD()
    try:
        if not kernel32.DeviceIoControl(
            handle,
            FSCTL_SET_SPARSE,
            None,
            0,
            None,
            0,
            ctypes.byref(returned),
            None,
        ):
            return False

        zero_range = FileZeroDataInformation(offset, offset + length)
        return bool(
            kernel32.DeviceIoControl(
                handle,
                FSCTL_SET_ZERO_DATA,
                ctypes.byref(zero_range),
                ctypes.sizeof(zero_range),
                None,
                0,
                ctypes.byref(returned),
                None,
            )
        )
    finally:
        kernel32.CloseHandle(handle)


__all__ = ["release_uploaded_range"]
