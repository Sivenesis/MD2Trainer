#!/usr/bin/env python3
"""
MINECRAFT DUNGEONS II - STANDALONE NATIVE TRAINER v1.0.4
Target: Dungeons-WinGDK-Shipping.exe (Singleplayer / Offline)
Direct Win32 Memory Access - Zero Debugger, Zero Watchdog Conflicts, Zero Dependencies.
"""

import time
import tkinter as tk
from tkinter import messagebox, ttk

from trainer_memory import MemoryAccessError, MemoryManager, finite_float
from trainer_offsets import CHAINS
from trainer_widgets import FlowFrame


class TrainerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Dungeons II - Native Trainer v1.0.4")
        self.geometry("940x800")
        self.minsize(880, 720)
        self.configure(bg="#0b111b")

        self.mem = MemoryManager()
        self.value_rows = []
        self.next_connect_at = 0.0
        self.session_identity = None
        self.session_kind = "disconnected"
        self._god_original = None
        self._god_original_pid = None
        self._god_identity = None
        self._closing = False
        self.effect_controls = ()
        self.god_mode_active = False

        # Currency Freeze States
        self.freeze_emeralds_active = False
        self.freeze_springstone_active = False
        self.freeze_ench_active = False
        self.freeze_souls_active = False

        # Combat States
        self.auto_refill_ammo_active = False
        self.lock_speed_active = False
        self.locked_speed_val = 1.0
        self.infinite_potions_active = False
        self.infinite_roll_active = False
        self.lock_player_dmg_active = False
        self.locked_player_dmg_val = 1.0

        # Progression & Gear States
        self.lock_xp_gain_active = False
        self.locked_xp_gain_val = 1.0
        self.talisman_growth_mult = 1.0
        self.last_talisman_xp = {}
        self.selected_gear_item = None

        self.setup_styles()
        self.create_widgets()

        self.effect_controls = (
            ("god_mode_active", "btn_god", "God mode", "apply_god_mode"),
            (
                "freeze_emeralds_active",
                "btn_freeze_emeralds",
                "Freeze emeralds",
                "apply_freeze_emeralds",
            ),
            (
                "freeze_springstone_active",
                "btn_freeze_springstone",
                "Freeze shards",
                "apply_freeze_springstone",
            ),
            ("freeze_ench_active", "btn_freeze_ench", "Freeze enchantment", "apply_freeze_ench"),
            ("freeze_souls_active", "btn_freeze_souls", "Freeze souls", "apply_freeze_souls"),
            ("auto_refill_ammo_active", "btn_auto_refill", "Infinite arrows", "apply_auto_refill"),
            ("lock_speed_active", "btn_lock_speed", "Lock speed", "apply_lock_speed"),
            (
                "infinite_potions_active",
                "btn_infinite_potions",
                "Infinite potions",
                "apply_infinite_potions",
            ),
            ("infinite_roll_active", "btn_infinite_roll", "Infinite roll", "apply_infinite_roll"),
            ("lock_player_dmg_active", "btn_lock_dmg", "Lock damage", "apply_locked_damage"),
            ("lock_xp_gain_active", "btn_lock_xp", "Lock XP", "apply_locked_xp"),
        )
        self.try_connect()
        self._refresh_job = self.after(500, self.refresh_loop)

    def destroy(self):
        self._closing = True
        if getattr(self, "_refresh_job", None):
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        self.mem.close()
        super().destroy()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TNotebook",
            background="#0b111b",
            borderwidth=0,
            bordercolor="#0b111b",
            lightcolor="#0b111b",
            darkcolor="#0b111b",
        )
        for name in ("Horizontal.TScrollbar", "Vertical.TScrollbar"):
            style.configure(
                name,
                background="#223146",
                troughcolor="#0b111b",
                borderwidth=0,
                bordercolor="#0b111b",
                lightcolor="#223146",
                darkcolor="#223146",
                arrowcolor="#8fa2b8",
                arrowsize=12,
            )
        style.configure(
            "TNotebook.Tab", bordercolor="#0b111b", lightcolor="#0b111b", darkcolor="#0b111b"
        )
        style.configure(
            "TNotebook.Tab",
            background="#131e2c",
            foreground="#e6eef8",
            padding=[16, 6],
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#223146")],
            foreground=[("selected", "#64d8cb")],
        )
        style.configure("TFrame", background="#0b111b")
        style.configure("Card.TFrame", background="#131e2c", relief="flat")
        style.configure("TLabel", background="#131e2c", foreground="#e6eef8", font=("Segoe UI", 9))
        style.configure(
            "Header.TLabel",
            background="#0b111b",
            foreground="#64d8cb",
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background="#0b111b",
            foreground="#70ddb1",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Value.TLabel",
            background="#131e2c",
            foreground="#f9e2af",
            font=("Consolas", 10, "bold"),
        )
        style.configure(
            "TButton",
            background="#223146",
            foreground="#e6eef8",
            font=("Segoe UI", 9),
            borderwidth=0,
            padding=[6, 3],
        )
        style.configure("Accent.TButton", background="#64d8cb", foreground="#081c18")
        style.map("Accent.TButton", background=[("active", "#70ddb1")])
        style.map("TButton", background=[("active", "#45475a"), ("pressed", "#585b70")])

        # Treeview styling
        style.configure(
            "Gear.Treeview",
            background="#0b111b",
            foreground="#e6eef8",
            fieldbackground="#0b111b",
            font=("Segoe UI", 9),
            rowheight=24,
        )
        style.configure(
            "Gear.Treeview.Heading",
            background="#223146",
            foreground="#64d8cb",
            font=("Segoe UI", 9, "bold"),
            padding=[4, 4],
        )
        style.map(
            "Gear.Treeview",
            background=[("selected", "#45475a")],
            foreground=[("selected", "#f9e2af")],
        )

    def create_widgets(self):
        # Top Header Bar
        top_bar = tk.Frame(self, bg="#0b111b", padx=16, pady=10)
        top_bar.pack(fill="x")

        title_lbl = tk.Label(
            top_bar,
            text="MINECRAFT DUNGEONS II - NATIVE TRAINER v1.0.4",
            font=("Segoe UI", 13, "bold"),
            bg="#0b111b",
            fg="#64d8cb",
        )
        title_lbl.pack(side="left")

        ttk.Button(top_bar, text="Reconnect", command=self.try_connect).pack(side="right")
        self.status_lbl = tk.Label(
            self,
            text="Searching for game process...",
            bg="#0b111b",
            fg="#8fa2b8",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        )
        self.status_lbl.pack(side="bottom", fill="x", padx=18, pady=10)
        self.status_lbl.bind(
            "<Configure>",
            lambda event: self.status_lbl.config(wraplength=max(200, event.width - 16)),
        )

        self.session_label = tk.Label(
            self,
            text="Waiting for game",
            bg="#122b2e",
            fg="#64d8cb",
            font=("Segoe UI", 10),
            anchor="w",
            padx=16,
            pady=10,
        )
        self.session_label.pack(fill="x", padx=14)
        self.session_label.bind(
            "<Configure>",
            lambda event: self.session_label.config(wraplength=max(200, event.width - 32)),
        )
        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=8)

        self.tab_currencies = self.create_tab("Currencies")
        self.tab_combat = self.create_tab("Combat")
        self.tab_movement = self.create_tab("Movement")
        self.tab_progression = self.create_tab("Progression")
        self.tab_gear = self.create_tab("Gear & Talismans")

        self.build_currencies_tab()
        self.build_combat_tab()
        self.build_movement_tab()
        self.build_progression_tab()
        self.build_gear_talismans_tab()
        self.finish_layout()
        self.bind_all("<MouseWheel>", self.scroll_page, add="+")

    def finish_layout(self):
        def visit(widget):
            if isinstance(widget, FlowFrame) and not widget.items:
                for child in widget.winfo_children():
                    child.pack_forget()
                    widget.add(child)
            if isinstance(widget, tk.Label):
                widget.config(justify="left")
                widget.bind(
                    "<Configure>",
                    lambda event, label=widget: label.config(
                        wraplength=max(180, label.master.winfo_width() - 40)
                    ),
                )
            for child in widget.winfo_children():
                visit(child)

        for tab in (
            self.tab_currencies,
            self.tab_combat,
            self.tab_movement,
            self.tab_progression,
            self.tab_gear,
        ):
            visit(tab)
            for child in tab.winfo_children():
                if (
                    isinstance(child, tk.Frame)
                    and not getattr(child, "is_option_card", False)
                    and child.winfo_manager() == "grid"
                ):
                    child.grid_configure(sticky="ew", pady=(0, 12))
                    for control in child.winfo_children():
                        control.pack_forget()
                        control.pack(anchor="w", pady=4)

    def scroll_page(self, event):
        # Keep the gear table's own scrolling behavior when the pointer is over it.
        if event.widget == self.gear_tree:
            return
        container = self.nametowidget(self.notebook.select())
        canvas = next(w for w in container.winfo_children() if isinstance(w, tk.Canvas))
        if canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(-int(event.delta / 120), "units")

    def create_tab(self, name):
        container = tk.Frame(self.notebook, bg="#0b111b")
        self.notebook.add(container, text=name)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        canvas = tk.Canvas(container, bg="#0b111b", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")

        def update_scrollbar(scrollbar, first, last):
            scrollbar.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()

        canvas.configure(
            yscrollcommand=lambda first, last: update_scrollbar(vertical, first, last),
            xscrollcommand=lambda first, last: update_scrollbar(horizontal, first, last),
        )
        frame = tk.Frame(canvas, bg="#0b111b", padx=4, pady=12)
        frame.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window, width=max(event.width, frame.winfo_reqwidth())
            ),
        )
        frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        return frame

    def try_connect(self):
        self.reset_session()
        self.next_connect_at = time.monotonic() + 3.0
        if self.mem.attach():
            self.status_lbl.config(
                text=f"Connected (PID {self.mem.pid}); loading character...", fg="#edc58c"
            )
        else:
            self.status_lbl.config(text=self.mem.last_error, fg="#f58a92")

    # ==========================================
    # Tab 1: Currencies (Emeralds, Echo Shards, Enchantment Points with Freeze, and Gain Mult)
    # ==========================================
    def build_currencies_tab(self):
        f = self.tab_currencies

        # Emeralds (Green Gem)
        self.lbl_emeralds = self.add_row(
            f,
            0,
            "Emeralds (Green Gem):",
            "emeralds_current",
            [
                ("+1,000", lambda: self.adjust_emeralds(1000)),
                ("Max (9,999)", lambda: self.set_emeralds(9999)),
            ],
            custom_entry=True,
            setter=self.set_emeralds,
        )

        # Freeze Emeralds Row
        frz_em_frame = tk.Frame(f, bg="#131e2c", pady=2)
        frz_em_frame.grid(row=1, column=0, columnspan=5, sticky="w")
        self.btn_freeze_emeralds = tk.Button(
            frz_em_frame,
            text="FREEZE EMERALDS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=3,
            relief="flat",
            command=self.toggle_freeze_emeralds,
        )
        self.btn_freeze_emeralds.pack(side="left")
        tk.Label(
            frz_em_frame,
            text="Locks Emeralds continuously to max/current amount (Unlimited purchases)",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=10)

        # Echo Shards (SpringStone)
        self.lbl_springstone = self.add_row(
            f,
            2,
            "Echo Shards (Blue Shard):",
            "springstone_current",
            [
                ("+500", lambda: self.adjust_springstone(500)),
                ("Max (9,999)", lambda: self.set_springstone(9999)),
            ],
            custom_entry=True,
            setter=self.set_springstone,
        )

        # Freeze Echo Shards Row
        frz_sp_frame = tk.Frame(f, bg="#131e2c", pady=2)
        frz_sp_frame.grid(row=3, column=0, columnspan=5, sticky="w")
        self.btn_freeze_springstone = tk.Button(
            frz_sp_frame,
            text="FREEZE ECHO SHARDS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=3,
            relief="flat",
            command=self.toggle_freeze_springstone,
        )
        self.btn_freeze_springstone.pack(side="left")
        tk.Label(
            frz_sp_frame,
            text="Locks Echo Shards balance continuously to prevent consumption",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=10)

        # Enchantment Points
        self.lbl_ench = self.add_row(
            f,
            4,
            "Enchantment Points (Purple):",
            "ench_points_cur",
            [
                ("+5 Points", lambda: self.adjust_ench_points(5)),
                ("Set 99 Points", lambda: self.set_ench_points(99)),
            ],
            custom_entry=True,
            setter=self.set_ench_points,
        )

        # Freeze Enchantment Points Row
        frz_ep_frame = tk.Frame(f, bg="#131e2c", pady=2)
        frz_ep_frame.grid(row=5, column=0, columnspan=5, sticky="w")
        self.btn_freeze_ench = tk.Button(
            frz_ep_frame,
            text="FREEZE ENCH POINTS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=3,
            relief="flat",
            command=self.toggle_freeze_ench,
        )
        self.btn_freeze_ench.pack(side="left")
        tk.Label(
            frz_ep_frame,
            text="Locks Enchantment Points continuously so enchanting equipment never depletes points",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=10)

        # Master Freeze All Currencies Row
        frz_all_frame = tk.Frame(f, bg="#131e2c", pady=6)
        frz_all_frame.grid(row=6, column=0, columnspan=5, sticky="w")
        self.btn_freeze_all = tk.Button(
            frz_all_frame,
            text="FREEZE ALL CURRENCIES (TOGGLE)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#64d8cb",
            padx=14,
            pady=4,
            relief="flat",
            command=self.toggle_freeze_all_currencies,
        )
        self.btn_freeze_all.pack(side="left")

        # Currency Gain Multiplier
        self.lbl_curr_mult = self.add_row(
            f,
            7,
            "Currency Gain Multiplier:",
            "emerald_increase_cur",
            [
                ("2x Gain", lambda: self.set_currency_gain(2.0)),
                ("3x Gain", lambda: self.set_currency_gain(3.0)),
                ("5x Gain", lambda: self.set_currency_gain(5.0)),
                ("10x Gain", lambda: self.set_currency_gain(10.0)),
                ("Reset (1x)", lambda: self.set_currency_gain(1.0)),
            ],
            custom_entry=True,
            setter=self.set_currency_gain,
        )

    def set_emeralds(self, val):
        val = finite_float(val)
        self.mem.write_float("emeralds_cap_base", max(9999.0, val))
        self.mem.write_float("emeralds_cap_cur", max(9999.0, val))
        self.mem.write_float("emeralds_base", val)
        self.mem.write_float("emeralds_current", val)

    def adjust_emeralds(self, delta):
        cur = self.mem.require_float("emeralds_current")
        self.set_emeralds(cur + delta)

    def toggle_freeze_emeralds(self):
        self.toggle_effect("freeze_emeralds_active")

    def apply_freeze_emeralds(self):
        cap = self.mem.require_float("emeralds_cap_cur")
        val = max(cap, 9999.0)
        self.mem.write_float("emeralds_cap_base", val)
        self.mem.write_float("emeralds_cap_cur", val)
        self.mem.write_float("emeralds_base", val)
        self.mem.write_float("emeralds_current", val)

    def set_springstone(self, val):
        val = finite_float(val)
        self.mem.write_float("springstone_cap_base", max(9999.0, val))
        self.mem.write_float("springstone_cap_cur", max(9999.0, val))
        self.mem.write_float("springstone_base", val)
        self.mem.write_float("springstone_current", val)

    def adjust_springstone(self, delta):
        cur = self.mem.require_float("springstone_current")
        self.set_springstone(cur + delta)

    def toggle_freeze_springstone(self):
        self.toggle_effect("freeze_springstone_active")

    def apply_freeze_springstone(self):
        cap = self.mem.require_float("springstone_cap_cur")
        val = max(cap, 9999.0)
        self.mem.write_float("springstone_cap_base", val)
        self.mem.write_float("springstone_cap_cur", val)
        self.mem.write_float("springstone_base", val)
        self.mem.write_float("springstone_current", val)

    def set_ench_points(self, val):
        val = finite_float(val)
        self.mem.write_float("ench_points_cap_base", max(99.0, val))
        self.mem.write_float("ench_points_cap_cur", max(99.0, val))
        self.mem.write_float("ench_points_base", val)
        self.mem.write_float("ench_points_cur", val)

    def adjust_ench_points(self, delta):
        cur = self.mem.require_float("ench_points_cur")
        self.set_ench_points(cur + delta)

    def toggle_freeze_ench(self):
        self.toggle_effect("freeze_ench_active")

    def apply_freeze_ench(self):
        val = 99.0
        self.mem.write_float("ench_points_cap_base", val)
        self.mem.write_float("ench_points_cap_cur", val)
        self.mem.write_float("ench_points_base", val)
        self.mem.write_float("ench_points_cur", val)

    def toggle_freeze_all_currencies(self):
        target = not (
            self.freeze_emeralds_active
            and self.freeze_springstone_active
            and self.freeze_ench_active
        )
        if target:
            if not self.freeze_emeralds_active:
                self.toggle_freeze_emeralds()
            if not self.freeze_springstone_active:
                self.toggle_freeze_springstone()
            if not self.freeze_ench_active:
                self.toggle_freeze_ench()
        else:
            if self.freeze_emeralds_active:
                self.toggle_freeze_emeralds()
            if self.freeze_springstone_active:
                self.toggle_freeze_springstone()
            if self.freeze_ench_active:
                self.toggle_freeze_ench()

    def set_currency_gain(self, mult):
        mult = finite_float(mult)
        if mult <= 1.0:
            self.mem.write_float("emerald_increase_base", 0.0)
            self.mem.write_float("emerald_increase_cur", 0.0)
            self.mem.write_float("emerald_max_add_base", 1.0)
            self.mem.write_float("emerald_max_add_cur", 1.0)
            self.mem.write_float("emerald_drop_chance_base", 0.0)
            self.mem.write_float("emerald_drop_chance_cur", 0.0)
            self.mem.write_float("soul_gather_base", 1.0)
            self.mem.write_float("soul_gather_cur", 1.0)
        else:
            pct = mult - 1.0
            max_add = finite_float(max(1.0, mult * 5.0))
            self.mem.write_float("emerald_increase_base", pct)
            self.mem.write_float("emerald_increase_cur", pct)
            self.mem.write_float("emerald_max_add_base", max_add)
            self.mem.write_float("emerald_max_add_cur", max_add)
            self.mem.write_float("emerald_drop_chance_base", mult)
            self.mem.write_float("emerald_drop_chance_cur", mult)
            self.mem.write_float("soul_gather_base", mult)
            self.mem.write_float("soul_gather_cur", mult)

    # ==========================================
    # Tab 2: Combat (God Mode, Damage Multiplier, Potions, Stats, Souls & Freeze, Arrows & Auto-Refill, Rapid Fire)
    # ==========================================
    def build_combat_tab(self):
        f = self.tab_combat

        # God Mode Toggle Button
        god_frame = tk.Frame(f, bg="#131e2c", pady=3)
        god_frame.grid(row=0, column=0, columnspan=5, sticky="w")
        self.btn_god = tk.Button(
            god_frame,
            text="TOGGLE GOD MODE (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=14,
            pady=4,
            relief="flat",
            command=self.toggle_god_mode,
        )
        self.btn_god.pack(side="left")

        god_hint = tk.Label(
            god_frame,
            text="Keeps health and shield full while active",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        god_hint.pack(side="left", padx=10)

        # Player Damage Multiplier
        self.lbl_player_dmg = self.add_row(
            f,
            1,
            "Player Damage Multiplier:",
            "player_dmg_mult_cur",
            [
                ("2x Dmg", lambda: self.set_player_damage(2.0)),
                ("5x Dmg", lambda: self.set_player_damage(5.0)),
                ("10x Dmg", lambda: self.set_player_damage(10.0)),
                ("50x Dmg", lambda: self.set_player_damage(50.0)),
                ("One-Hit Kill", lambda: self.set_player_damage(9999.0)),
                ("Reset (1x)", lambda: self.set_player_damage(1.0)),
            ],
            custom_entry=True,
            setter=self.set_player_damage,
        )

        # Lock Player Damage Row
        lock_dmg_frame = tk.Frame(f, bg="#131e2c", pady=1)
        lock_dmg_frame.grid(row=2, column=0, columnspan=5, sticky="w")
        self.btn_lock_dmg = tk.Button(
            lock_dmg_frame,
            text="LOCK DAMAGE (OFF)",
            font=("Segoe UI", 8, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=10,
            pady=2,
            relief="flat",
            command=self.toggle_lock_player_damage,
        )
        self.btn_lock_dmg.pack(side="left")
        lbl_dmg_hint = tk.Label(
            lock_dmg_frame,
            text="Locks damage multiplier continuously so attacks/animations cannot reset multiplier",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_dmg_hint.pack(side="left", padx=10)

        # Health
        self.lbl_health = self.add_row(
            f,
            3,
            "Health (Current / Max):",
            "health_current",
            [("Full Heal", self.full_heal), ("Set 10,000 HP", lambda: self.set_health(10000))],
            custom_entry=True,
            setter=self.set_health,
        )

        # Shield
        self.lbl_shield = self.add_row(
            f,
            4,
            "Shield:",
            "shield_current",
            [("Set 1,000 Shield", lambda: self.mem.write_float("shield_current", 1000))],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("shield_current", v),
        )

        # Artifact Cooldown
        self.lbl_art_cd = self.add_row(
            f,
            5,
            "Artifact Cooldown:",
            "artifact_cd",
            [("Fast (0.05x)", self.set_instant_artifact), ("Reset (1.0x)", self.reset_artifact_cd)],
        )

        # Potion Cooldown
        self.lbl_pot_cd = self.add_row(
            f,
            6,
            "Potion Cooldown:",
            "potion_base_cd_cur",
            [("Instant (0.1s)", self.set_instant_potion), ("Reset (30s)", self.reset_potion)],
            custom_entry=True,
            setter=self.set_potion_cd,
        )

        # Infinite Potions Toggle Row
        pot_frame = tk.Frame(f, bg="#131e2c", pady=1)
        pot_frame.grid(row=7, column=0, columnspan=5, sticky="w")
        self.btn_infinite_potions = tk.Button(
            pot_frame,
            text="INFINITE POTIONS (OFF)",
            font=("Segoe UI", 8, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=10,
            pady=2,
            relief="flat",
            command=self.toggle_infinite_potions,
        )
        self.btn_infinite_potions.pack(side="left")
        lbl_pot_hint = tk.Label(
            pot_frame,
            text="Infinite Potions: Locks potion charges to 5 and auto-recharges instantly",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_pot_hint.pack(side="left", padx=10)

        # Crit Chance & Multiplier
        self.lbl_crit = self.add_row(
            f,
            8,
            "Critical Hit Chance (1.0=100%):",
            "crit_chance",
            [
                ("100% Crit", lambda: self.mem.write_float("crit_chance", 1.0)),
                ("500% Crit Dmg", lambda: self.mem.write_float("crit_multiplier", 5.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("crit_chance", v),
        )

        # Melee Attack Speed
        self.lbl_melee_spd = self.add_row(
            f,
            9,
            "Melee Attack Speed:",
            "melee_speed",
            [
                ("2x Speed", lambda: self.mem.write_float("melee_speed", 2.0)),
                ("5x Speed", lambda: self.mem.write_float("melee_speed", 5.0)),
                ("Reset", lambda: self.mem.write_float("melee_speed", 1.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("melee_speed", v),
        )

        # Melee Reach
        self.lbl_reach = self.add_row(
            f,
            10,
            "Melee Reach / Range:",
            "melee_reach",
            [
                ("Super (2500)", lambda: self.mem.write_float("melee_reach", 2500.0)),
                ("Reset (250)", lambda: self.mem.write_float("melee_reach", 250.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("melee_reach", v),
        )

        # MultiShot
        self.lbl_multi = self.add_row(
            f,
            11,
            "MultiShot (Chance & Arrows):",
            "multishot_chance",
            [("100% + 5 Arrows", self.enable_multishot)],
        )

        # Souls (Moved from Currencies to Combat)
        self.lbl_souls = self.add_row(
            f,
            12,
            "Souls (Soul Energy):",
            "souls_current",
            [
                ("+500", lambda: self.adjust_souls(500)),
                ("Max (99,999)", lambda: self.set_souls(99999)),
            ],
            custom_entry=True,
            setter=self.set_souls,
        )

        # Freeze Souls Toggle Row
        freeze_souls_frame = tk.Frame(f, bg="#131e2c", pady=1)
        freeze_souls_frame.grid(row=13, column=0, columnspan=5, sticky="w")
        self.btn_freeze_souls = tk.Button(
            freeze_souls_frame,
            text="FREEZE SOULS (OFF)",
            font=("Segoe UI", 8, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=10,
            pady=2,
            relief="flat",
            command=self.toggle_freeze_souls,
        )
        self.btn_freeze_souls.pack(side="left")
        lbl_souls_hint = tk.Label(
            freeze_souls_frame,
            text="Locks Souls to Max capacity continuously (Unlimited Soul Artifact activations)",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_souls_hint.pack(side="left", padx=10)

        # Arrows / Ammo (Moved from Currencies to Combat)
        self.lbl_ammo = self.add_row(
            f,
            14,
            "Arrows (Ammo Count):",
            "ammo_current",
            [("Refill (999)", lambda: self.set_ammo(999)), ("Max Cap (999)", self.max_ammo_cap)],
            custom_entry=True,
            setter=self.set_ammo,
        )

        # Auto-Refill Ammo Toggle Row
        refill_frame = tk.Frame(f, bg="#131e2c", pady=1)
        refill_frame.grid(row=15, column=0, columnspan=5, sticky="w")
        self.btn_auto_refill = tk.Button(
            refill_frame,
            text="AUTO-REFILL ARROWS (OFF)",
            font=("Segoe UI", 8, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=10,
            pady=2,
            relief="flat",
            command=self.toggle_auto_refill,
        )
        self.btn_auto_refill.pack(side="left")
        lbl_refill_hint = tk.Label(
            refill_frame,
            text="Infinite Arrows: Keeps ammo topped to max every game tick",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_refill_hint.pack(side="left", padx=10)

        # Rapid Fire (Moved from Currencies to Combat)
        self.lbl_rapid = self.add_row(
            f,
            16,
            "Rapid Fire (Bow Speed):",
            "rapid_fire_cur",
            [
                ("Rapid (3x)", lambda: self.set_rapid_fire(3.0)),
                ("Insane (5x)", lambda: self.set_rapid_fire(5.0)),
                ("Reset (1x)", lambda: self.set_rapid_fire(1.0)),
            ],
            custom_entry=True,
            setter=self.set_rapid_fire,
        )

    def set_player_damage(self, mult):
        mult = finite_float(mult)
        self.locked_player_dmg_val = mult
        self.apply_player_damage(mult)

    def apply_player_damage(self, mult):
        self.mem.write_float("player_dmg_mult_base", mult)
        self.mem.write_float("player_dmg_mult_cur", mult)
        self.mem.write_float("melee_damage_base", mult)
        self.mem.write_float("melee_damage_cur", mult)
        self.mem.write_float("ranged_damage_base", mult)
        self.mem.write_float("ranged_damage_cur", mult)
        self.mem.write_float("artifact_damage_base", mult)
        self.mem.write_float("artifact_damage_cur", mult)

    def toggle_lock_player_damage(self):
        self.toggle_effect("lock_player_dmg_active")

    def set_instant_artifact(self):
        self.mem.write_float("artifact_cd_base", 0.05)
        self.mem.write_float("artifact_cd", 0.05)

    def reset_artifact_cd(self):
        self.mem.write_float("artifact_cd_base", 1.0)
        self.mem.write_float("artifact_cd", 1.0)

    def set_potion_cd(self, val):
        val = finite_float(val)
        val = max(0.05, val)
        self.mem.write_float("potion_base_cd_base", val)
        self.mem.write_float("potion_base_cd_cur", val)
        self.mem.write_float("potion_cd_base", 1.0)
        self.mem.write_float("potion_cd", 1.0)
        self.mem.write_float("potion_max_charges_base", 5.0)
        self.mem.write_float("potion_max_charges_cur", 5.0)
        self.mem.write_float("potion_charges_base", 5.0)
        self.mem.write_float("potion_charges_cur", 5.0)

    def set_instant_potion(self):
        self.mem.write_float("potion_base_cd_base", 0.1)
        self.mem.write_float("potion_base_cd_cur", 0.1)
        self.mem.write_float("potion_cd_base", 0.05)
        self.mem.write_float("potion_cd", 0.05)
        self.mem.write_float("potion_max_charges_base", 5.0)
        self.mem.write_float("potion_max_charges_cur", 5.0)
        self.mem.write_float("potion_charges_base", 5.0)
        self.mem.write_float("potion_charges_cur", 5.0)

    def reset_potion(self):
        self.infinite_potions_active = False
        self.btn_infinite_potions.config(text="INFINITE POTIONS (OFF)", bg="#223146", fg="#f58a92")
        self.mem.write_float("potion_base_cd_base", 30.0)
        self.mem.write_float("potion_base_cd_cur", 30.0)
        self.mem.write_float("potion_cd_base", 1.0)
        self.mem.write_float("potion_cd", 1.0)
        self.mem.write_float("potion_max_charges_base", 1.0)
        self.mem.write_float("potion_max_charges_cur", 1.0)
        self.mem.write_float("potion_charges_base", 1.0)
        self.mem.write_float("potion_charges_cur", 1.0)

    def toggle_infinite_potions(self):
        self.toggle_effect("infinite_potions_active")

    def apply_infinite_potions(self):
        self.mem.write_float("potion_max_charges_base", 5.0)
        self.mem.write_float("potion_max_charges_cur", 5.0)
        self.mem.write_float("potion_charges_base", 5.0)
        self.mem.write_float("potion_charges_cur", 5.0)

    def toggle_god_mode(self):
        if not self.god_mode_active:
            self.apply_god_mode()
        else:
            if self._god_original and self._god_identity == self.mem.character_identity():
                resist_addr, resistance, flag_addr, flag = self._god_original
                if self.mem.resolve_chain(CHAINS["damage_resist"]) == resist_addr:
                    self.mem.write_float("damage_resist", resistance)
                if self.mem.resolve_chain(CHAINS["actor_invincible"]) == flag_addr:
                    current = self.mem.read_byte("actor_invincible")
                    if current is None:
                        raise MemoryAccessError("Cannot read actor flags.")
                    self.mem.write_byte("actor_invincible", (current & ~0x04) | (flag & 0x04))
            self._god_original = None
        self.god_mode_active = not self.god_mode_active
        if self.god_mode_active:
            self.btn_god.config(text="GOD MODE: ACTIVE (IMMUNE)", bg="#70ddb1", fg="#081c18")
        else:
            self.btn_god.config(text="TOGGLE GOD MODE (OFF)", bg="#223146", fg="#f58a92")

    def apply_god_mode(self):
        resistance_addr = self.mem.resolve_chain(CHAINS["damage_resist"])
        flag_addr = self.mem.resolve_chain(CHAINS["actor_invincible"])
        flag = self.mem.read_byte("actor_invincible")
        if not resistance_addr or not flag_addr or flag is None:
            raise MemoryAccessError("Cannot read God Mode attributes.")
        if (
            self._god_original is None
            or self._god_identity != self.mem.character_identity()
            or self._god_original[0] != resistance_addr
            or self._god_original[2] != flag_addr
        ):
            self._god_original = (
                resistance_addr,
                self.mem.require_float("damage_resist"),
                flag_addr,
                flag,
            )
            self._god_original_pid = self.mem.pid
            self._god_identity = self.mem.character_identity()
        h_max = self.mem.require_float("health_max")
        shield_max = self.mem.require_float("shield_max")
        self.mem.write_float("health_current", h_max)
        self.mem.write_float("shield_current", shield_max)
        self.mem.write_float("damage_resist", 0.0)
        # Preserve unrelated actor flags; the previous 116 -> 112 change clears bit 2.
        self.mem.write_byte("actor_invincible", flag & ~0x04)

    def full_heal(self):
        h_max = self.mem.require_float("health_max")
        self.mem.write_float("health_current", h_max)

    def set_health(self, val):
        self.mem.write_float("health_max", val)
        self.mem.write_float("health_current", val)

    def enable_multishot(self):
        self.mem.write_float("multishot_chance", 1.0)
        self.mem.write_float("multishot_count", 5.0)

    def set_souls(self, val):
        val = finite_float(val)
        self.mem.write_float("souls_cap_base", max(100.0, val))
        self.mem.write_float("souls_cap_cur", max(100.0, val))
        self.mem.write_float("souls_base", val)
        self.mem.write_float("souls_current", val)

    def adjust_souls(self, delta):
        cur = self.mem.require_float("souls_current")
        self.set_souls(cur + delta)

    def toggle_freeze_souls(self):
        self.toggle_effect("freeze_souls_active")

    def apply_freeze_souls(self):
        s_cap = self.mem.require_float("souls_cap_cur")
        s_val = max(s_cap, 99999.0)
        self.mem.write_float("souls_cap_base", s_val)
        self.mem.write_float("souls_cap_cur", s_val)
        self.mem.write_float("souls_base", s_val)
        self.mem.write_float("souls_current", s_val)

    def set_ammo(self, val):
        val = finite_float(val)
        cur_max = self.mem.require_float("ammo_max_cur")
        if val > cur_max:
            self.mem.write_float("ammo_max_base", val)
            self.mem.write_float("ammo_max_cur", val)
        self.mem.write_float("ammo_base", val)
        self.mem.write_float("ammo_current", val)

    def max_ammo_cap(self):
        self.mem.write_float("ammo_max_base", 999.0)
        self.mem.write_float("ammo_max_cur", 999.0)
        self.mem.write_float("ammo_base", 999.0)
        self.mem.write_float("ammo_current", 999.0)

    def toggle_auto_refill(self):
        self.toggle_effect("auto_refill_ammo_active")

    def apply_auto_refill(self):
        m = self.mem.require_float("ammo_max_cur")
        m = max(m, 999.0)
        self.mem.write_float("ammo_max_base", m)
        self.mem.write_float("ammo_max_cur", m)
        self.mem.write_float("ammo_base", m)
        self.mem.write_float("ammo_current", m)

    def set_rapid_fire(self, spd):
        spd = finite_float(spd)
        self.mem.write_float("rapid_fire_base", spd)
        self.mem.write_float("rapid_fire_cur", spd)

    # ==========================================
    # Tab 3: Movement
    # ==========================================
    def build_movement_tab(self):
        f = self.tab_movement

        # Movement Speed Multiplier
        self.lbl_move_mult = self.add_row(
            f,
            0,
            "Speed Multiplier (GAS):",
            "move_mult_cur",
            [
                ("1.5x", lambda: self.set_speed(1.5)),
                ("2.0x", lambda: self.set_speed(2.0)),
                ("3.0x", lambda: self.set_speed(3.0)),
                ("Reset (1.0)", lambda: self.set_speed(1.0)),
            ],
            custom_entry=True,
            setter=self.set_speed,
        )

        # Lock Speed Multiplier Toggle Row
        speed_lock_frame = tk.Frame(f, bg="#131e2c", pady=2)
        speed_lock_frame.grid(row=1, column=0, columnspan=5, sticky="w")
        self.btn_lock_speed = tk.Button(
            speed_lock_frame,
            text="LOCK SPEED (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
            relief="flat",
            command=self.toggle_lock_speed,
        )
        self.btn_lock_speed.pack(side="left")
        lbl_speed_hint = tk.Label(
            speed_lock_frame,
            text="Locks speed multiplier so attacks / montages cannot reset speed to 1.0",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_speed_hint.pack(side="left", padx=10)

        # Jump Height
        self.lbl_jump = self.add_row(
            f,
            2,
            "Jump Height (Default: 1440):",
            "jump_velocity",
            [
                ("High (2200)", lambda: self.mem.write_float("jump_velocity", 2200.0)),
                ("Super (3000)", lambda: self.mem.write_float("jump_velocity", 3000.0)),
                ("Reset (1440)", lambda: self.mem.write_float("jump_velocity", 1440.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("jump_velocity", v),
        )

        # Gravity Scale
        self.lbl_grav = self.add_row(
            f,
            3,
            "Gravity Scale (Default: 1.2):",
            "gravity",
            [
                ("Moon (0.4)", lambda: self.mem.write_float("gravity", 0.4)),
                ("Low (0.7)", lambda: self.mem.write_float("gravity", 0.7)),
                ("Reset (1.2)", lambda: self.mem.write_float("gravity", 1.2)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("gravity", v),
        )

        # Roll Cooldown
        self.lbl_roll = self.add_row(
            f,
            4,
            "Roll Cooldown:",
            "roll_cd",
            [("Instant Roll (0.1s)", self.set_instant_roll), ("Reset (2.5s)", self.reset_roll)],
            custom_entry=True,
            setter=self.set_roll_cd,
        )

        # Infinite Roll Toggle Row
        roll_frame = tk.Frame(f, bg="#131e2c", pady=2)
        roll_frame.grid(row=5, column=0, columnspan=5, sticky="w")
        self.btn_infinite_roll = tk.Button(
            roll_frame,
            text="INFINITE ROLL (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
            relief="flat",
            command=self.toggle_infinite_roll,
        )
        self.btn_infinite_roll.pack(side="left")
        lbl_roll_hint = tk.Label(
            roll_frame,
            text="Infinite Roll: Continually keeps roll charges at 5 for nonstop tumbling",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_roll_hint.pack(side="left", padx=10)

        # Time Dilation
        self.lbl_time = self.add_row(
            f,
            6,
            "Time Dilation (Game Speed):",
            "time_dilation",
            [
                ("1.25x", lambda: self.mem.write_float("time_dilation", 1.25)),
                ("1.5x", lambda: self.mem.write_float("time_dilation", 1.5)),
                ("Reset (1.0)", lambda: self.mem.write_float("time_dilation", 1.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("time_dilation", v),
        )

    def set_roll_cd(self, val):
        val = finite_float(val)
        val = max(0.05, val)
        self.mem.write_float("roll_cd_base", val)
        self.mem.write_float("roll_cd", val)
        self.mem.write_float("roll_max_charges_base", 5.0)
        self.mem.write_float("roll_max_charges_cur", 5.0)
        self.mem.write_float("roll_charges_base", 5.0)
        self.mem.write_float("roll_charges_cur", 5.0)

    def set_instant_roll(self):
        self.mem.write_float("roll_cd_base", 0.1)
        self.mem.write_float("roll_cd", 0.1)
        self.mem.write_float("roll_max_charges_base", 5.0)
        self.mem.write_float("roll_max_charges_cur", 5.0)
        self.mem.write_float("roll_charges_base", 5.0)
        self.mem.write_float("roll_charges_cur", 5.0)

    def reset_roll(self):
        self.infinite_roll_active = False
        self.btn_infinite_roll.config(text="INFINITE ROLL (OFF)", bg="#223146", fg="#f58a92")
        self.mem.write_float("roll_cd_base", 2.5)
        self.mem.write_float("roll_cd", 2.5)
        self.mem.write_float("roll_max_charges_base", 1.0)
        self.mem.write_float("roll_max_charges_cur", 1.0)
        self.mem.write_float("roll_charges_base", 1.0)
        self.mem.write_float("roll_charges_cur", 1.0)

    def toggle_infinite_roll(self):
        self.toggle_effect("infinite_roll_active")

    def apply_infinite_roll(self):
        self.mem.write_float("roll_max_charges_base", 5.0)
        self.mem.write_float("roll_max_charges_cur", 5.0)
        self.mem.write_float("roll_charges_base", 5.0)
        self.mem.write_float("roll_charges_cur", 5.0)

    def set_speed(self, val):
        val = finite_float(val)
        self.locked_speed_val = val
        self.mem.write_float("move_mult_base", val)
        self.mem.write_float("move_mult_cur", val)

    def toggle_lock_speed(self):
        self.toggle_effect("lock_speed_active")

    def apply_lock_speed(self):
        self.mem.write_float("move_mult_base", self.locked_speed_val)
        self.mem.write_float("move_mult_cur", self.locked_speed_val)

    # ==========================================
    # Tab 4: Progression
    # ==========================================
    def build_progression_tab(self):
        f = self.tab_progression

        # XP Gain Multiplier (Yield)
        self.lbl_xp_gain = self.add_row(
            f,
            0,
            "XP Gain Multiplier (Yield):",
            "xp_gain_mult_cur",
            [
                ("2x XP", lambda: self.set_xp_gain(2.0)),
                ("5x XP", lambda: self.set_xp_gain(5.0)),
                ("10x XP", lambda: self.set_xp_gain(10.0)),
                ("25x XP", lambda: self.set_xp_gain(25.0)),
                ("50x XP", lambda: self.set_xp_gain(50.0)),
                ("Reset (1x)", lambda: self.set_xp_gain(1.0)),
            ],
            custom_entry=True,
            setter=self.set_xp_gain,
        )

        # Lock XP Multiplier Toggle Row
        lock_xp_frame = tk.Frame(f, bg="#131e2c", pady=2)
        lock_xp_frame.grid(row=1, column=0, columnspan=5, sticky="w")
        self.btn_lock_xp = tk.Button(
            lock_xp_frame,
            text="LOCK XP MULT (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
            relief="flat",
            command=self.toggle_lock_xp_gain,
        )
        self.btn_lock_xp.pack(side="left")
        lbl_xp_hint = tk.Label(
            lock_xp_frame,
            text="Keeps the XP multiplier active for this character; changing character stops the lock",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_xp_hint.pack(side="left", padx=10)

        # Master Loot Multiplier
        self.lbl_master_loot = self.add_row(
            f,
            2,
            "Master Loot Multiplier:",
            "loot_multiplier",
            [
                ("2x Loot", lambda: self.set_master_loot(2.0)),
                ("3x Loot", lambda: self.set_master_loot(3.0)),
                ("5x Loot", lambda: self.set_master_loot(5.0)),
                ("10x Loot", lambda: self.set_master_loot(10.0)),
                ("Reset (1x)", lambda: self.set_master_loot(1.0)),
            ],
            custom_entry=True,
            setter=self.set_master_loot,
        )

        # Drop Duplication Chance
        self.lbl_dup = self.add_row(
            f,
            3,
            "Drop Duplication Chance:",
            "drop_duplication",
            [
                ("2x (100%)", lambda: self.set_drop_duplication(1.0)),
                ("3x (200%)", lambda: self.set_drop_duplication(2.0)),
                ("5x (400%)", lambda: self.set_drop_duplication(4.0)),
                ("10x (900%)", lambda: self.set_drop_duplication(9.0)),
                ("Reset (0%)", lambda: self.set_drop_duplication(0.0)),
            ],
            custom_entry=True,
            setter=self.set_drop_duplication,
        )

        # Max Loot Payouts Cap
        self.lbl_max_payouts = self.add_row(
            f,
            4,
            "Max Loot Payouts Cap:",
            "max_payouts_cur",
            [
                ("Default (1)", lambda: self.set_max_payouts(1.0)),
                ("5 Payouts", lambda: self.set_max_payouts(5.0)),
                ("10 Payouts", lambda: self.set_max_payouts(10.0)),
                ("50 Payouts", lambda: self.set_max_payouts(50.0)),
            ],
            custom_entry=True,
            setter=self.set_max_payouts,
        )

        # Looting Drop Multiplier
        self.lbl_loot = self.add_row(
            f,
            5,
            "Looting Drop Multiplier:",
            "loot_multiplier",
            [
                ("5x Drops", lambda: self.set_looting_multiplier(5.0)),
                ("10x Drops", lambda: self.set_looting_multiplier(10.0)),
                ("25x Drops", lambda: self.set_looting_multiplier(25.0)),
                ("Reset (0)", lambda: self.set_looting_multiplier(0.0)),
            ],
            custom_entry=True,
            setter=self.set_looting_multiplier,
        )

        # Rarity Bonus Chance
        self.lbl_rarity = self.add_row(
            f,
            6,
            "Rarity Bonus Chance:",
            "rarity_bonus",
            [
                ("100% Unique/Rare", lambda: self.set_rarity_bonus(1.0)),
                ("Reset (0)", lambda: self.set_rarity_bonus(0.0)),
            ],
            custom_entry=True,
            setter=self.set_rarity_bonus,
        )

        # Character Level
        self.lbl_level = self.add_row(
            f,
            7,
            "Character Level:",
            "level",
            [
                ("Level 50", lambda: self.mem.write_float("level", 50.0)),
                ("Level 100", lambda: self.mem.write_float("level", 100.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("level", v),
        )

        # Current XP
        self.lbl_xp = self.add_row(
            f,
            8,
            "Current XP:",
            "xp_current",
            [
                ("+10,000 XP", lambda: self.adjust_xp(10000.0)),
                ("+50,000 XP", lambda: self.adjust_xp(50000.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("xp_current", v),
        )

        # Vendors
        self.lbl_vendor = self.add_row(
            f,
            9,
            "Vendor Upgrades & Restock:",
            "merchant_charges",
            [("Max All Vendors", self.max_all_vendors)],
        )

    def set_xp_gain(self, mult):
        mult = finite_float(mult)
        self.locked_xp_gain_val = mult
        self.apply_xp_gain(mult)

    def apply_xp_gain(self, mult):
        self.mem.write_float("xp_gain_mult_base", mult)
        self.mem.write_float("xp_gain_mult_cur", mult)

    def toggle_lock_xp_gain(self):
        self.toggle_effect("lock_xp_gain_active")

    def set_master_loot(self, mult):
        mult = finite_float(mult)
        if mult <= 1.0:
            self.mem.write_float("drop_dup_base", 0.0)
            self.mem.write_float("drop_duplication", 0.0)
            self.mem.write_float("max_payouts_base", 1.0)
            self.mem.write_float("max_payouts_cur", 1.0)
            self.mem.write_float("loot_mult_base", 0.0)
            self.mem.write_float("loot_multiplier", 0.0)
            self.mem.write_float("drop_chance_base", 0.0)
            self.mem.write_float("drop_chance", 0.0)
        else:
            dup_val = mult - 1.0
            payout_val = mult
            self.mem.write_float("drop_dup_base", dup_val)
            self.mem.write_float("drop_duplication", dup_val)
            self.mem.write_float("max_payouts_base", payout_val)
            self.mem.write_float("max_payouts_cur", payout_val)
            self.mem.write_float("loot_mult_base", mult)
            self.mem.write_float("loot_multiplier", mult)
            self.mem.write_float("drop_chance_base", mult)
            self.mem.write_float("drop_chance", mult)

    def set_drop_duplication(self, val):
        val = finite_float(val)
        self.mem.write_float("drop_dup_base", val)
        self.mem.write_float("drop_duplication", val)
        cur_payouts = self.mem.require_float("max_payouts_cur")
        needed = max(1.0, val + 1.0)
        if cur_payouts < needed:
            self.mem.write_float("max_payouts_base", needed)
            self.mem.write_float("max_payouts_cur", needed)

    def set_max_payouts(self, val):
        val = finite_float(val)
        self.mem.write_float("max_payouts_base", val)
        self.mem.write_float("max_payouts_cur", val)

    def set_looting_multiplier(self, val):
        val = finite_float(val)
        self.mem.write_float("loot_mult_base", val)
        self.mem.write_float("loot_multiplier", val)

    def set_rarity_bonus(self, val):
        val = finite_float(val)
        self.mem.write_float("rarity_bonus_base", val)
        self.mem.write_float("rarity_bonus", val)

    def adjust_xp(self, delta):
        cur = self.mem.require_float("xp_current")
        self.mem.write_float("xp_current", cur + delta)

    def max_all_vendors(self):
        self.mem.write_float("merchant_charges", 99.0)
        self.mem.write_float("merchant_upg", 3.0)
        self.mem.write_float("enchantsmith_upg", 3.0)
        self.mem.write_float("blacksmith_upg", 3.0)

    # ==========================================
    # Tab 5: Gear & Talismans
    # ==========================================
    def build_gear_talismans_tab(self):
        f = self.tab_gear

        # --- Card 1: Talismans Growth & Max Out ---
        tal_card = tk.LabelFrame(
            f,
            text=" TALISMANS PROGRESSION & GROWTH ",
            bg="#131e2c",
            fg="#64d8cb",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=10,
        )
        tal_card.pack(fill="x", pady=(0, 10))

        # Growth Multiplier Row
        t_row = FlowFrame(tal_card, bg="#131e2c")
        t_row.pack(fill="x", pady=4)

        tk.Label(
            t_row,
            text="Growth Multiplier:",
            bg="#131e2c",
            fg="#e6eef8",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 10))
        self.lbl_tal_growth_val = tk.Label(
            t_row,
            text="1.0x",
            bg="#131e2c",
            fg="#f9e2af",
            font=("Consolas", 10, "bold"),
            width=9,
            anchor="w",
        )
        self.lbl_tal_growth_val.pack(side="left", padx=(0, 8))

        self.tal_entry_var = tk.StringVar()
        tal_entry = tk.Entry(
            t_row,
            textvariable=self.tal_entry_var,
            width=6,
            bg="#223146",
            fg="#e6eef8",
            insertbackground="#e6eef8",
            relief="flat",
            font=("Consolas", 9),
        )
        tal_entry.pack(side="left", padx=(0, 4))

        def on_set_tal_growth():
            val = self.tal_entry_var.get().strip()
            if val:
                try:
                    self.set_talisman_growth(float(val))
                except (ValueError, MemoryAccessError, OverflowError) as exc:
                    self.show_error(exc)

        ttk.Button(t_row, text="Set", command=on_set_tal_growth, width=4).pack(
            side="left", padx=(0, 8)
        )

        for text, mult in [
            ("2x", 2.0),
            ("5x", 5.0),
            ("10x", 10.0),
            ("25x", 25.0),
            ("50x", 50.0),
            ("Reset (1x)", 1.0),
        ]:
            ttk.Button(t_row, text=text, command=lambda m=mult: self.set_talisman_growth(m)).pack(
                side="left", padx=3
            )

        # Talisman Action Buttons
        t_act_row = FlowFrame(tal_card, bg="#131e2c")
        t_act_row.pack(fill="x", pady=6)

        btn_max_tal = tk.Button(
            t_act_row,
            text="MAX OUT EQUIPPED TALISMANS",
            font=("Segoe UI", 9, "bold"),
            bg="#70ddb1",
            fg="#11111b",
            padx=12,
            pady=4,
            relief="flat",
            command=self.max_out_equipped_talismans,
        )
        btn_max_tal.pack(side="left", padx=(0, 8))

        btn_max_all_tal = tk.Button(
            t_act_row,
            text="MAX ALL TALISMANS (INVENTORY)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#64d8cb",
            padx=12,
            pady=4,
            relief="flat",
            command=self.max_out_all_talismans,
        )
        btn_max_all_tal.pack(side="left", padx=(0, 8))

        btn_add_tal_xp = ttk.Button(
            t_act_row, text="+10,000 XP To Talismans", command=self.add_xp_to_talismans
        )
        btn_add_tal_xp.pack(side="left", padx=3)

        lbl_tal_hint = tk.Label(
            tal_card,
            text="Talisman XP gains in combat are auto-scaled in real-time. Max Out writes rank/XP; perk activation and persistence require in-game verification.",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_tal_hint.pack(anchor="w", pady=(2, 0))

        # --- Card 2: Current Equipped Gear Editor ---
        gear_card = tk.LabelFrame(
            f,
            text=" CURRENT EQUIPPED GEAR EDITOR ",
            bg="#131e2c",
            fg="#64d8cb",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=10,
        )
        gear_card.pack(fill="both", expand=True)

        # Batch Operations Header
        batch_row = FlowFrame(gear_card, bg="#131e2c")
        batch_row.pack(fill="x", pady=(0, 8))

        ttk.Button(
            batch_row,
            text="Quick Max Power (100)",
            command=lambda: self.batch_set_gear_power(100.0),
        ).pack(side="left", padx=3)
        ttk.Button(
            batch_row,
            text="Super Max Power (250)",
            command=lambda: self.batch_set_gear_power(250.0),
        ).pack(side="left", padx=3)
        ttk.Button(batch_row, text="Make All Special", command=self.batch_make_gear_special).pack(
            side="left", padx=3
        )
        ttk.Button(batch_row, text="Refresh Gear List", command=self.refresh_gear_table).pack(
            side="right", padx=3
        )

        # Treeview Table
        tree_frame = tk.Frame(gear_card, bg="#0b111b")
        tree_frame.pack(fill="both", expand=True, pady=4)

        columns = ("slot", "name", "power", "rarity", "progress")
        self.gear_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", style="Gear.Treeview", height=8
        )
        self.gear_tree.heading("slot", text="Equipped Slot")
        self.gear_tree.heading("name", text="Item Name")
        self.gear_tree.heading("power", text="Power Level")
        self.gear_tree.heading("rarity", text="Rarity")
        self.gear_tree.heading("progress", text="Talisman Rank / XP")

        self.gear_tree.column("slot", width=170, anchor="w")
        self.gear_tree.column("name", width=210, anchor="w")
        self.gear_tree.column("power", width=100, anchor="center")
        self.gear_tree.column("rarity", width=110, anchor="center")
        self.gear_tree.column("progress", width=180, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.gear_tree.yview)
        self.gear_tree.configure(yscrollcommand=tree_scroll.set)

        self.gear_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.gear_tree.bind("<<TreeviewSelect>>", self.on_gear_item_selected)

        # Selected Item Controls Bar
        self.sel_frame = tk.Frame(gear_card, bg="#131e2c", pady=8)
        self.sel_frame.pack(fill="x")

        self.lbl_selected_item = tk.Label(
            self.sel_frame,
            text="Select an item above to customize its Power and Rarity",
            bg="#131e2c",
            fg="#f9e2af",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_selected_item.pack(anchor="w", pady=(0, 6))

        ctrl_row = FlowFrame(self.sel_frame, bg="#131e2c")
        ctrl_row.pack(fill="x")

        tk.Label(
            ctrl_row, text="Power:", bg="#131e2c", fg="#e6eef8", font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(0, 6))
        self.gear_power_var = tk.StringVar()
        self.entry_gear_power = tk.Entry(
            ctrl_row,
            textvariable=self.gear_power_var,
            width=7,
            bg="#223146",
            fg="#e6eef8",
            insertbackground="#e6eef8",
            relief="flat",
            font=("Consolas", 9),
        )
        self.entry_gear_power.pack(side="left", padx=(0, 4))
        ttk.Button(ctrl_row, text="Set", command=self.on_set_selected_power, width=4).pack(
            side="left", padx=(0, 8)
        )

        for text, val in [
            ("+10", 10),
            ("+25", 25),
            ("Set 50", 50),
            ("Set 100", 100),
            ("Set 250", 250),
        ]:
            ttk.Button(
                ctrl_row, text=text, command=lambda v=val: self.adjust_selected_power(v)
            ).pack(side="left", padx=2)

        tk.Label(
            ctrl_row, text=" |  Rarity:", bg="#131e2c", fg="#e6eef8", font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(8, 6))
        ttk.Button(
            ctrl_row, text="Make Special", command=lambda: self.set_selected_rarity("Special")
        ).pack(side="left", padx=2)
        ttk.Button(
            ctrl_row, text="Make Rare", command=lambda: self.set_selected_rarity("Rare")
        ).pack(side="left", padx=2)
        ttk.Button(
            ctrl_row, text="Make Common", command=lambda: self.set_selected_rarity("Common")
        ).pack(side="left", padx=2)

    def set_talisman_growth(self, mult):
        mult = finite_float(mult)
        if mult < 1:
            raise ValueError("Growth multiplier must be at least 1.")
        self.talisman_growth_mult = mult
        self.last_talisman_xp.clear()
        self.lbl_tal_growth_val.config(text=f"{self.talisman_growth_mult:.1f}x")

    def max_out_equipped_talismans(self):
        cnt = self.mem.max_out_talismans(only_equipped=True)
        self.refresh_gear_table()
        if cnt > 0:
            messagebox.showinfo(
                "Talismans Maxed",
                f"Wrote rank/XP for {cnt} equipped talisman(s) to Max Rank & 100k XP!",
            )

    def max_out_all_talismans(self):
        cnt = self.mem.max_out_talismans(only_equipped=False)
        self.refresh_gear_table()
        if cnt > 0:
            messagebox.showinfo(
                "Talismans Maxed",
                f"Wrote rank/XP for {cnt} talisman(s) across equipment and inventory!",
            )

    def add_xp_to_talismans(self):
        items = self.mem.get_equipped_gear()
        for it in items:
            if it["is_talisman"]:
                addr = it["item_addr"]
                cur_xp = self.mem.read_f32(addr + 0x6C)
                self.mem.set_talisman_xp(it, cur_xp + 10000.0)
        self.refresh_gear_table()

    def refresh_gear_table(self):
        if not self.mem.h_proc:
            return
        selected_slot = None
        sel = self.gear_tree.selection()
        if sel:
            selected_slot = self.gear_tree.item(sel[0], "values")[0]

        self.selected_gear_item = None
        self.lbl_selected_item.config(text="Select an item to edit its power and rarity")
        for row in self.gear_tree.get_children():
            self.gear_tree.delete(row)

        self.current_gear_cache = self.mem.get_equipped_gear()
        for it in self.current_gear_cache:
            pwr_str = f"{it['power']:.1f}" if it["power"] > 0 else "---"
            prog_str = (
                f"Rank {it['level'] + 1} ({it['xp']:,.0f} XP)" if it["is_talisman"] else "---"
            )
            item_id = self.gear_tree.insert(
                "", "end", values=(it["label"], it["name"], pwr_str, it["rarity"], prog_str)
            )
            if selected_slot and it["label"] == selected_slot:
                self.gear_tree.selection_set(item_id)
                self.on_gear_item_selected(None)

    def on_gear_item_selected(self, event):
        sel = self.gear_tree.selection()
        if not sel:
            self.selected_gear_item = None
            self.lbl_selected_item.config(
                text="Select an item above to customize its Power and Rarity"
            )
            return
        vals = self.gear_tree.item(sel[0], "values")
        slot_label = vals[0]
        for it in getattr(self, "current_gear_cache", []):
            if it["label"] == slot_label:
                self.selected_gear_item = it
                self.gear_power_var.set(str(int(it["power"]) if it["power"] > 0 else 50))
                pwr_disp = f"Power: {it['power']:.1f}" if it["power"] > 0 else "Talisman Item"
                self.lbl_selected_item.config(
                    text=f"Selected: {it['name']} ({it['label']}) - {pwr_disp}, Rarity: {it['rarity']}"
                )
                break

    def on_set_selected_power(self):
        if not self.selected_gear_item:
            return
        val = self.gear_power_var.get().strip()
        if val:
            try:
                pwr = finite_float(val)
                self.mem.set_gear_power(
                    self.selected_gear_item["item_addr"],
                    self.selected_gear_item["slot_tag"],
                    pwr,
                    expected=self.selected_gear_item,
                )
                self.refresh_gear_table()
            except (ValueError, MemoryAccessError, OverflowError) as exc:
                self.show_error(exc)

    def adjust_selected_power(self, val):
        if not self.selected_gear_item:
            return
        if val in [50, 100, 250]:
            pwr = finite_float(val)
        else:
            current = self.mem.require_item(
                self.selected_gear_item["item_addr"], self.selected_gear_item
            )
            cur = current["power"]
            pwr = max(1.0, (cur if cur > 0 else 10.0) + val)
        self.mem.set_gear_power(
            self.selected_gear_item["item_addr"],
            self.selected_gear_item["slot_tag"],
            pwr,
            expected=self.selected_gear_item,
        )
        self.refresh_gear_table()

    def set_selected_rarity(self, rarity_name):
        if not self.selected_gear_item:
            return
        self.mem.set_gear_rarity(
            self.selected_gear_item["item_addr"], rarity_name, expected=self.selected_gear_item
        )
        self.refresh_gear_table()

    def batch_set_gear_power(self, power_val):
        items = self.mem.get_equipped_gear()
        for it in items:
            if not it["is_talisman"]:
                self.mem.set_gear_power(it["item_addr"], it["slot_tag"], power_val, expected=it)
        self.refresh_gear_table()

    def batch_make_gear_special(self):
        items = self.mem.get_equipped_gear()
        for it in items:
            if not it["is_talisman"]:
                self.mem.set_gear_rarity(it["item_addr"], "Special", expected=it)
        self.refresh_gear_table()

    # ==========================================
    # GUI Helpers
    # ==========================================
    def add_row(
        self,
        parent,
        row_idx,
        label_text,
        key,
        buttons,
        custom_entry=False,
        is_byte=False,
        setter=None,
    ):
        short_titles = {
            "emeralds_current": "Emeralds",
            "springstone_current": "Echo Shards",
            "ench_points_cur": "Enchantment points",
            "emerald_increase_cur": "Currency gain multiplier (Emeralds & Souls)",
            "souls_current": "Soul energy",
            "ammo_current": "Arrow supply",
            "rapid_fire_cur": "Bow attack speed",
            "health_current": "Health",
            "shield_current": "Shield",
            "artifact_cd": "Artifact cooldown",
            "potion_base_cd_cur": "Potion cooldown",
            "crit_chance": "Critical hit chance",
            "melee_speed": "Melee attack speed",
            "melee_reach": "Melee reach",
            "multishot_chance": "Multishot",
            "move_mult_cur": "Movement speed",
            "jump_velocity": "Jump height",
            "gravity": "Gravity",
            "roll_cd": "Roll cooldown",
            "time_dilation": "Player time scale",
            "level": "Character level",
            "xp_current": "Experience",
            "camera_fov": "Field of view",
        }
        card = tk.Frame(
            parent,
            bg="#131e2c",
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground="#223146",
        )
        card.is_option_card = True
        card.grid(row=row_idx, column=0, columnspan=5, sticky="ew", pady=(0, 12))
        card.columnconfigure(0, weight=1)
        tk.Label(
            card,
            text=short_titles.get(key, label_text.rstrip(":")),
            bg="#131e2c",
            fg="#e6eef8",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        lbl_val = tk.Label(
            card,
            text="\u2014",
            bg="#131e2c",
            fg="#64d8cb",
            font=("Segoe UI", 13, "bold"),
            anchor="e",
        )
        lbl_val.grid(row=0, column=1, sticky="e")
        controls = FlowFrame(card, bg="#131e2c")
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        if custom_entry:
            input_group = tk.Frame(controls, bg="#131e2c")
            tk.Label(
                input_group, text="Custom", bg="#131e2c", fg="#8fa2b8", font=("Segoe UI", 9)
            ).pack(side="left", padx=(0, 8))
            entry_var = tk.StringVar()
            entry = tk.Entry(
                input_group,
                textvariable=entry_var,
                width=9,
                bg="#0b111b",
                fg="#e6eef8",
                insertbackground="#e6eef8",
                relief="flat",
                font=("Segoe UI", 11),
                highlightthickness=1,
                highlightbackground="#344b64",
                highlightcolor="#64d8cb",
            )
            entry.pack(side="left", padx=(0, 8), ipady=6)

            def on_set():
                val = entry_var.get().strip()
                if val:
                    try:
                        num = finite_float(val) if not is_byte else int(val)
                        if setter:
                            setter(num)
                        elif is_byte:
                            self.mem.write_byte(key, num)
                        else:
                            self.mem.write_float(key, num)
                    except (ValueError, OverflowError) as exc:
                        messagebox.showerror("Invalid value", str(exc), parent=self)

            entry.bind("<Return>", lambda event: on_set())
            ttk.Button(input_group, text="Apply", command=on_set, style="Accent.TButton").pack(
                side="left"
            )
            controls.add(input_group)
        for text, cmd in buttons:
            controls.add(ttk.Button(controls, text=text, command=cmd))
        row = (lbl_val, key, is_byte)
        self.value_rows.append(row)
        return row

    def show_error(self, error):
        self.status_lbl.config(text=str(error), fg="#f58a92")

    def report_callback_exception(self, exc_type, exc_value, traceback):
        self.show_error(exc_value)
        if not isinstance(exc_value, (MemoryAccessError, ValueError, OverflowError)):
            super().report_callback_exception(exc_type, exc_value, traceback)

    def toggle_effect(self, flag):
        _, button_name, label, method = next(
            item for item in self.effect_controls if item[0] == flag
        )
        button = getattr(self, button_name)
        if getattr(self, flag):
            setattr(self, flag, False)
            button.config(text=f"{label} (OFF)", bg="#223146", fg="#f58a92")
            if flag == "infinite_potions_active":
                self.reset_potion()
            elif flag == "infinite_roll_active":
                self.reset_roll()
            return
        locks = {
            "lock_speed_active": ("move_mult_cur", "locked_speed_val"),
            "lock_player_dmg_active": ("player_dmg_mult_cur", "locked_player_dmg_val"),
            "lock_xp_gain_active": ("xp_gain_mult_cur", "locked_xp_gain_val"),
        }
        if flag in locks:
            key, attribute = locks[flag]
            setattr(self, attribute, self.mem.require_float(key))
        if flag == "infinite_potions_active":
            self.set_instant_potion()
        elif flag == "infinite_roll_active":
            self.set_instant_roll()
        getattr(self, method)()
        setattr(self, flag, True)
        state = "FROZEN" if flag.startswith("freeze_") else "ON"
        button.config(text=f"{label}: {state}", bg="#70ddb1", fg="#081c18")

    def reset_effects(self):
        for flag, button, label, method in self.effect_controls:
            setattr(self, flag, False)
            getattr(self, button).config(text=f"{label} (OFF)", bg="#223146", fg="#f58a92")
        self._god_original = None
        self._god_original_pid = None
        self._god_identity = None

    def reset_session(self):
        self.reset_effects()
        self.session_identity = None
        self.session_kind = "disconnected"
        self.selected_gear_item = None
        self.current_gear_cache = []
        self.last_talisman_xp.clear()
        self.talisman_growth_mult = 1.0
        self.lbl_tal_growth_val.config(text="1.0x")
        for row in self.gear_tree.get_children():
            self.gear_tree.delete(row)
        self.lbl_selected_item.config(text="Refresh the gear list after loading a character")
        for label, key, is_byte in self.value_rows:
            label.config(text="---")

    def apply_locked_damage(self):
        self.apply_player_damage(self.locked_player_dmg_val)

    def apply_locked_xp(self):
        self.apply_xp_gain(self.locked_xp_gain_val)

    def update_talisman_growth(self):
        if self.talisman_growth_mult <= 1:
            self.last_talisman_xp.clear()
            return
        history = {}
        for item in self.mem.get_equipped_gear():
            if not item["is_talisman"]:
                continue
            key = (item["identity"], item["slot_tag"], item["item_addr"], item["name_index"])
            xp = item["xp"]
            previous = self.last_talisman_xp.get(key)
            if previous is not None and xp > previous:
                xp = finite_float(xp + (xp - previous) * (self.talisman_growth_mult - 1))
                self.mem.set_talisman_xp(item, xp)
            history[key] = xp
        self.last_talisman_xp = history

    def refresh_values(self):
        if not self.mem.is_alive():
            self.reset_session()
            if time.monotonic() >= self.next_connect_at:
                self.try_connect()
            self.session_label.config(text="DISCONNECTED - launch the game and load a character")
            return
        identity = self.mem.character_identity()
        kind = self.mem.session_kind()
        if identity != self.session_identity or kind != self.session_kind:
            self.reset_session()
            self.session_identity = identity
            self.session_kind = kind
            self.status_lbl.config(
                text=f"Connected (PID {self.mem.pid}); character/session changed, effects reset.",
                fg="#8fa2b8",
            )
        labels = {
            "client": "MULTIPLAYER - all commands available; server-managed changes may be ignored",
            "local": "LOCAL AUTHORITY - solo or host; effects depend on game compatibility",
            "loading": "LOADING CHARACTER - waiting for readable values",
            "unknown": "UNKNOWN SESSION - check game compatibility",
            "disconnected": "DISCONNECTED - waiting for the game",
        }
        self.session_label.config(text=labels[kind])
        if identity is None or kind not in ("local", "client"):
            return
        errors = []
        for flag, button, label, method in self.effect_controls:
            if getattr(self, flag):
                try:
                    getattr(self, method)()
                except (MemoryAccessError, ValueError, OverflowError) as exc:
                    setattr(self, flag, False)
                    getattr(self, button).config(
                        text=f"{label} (ERROR)", bg="#223146", fg="#f58a92"
                    )
                    errors.append(f"{label}: {exc}")
        try:
            self.update_talisman_growth()
        except (MemoryAccessError, ValueError, OverflowError) as exc:
            self.last_talisman_xp.clear()
            self.talisman_growth_mult = 1.0
            self.lbl_tal_growth_val.config(text="1.0x (stopped)")
            errors.append(str(exc))
        for label, key, is_byte in self.value_rows:
            value = self.mem.read_byte(key) if is_byte else self.mem.read_float(key)
            if value is None:
                text = "---"
            elif key == "emerald_increase_cur":
                text = f"{value + 1:.1f}x"
            elif key in ("player_dmg_mult_cur", "xp_gain_mult_cur"):
                text = f"{value:.1f}x"
            else:
                text = f"{value:,.2f}".rstrip("0").rstrip(".")
            label.config(text=text)
        if errors:
            self.show_error(" | ".join(errors))

    def refresh_loop(self):
        try:
            self.refresh_values()
        except Exception as exc:
            self.reset_session()
            self.show_error(exc)
        finally:
            if not self._closing:
                self._refresh_job = self.after(250, self.refresh_loop)


if __name__ == "__main__":
    app = TrainerApp()
    app.mainloop()
