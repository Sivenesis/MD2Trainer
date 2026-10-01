"""
Unit and Regression Test Suite for Minecraft Dungeons II Standalone Native Trainer
Target: 64-bit Windows
Usage: python -m unittest -v test_trainer.py
"""

import ctypes
import os
import unittest
from unittest.mock import patch

import trainer_gui as gui
import trainer_memory as memory
import trainer_offsets as offsets


class OffsetsTests(unittest.TestCase):
    def test_engine_offset_and_fnames_offset(self):
        self.assertEqual(offsets.ENGINE_OFFSET, 0x0B0577C8)
        self.assertEqual(offsets.FNAMES_BLOCKS_OFFSET, 0x0ADE3F90)

    def test_chains_structure(self):
        self.assertIn("emeralds_current", offsets.CHAINS)
        self.assertIn("springstone_current", offsets.CHAINS)
        self.assertIn("ench_points_cur", offsets.CHAINS)
        self.assertIn("player_dmg_mult_cur", offsets.CHAINS)
        self.assertIn("xp_gain_mult_cur", offsets.CHAINS)
        self.assertIn("power_melee_cur", offsets.CHAINS)
        self.assertIn("health_current", offsets.CHAINS)

        for key, chain in offsets.CHAINS.items():
            self.assertIsInstance(chain, list, f"{key} chain must be a list")
            self.assertGreater(len(chain), 0, f"{key} chain must not be empty")
            for off_str in chain:
                int(off_str, 16)  # Verify valid hex string

    def test_rarity_indices(self):
        self.assertIn("Common", offsets.RARITY_INDICES)
        self.assertIn("Rare", offsets.RARITY_INDICES)
        self.assertIn("Special", offsets.RARITY_INDICES)
        self.assertIn("Unique", offsets.RARITY_INDICES)
        self.assertEqual(offsets.RARITY_INDICES["Common"], 5234547)
        self.assertEqual(offsets.RARITY_INDICES["Special"], 5234598)


class MemoryManagerUnitTests(unittest.TestCase):
    def setUp(self):
        self.mem = memory.MemoryManager()
        # Open handle to current test process for safe, non-destructive Win32 pointer chain testing
        self.mem.h_proc = memory.k32.OpenProcess(memory.PROCESS_ACCESS, False, os.getpid())
        self.assertTrue(self.mem.h_proc)
        self.mem.pid = os.getpid()

        # Construct synthetic nested memory structures in process memory
        self.target_buf = ctypes.create_string_buffer(64)
        self.middle_buf = ctypes.create_string_buffer(64)
        ctypes.c_uint64.from_buffer(self.middle_buf, 8).value = ctypes.addressof(self.target_buf)

        self.root_ptr = ctypes.c_uint64(ctypes.addressof(self.middle_buf))
        self.mem.base_addr = ctypes.addressof(self.root_ptr) - offsets.ENGINE_OFFSET

        self.test_chains = patch.dict(
            offsets.CHAINS,
            {
                "test_float": ["10", "8"],
                "test_byte": ["20", "8"],
            },
        )
        self.test_chains.start()

    def tearDown(self):
        self.test_chains.stop()
        self.mem.close()

    def test_finite_float_validation(self):
        self.assertEqual(memory.finite_float(10.5), 10.5)
        self.assertEqual(memory.finite_float("42.0"), 42.0)
        with self.assertRaises(ValueError):
            memory.finite_float(float("inf"))
        with self.assertRaises(ValueError):
            memory.finite_float(float("-inf"))
        with self.assertRaises(ValueError):
            memory.finite_float(float("nan"))
        with self.assertRaises(ValueError):
            memory.finite_float(1e40)

    def test_classify_session_role(self):
        self.assertEqual(memory.classify_session_role(3), "local")
        self.assertEqual(memory.classify_session_role(2), "client")
        self.assertEqual(memory.classify_session_role(1), "client")
        self.assertEqual(memory.classify_session_role(0), "unknown")
        self.assertEqual(memory.classify_session_role(None), "unknown")

    def test_is_alive_current_process(self):
        self.assertTrue(self.mem.is_alive())
        # Simulate terminated process
        with patch.object(memory.k32, "GetExitCodeProcess", return_value=True) as mock_exit:
            code = ctypes.wintypes.DWORD(0)
            mock_exit.side_effect = lambda h, ptr: (
                ctypes.memmove(ptr, ctypes.byref(code), 4),
                True,
            )[1]
            self.assertFalse(self.mem.is_alive())
            self.assertIsNone(self.mem.h_proc)

    def test_native_pointer_chain_resolve(self):
        resolved = self.mem.resolve_chain(["10", "8"])
        expected = ctypes.addressof(self.target_buf) + 0x10
        self.assertEqual(resolved, expected)

    def test_read_and_write_float(self):
        self.mem.write_float("test_float", 123.456)
        val = self.mem.read_float("test_float")
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 123.456, places=2)

    def test_read_and_write_byte(self):
        self.mem.write_byte("test_byte", 0x7F)
        val = self.mem.read_byte("test_byte")
        self.assertEqual(val, 0x7F)
        with self.assertRaises(ValueError):
            self.mem.write_byte("test_byte", 300)

    def test_raw_primitives(self):
        addr = ctypes.addressof(self.target_buf)
        self.mem.write_u32(addr, 0xDEADBEEF)
        self.assertEqual(self.mem.read_u32(addr), 0xDEADBEEF)

        self.mem.write_f32(addr + 4, 999.5)
        self.assertAlmostEqual(self.mem.read_f32(addr + 4), 999.5, places=2)

        self.mem.write_ptr(addr + 8, 0x7FF612345678)
        self.assertEqual(self.mem.read_ptr(addr + 8), 0x7FF612345678)


