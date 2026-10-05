"""
Minecraft Dungeons II - Process Memory Manager & Win32 I/O Layer
Target: Dungeons-WinGDK-Shipping.exe (Singleplayer / Offline)
The target process is chosen by the user (list_processes() + MemoryManager.attach(pid)).
"""

import ctypes
import math
import ntpath
import struct
from ctypes import wintypes

from trainer_offsets import (
    CHAINS,
    ENGINE_OFFSET,
    FNAMES_BLOCKS_OFFSET,
    RARITY_INDICES,
)

k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

# Process Memory Access Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_ACCESS = (
    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
)

# Win32 API Function Signatures
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE

k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.CloseHandle.restype = wintypes.BOOL

k32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
k32.QueryFullProcessImageNameW.restype = wintypes.BOOL

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
    """An operation cannot be completed against the game process."""


def finite_float(value):
    """Validate that value is a finite number representable in 32-bit float range."""
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


def list_processes():
    """Return [(pid, exe_name)] for every process this user can query, sorted by name."""
    bytes_needed = wintypes.DWORD()
    capacity = 2048
    while True:
        pids = (wintypes.DWORD * capacity)()
        if not k32.K32EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(bytes_needed)):
            raise MemoryAccessError(
                f"Cannot list processes (Windows error {ctypes.GetLastError()})."
            )
        if bytes_needed.value < ctypes.sizeof(pids):
            break
        capacity *= 2
    process_count = bytes_needed.value // ctypes.sizeof(wintypes.DWORD)

    found = []
    for i in range(process_count):
        pid = pids[i]
        if pid == 0:
            continue
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            continue
        try:
            size = wintypes.DWORD(32768)
            path = ctypes.create_unicode_buffer(size.value)
            if k32.QueryFullProcessImageNameW(h, 0, path, ctypes.byref(size)):
                found.append((pid, ntpath.basename(path.value)))
        finally:
            k32.CloseHandle(h)
    found.sort(key=lambda item: (item[1].lower(), item[0]))
    return found


