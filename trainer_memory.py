"""
Minecraft Dungeons II - Process Memory Manager & Win32 I/O Layer
Target: Dungeons-WinGDK-Shipping.exe (Singleplayer / Offline)
"""

import ctypes
import math
import struct
import sys
from ctypes import wintypes

from trainer_offsets import (
    CHAINS,
    ENGINE_OFFSET,
    FNAMES_BLOCKS_OFFSET,
    RARITY_INDICES,
)

if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
    raise SystemExit("This trainer requires Windows and 64-bit Python 3.10+.")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE

# Process Memory Access Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_ACCESS = (
    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
)

# Win32 API Function Signatures
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


class MemoryManager:
    """Manages process attachment, memory reads/writes, pointer chains, and game structures."""

    def __init__(self):
        self.pid = None
        self.base_addr = None
        self.h_proc = None
        self.blocks_addr = None
        self.last_error = "Game not found. Waiting for Dungeons-WinGDK-Shipping.exe..."

    def close(self):
        if self.h_proc:
            k32.CloseHandle(self.h_proc)
            self.h_proc = None
        self.pid = None
        self.base_addr = None
        self.blocks_addr = None

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
        self.last_error = "Game not found. Waiting for Dungeons-WinGDK-Shipping.exe..."
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
            h = k32.OpenProcess(0x0410, False, pid)
            if not h:
                continue
            try:
                mods = (wintypes.HMODULE * 1)()
                cb = wintypes.DWORD()
                if psapi.EnumProcessModulesEx(h, mods, ctypes.sizeof(mods), ctypes.byref(cb), 3):
                    mod_name = (ctypes.c_char * 260)()
                    psapi.GetModuleBaseNameA(h, mods[0], mod_name, 260)
                    if (
                        mod_name.value.decode(errors="ignore").lower()
                        == "dungeons-wingdk-shipping.exe"
                    ):
                        self.pid = pid
                        self.base_addr = mods[0]
                        break
            finally:
                k32.CloseHandle(h)

        if not self.pid:
            return False

        self.h_proc = k32.OpenProcess(PROCESS_ACCESS, False, self.pid)
        if self.h_proc:
            self.blocks_addr = self.base_addr + FNAMES_BLOCKS_OFFSET
            return True
        else:
            self.last_error = (
                f"Process found, but access denied (Windows error {ctypes.get_last_error()})."
            )
            self.close()
            return False

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
            raise MemoryAccessError("No writable process/address. Load a character first.")
        written = ctypes.c_size_t()
        if not k32.WriteProcessMemory(
            self.h_proc, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        ) or written.value != len(data):
            raise MemoryAccessError(
                f"Write failed (Windows error {ctypes.get_last_error()}); "
                "the operation may have been partially applied."
            )
        return True

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
        val = finite_float(val)
        addr = self.resolve_chain(CHAINS[key])
        if not addr:
            raise MemoryAccessError(
                f"Cannot resolve {key}. Load a character or check game compatibility."
            )
        buf4 = struct.pack("<f", val)
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
            raise MemoryAccessError(
                f"Cannot resolve {key}. Load a character or check game compatibility."
            )
        val_int = int(val)
        if val_int != val or not 0 <= val_int <= 255:
            raise ValueError("Enter a whole number between 0 and 255.")
        buf1 = struct.pack("<B", val_int)
        return self.write_memory(addr, buf1)

    # Raw Memory Primitives
    def read_ptr(self, addr):
        data = self.read_memory(addr, 8)
        if data is not None:
            return struct.unpack("<Q", data)[0]
        raise MemoryAccessError("Cannot read pointer.")

    def write_ptr(self, addr, val):
        return self.write_memory(addr, struct.pack("<Q", int(val)))

    def read_u32(self, addr):
        data = self.read_memory(addr, 4)
        if data is not None:
            return struct.unpack("<I", data)[0]
        raise MemoryAccessError("Cannot read integer.")

    def write_u32(self, addr, val):
        if int(val) != val or not 0 <= val <= 0xFFFFFFFF:
            raise ValueError("Enter a whole number between 0 and 4294967295.")
        return self.write_memory(addr, struct.pack("<I", int(val)))

    def read_f32(self, addr):
        data = self.read_memory(addr, 4)
        if data is not None:
            val = struct.unpack("<f", data)[0]
            if math.isfinite(val):
                return val
        raise MemoryAccessError("Cannot read a finite float.")

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
        entry = bptr + offset * 2
        header = self.read_memory(entry, 2)
        if header is None:
            return ""
        value = struct.unpack("<H", header)[0]
        length, wide = value >> 6, value & 1
        if not 0 < length <= 1023:
            return ""
        data = self.read_memory(entry + 2, length * (2 if wide else 1))
        if data is None:
            return ""
        return data.decode("utf-16-le" if wide else "utf-8", errors="replace")

    def character_identity(self):
        """Identify the actual pawn, not the address of the controller's pawn field."""
        if not self.h_proc:
            return None
        address = self.resolve_chain(["2F8", "30", "0", "38", "1248"])
        if not address:
            return None
        pawn = self.read_ptr(address)
        return (self.pid, pawn) if pawn else None

    def get_equipped_gear(self):
        return self.get_gear_items(include_inventory=False)

    def get_gear_items(self, include_inventory=False):
        identity = self.character_identity()
        if identity is None:
            return []
        inv_comp = self.read_ptr(identity[1] + 0xDA0)
        if not inv_comp:
            return []
        slots_data = self.read_ptr(inv_comp + 0x260)
        slots_count = self.read_u32(inv_comp + 0x268)
        if slots_count > 256 or (slots_count and not slots_data):
            raise MemoryAccessError("Invalid inventory slot array; check game compatibility.")
        items = []
        total_entries = 0
        for slot in range(slots_count):
            slot_addr = slots_data + slot * 0x50
            tag = self.get_fname(self.read_u32(slot_addr + 0xC))
            equipped = tag.startswith("SW.ItemSlot.Equipment.")
            if not equipped and not include_inventory:
                continue
            count = self.read_u32(slot_addr + 0x48)
            data = self.read_ptr(slot_addr + 0x40)
            total_entries += count
            if count > 4096 or total_entries > 16384 or (count and not data):
                raise MemoryAccessError("Invalid inventory item array; check game compatibility.")
            # Equipment slots expose the first entry, as in v1.0.4. Inventory entries
            # are examined by item tag rather than assuming slot 7 contains talismans.
            for index in range(min(count, 1) if equipped else count):
                address = data + index * 0xD8
                name_index = self.read_u32(address)
                name = self.get_fname(name_index)
                if not name.startswith("SW.Item."):
                    raise MemoryAccessError(
                        "Unrecognized item tag; refresh inventory or check compatibility."
                    )
                talisman = "talisman" in (tag + name).lower()
                if not equipped and not talisman:
                    continue
                items.append(
                    {
                        "identity": identity,
                        "name_index": name_index,
                        "slot_idx": slot,
                        "slot_tag": tag,
                        "label": tag.removeprefix("SW.ItemSlot.Equipment."),
                        "item_addr": address,
                        "name": name.removeprefix("SW.Item."),
                        "power": self.read_f32(address + 0x60),
                        "power_orig": self.read_f32(address + 0x5C),
                        "rarity": self.get_fname(self.read_u32(address + 0x14)).removeprefix(
                            "SW.Rarity."
                        ),
                        "level": self.read_u32(address + 0x68),
                        "xp": self.read_f32(address + 0x6C),
                        "is_talisman": talisman,
                        "equipped": equipped,
                    }
                )
        if self.character_identity() != identity:
            raise MemoryAccessError("Character changed while reading inventory. Refresh the list.")
        return items

    def require_item(self, address, expected=None):
        items = self.get_gear_items(
            include_inventory=bool(expected and not expected.get("equipped", True))
        )
        fields = ("identity", "slot_tag", "item_addr", "name_index")
        for item in items:
            if item["item_addr"] == address:
                if expected is not None and any(
                    item.get(key) != expected.get(key) for key in fields
                ):
                    break
                return item
        raise MemoryAccessError(
            "The selected item changed. Refresh the gear list and select it again."
        )

    def set_gear_power(self, item_addr, slot_tag, power_val, expected=None):
        power_val = finite_float(power_val)
        if power_val < 0:
            raise ValueError("Power cannot be negative.")
        item = self.require_item(item_addr, expected)
        if item["slot_tag"] != slot_tag:
            raise MemoryAccessError("The equipment slot changed. Refresh the list.")
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

    def set_gear_rarity(self, item_addr, rarity_name, expected=None):
        idx = RARITY_INDICES.get(rarity_name)
        canonical = "Special" if rarity_name == "Unique" else rarity_name
        if not idx or self.get_fname(idx) != f"SW.Rarity.{canonical}":
            raise MemoryAccessError(
                "Rarity identifier does not match this game build; no rarity change applied."
            )
        self.require_item(item_addr, expected)
        return self.write_u32(item_addr + 0x14, idx)

    def set_talisman_level_xp(self, item_addr, level, xp, expected=None):
        xp = finite_float(xp)
        if int(level) != level or not 0 <= level <= 2 or xp < 0:
            raise ValueError("Talisman rank must be 0-2 and XP must be non-negative.")
        item = self.require_item(item_addr, expected)
        if not item["is_talisman"]:
            raise MemoryAccessError("Selected item is not a talisman.")
        self.write_u32(item_addr + 0x68, level)
        self.write_f32(item_addr + 0x6C, xp)
        return True

    def set_talisman_xp(self, item, xp):
        xp = finite_float(xp)
        if xp < 0:
            raise ValueError("XP cannot be negative.")
        current = self.require_item(item["item_addr"], item)
        if not current["is_talisman"]:
            raise MemoryAccessError("Selected item is not a talisman.")
        return self.write_f32(current["item_addr"] + 0x6C, xp)

    def max_out_talismans(self, only_equipped=True):
        items = self.get_gear_items(include_inventory=not only_equipped)
        count = 0
        for item in items:
            if item["is_talisman"]:
                try:
                    self.set_talisman_level_xp(item["item_addr"], 2, 100000.0, expected=item)
                except MemoryAccessError as exc:
                    raise MemoryAccessError(
                        f"Stopped after {count} updated talisman(s). {exc}"
                    ) from exc
                count += 1
        return count

    def session_kind(self):
        if not self.h_proc or not self.is_alive():
            return "disconnected"
        if self.read_float("health_current") is None:
            return "loading"
        role = self.read_byte("player_role")
        return classify_session_role(role)