class GuiAndFeaturesTests(unittest.TestCase):
    def setUp(self):
        # Create headless Tkinter app without spawning real process or loop
        with (
            patch.object(memory.MemoryManager, "attach", return_value=False),
            patch.object(gui.TrainerApp, "refresh_loop"),
        ):
            self.app = gui.TrainerApp()
            self.app.withdraw()  # Do not display window during automated testing
        self.app.after_cancel(self.app._refresh_job)
        self.app._refresh_job = None
        for name, value in (
            ("write_float", True),
            ("write_byte", True),
            ("read_float", 100.0),
            ("read_byte", 0x74),
            ("resolve_chain", 0x10000),
            ("character_identity", (123, 0x20000)),
        ):
            patcher = patch.object(self.app.mem, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.app.destroy()

    def test_all_tabs_created(self):
        tab_titles = [
            self.app.notebook.tab(i, "text") for i in range(len(self.app.notebook.tabs()))
        ]
        self.assertEqual(
            tab_titles, ["Currencies", "Combat", "Movement", "Progression", "Gear & Talismans"]
        )
        self.assertNotIn("Developer", tab_titles)

    def test_currency_freeze_toggles(self):
        self.assertFalse(self.app.freeze_emeralds_active)
        self.app.toggle_freeze_emeralds()
        self.assertTrue(self.app.freeze_emeralds_active)
        self.assertIn("FROZEN", self.app.btn_freeze_emeralds.cget("text"))
        self.app.toggle_freeze_emeralds()
        self.assertFalse(self.app.freeze_emeralds_active)

        self.assertFalse(self.app.freeze_springstone_active)
        self.app.toggle_freeze_springstone()
        self.assertTrue(self.app.freeze_springstone_active)
        self.app.toggle_freeze_springstone()
        self.assertFalse(self.app.freeze_springstone_active)

        self.assertFalse(self.app.freeze_ench_active)
        self.app.toggle_freeze_ench()
        self.assertTrue(self.app.freeze_ench_active)
        self.app.toggle_freeze_ench()
        self.assertFalse(self.app.freeze_ench_active)

    def test_freeze_all_currencies_toggle(self):
        self.app.freeze_emeralds_active = False
        self.app.freeze_springstone_active = False
        self.app.freeze_ench_active = False

        self.app.toggle_freeze_all_currencies()
        self.assertTrue(self.app.freeze_emeralds_active)
        self.assertTrue(self.app.freeze_springstone_active)
        self.assertTrue(self.app.freeze_ench_active)

        self.app.toggle_freeze_all_currencies()
        self.assertFalse(self.app.freeze_emeralds_active)
        self.assertFalse(self.app.freeze_springstone_active)
        self.assertFalse(self.app.freeze_ench_active)

    def test_combat_toggles(self):
        # God Mode
        self.assertFalse(self.app.god_mode_active)
        self.app.toggle_god_mode()
        self.assertTrue(self.app.god_mode_active)
        self.app.toggle_god_mode()
        self.assertFalse(self.app.god_mode_active)

        # Player Damage Lock
        self.assertFalse(self.app.lock_player_dmg_active)
        self.app.toggle_lock_player_damage()
        self.assertTrue(self.app.lock_player_dmg_active)
        self.app.toggle_lock_player_damage()
        self.assertFalse(self.app.lock_player_dmg_active)

        # Freeze Souls
        self.assertFalse(self.app.freeze_souls_active)
        self.app.toggle_freeze_souls()
        self.assertTrue(self.app.freeze_souls_active)
        self.app.toggle_freeze_souls()
        self.assertFalse(self.app.freeze_souls_active)

        # Auto Refill Ammo
        self.assertFalse(self.app.auto_refill_ammo_active)
        self.app.toggle_auto_refill()
        self.assertTrue(self.app.auto_refill_ammo_active)
        self.app.toggle_auto_refill()
        self.assertFalse(self.app.auto_refill_ammo_active)

        # Infinite Potions
        self.assertFalse(self.app.infinite_potions_active)
        self.app.toggle_infinite_potions()
        self.assertTrue(self.app.infinite_potions_active)
        self.app.toggle_infinite_potions()
        self.assertFalse(self.app.infinite_potions_active)

    def test_movement_and_progression_toggles(self):
        # Lock Movement Speed
        self.assertFalse(self.app.lock_speed_active)
        self.app.toggle_lock_speed()
        self.assertTrue(self.app.lock_speed_active)
        self.app.toggle_lock_speed()
        self.assertFalse(self.app.lock_speed_active)

        # Infinite Roll
        self.assertFalse(self.app.infinite_roll_active)
        self.app.toggle_infinite_roll()
        self.assertTrue(self.app.infinite_roll_active)
        self.app.toggle_infinite_roll()
        self.assertFalse(self.app.infinite_roll_active)

        # Lock XP Gain
        self.assertFalse(self.app.lock_xp_gain_active)
        self.app.toggle_lock_xp_gain()
        self.assertTrue(self.app.lock_xp_gain_active)
        self.app.toggle_lock_xp_gain()
        self.assertFalse(self.app.lock_xp_gain_active)

    def test_gear_operations_dispatch(self):
        self.app.mem.h_proc = 123  # Simulated process handle
        mock_gear = [
            {
                "slot_idx": 23,
                "slot_tag": "SW.ItemSlot.Equipment.Talisman1",
                "label": "Talisman1",
                "item_addr": 0x1000,
                "name": "HealthBoost",
                "power": 10.0,
                "power_orig": 10.0,
                "rarity": "Special",
                "level": 1,
                "xp": 500.0,
                "is_talisman": True,
            }
        ]
        with patch.object(self.app.mem, "get_equipped_gear", return_value=mock_gear):
            self.app.refresh_gear_table()
            items = self.app.gear_tree.get_children()
            self.assertEqual(len(items), 1)

            # Test max out talismans routine without blocking modal dialog
            with (
                patch.object(self.app.mem, "max_out_talismans", return_value=1) as mock_max,
                patch.object(gui.messagebox, "showinfo") as mock_box,
            ):
                self.app.max_out_equipped_talismans()
                mock_max.assert_called_with(only_equipped=True)
                mock_box.assert_called_once()
        self.app.mem.h_proc = None

    def test_multipliers_and_setters(self):
        with patch.object(self.app.mem, "write_float") as mock_wf:
            self.app.set_currency_gain(5.0)
            mock_wf.assert_any_call("emerald_increase_cur", 4.0)

            self.app.set_player_damage(10.0)
            mock_wf.assert_any_call("player_dmg_mult_cur", 10.0)
            mock_wf.assert_any_call("melee_damage_cur", 10.0)
            mock_wf.assert_any_call("ranged_damage_cur", 10.0)

            self.app.set_xp_gain(25.0)
            mock_wf.assert_any_call("xp_gain_mult_cur", 25.0)

    def test_gear_power_and_rarity_methods(self):
        with (
            patch.object(self.app.mem, "write_f32") as mock_wf32,
            patch.object(self.app.mem, "write_float") as mock_wf,
            patch.object(self.app.mem, "write_u32") as mock_wu32,
            patch.object(
                self.app.mem,
                "require_item",
                return_value={"slot_tag": "SW.ItemSlot.Equipment.MeleeWeapon", "is_talisman": True},
            ),
            patch.object(self.app.mem, "get_fname", return_value="SW.Rarity.Special"),
        ):
            # Melee power
            self.app.mem.set_gear_power(0x2000, "SW.ItemSlot.Equipment.MeleeWeapon", 150.0)
            mock_wf32.assert_any_call(0x2000 + 0x60, 150.0)
            mock_wf.assert_any_call("power_melee_cur", 150.0)

            # Rarity
            res = self.app.mem.set_gear_rarity(0x2000, "Special")
            self.assertTrue(res)
            mock_wu32.assert_called_with(0x2000 + 0x14, offsets.RARITY_INDICES["Special"])

            # Talisman level and XP
            self.app.mem.set_talisman_level_xp(0x2000, 2, 50000.0)
            mock_wu32.assert_any_call(0x2000 + 0x68, 2)
            mock_wf32.assert_any_call(0x2000 + 0x6C, 50000.0)


if __name__ == "__main__":
    unittest.main()