class MemoryManager:
    """Manages process attachment, memory reads/writes, pointer chains, and game structures."""

    NOT_ATTACHED = "Not attached. Select a process and click Attach."

    def __init__(self):
        self.pid = None
        self.base_addr = None
        self.h_proc = None
        self.blocks_addr = None
        self.last_error = self.NOT_ATTACHED

    def close(self):
        if self.h_proc:
            k32.CloseHandle(self.h_proc)
            self.h_proc = None
        self.pid = None
        self.base_addr = None
        self.blocks_addr = None

    def detach(self):
        self.close()
        self.last_error = self.NOT_ATTACHED

    def is_alive(self):
        if not self.h_proc:
            return False
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(self.h_proc, ctypes.byref(code)) or code.value != 259:
            self.close()
            self.last_error = "Process exited or connection lost. Select a process to re-attach."
            return False
        return True

    def attach(self, pid):
        """Attach to the process with the given PID (chosen by the user)."""
        self.close()
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            self.last_error = "Invalid process ID."
            return False

        h = k32.OpenProcess(PROCESS_ACCESS, False, pid)
        if not h:
            self.last_error = (
                f"Cannot open process {pid}: access denied or it exited "
                f"(Windows error {ctypes.GetLastError()}). Try running as administrator."
            )
            return False

        mods = (wintypes.HMODULE * 1)()
        cb = wintypes.DWORD()
        if not psapi.EnumProcessModulesEx(h, mods, ctypes.sizeof(mods), ctypes.byref(cb), 3):
            self.last_error = (
                f"Cannot read modules of process {pid} (Windows error {ctypes.GetLastError()})."
            )
            k32.CloseHandle(h)
            return False

        self.h_proc = h
        self.pid = pid
        self.base_addr = mods[0]
        self.blocks_addr = self.base_addr + FNAMES_BLOCKS_OFFSET
        self.last_error = ""
        return True

    def read_memory(self, address, size):
        if not self.h_proc or not address:
            return None
        buf = ctypes.create_string_buffer(size)
        transferred = ctypes.c_size_t()
        if (
            k32.ReadProcessMemory(
                self.h_proc, ctypes.c_void_p(address), buf, size, ctypes.byref(transferred)
            )
            and transferred.value == size
        ):
            return buf.raw
        return None

    def write_memory(self, address, data):
        if not self.h_proc or not address:
            return False
        bytes_written = ctypes.c_size_t()
        return bool(
            k32.WriteProcessMemory(
                self.h_proc, ctypes.c_void_p(address), data, len(data), ctypes.byref(bytes_written)
            )
            and bytes_written.value == len(data)
        )

    def resolve_chain(self, offsets_list):
        if not self.h_proc or not self.base_addr:
            return None
        curr_addr = self.base_addr + ENGINE_OFFSET
        buf8 = ctypes.create_string_buffer(8)
        transferred = ctypes.c_size_t()
        for off_str in reversed(offsets_list):
            off = int(off_str, 16)
            res = k32.ReadProcessMemory(
                self.h_proc, ctypes.c_void_p(curr_addr), buf8, 8, ctypes.byref(transferred)
            )
            if not res or transferred.value != 8:
                return None
            ptr = struct.unpack("<Q", buf8.raw)[0]
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
            val = struct.unpack("<f", data)[0]
            return val if math.isfinite(val) else None
        return None

    def require_float(self, key):
        val = self.read_float(key)
        if val is None:
            raise MemoryAccessError(f"Cannot read {key}.")
        return val

    def write_float(self, key, val):
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            return False
        buf4 = struct.pack("<f", finite_float(val))
        return self.write_memory(addr, buf4)

    def read_byte(self, key):
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            return None
        data = self.read_memory(addr, 1)
        if data is not None:
            return data[0]
        return None

    def write_byte(self, key, val):
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            return False
        val_int = int(val)
        if not 0 <= val_int <= 255:
            raise ValueError("Enter a whole number between 0 and 255.")
        buf1 = struct.pack("<B", val_int)
        return self.write_memory(addr, buf1)

    # Raw Memory Primitives
    def read_ptr(self, addr):
        data = self.read_memory(addr, 8)
        if data is not None:
            return struct.unpack("<Q", data)[0]
        return 0

    def write_ptr(self, addr, val):
        return self.write_memory(addr, struct.pack("<Q", int(val)))

    def read_u32(self, addr):
        data = self.read_memory(addr, 4)
        if data is not None:
            return struct.unpack("<I", data)[0]
        return 0

    def write_u32(self, addr, val):
        return self.write_memory(addr, struct.pack("<I", int(val)))

    def read_f32(self, addr):
        data = self.read_memory(addr, 4)
        if data is not None:
            val = struct.unpack("<f", data)[0]
            return val if math.isfinite(val) else 0.0
        return 0.0

    def write_f32(self, addr, val):
        return self.write_memory(addr, struct.pack("<f", finite_float(val)))

    # FName Resolver
    def get_fname(self, comp_idx):
        if not self.h_proc or not self.blocks_addr or not comp_idx:
            return ""
        block_idx = comp_idx >> 16
        offset = comp_idx & 0xFFFF
        buf8 = self.read_memory(self.blocks_addr + block_idx * 8, 8)
        if not buf8:
            return ""
        bptr = struct.unpack("<Q", buf8)[0]
        if not bptr:
            return ""
        ebuf = self.read_memory(bptr + offset * 2, 256)
        if not ebuf:
            return ""
        hdr = struct.unpack("<H", ebuf[:2])[0]
        length = min(hdr >> 6, 250)
        return ebuf[2 : 2 + length].decode("ascii", errors="ignore")

    # Inventory & Gear Operations
    def get_equipped_gear(self):
        pawn_addr = self.resolve_chain(["2F8", "30", "0", "38", "1248"])
        if not pawn_addr:
            return []
        pawn = self.read_ptr(pawn_addr)
        if not pawn:
            return []
        inv_comp = self.read_ptr(pawn + 0xDA0)
        if not inv_comp:
            return []
        slots_data = self.read_ptr(inv_comp + 0x158 + 0x108)
        slots_count = self.read_u32(inv_comp + 0x158 + 0x110)
        if not slots_data or slots_count == 0:
            return []

        equipped = []
        for s in range(slots_count):
            slot_addr = slots_data + s * 0x50
            stag = self.get_fname(self.read_u32(slot_addr + 0xC))
            if "Equipment" in stag:
                cnt = self.read_u32(slot_addr + 0x48)
                idata = self.read_ptr(slot_addr + 0x40)
                lbl = stag.replace("SW.ItemSlot.Equipment.", "")
                if cnt > 0 and idata:
                    itag = self.get_fname(self.read_u32(idata + 0x0)).replace("SW.Item.", "")
                    rtag = self.get_fname(self.read_u32(idata + 0x14)).replace("SW.Rarity.", "")
                    pwr = self.read_f32(idata + 0x60)
                    pwr_orig = self.read_f32(idata + 0x5C)
                    lvl = self.read_u32(idata + 0x68)
                    xp = self.read_f32(idata + 0x6C)
                    equipped.append(
                        {
                            "slot_idx": s,
                            "slot_tag": stag,
                            "label": lbl,
                            "item_addr": idata,
                            "name": itag,
                            "power": pwr,
                            "power_orig": pwr_orig,
                            "rarity": rtag if rtag else "None",
                            "level": lvl,
                            "xp": xp,
                            "is_talisman": "talisman" in lbl.lower(),
                        }
                    )
        return equipped

    def set_gear_power(self, item_addr, slot_tag, power_val):
        power_val = finite_float(power_val)
        self.write_f32(item_addr + 0x5C, power_val)
        self.write_f32(item_addr + 0x60, power_val)
        if "MeleeWeapon" in slot_tag:
            self.write_float("power_melee_base", power_val)
            self.write_float("power_melee_cur", power_val)
        elif "RangedWeapon" in slot_tag:
            self.write_float("power_ranged_base", power_val)
            self.write_float("power_ranged_cur", power_val)
        elif "Armor" in slot_tag:
            self.write_float("power_armor_base", power_val)
            self.write_float("power_armor_cur", power_val)
        elif "Artifact.Slot1" in slot_tag:
            self.write_float("power_artifact0_base", power_val)
            self.write_float("power_artifact0_cur", power_val)
        elif "Artifact.Slot2" in slot_tag:
            self.write_float("power_artifact1_base", power_val)
            self.write_float("power_artifact1_cur", power_val)
        elif "Artifact.Slot3" in slot_tag:
            self.write_float("power_artifact2_base", power_val)
            self.write_float("power_artifact2_cur", power_val)
        return True

    def set_gear_rarity(self, item_addr, rarity_name):
        idx = RARITY_INDICES.get(rarity_name)
        if idx:
            return self.write_u32(item_addr + 0x14, idx)
        return False

    def set_talisman_level_xp(self, item_addr, level, xp):
        self.write_u32(item_addr + 0x68, int(level))
        self.write_f32(item_addr + 0x6C, finite_float(xp))
        return True

    def max_out_talismans(self, only_equipped=True):
        items = self.get_equipped_gear()
        count = 0
        for it in items:
            if it["is_talisman"]:
                addr = it["item_addr"]
                self.write_u32(addr + 0x68, 2)
                self.write_f32(addr + 0x6C, 100000.0)
                count += 1
        if not only_equipped:
            pawn_addr = self.resolve_chain(["2F8", "30", "0", "38", "1248"])
            if pawn_addr:
                pawn = self.read_ptr(pawn_addr)
                if pawn:
                    inv_comp = self.read_ptr(pawn + 0xDA0)
                    if inv_comp:
                        slots_data = self.read_ptr(inv_comp + 0x158 + 0x108)
                        slots_count = self.read_u32(inv_comp + 0x158 + 0x110)
                        if slots_data and slots_count > 7:
                            slot7 = slots_data + 7 * 0x50
                            cnt = self.read_u32(slot7 + 0x48)
                            idata = self.read_ptr(slot7 + 0x40)
                            inv_entry_size = 0xD8
                            for i in range(cnt):
                                t_addr = idata + i * inv_entry_size
                                self.write_u32(t_addr + 0x68, 2)
                                self.write_f32(t_addr + 0x6C, 100000.0)
                                count += 1
        return count

    def session_kind(self):
        if not self.h_proc or not self.is_alive():
            return "disconnected"
        if self.read_float("health_current") is None:
            return "loading"
        role = self.read_byte("player_role")
        return classify_session_role(role)
