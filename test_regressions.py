"""Regression tests for trainer memory and GUI components; never attach to the game."""

import math
import unittest
from unittest.mock import Mock, patch

import trainer_gui as gui
import trainer_memory as memory
from trainer_offsets import RARITY_INDICES


def item(**changes):
    result = {
        "identity": (123, 0x10000),
        "name_index": 42,
        "item_addr": 0x20000,
        "slot_tag": "SW.ItemSlot.Equipment.MeleeWeapon",
        "is_talisman": False,
        "equipped": True,
        "xp": 100.0,
        "level": 0,
        "power": 50.0,
        "label": "MeleeWeapon",
        "name": "Sword",
        "rarity": "Common",
    }
    result.update(changes)
    return result


class MemoryRegressions(unittest.TestCase):
    def setUp(self):
        self.mem = memory.MemoryManager()

    def test_open_process_declares_handle_and_arguments(self):
        self.assertEqual(memory.k32.OpenProcess.restype, memory.wintypes.HANDLE)
        self.assertEqual(len(memory.k32.OpenProcess.argtypes), 3)

    def test_missing_process_write_raises(self):
        with self.assertRaises(memory.MemoryAccessError):
            self.mem.write_memory(0x10000, b"test")

    def test_partial_native_write_raises(self):
        self.mem.h_proc = 123  # API below is mocked; never sent to Windows.

        def partial(handle, address, data, size, written):
            written._obj.value = size - 1
            return True

        with patch.object(memory.k32, "WriteProcessMemory", side_effect=partial):
            with self.assertRaisesRegex(memory.MemoryAccessError, "partially"):
                self.mem.write_memory(0x10000, b"test")

    def test_unresolved_chain_write_raises(self):
        with patch.object(self.mem, "resolve_chain", return_value=None):
            with self.assertRaises(memory.MemoryAccessError):
                self.mem.write_float("health_current", 100)

    def test_fractional_byte_rejected_before_write(self):
        with (
            patch.object(self.mem, "resolve_chain", return_value=0x10000),
            patch.object(self.mem, "write_memory") as write,
        ):
            with self.assertRaises(ValueError):
                self.mem.write_byte("actor_invincible", 1.9)
            write.assert_not_called()

    def test_raw_read_failure_is_not_zero(self):
        for method in (self.mem.read_ptr, self.mem.read_u32, self.mem.read_f32):
            with self.subTest(method=method.__name__), self.assertRaises(memory.MemoryAccessError):
                method(0x10000)

    def test_nonfinite_raw_float_rejected(self):
        import struct

        with patch.object(self.mem, "read_memory", return_value=struct.pack("<f", math.nan)):
            with self.assertRaises(memory.MemoryAccessError):
                self.mem.read_f32(0x10000)

    def test_stale_item_cannot_be_written(self):
        original = item()
        for current in (
            [],
            [item(name_index=43)],
            [item(identity=(456, 0x10000))],
            [item(slot_tag="AnotherSlot")],
        ):
            with (
                self.subTest(current=current),
                patch.object(self.mem, "get_gear_items", return_value=current),
                patch.object(self.mem, "write_f32") as write,
            ):
                with self.assertRaises(memory.MemoryAccessError):
                    self.mem.set_gear_power(
                        original["item_addr"], original["slot_tag"], 100, expected=original
                    )
                write.assert_not_called()

    def test_power_failure_propagates_and_stops_following_writes(self):
        original = item()
        with (
            patch.object(self.mem, "get_gear_items", return_value=[original]),
            patch.object(
                self.mem, "write_f32", side_effect=memory.MemoryAccessError("failed")
            ) as raw,
            patch.object(self.mem, "write_float") as derived,
        ):
            with self.assertRaises(memory.MemoryAccessError):
                self.mem.set_gear_power(
                    original["item_addr"], original["slot_tag"], 100, expected=original
                )
            self.assertEqual(raw.call_count, 1)
            derived.assert_not_called()

    def test_rarity_must_match_runtime_fname(self):
        with (
            patch.object(self.mem, "get_fname", return_value="SW.Unrelated.Name"),
            patch.object(self.mem, "write_u32") as write,
        ):
            with self.assertRaises(memory.MemoryAccessError):
                self.mem.set_gear_rarity(0x20000, "Special", expected=item())
            write.assert_not_called()

    def test_rarity_revalidates_item_and_accepts_special_alias(self):
        original = item()
        with (
            patch.object(self.mem, "get_fname", return_value="SW.Rarity.Special"),
            patch.object(self.mem, "get_gear_items", return_value=[original]),
            patch.object(self.mem, "write_u32", return_value=True) as write,
        ):
            self.assertTrue(
                self.mem.set_gear_rarity(original["item_addr"], "Unique", expected=original)
            )
            write.assert_called_once_with(original["item_addr"] + 0x14, RARITY_INDICES["Special"])

    def test_talisman_write_validates_every_value_before_mutating(self):
        with patch.object(self.mem, "write_u32") as write:
            for level, xp in ((1.5, 100), (-1, 100), (2, math.inf), (2, -1)):
                with self.subTest(level=level, xp=xp), self.assertRaises(ValueError):
                    self.mem.set_talisman_level_xp(0x20000, level, xp, expected=item())
            write.assert_not_called()

    def test_max_talismans_reports_partial_batch_count(self):
        tal = item(is_talisman=True)
        with (
            patch.object(self.mem, "get_gear_items", return_value=[tal, tal]),
            patch.object(
                self.mem,
                "set_talisman_level_xp",
                side_effect=[True, memory.MemoryAccessError("failed")],
            ),
        ):
            with self.assertRaisesRegex(memory.MemoryAccessError, "after 1 updated"):
                self.mem.max_out_talismans()

    def test_inventory_slot_count_is_bounded(self):
        with (
            patch.object(self.mem, "character_identity", return_value=(123, 0x10000)),
            patch.object(self.mem, "read_ptr", return_value=0x20000),
            patch.object(self.mem, "read_u32", return_value=0xFFFFFFFF),
        ):
            with self.assertRaisesRegex(memory.MemoryAccessError, "slot array"):
                self.mem.get_gear_items(True)

    def test_inventory_item_count_is_bounded(self):
        with (
            patch.object(self.mem, "character_identity", return_value=(123, 0x10000)),
            patch.object(self.mem, "read_ptr", return_value=0x20000),
            patch.object(self.mem, "read_u32", side_effect=[1, 42, 0xFFFFFFFF]),
            patch.object(self.mem, "get_fname", return_value="SW.ItemSlot.Inventory.Talismans"),
        ):
            with self.assertRaisesRegex(memory.MemoryAccessError, "item array"):
                self.mem.get_gear_items(True)

    def test_inventory_talismans_are_found_by_tags_not_slot_seven(self):
        identity = (123, 0x10000)
        slots, first, second = 0x30000, 0x40000, 0x50000

        def read_ptr(address):
            return {
                0x10000 + 0xDA0: 0x20000,
                0x20000 + 0x260: slots,
                slots + 0x40: first,
                slots + 0x50 + 0x40: second,
            }[address]

        def read_u32(address):
            return {
                0x20000 + 0x268: 2,
                slots + 0xC: 1,
                slots + 0x48: 1,
                slots + 0x50 + 0xC: 2,
                slots + 0x50 + 0x48: 1,
                first: 3,
                second: 4,
                second + 0x14: 5,
                second + 0x68: 0,
            }[address]

        names = {
            1: "SW.ItemSlot.Inventory.Weapon",
            2: "SW.ItemSlot.Inventory.Talismans",
            3: "SW.Item.Sword",
            4: "SW.Item.Talisman.Health",
            5: "SW.Rarity.Common",
        }
        with (
            patch.object(self.mem, "character_identity", return_value=identity),
            patch.object(self.mem, "read_ptr", side_effect=read_ptr),
            patch.object(self.mem, "read_u32", side_effect=read_u32),
            patch.object(self.mem, "read_f32", return_value=1.0),
            patch.object(self.mem, "get_fname", side_effect=names.__getitem__),
        ):
            result = self.mem.get_gear_items(True)
        self.assertEqual([i["item_addr"] for i in result], [second])
        self.assertFalse(result[0]["equipped"])

    def test_fname_reads_exact_utf16_payload(self):
        import struct

        self.mem.h_proc = 123
        self.mem.blocks_addr = 0x10000
        value = "Rare"
        blocks = {
            0x10000: struct.pack("<Q", 0x20000),
            0x20002: struct.pack("<H", (len(value) << 6) | 1),
            0x20004: value.encode("utf-16-le"),
        }
        with patch.object(
            self.mem, "read_memory", side_effect=lambda address, size: blocks[address]
        ) as read:
            self.assertEqual(self.mem.get_fname(1), value)
        self.assertEqual(read.call_args.args[1], 8)


