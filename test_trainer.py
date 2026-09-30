"""Run on 64-bit Windows: python -m unittest -v.

Native tests access only buffers owned by this test process, never the game.
GUI tests substitute a memory manager and do not attach to any process.
"""

import ctypes
import math
import os
import struct
import unittest
from unittest.mock import Mock, patch

import trainer_gui as trainer
import trainer_memory as memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.mem = trainer.MemoryManager()
        self.mem.h_proc = memory.k32.OpenProcess(memory.PROCESS_ACCESS, False, os.getpid())
        self.assertTrue(self.mem.h_proc)
        self.mem.pid = os.getpid()
        self.target = ctypes.create_string_buffer(32)
        self.target[16] = b"\x03"  # Synthetic locally authoritative character.
        self.initial_target = self.target.raw
        self.middle = ctypes.create_string_buffer(32)
        ctypes.c_uint64.from_buffer(self.middle, 8).value = ctypes.addressof(self.target)
        self.root = ctypes.c_uint64(ctypes.addressof(self.middle))
        self.mem.base_addr = ctypes.addressof(self.root) - 0x0B0577C8
        self.chains = patch.dict(memory.CHAINS, {"test": ["4", "8"], "player_role": ["10", "8"]})
        self.chains.start()

    def tearDown(self):
        self.chains.stop()
        self.mem.close()

    def test_native_pointer_chain_and_float_round_trip(self):
        self.assertGreater(ctypes.addressof(self.target), 2**32)
        self.assertEqual(self.mem.resolve_chain(["4", "8"]), ctypes.addressof(self.target) + 4)
        self.assertTrue(self.mem.write_float("test", 1234.5))
        self.assertEqual(self.mem.read_float("test"), 1234.5)

    def test_native_byte_round_trip_and_zero_float(self):
        self.mem.write_byte("test", 251)
        self.assertEqual(self.mem.read_byte("test"), 251)
        self.mem.write_float("test", 0)
        self.assertEqual(self.mem.require_float("test"), 0)

    def test_close_is_idempotent_and_clears_connection(self):
        self.assertTrue(self.mem.is_alive())
        self.mem.close()
        self.mem.close()
        self.assertFalse(self.mem.is_alive())
        self.assertIsNone(self.mem.pid)
        self.assertIsNone(self.mem.base_addr)

    def test_process_exit_clears_connection(self):
        def exited(handle, code):
            code._obj.value = 0
            return True

        with patch.object(memory.k32, "GetExitCodeProcess", side_effect=exited):
            self.assertFalse(self.mem.is_alive())
        self.assertIsNone(self.mem.h_proc)

    def test_invalid_pointer_does_not_write(self):
        self.root.value = 0
        self.assertIsNone(self.mem.read_float("test"))
        with self.assertRaises(trainer.MemoryAccessError):
            self.mem.write_float("test", 10)
        self.assertEqual(self.target.raw, self.initial_target)

    def test_partial_reads_are_rejected(self):
        def short_read(handle, address, buffer, size, transferred):
            transferred._obj.value = size - 1
            return True

        with patch.object(memory.k32, "ReadProcessMemory", side_effect=short_read):
            self.assertIsNone(self.mem.read_memory(ctypes.addressof(self.target), 4))
            self.assertIsNone(self.mem.resolve_chain(["4", "8"]))

    def test_partial_writes_are_reported(self):
        def short_write(handle, address, buffer, size, transferred):
            transferred._obj.value = size - 1
            return True

        with patch.object(memory.k32, "WriteProcessMemory", side_effect=short_write):
            with self.assertRaises(trainer.MemoryAccessError):
                self.mem.write_float("test", 10)

    def test_invalid_numbers_never_reach_memory(self):
        for value in (math.nan, math.inf, -math.inf, 1e39, -1e39):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.mem.write_float("test", value)
        self.assertEqual(self.target.raw, self.initial_target)
        for value in (-1, 256, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.mem.write_byte("test", value)

    def test_nonfinite_reads_are_unavailable(self):
        ctypes.memmove(ctypes.addressof(self.target) + 4, struct.pack("<f", math.nan), 4)
        self.assertIsNone(self.mem.read_float("test"))

    def test_enumeration_failure_is_reported(self):
        with patch.object(memory.k32, "K32EnumProcesses", return_value=False):
            self.assertFalse(self.mem.attach())
        self.assertIn("Cannot list processes", self.mem.last_error)

    def test_candidate_handle_is_closed_when_module_inspection_fails(self):
        self.mem.close()

        def enumerate_one(pids, size, transferred):
            pids[0] = 123
            transferred._obj.value = ctypes.sizeof(memory.wintypes.DWORD)
            return True

        with (
            patch.object(memory.k32, "K32EnumProcesses", side_effect=enumerate_one),
            patch.object(memory.k32, "OpenProcess", return_value=456),
            patch.object(memory.psapi, "EnumProcessModulesEx", return_value=False),
            patch.object(memory.k32, "CloseHandle") as close,
        ):
            self.assertFalse(self.mem.attach())
            close.assert_called_once_with(456)
        self.assertIsNone(self.mem.h_proc)

    def test_unknown_session_rejects_writes_but_allows_reads(self):
        for role in (0, 255):
            with self.subTest(role=role):
                self.target[16] = bytes([role])
                before = self.target.raw
                self.assertEqual(self.mem.read_float("test"), 0.0)
                with patch.object(memory.k32, "WriteProcessMemory") as write:
                    with self.assertRaises(trainer.MemoryAccessError):
                        self.mem.write_float("test", 9999)
                    with self.assertRaises(trainer.MemoryAccessError):
                        self.mem.write_byte("test", 1)
                    write.assert_not_called()
                self.assertEqual(self.target.raw, before)

    def test_multiplayer_roles_allow_native_writes(self):
        for role in (1, 2):
            with self.subTest(role=role):
                self.target[16] = bytes([role])
                self.mem.write_float("test", 1234.5)
                self.assertEqual(self.mem.read_float("test"), 1234.5)
                self.mem.write_byte("test", 7)
                self.assertEqual(self.mem.read_byte("test"), 7)


class AppTests(unittest.TestCase):
    def setUp(self):
        with patch.object(trainer.MemoryManager, "attach", return_value=False):
            self.app = trainer.TrainerApp()
            self.app.withdraw()
        self.app.after_cancel(self.app._refresh_job)
        self.app.update_idletasks()
        self.app.mem = Mock(spec=trainer.MemoryManager)
        self.app.mem.h_proc = 1
        self.app.mem.pid = 123
        self.app.mem.is_alive.return_value = True
        self.app.mem.read_float.return_value = 10.0
        self.app.mem.require_float.return_value = 10.0
        self.app.mem.read_byte.return_value = 3
        self.app.mem.session_write_error.return_value = None
        self.app.mem.resolve_chain.return_value = 0x10168
        self.app.mem.session_kind.side_effect = lambda: trainer.MemoryManager.session_kind(
            self.app.mem
        )

    def tearDown(self):
        self.app.update_idletasks()
        self.app.on_close()

    def test_currency_adjustments_preserve_existing_balance(self):
        for method, key, delta in (
            ("adjust_emeralds", "emeralds_current", 1000),
            ("adjust_springstone", "springstone_current", 500),
            ("adjust_ench_points", "ench_points_cur", 5),
            ("adjust_souls", "souls_current", 500),
            ("adjust_xp", "xp_current", 10000),
        ):
            with self.subTest(method=method):
                self.app.mem.reset_mock()
                getattr(self.app, method)(delta)
                self.assertEqual(self.app.mem.require_float.call_args_list[0].args, (key,))
                self.app.mem.write_float.assert_any_call(key, 10.0 + delta)

    def test_enchantment_maximum_increases_with_available_points(self):
        self.app.mem.require_float.return_value = 18.0
        self.app.set_ench_points(99)
        self.app.mem.write_float.assert_any_call("ench_points_max_base", 99.0)
        self.app.mem.write_float.assert_any_call("ench_points_max_cur", 99.0)
        self.app.mem.write_float.assert_any_call("ench_points_cur", 99.0)

    def test_lowering_available_points_preserves_maximum(self):
        self.app.mem.require_float.return_value = 18.0
        self.app.set_ench_points(7)
        keys = [call.args[0] for call in self.app.mem.write_float.call_args_list]
        self.assertNotIn("ench_points_max_cur", keys)
        self.assertNotIn("ench_points_max_base", keys)

    def test_level_updates_both_values_and_rejects_invalid_levels(self):
        self.app.set_level(50)
        self.app.mem.write_float.assert_any_call("level_base", 50.0)
        self.app.mem.write_float.assert_any_call("level", 50.0)
        self.app.mem.reset_mock()
        for level in (0, -1, 101, 1.5, math.nan):
            with self.subTest(level=level), self.assertRaises(ValueError):
                self.app.set_level(level)
        self.app.mem.write_float.assert_not_called()

    def test_failed_balance_reads_do_not_overwrite_currency(self):
        self.app.mem.require_float.side_effect = trainer.MemoryAccessError("unavailable")
        for method in (
            "adjust_emeralds",
            "adjust_springstone",
            "adjust_ench_points",
            "adjust_souls",
            "adjust_xp",
        ):
            with self.subTest(method=method), self.assertRaises(trainer.MemoryAccessError):
                getattr(self.app, method)(5)
        self.app.mem.write_float.assert_not_called()

    def test_nonfinite_currency_rejected_before_cap_writes(self):
        for method in ("set_emeralds", "set_springstone", "set_ench_points", "set_souls"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                getattr(self.app, method)(math.nan)
        self.app.mem.write_float.assert_not_called()

    def test_failed_activation_does_not_show_enabled_toggle(self):
        self.app.mem.write_float.side_effect = trainer.MemoryAccessError("failed")
        for method, state in (
            ("toggle_freeze_souls", "freeze_souls_active"),
            ("toggle_auto_refill", "auto_refill_ammo_active"),
            ("toggle_infinite_potions", "infinite_potions_active"),
            ("toggle_infinite_roll", "infinite_roll_active"),
            ("toggle_lock_speed", "lock_speed_active"),
        ):
            with self.subTest(method=method):
                with self.assertRaises(trainer.MemoryAccessError):
                    getattr(self.app, method)()
                self.assertFalse(getattr(self.app, state))

    def test_resets_disable_continuous_charge_writes(self):
        self.app.infinite_potions_active = True
        self.app.infinite_roll_active = True
        self.app.reset_potion()
        self.app.reset_roll()
        self.assertFalse(self.app.infinite_potions_active)
        self.assertFalse(self.app.infinite_roll_active)
        self.app.mem.write_float.assert_any_call("potion_max_charges_cur", 1.0)
        self.app.mem.write_float.assert_any_call("roll_max_charges_cur", 1.0)

    def test_switching_charge_toggles_off_resets_cooldowns(self):
        self.app.infinite_potions_active = True
        self.app.infinite_roll_active = True
        self.app.toggle_infinite_potions()
        self.app.toggle_infinite_roll()
        self.app.mem.write_float.assert_any_call("potion_base_cd_cur", 30.0)
        self.app.mem.write_float.assert_any_call("roll_cd", 2.5)

    def test_speed_lock_supports_slow_speeds_and_updates_label(self):
        self.app.mem.require_float.return_value = 0.5
        self.app.toggle_lock_speed()
        self.assertEqual(self.app.locked_speed_val, 0.5)
        self.app.set_speed(0.7)
        self.assertIn("0.7x", self.app.btn_lock_speed.cget("text"))

    def test_refresh_survives_failed_writes(self):
        self.app.freeze_souls_active = True
        self.app.mem.write_float.side_effect = trainer.MemoryAccessError("write failed")
        with patch.object(self.app, "after") as after:
            self.app.refresh_loop()
        after.assert_called_once_with(250, self.app.refresh_loop)
        self.assertIn("write failed", self.app.status_lbl.cget("text"))
        self.app._refresh_job = None

    def test_unavailable_character_blocks_continuous_writes(self):
        self.app.mem.read_float.return_value = None
        self.app.freeze_souls_active = True
        self.app.refresh_values()
        self.app.mem.write_float.assert_not_called()
        self.assertIn("Character unavailable", self.app.status_lbl.cget("text"))

    def test_failed_effect_does_not_block_other_effects(self):
        self.app.god_mode_active = True
        self.app.freeze_souls_active = True
        with (
            patch.object(
                self.app, "apply_god_mode", side_effect=trainer.MemoryAccessError("god failed")
            ),
            patch.object(self.app, "apply_freeze_souls") as souls,
        ):
            self.app.refresh_values()
        souls.assert_called_once()
        self.assertIn("god failed", self.app.status_lbl.cget("text"))

    def test_client_session_preserves_all_continuous_effects(self):
        self.app.mem.read_byte.return_value = 2
        self.app.refresh_values()
        for flag, method in (
            ("god_mode_active", "apply_god_mode"),
            ("freeze_souls_active", "apply_freeze_souls"),
            ("auto_refill_ammo_active", "apply_auto_refill"),
            ("lock_speed_active", "apply_lock_speed"),
            ("infinite_potions_active", "apply_infinite_potions"),
            ("infinite_roll_active", "apply_infinite_roll"),
        ):
            with self.subTest(effect=method):
                setattr(self.app, flag, True)
                with patch.object(self.app, method) as apply:
                    self.app.refresh_values()
                    self.app.refresh_values()
                self.assertEqual(apply.call_count, 2)
                self.assertTrue(getattr(self.app, flag))
                setattr(self.app, flag, False)
        self.assertIn("Multiplayer controls available", self.app.status_lbl.cget("text"))
        self.assertEqual(self.app.lbl_emeralds[0].cget("text"), "10")
        self.assertEqual(self.app.session_kind, "client")
        self.assertTrue(
            all(self.app.notebook.tab(tab, "state") == "normal" for tab in self.app.edit_tabs)
        )

    def test_known_local_and_client_sessions_show_editing_tabs(self):
        for role, expected in (
            (3, "local"),
            (2, "client"),
            (1, "client"),
            (0, "unknown"),
            (None, "unknown"),
        ):
            with self.subTest(role=role):
                self.app.mem.read_byte.return_value = role
                self.app.refresh_values()
                self.assertEqual(self.app.session_kind, expected)
                states = [self.app.notebook.tab(tab, "state") for tab in self.app.edit_tabs]
                self.assertEqual(
                    states, ["normal" if expected in ("local", "client") else "hidden"] * 5
                )
                navigation = [
                    self.app.navigation[tab].winfo_manager() for tab in self.app.edit_tabs
                ]
                self.assertEqual(
                    navigation, ["pack" if expected in ("local", "client") else ""] * 5
                )

    def test_character_change_resets_locks_without_writing_to_new_character(self):
        self.app.refresh_values()
        self.app.freeze_souls_active = True
        self.app.god_mode_active = True
        self.app.mem.resolve_chain.return_value = 0x20168
        self.app.refresh_values()
        self.assertFalse(self.app.freeze_souls_active)
        self.assertFalse(self.app.god_mode_active)
        self.app.mem.write_float.assert_not_called()
        self.app.mem.write_byte.assert_not_called()

    def test_disconnection_and_loading_hide_commands_and_reset_locks(self):
        self.app.refresh_values()
        self.app.infinite_roll_active = True
        self.app.mem.read_float.return_value = None
        self.app.refresh_values()
        self.assertEqual(self.app.session_kind, "loading")
        self.assertFalse(self.app.infinite_roll_active)
        self.app.mem.is_alive.return_value = False
        self.app.mem.h_proc = None
        self.app.mem.last_error = "Closed"
        self.app.refresh_values()
        self.assertEqual(self.app.session_kind, "disconnected")
        self.assertTrue(
            all(self.app.notebook.tab(tab, "state") == "hidden" for tab in self.app.edit_tabs)
        )

    def test_hidden_tabs_return_in_original_order_without_reactivating_locks(self):
        self.app.refresh_values()
        self.app.lock_speed_active = True
        self.app.mem.read_byte.return_value = 2
        self.app.refresh_values()
        self.app.mem.read_byte.return_value = 3
        self.app.refresh_values()
        titles = [self.app.notebook.tab(tab, "text") for tab in self.app.notebook.tabs()]
        self.assertEqual(
            titles, ["Overview", "Currencies", "Combat", "Movement", "Progression", "Developer"]
        )
        self.assertFalse(self.app.lock_speed_active)

    def test_role_detection_does_not_label_authority_as_offline(self):
        self.assertEqual(memory.classify_session_role(3), "local")
        self.assertEqual(memory.classify_session_role(2), "client")
        self.app.refresh_values()
        self.assertIn("SOLO / HOST", self.app.session_badge.cget("text"))

    def test_copy_session_diagnostics_does_not_write_to_game(self):
        self.app.refresh_values()
        with (
            patch.object(self.app, "clipboard_clear") as clear,
            patch.object(self.app, "clipboard_append") as append,
        ):
            self.app.copy_session_diagnostics()
        clear.assert_called_once()
        self.assertIn("Local role: 3", append.call_args.args[0])
        self.assertIn("123", append.call_args.args[0])
        self.app.mem.write_float.assert_not_called()

    def test_god_mode_does_not_restore_another_process_snapshot(self):
        self.app.god_mode_active = True
        self.app._god_original_pid = 456
        self.app._god_original = (100, 0.7, 200, 116)
        self.app.toggle_god_mode()
        self.app.mem.write_float.assert_not_called()
        self.app.mem.write_byte.assert_not_called()
        self.assertFalse(self.app.god_mode_active)

    def test_disconnect_clears_values_and_retries(self):
        self.app.lbl_emeralds[0].config(text="9999")
        self.app.mem.is_alive.return_value = False
        self.app.mem.h_proc = None
        self.app.mem.last_error = "Game closed"
        self.app.next_connect_at = 0
        with patch.object(self.app, "try_connect") as reconnect:
            self.app.refresh_values()
        reconnect.assert_called_once()
        self.assertEqual(self.app.lbl_emeralds[0].cget("text"), "---")

    def test_god_mode_preserves_other_bits_and_restores_resistance(self):
        self.app.mem.resolve_chain.side_effect = lambda chain: (
            100 if chain == memory.CHAINS["damage_resist"] else 200
        )
        self.app.mem.read_byte.return_value = 0b10101111
        self.app.mem.require_float.side_effect = lambda key: {
            "damage_resist": 0.7,
            "health_max": 200,
            "shield_max": 30,
        }[key]
        self.app.toggle_god_mode()
        self.app.mem.write_byte.assert_called_with("actor_invincible", 0b10101011)
        self.app.mem.write_float.assert_any_call("shield_current", 30)
        # An unrelated flag changes while enabled; disabling must preserve it.
        self.app.mem.read_byte.return_value = 0b00101011
        self.app.toggle_god_mode()
        self.app.mem.write_byte.assert_called_with("actor_invincible", 0b00101111)
        self.app.mem.write_float.assert_any_call("damage_resist", 0.7)

    def test_tabs_have_scrollable_content(self):
        self.app.update_idletasks()
        for tab_id in self.app.notebook.tabs():
            tab = self.app.nametowidget(tab_id)
            canvas = next(
                child for child in tab.winfo_children() if isinstance(child, trainer.tk.Canvas)
            )
            self.assertTrue(canvas.cget("scrollregion"))
            self.assertTrue(canvas.cget("xscrollcommand"))
            self.assertTrue(canvas.cget("yscrollcommand"))


if __name__ == "__main__":
    unittest.main()
