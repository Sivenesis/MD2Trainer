"""Validated Win32 process access and character session detection."""

import ctypes
import math
import struct
import sys
from ctypes import wintypes

from trainer_offsets import CHAINS, ENGINE_OFFSET

if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
    raise SystemExit("This trainer requires Windows and 64-bit Python 3.10+.")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

# ctypes defaults to C int: handles and pointers must be declared explicitly.
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.CloseHandle.restype = wintypes.BOOL
k32.K32EnumProcesses.argtypes = [
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
k32.K32EnumProcesses.restype = wintypes.BOOL
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.GetExitCodeProcess.restype = wintypes.BOOL
for api in (k32.ReadProcessMemory, k32.WriteProcessMemory):
    api.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    api.restype = wintypes.BOOL
psapi.EnumProcessModulesEx.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.HMODULE),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
]
psapi.EnumProcessModulesEx.restype = wintypes.BOOL
psapi.GetModuleBaseNameA.argtypes = [
    wintypes.HANDLE,
    wintypes.HMODULE,
    ctypes.POINTER(ctypes.c_char),
    wintypes.DWORD,
]
psapi.GetModuleBaseNameA.restype = wintypes.DWORD


class MemoryAccessError(RuntimeError):
    """An operation cannot be completed against the current game process."""


def finite_float(value):
    value = float(value)
    if not math.isfinite(value) or abs(value) > 3.4028234663852886e38:
        raise ValueError("Enter a finite number within the 32-bit float range.")
    return value


def classify_session_role(role):
    if role == 3:
        return "local"
    if role in (1, 2):
        return "client"
    return "unknown"


# Process Memory Access Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_ACCESS = (
    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
)


class MemoryManager:
    """Own one process handle; failed or partial operations never count as success."""

    def __init__(self):
        self.pid = None
        self.base_addr = None
        self.h_proc = None
        self.last_error = "Game not found. Launch the game and load a character."

    def close(self):
        if self.h_proc:
            k32.CloseHandle(self.h_proc)
            self.h_proc = None
        self.pid = None
        self.base_addr = None

    def is_alive(self):
        if not self.h_proc:
            return False
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(self.h_proc, ctypes.byref(code)) or code.value != 259:
            self.close()
            self.last_error = "Game closed or connection lost. Waiting to reconnect..."
            return False
        return True

    def attach(self):
        self.close()
        self.last_error = "Game not found. Launch the game and load a character."
        bytes_needed = wintypes.DWORD()
        capacity = 2048
        while True:
            pids = (wintypes.DWORD * capacity)()
            if not k32.K32EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(bytes_needed)):
                self.last_error = (
                    f"Cannot list processes (Windows error {ctypes.get_last_error()})."
                )
                return False
            if bytes_needed.value < ctypes.sizeof(pids):
                break
            capacity *= 2
        process_count = bytes_needed.value // ctypes.sizeof(wintypes.DWORD)

        for i in range(process_count):
            pid = pids[i]
            if pid == 0:
                continue
            handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not handle:
                continue
            try:
                modules = (wintypes.HMODULE * 1)()
                module_bytes = wintypes.DWORD()
                if not psapi.EnumProcessModulesEx(
                    handle, modules, ctypes.sizeof(modules), ctypes.byref(module_bytes), 3
                ):
                    continue
                module_name = ctypes.create_string_buffer(260)
                if not psapi.GetModuleBaseNameA(handle, modules[0], module_name, len(module_name)):
                    continue
                if module_name.value.lower() == b"dungeons-wingdk-shipping.exe":
                    self.pid = pid
                    self.base_addr = modules[0]
                    break
            finally:
                k32.CloseHandle(handle)

        if not self.pid:
            return False

        self.h_proc = k32.OpenProcess(PROCESS_ACCESS, False, self.pid)
        if not self.h_proc:
            self.last_error = (
                f"Game found, but memory access denied (Windows error {ctypes.get_last_error()})."
            )
            self.close()
            return False
        return True

    def read_memory(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        transferred = ctypes.c_size_t()
        if (
            self.h_proc
            and k32.ReadProcessMemory(
                self.h_proc, ctypes.c_void_p(address), buffer, size, ctypes.byref(transferred)
            )
            and transferred.value == size
        ):
            return buffer.raw
        return None

    def resolve_chain(self, offsets_list):
        if not self.h_proc or not self.base_addr:
            return None
        curr_addr = self.base_addr + ENGINE_OFFSET
        for off_str in reversed(offsets_list):
            off = int(off_str, 16)
            data = self.read_memory(curr_addr, 8)
            if data is None:
                return None
            ptr = struct.unpack("<Q", data)[0]
            if not ptr or ptr < 0x10000:
                return None
            curr_addr = ptr + off
        return curr_addr

    def read_float(self, key):
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            return None
        data = self.read_memory(addr, 4)
        if data is not None:
            value = struct.unpack("<f", data)[0]
            return value if math.isfinite(value) else None
        return None

    def require_float(self, key):
        value = self.read_float(key)
        if value is None:
            raise MemoryAccessError(
                f"Cannot read {key}. Load a character and check game compatibility."
            )
        return value

    def write_float(self, key, val):
        return self.write_value(key, struct.pack("<f", finite_float(val)))

    def read_byte(self, key):
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            return None
        data = self.read_memory(addr, 1)
        if data is not None:
            return data[0]
        return None

    def write_byte(self, key, val):
        if int(val) != val or not 0 <= val <= 255:
            raise ValueError("Enter a whole number between 0 and 255.")
        return self.write_value(key, struct.pack("<B", int(val)))

    def write_value(self, key, data):
        error = self.session_write_error()
        if error:
            raise MemoryAccessError(error)
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            raise MemoryAccessError(
                f"Cannot resolve {key}. Load a character and check game compatibility."
            )
        bytes_written = ctypes.c_size_t()
        if not k32.WriteProcessMemory(
            self.h_proc, ctypes.c_void_p(addr), data, len(data), ctypes.byref(bytes_written)
        ) or bytes_written.value != len(data):
            raise MemoryAccessError(
                f"Cannot write {key} (Windows error {ctypes.get_last_error()}). "
                "The operation may have been partially applied."
            )
        return True

    def session_write_error(self):
        role = self.read_byte("player_role")
        if role in (1, 2, 3):  # A network role alone does not determine which effects work.
            return None
        return "Read-only: character authority is unavailable. Load a character and check game compatibility."

    def session_kind(self):
        if not self.h_proc:
            return "disconnected"
        if self.read_float("health_current") is None:
            return "loading"
        return classify_session_role(self.read_byte("player_role"))