class GuiRegressions(unittest.TestCase):
    def setUp(self):
        with patch.object(memory.MemoryManager, "attach", return_value=False):
            self.app = gui.TrainerApp()
        self.app.withdraw()
        self.app.after_cancel(self.app._refresh_job)
        self.app._refresh_job = None
        self.app.mem = Mock(spec=memory.MemoryManager)
        self.mem = self.app.mem
        self.mem.h_proc = 123
        self.mem.pid = 123
        self.mem.last_error = "Disconnected"
        self.mem.is_alive.return_value = True
        self.mem.character_identity.return_value = (123, 0x10000)
        self.mem.session_kind.return_value = "local"
        self.mem.read_float.return_value = 100.0
        self.mem.require_float.return_value = 100.0
        self.mem.read_byte.return_value = 0b10101111
        self.mem.resolve_chain.return_value = 0x20000
        self.mem.get_equipped_gear.return_value = []
        self.app.refresh_values()

    def tearDown(self):
        self.app.destroy()

    def test_unreadable_balance_aborts_increment(self):
        self.mem.require_float.side_effect = memory.MemoryAccessError("unreadable")
        with self.assertRaises(memory.MemoryAccessError):
            self.app.adjust_emeralds(100)
        self.mem.write_float.assert_not_called()

    def test_overflowing_derived_multiplier_aborts_before_any_write(self):
        with self.assertRaises(ValueError):
            self.app.set_currency_gain(1e38)
        self.mem.write_float.assert_not_called()

    def test_relative_gear_power_uses_a_fresh_read(self):
        original = item(power=10)
        self.app.selected_gear_item = original
        self.mem.require_item.return_value = item(power=50)
        with patch.object(self.app, "refresh_gear_table"):
            self.app.adjust_selected_power(10)
        self.mem.set_gear_power.assert_called_once_with(
            original["item_addr"], original["slot_tag"], 60, expected=original
        )

    def test_reconnection_clears_effects_selection_and_history(self):
        self.app.lock_speed_active = True
        self.app.selected_gear_item = item()
        self.app.last_talisman_xp = {123: 100}
        self.app.talisman_growth_mult = 5
        self.mem.is_alive.return_value = False
        self.app.next_connect_at = 0
        self.app.refresh_values()
        self.assertFalse(self.app.lock_speed_active)
        self.assertIsNone(self.app.selected_gear_item)
        self.assertEqual(self.app.last_talisman_xp, {})
        self.assertEqual(self.app.talisman_growth_mult, 1)
        self.mem.write_float.assert_not_called()

    def test_character_change_in_same_process_clears_effects(self):
        self.app.auto_refill_ammo_active = True
        self.mem.character_identity.return_value = (123, 0x99999)
        self.app.refresh_values()
        self.assertFalse(self.app.auto_refill_ammo_active)
        self.mem.write_float.assert_not_called()

    def test_stable_multiplayer_keeps_effects_working(self):
        self.mem.session_kind.return_value = "client"
        self.app.refresh_values()
        self.app.lock_speed_active = True
        self.app.auto_refill_ammo_active = True
        self.app.refresh_values()
        self.assertTrue(self.app.lock_speed_active)
        self.assertTrue(self.app.auto_refill_ammo_active)
        self.mem.write_float.assert_any_call("move_mult_cur", 1.0)
        self.mem.write_float.assert_any_call("ammo_current", 999.0)
        self.assertIn("MULTIPLAYER", self.app.session_label.cget("text"))

    def test_one_failed_effect_does_not_block_others(self):
        self.app.lock_speed_active = True
        self.app.auto_refill_ammo_active = True
        with (
            patch.object(
                self.app, "apply_lock_speed", side_effect=memory.MemoryAccessError("failed")
            ),
            patch.object(self.app, "apply_auto_refill") as arrows,
        ):
            self.app.refresh_values()
        arrows.assert_called_once()
        self.assertFalse(self.app.lock_speed_active)
        self.assertIn("failed", self.app.status_lbl.cget("text"))

    def test_polling_is_rescheduled_after_exception(self):
        with (
            patch.object(self.app, "refresh_values", side_effect=ValueError("failure")),
            patch.object(self.app, "after", return_value=None) as schedule,
        ):
            self.app.refresh_loop()
        schedule.assert_called_once_with(250, self.app.refresh_loop)
        self.assertIn("failure", self.app.status_lbl.cget("text"))

    def test_failed_activation_never_sets_toggle_on(self):
        with patch.object(
            self.app, "apply_auto_refill", side_effect=memory.MemoryAccessError("failed")
        ):
            with self.assertRaises(memory.MemoryAccessError):
                self.app.toggle_auto_refill()
        self.assertFalse(self.app.auto_refill_ammo_active)

    def test_potion_and_roll_reset_stop_continuous_writes(self):
        self.app.infinite_potions_active = True
        self.app.infinite_roll_active = True
        self.app.reset_potion()
        self.app.reset_roll()
        self.mem.write_float.reset_mock()
        self.app.refresh_values()
        self.mem.write_float.assert_not_called()

    def test_speed_setter_updates_active_lock(self):
        self.app.lock_speed_active = True
        self.app.set_speed(3)
        self.app.refresh_values()
        self.assertEqual(self.app.locked_speed_val, 3)
        self.mem.write_float.assert_any_call("move_mult_cur", 3)

    def test_god_mode_preserves_other_bits_and_original_resistance(self):
        self.mem.require_float.side_effect = lambda key: {
            "health_max": 200,
            "shield_max": 40,
            "damage_resist": 0.7,
        }[key]
        self.app.toggle_god_mode()
        self.mem.write_byte.assert_called_with("actor_invincible", 0b10101011)
        self.mem.read_byte.return_value = 0b00101011
        self.app.toggle_god_mode()
        self.mem.write_byte.assert_called_with("actor_invincible", 0b00101111)
        self.mem.write_float.assert_any_call("damage_resist", 0.7)

    def test_god_mode_never_restores_a_different_character(self):
        self.app.toggle_god_mode()
        self.mem.write_float.reset_mock()
        self.mem.write_byte.reset_mock()
        self.mem.character_identity.return_value = (123, 0x99999)
        self.app.toggle_god_mode()
        self.mem.write_float.assert_not_called()
        self.mem.write_byte.assert_not_called()

    def test_gear_ui_passes_observed_identity(self):
        original = item()
        self.app.selected_gear_item = original
        self.app.gear_power_var.set("100")
        with patch.object(self.app, "refresh_gear_table"):
            self.app.on_set_selected_power()
        self.mem.set_gear_power.assert_called_once_with(
            original["item_addr"], original["slot_tag"], 100, expected=original
        )

    def test_refresh_empty_inventory_clears_selection(self):
        self.app.selected_gear_item = item()
        self.app.refresh_gear_table()
        self.assertIsNone(self.app.selected_gear_item)

    def test_talisman_growth_does_not_reapply_its_own_bonus(self):
        tal = item(is_talisman=True)
        self.app.set_talisman_growth(2)
        self.mem.get_equipped_gear.return_value = [tal]
        self.app.update_talisman_growth()
        tal["xp"] = 110
        self.app.update_talisman_growth()
        self.mem.set_talisman_xp.assert_called_once_with(tal, 120)
        tal["xp"] = 120
        self.app.update_talisman_growth()
        self.assertEqual(self.mem.set_talisman_xp.call_count, 1)

    def test_replaced_talisman_starts_new_baseline(self):
        tal = item(is_talisman=True)
        self.app.set_talisman_growth(2)
        self.mem.get_equipped_gear.return_value = [tal]
        self.app.update_talisman_growth()
        self.mem.get_equipped_gear.return_value = [item(is_talisman=True, name_index=99, xp=10000)]
        self.app.update_talisman_growth()
        self.mem.set_talisman_xp.assert_not_called()

    def test_nonfinite_growth_input_does_not_enable_background_work(self):
        with self.assertRaises(ValueError):
            self.app.set_talisman_growth(math.nan)
        self.assertEqual(self.app.talisman_growth_mult, 1)

    def test_every_tab_has_scrollbars(self):
        for tab in self.app.notebook.tabs():
            children = self.app.nametowidget(tab).winfo_children()
            self.assertEqual(sum(isinstance(w, gui.tk.Canvas) for w in children), 1)
            self.assertEqual(sum(isinstance(w, gui.ttk.Scrollbar) for w in children), 2)

    def test_destroy_closes_memory_handle(self):
        # tearDown exercises destruction; a separate app keeps it idempotent here.
        with patch.object(memory.MemoryManager, "attach", return_value=False):
            app = gui.TrainerApp()
        with patch.object(app.mem, "close") as close:
            app.destroy()
            close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
