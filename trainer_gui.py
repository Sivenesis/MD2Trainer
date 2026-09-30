"""Tkinter interface and gameplay commands for the native trainer."""

import time
import tkinter as tk
from tkinter import messagebox, ttk

from trainer_memory import MemoryAccessError, MemoryManager, finite_float
from trainer_offsets import CHAINS

SESSION_VIEWS = {
    "disconnected": ("GAME NOT CONNECTED", "Launch the game. Detection is automatic.", "#8fa2b8"),
    "loading": (
        "WAITING FOR CHARACTER",
        "Load a character into a camp or mission to see available options.",
        "#edc58c",
    ),
    "client": (
        "MULTIPLAYER CLIENT",
        "All commands available. Speed, jump and arrows reported working; server-managed changes such as balances may be ignored.",
        "#64d8cb",
    ),
    "local": (
        "LOCAL AUTHORITY · SOLO / HOST",
        "Editing options are available. This detection cannot distinguish offline solo from a local host.",
        "#70ddb1",
    ),
    "unknown": (
        "SESSION NOT RECOGNIZED",
        "Editing options are hidden until the session can be identified. Check game compatibility.",
        "#edc58c",
    ),
}


class FlowFrame(tk.Frame):
    """Wrap controls to the available width instead of clipping a long row."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.items = []
        self.bind("<Configure>", self.arrange)

    def add(self, widget):
        self.items.append(widget)
        self.arrange()

    def arrange(self, event=None):
        width = max(200, self.winfo_width())
        x = y = row_height = 0
        for widget in self.items:
            item_width = min(width, widget.winfo_reqwidth())
            item_height = widget.winfo_reqheight()
            if x and x + item_width > width:
                x = 0
                y += row_height + 8
                row_height = 0
            widget.place(x=x, y=y, width=item_width, height=item_height)
            x += item_width + 8
            row_height = max(row_height, item_height)
        self.configure(height=y + row_height)


class TrainerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft Dungeons II - Native Trainer v1.0.1")
        self.geometry("1160x840")
        self.minsize(960, 720)
        self.configure(bg="#0b111b")

        self.mem = MemoryManager()
        self.next_connect_at = 0.0
        self.value_rows = []
        self.edit_tabs = []
        self.session_kind = None
        self.session_identity = None
        self.navigation = {}
        self.god_mode_active = False
        self._god_original = None
        self._god_original_pid = None
        self.freeze_souls_active = False
        self.auto_refill_ammo_active = False
        self.lock_speed_active = False
        self.locked_speed_val = 1.0
        self.infinite_potions_active = False
        self.infinite_roll_active = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_styles()
        self.create_widgets()

        self.try_connect()
        self._refresh_job = self.after(500, self.refresh_loop)

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
        style.layout("TNotebook.Tab", [])
        style.configure(
            "TNotebook.Tab",
            background="#131e2c",
            foreground="#e6eef8",
            padding=[18, 6],
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
            foreground="#edc58c",
            font=("Consolas", 10, "bold"),
        )
        style.configure(
            "TButton",
            background="#223146",
            foreground="#e6eef8",
            font=("Segoe UI", 10),
            borderwidth=0,
            padding=[12, 8],
            relief="flat",
            focuscolor="#223146",
        )
        style.map(
            "TButton",
            background=[("active", "#30475e"), ("pressed", "#3c566e")],
            bordercolor=[("focus", "#64d8cb")],
        )
        style.configure(
            "Accent.TButton",
            background="#64d8cb",
            foreground="#081c18",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#70ddb1")])
        for scrollbar in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(
                scrollbar,
                background="#223146",
                troughcolor="#0b111b",
                borderwidth=0,
                arrowsize=10,
                bordercolor="#0b111b",
                lightcolor="#223146",
                darkcolor="#223146",
                arrowcolor="#8fa2b8",
            )

    def create_widgets(self):
        main = tk.Frame(self, bg="#0b111b", padx=24, pady=18)
        main.pack(fill="both", expand=True)
        top_bar = tk.Frame(main, bg="#0b111b")
        top_bar.pack(fill="x", pady=(0, 14))
        top_bar.columnconfigure(0, weight=1)
        tk.Label(
            top_bar,
            text="DUNGEONS II  /  TRAINER",
            bg="#0b111b",
            fg="#e6eef8",
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.session_mode_label = tk.Label(
            top_bar,
            text="Waiting for game",
            bg="#0b111b",
            fg="#8fa2b8",
            font=("Segoe UI", 9),
            anchor="e",
        )
        self.session_mode_label.grid(row=0, column=1, padx=16)
        ttk.Button(top_bar, text="Reconnect", command=self.try_connect).grid(
            row=0, column=2, sticky="e"
        )

        session_card = tk.Frame(
            main,
            bg="#122b2e",
            padx=14,
            pady=10,
            highlightthickness=1,
            highlightbackground="#234047",
        )
        session_card.pack(fill="x", pady=(0, 14))
        self.session_badge = tk.Label(
            session_card, text="", bg="#122b2e", font=("Segoe UI", 13, "bold"), anchor="w"
        )
        self.session_badge.pack(fill="x")
        self.session_hint = tk.Label(
            session_card,
            text="",
            bg="#122b2e",
            fg="#b7c7d9",
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
        )
        self.session_hint.pack(fill="x", pady=(4, 0))
        session_card.bind(
            "<Configure>",
            lambda event: self.session_hint.configure(wraplength=max(200, event.width - 40)),
        )

        self.nav_frame = tk.Frame(main, bg="#0e1622", padx=4, pady=4)
        self.nav_frame.pack(fill="x", pady=(0, 12))
        self.page_title = tk.Label(
            main,
            text="Overview",
            bg="#0b111b",
            fg="#e6eef8",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        )
        self.page_title.pack(fill="x", pady=(0, 10))

        self.status_lbl = tk.Label(
            main,
            text="Searching for the game...",
            font=("Segoe UI", 9),
            bg="#0b111b",
            fg="#8fa2b8",
            anchor="w",
            justify="left",
        )
        self.status_lbl.pack(side="bottom", fill="x", pady=(14, 0))
        main.bind(
            "<Configure>",
            lambda event: self.status_lbl.configure(wraplength=max(200, event.width - 56)),
        )
        self.notebook = ttk.Notebook(main, takefocus=False)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.update_navigation)
        self.tab_overview = self.create_tab("Overview", editing=False)
        self.tab_currencies = self.create_tab("Currencies")
        self.tab_combat = self.create_tab("Combat")
        self.tab_movement = self.create_tab("Movement")
        self.tab_progression = self.create_tab("Progression")
        self.tab_developer = self.create_tab("Developer")
        self.build_currencies_tab()
        self.build_combat_tab()
        self.build_movement_tab()
        self.build_progression_tab()
        self.build_developer_tab()
        self.build_overview()
        self.style_toggle_rows()
        self.set_session_view("disconnected")
        self.update_navigation()
        self.bind_all("<MouseWheel>", self.scroll_active_page, add="+")

    def update_navigation(self, event=None):
        selected = self.notebook.select()
        for tab, button in self.navigation.items():
            active = str(tab) == selected
            button.config(
                bg="#1c3540" if active else "#0e1622", fg="#85ecdc" if active else "#8fa2b8"
            )
        if selected:
            title = self.notebook.tab(selected, "text")
            self.page_title.config(text="Advanced" if title == "Developer" else title)

    def scroll_active_page(self, event):
        if not self.notebook.select():
            return
        tab = self.nametowidget(self.notebook.select())
        canvas = next(
            (child for child in tab.winfo_children() if isinstance(child, tk.Canvas)), None
        )
        if canvas and canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(-int(event.delta / 120), "units")

    def create_tab(self, name, editing=True):
        container = tk.Frame(self.notebook, bg="#0b111b")
        self.notebook.add(container, text=name)
        label = "Advanced" if name == "Developer" else name
        button = tk.Button(
            self.nav_frame,
            text=label,
            anchor="center",
            relief="flat",
            bd=0,
            bg="#0e1622",
            fg="#8fa2b8",
            activebackground="#1c3540",
            activeforeground="#85ecdc",
            font=("Segoe UI", 10),
            padx=14,
            pady=9,
            cursor="hand2",
            command=lambda: self.notebook.select(container),
        )
        button.pack(side="left", padx=2)
        self.navigation[container] = button
        if editing:
            self.edit_tabs.append(container)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        canvas = tk.Canvas(container, bg="#0b111b", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        vertical = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")

        def update_scrollbar(scrollbar, first, last):
            scrollbar.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()

        canvas.configure(
            xscrollcommand=lambda first, last: update_scrollbar(horizontal, first, last),
            yscrollcommand=lambda first, last: update_scrollbar(vertical, first, last),
        )
        frame = tk.Frame(canvas, bg="#0b111b", padx=0, pady=0)
        frame.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        return frame

    def style_toggle_rows(self):
        for tab in (self.tab_currencies, self.tab_combat, self.tab_movement):
            for frame in tab.winfo_children():
                if not isinstance(frame, tk.Frame) or getattr(frame, "is_option_card", False):
                    continue
                children = frame.winfo_children()
                if not children or not isinstance(children[0], tk.Button):
                    continue
                frame.grid_configure(sticky="ew", pady=(0, 12))
                frame.configure(
                    padx=16, pady=14, highlightthickness=1, highlightbackground="#223146"
                )
                for index, child in enumerate(children):
                    child.pack_forget()
                    child.pack(
                        anchor="w", fill="x" if index else "none", pady=(8, 0) if index else 0
                    )
                    if isinstance(child, tk.Label):
                        child.configure(justify="left", anchor="w", font=("Segoe UI", 9))
                        frame.bind(
                            "<Configure>",
                            lambda event, label=child: label.configure(
                                wraplength=max(180, event.width - 36)
                            ),
                            add="+",
                        )

    def build_overview(self):
        frame = self.tab_overview
        frame.columnconfigure(0, weight=1)
        self.overview_note = tk.Label(
            frame,
            text="",
            bg="#0b111b",
            fg="#8fa2b8",
            font=("Segoe UI", 10),
            wraplength=680,
            justify="left",
            anchor="w",
        )
        self.overview_note.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        host = tk.Frame(frame, bg="#0b111b")
        host.grid(row=1, column=0, sticky="ew")
        self.stat_cards = []
        definitions = (
            ("EMERALDS", "emeralds_current", "Available balance", "#70ddb1", "diamond"),
            ("ECHO SHARDS", "springstone_current", "Available balance", "#80baff", "shard"),
            ("ENCHANTMENT", "ench_points_cur", "Available points", "#c8a4ff", "diamond"),
            ("CHARACTER LEVEL", "level", "Your progression", "#edc58c", "bars"),
            ("HEALTH", "health_current", "Current health", "#f58a92", "health"),
            ("ARROWS", "ammo_current", "Ready to fire", "#a4bdcf", "arrow"),
        )
        for title, key, detail, accent, icon in definitions:
            card = tk.Frame(
                host,
                bg="#131e2c",
                padx=18,
                pady=18,
                height=152,
                highlightthickness=1,
                highlightbackground="#223146",
            )
            card.grid_propagate(False)
            card.columnconfigure(0, weight=1)
            tk.Label(
                card,
                text=title,
                bg="#131e2c",
                fg="#8fa2b8",
                font=("Segoe UI", 9, "bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            mark = tk.Canvas(card, width=28, height=28, bg="#131e2c", highlightthickness=0)
            mark.grid(row=0, column=1, rowspan=2, sticky="ne")
            if icon in ("diamond", "shard"):
                mark.create_polygon(14, 2, 24, 14, 14, 26, 4, 14, fill="", outline=accent, width=2)
                mark.create_line(14, 5, 14, 23, fill=accent, width=2)
            elif icon == "health":
                mark.create_line(14, 5, 14, 23, fill=accent, width=4)
                mark.create_line(5, 14, 23, 14, fill=accent, width=4)
            elif icon == "bars":
                for i in range(3):
                    mark.create_rectangle(
                        4 + i * 8, 18 - i * 6, 8 + i * 8, 25, fill=accent, outline=""
                    )
            else:
                mark.create_line(5, 24, 23, 6, fill=accent, width=2)
                mark.create_line(14, 6, 23, 6, 23, 15, fill=accent, width=2)
            value = tk.Label(
                card,
                text="\u2014",
                bg="#131e2c",
                fg="#e6eef8",
                font=("Segoe UI", 29, "bold"),
                anchor="w",
            )
            value.grid(row=1, column=0, sticky="w", pady=(12, 0))
            tk.Label(
                card, text=detail, bg="#131e2c", fg="#637991", font=("Segoe UI", 9), anchor="w"
            ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
            self.value_rows.append((value, key, False))
            self.stat_cards.append(card)

        def arrange_cards(event):
            columns = 3 if event.width >= 720 else 2
            for i in range(3):
                host.columnconfigure(
                    i, weight=1 if i < columns else 0, uniform="stats" if i < columns else ""
                )
            for i, card in enumerate(self.stat_cards):
                card.grid(
                    row=i // columns,
                    column=i % columns,
                    padx=(0, 12) if i % columns < columns - 1 else 0,
                    pady=(0, 12),
                    sticky="ew",
                )
            self.overview_note.configure(wraplength=max(200, event.width - 8))

        host.bind("<Configure>", arrange_cards)
        footer = tk.Frame(
            frame,
            bg="#131e2c",
            padx=18,
            pady=16,
            highlightthickness=1,
            highlightbackground="#223146",
        )
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        tk.Label(
            footer,
            text="Need to troubleshoot?",
            bg="#131e2c",
            fg="#e6eef8",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.copy_feedback = tk.Label(
            footer,
            text="Copy the session details to help investigate an issue.",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        )
        self.copy_feedback.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(5, 0))
        footer.bind(
            "<Configure>",
            lambda event: self.copy_feedback.configure(wraplength=max(160, event.width - 205)),
        )
        ttk.Button(footer, text="Copy details", command=self.copy_session_diagnostics).grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

    def copy_session_diagnostics(self):
        lines = [
            f"Session: {self.session_badge.cget('text')}",
            f"Process: {self.mem.pid or 'not connected'}",
            f"Local role: {self.mem.read_byte('player_role')}",
            f"Remote role: {self.mem.read_byte('player_remote_role')}",
            f"Status: {self.status_lbl.cget('text')}",
        ]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.copy_feedback.config(text="Session diagnostics copied.")

    def reset_continuous_options(self):
        for flag, button, text in (
            ("god_mode_active", self.btn_god, "TOGGLE GOD MODE (OFF)"),
            ("freeze_souls_active", self.btn_freeze_souls, "FREEZE SOULS (OFF)"),
            ("auto_refill_ammo_active", self.btn_auto_refill, "AUTO-REFILL ARROWS (OFF)"),
            ("lock_speed_active", self.btn_lock_speed, "LOCK SPEED (OFF)"),
            ("infinite_potions_active", self.btn_infinite_potions, "INFINITE POTIONS (OFF)"),
            ("infinite_roll_active", self.btn_infinite_roll, "INFINITE ROLL (OFF)"),
        ):
            setattr(self, flag, False)
            button.config(text=text, bg="#223146", fg="#f58a92")
        self._god_original = None
        self._god_original_pid = None

    def set_session_view(self, kind, identity=None):
        if kind not in SESSION_VIEWS:
            kind = "unknown"
        changed_character = self.session_identity is not None and self.session_identity != identity
        if (
            kind not in ("local", "client")
            or changed_character
            or (self.session_kind in ("local", "client") and kind != self.session_kind)
        ):
            self.reset_continuous_options()
        if kind != self.session_kind:
            title, hint, color = SESSION_VIEWS[kind]
            self.session_badge.config(text=title, fg=color)
            self.session_hint.config(text=hint)
            self.copy_feedback.config(text="Copy the session details to help investigate an issue.")
            self.overview_note.config(
                text=(
                    "Use the editing tabs for this session. Effects and persistence still need in-game validation."
                    if kind == "local"
                    else (
                        "All commands remain available in multiplayer. A successful memory write does not confirm an in-game effect."
                        if kind == "client"
                        else "Live readings only. Available commands appear automatically when the session supports them."
                    )
                )
            )
            for tab in self.edit_tabs:
                if kind in ("local", "client"):
                    self.notebook.add(tab)
                    self.navigation[tab].pack(side="left", padx=2)
                else:
                    self.notebook.hide(tab)
                    self.navigation[tab].pack_forget()
            if kind not in ("local", "client"):
                self.notebook.select(self.tab_overview.master.master)
        self.session_mode_label.config(
            text={
                "local": "Local control",
                "client": "Multiplayer controls",
                "loading": "Loading character",
                "unknown": "Session unknown",
                "disconnected": "Waiting for game",
            }[kind]
        )
        self.update_navigation()
        self.session_kind = kind
        self.session_identity = identity

    def try_connect(self):
        self.next_connect_at = time.monotonic() + 3.0
        self.clear_values()
        self.set_session_view("disconnected")
        if self.mem.attach():
            self.set_session_view("loading")
            self.status_lbl.config(
                text=f"Attached (PID {self.mem.pid}); checking character...", fg="#edc58c"
            )
        else:
            self.status_lbl.config(text=self.mem.last_error, fg="#f58a92")

    def clear_values(self):
        for label, key, is_byte in self.value_rows:
            label.config(text="---")

    def on_close(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self.mem.close()
        self.destroy()

    def report_callback_exception(self, exc_type, exc_value, traceback):
        if isinstance(exc_value, (MemoryAccessError, ValueError, OverflowError)):
            messagebox.showerror("Operation failed", str(exc_value), parent=self)
        else:
            super().report_callback_exception(exc_type, exc_value, traceback)

    # ==========================================
    # Tab 1: Currencies
    # ==========================================
    def build_currencies_tab(self):
        f = self.tab_currencies

        # Emeralds (Green Gem in Game, Cap: 9,999)
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

        # Echo Shards / SpringStone (Blue Shard in Screenshot 1)
        self.lbl_springstone = self.add_row(
            f,
            1,
            "Echo Shards (Blue Shard):",
            "springstone_current",
            [
                ("+500", lambda: self.adjust_springstone(500)),
                ("Max (9,999)", lambda: self.set_springstone(9999)),
            ],
            custom_entry=True,
            setter=self.set_springstone,
        )

        # Enchantment Points (Purple Diamond 51/1 in Screenshot 1)
        self.lbl_ench = self.add_row(
            f,
            2,
            "Enchantment Points (Purple):",
            "ench_points_cur",
            [
                ("+5 Points", lambda: self.adjust_ench_points(5)),
                ("Set 99 Points", lambda: self.set_ench_points(99)),
            ],
            custom_entry=True,
            setter=self.set_ench_points,
        )

        # Currency Gain Multiplier (Emeralds & Soul Gathering Scale)
        self.lbl_curr_mult = self.add_row(
            f,
            3,
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

        # Souls (with dedicated Freeze Souls toggle)
        self.lbl_souls = self.add_row(
            f,
            4,
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
        freeze_frame = tk.Frame(f, bg="#131e2c", pady=2)
        freeze_frame.grid(row=5, column=0, columnspan=5, sticky="w")
        self.btn_freeze_souls = tk.Button(
            freeze_frame,
            text="FREEZE SOULS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
            relief="flat",
            command=self.toggle_freeze_souls,
        )
        self.btn_freeze_souls.pack(side="left")
        lbl_souls_hint = tk.Label(
            freeze_frame,
            text="Locks Souls to Max capacity continuously (Unlimited Artifact activations)",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        lbl_souls_hint.pack(side="left", padx=10)

        # Arrows (Ammo) - Custom amount, respects lower values, auto-refill toggle
        self.lbl_ammo = self.add_row(
            f,
            6,
            "Arrows (Ammo Count):",
            "ammo_current",
            [("Refill (999)", lambda: self.set_ammo(999)), ("Max Cap (999)", self.max_ammo_cap)],
            custom_entry=True,
            setter=self.set_ammo,
        )

        # Auto-Refill (Infinite Ammo) Toggle Row
        refill_frame = tk.Frame(f, bg="#131e2c", pady=2)
        refill_frame.grid(row=7, column=0, columnspan=5, sticky="w")
        self.btn_auto_refill = tk.Button(
            refill_frame,
            text="AUTO-REFILL ARROWS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
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

        # Rapid Fire (Bow Attack Speed)
        self.lbl_rapid = self.add_row(
            f,
            8,
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

    def set_emeralds(self, val):
        val = finite_float(val)
        self.mem.write_float("emeralds_cap_base", max(9999.0, val))
        self.mem.write_float("emeralds_cap_cur", max(9999.0, val))
        self.mem.write_float("emeralds_base", val)
        self.mem.write_float("emeralds_current", val)

    def adjust_emeralds(self, delta):
        cur = self.mem.require_float("emeralds_current")
        self.set_emeralds(cur + delta)

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
            max_add = max(1.0, mult * 5.0)
            self.mem.write_float("emerald_increase_base", pct)
            self.mem.write_float("emerald_increase_cur", pct)
            self.mem.write_float("emerald_max_add_base", max_add)
            self.mem.write_float("emerald_max_add_cur", max_add)
            self.mem.write_float("emerald_drop_chance_base", mult)
            self.mem.write_float("emerald_drop_chance_cur", mult)
            self.mem.write_float("soul_gather_base", mult)
            self.mem.write_float("soul_gather_cur", mult)

    def set_springstone(self, val):
        val = finite_float(val)
        self.mem.write_float("springstone_cap_base", max(9999.0, val))
        self.mem.write_float("springstone_cap_cur", max(9999.0, val))
        self.mem.write_float("springstone_base", val)
        self.mem.write_float("springstone_current", val)

    def adjust_springstone(self, delta):
        cur = self.mem.require_float("springstone_current")
        self.set_springstone(cur + delta)

    def set_ench_points(self, val):
        val = finite_float(val)
        current_max = self.mem.require_float("ench_points_max_cur")
        self.mem.write_float("ench_points_cap_base", max(99.0, val))
        self.mem.write_float("ench_points_cap_cur", max(99.0, val))
        if val > current_max:
            self.mem.write_float("ench_points_max_base", val)
            self.mem.write_float("ench_points_max_cur", val)
        self.mem.write_float("ench_points_base", val)
        self.mem.write_float("ench_points_cur", val)

    def set_level(self, val):
        val = finite_float(val)
        if not val.is_integer() or not 1 <= val <= 100:
            raise ValueError("Enter a whole level between 1 and 100.")
        self.mem.write_float("level_base", val)
        self.mem.write_float("level", val)

    def adjust_ench_points(self, delta):
        cur = self.mem.require_float("ench_points_cur")
        self.set_ench_points(cur + delta)

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
        if not self.freeze_souls_active:
            self.apply_freeze_souls()
        self.freeze_souls_active = not self.freeze_souls_active
        if self.freeze_souls_active:
            self.btn_freeze_souls.config(
                text="SOULS: FROZEN (INFINITE)", bg="#70ddb1", fg="#081c18"
            )
        else:
            self.btn_freeze_souls.config(text="FREEZE SOULS (OFF)", bg="#223146", fg="#f58a92")

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
        # CRITICAL FIX: Write BOTH ammo_base and ammo_current so lower values are strictly respected
        self.mem.write_float("ammo_base", val)
        self.mem.write_float("ammo_current", val)

    def max_ammo_cap(self):
        self.mem.write_float("ammo_max_base", 999.0)
        self.mem.write_float("ammo_max_cur", 999.0)
        self.mem.write_float("ammo_base", 999.0)
        self.mem.write_float("ammo_current", 999.0)

    def toggle_auto_refill(self):
        if not self.auto_refill_ammo_active:
            self.apply_auto_refill()
        self.auto_refill_ammo_active = not self.auto_refill_ammo_active
        if self.auto_refill_ammo_active:
            self.btn_auto_refill.config(
                text="AUTO-REFILL: ON (INFINITE)", bg="#70ddb1", fg="#081c18"
            )
        else:
            self.btn_auto_refill.config(text="AUTO-REFILL ARROWS (OFF)", bg="#223146", fg="#f58a92")

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
    # Tab 2: Combat
    # ==========================================
    def build_combat_tab(self):
        f = self.tab_combat

        # God Mode Toggle Button
        god_frame = tk.Frame(f, bg="#131e2c", pady=6)
        god_frame.grid(row=0, column=0, columnspan=5, sticky="w")
        self.btn_god = tk.Button(
            god_frame,
            text="TOGGLE GOD MODE (OFF)",
            font=("Segoe UI", 10, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=16,
            pady=6,
            relief="flat",
            command=self.toggle_god_mode,
        )
        self.btn_god.pack(side="left")

        god_hint = tk.Label(
            god_frame,
            text="Locks Health to Max, Damage Resistance to 0 (Immune), Invincible Byte ON",
            bg="#131e2c",
            fg="#8fa2b8",
            font=("Segoe UI", 8),
        )
        god_hint.pack(side="left", padx=12)

        self.lbl_health = self.add_row(
            f,
            1,
            "Health (Current / Max):",
            "health_current",
            [("Full Heal", self.full_heal), ("Set 10,000 HP", lambda: self.set_health(10000))],
            custom_entry=True,
            setter=self.set_health,
        )

        self.lbl_shield = self.add_row(
            f,
            2,
            "Shield:",
            "shield_current",
            [("Set 1,000 Shield", lambda: self.mem.write_float("shield_current", 1000))],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("shield_current", v),
        )

        self.lbl_art_cd = self.add_row(
            f,
            3,
            "Artifact Cooldown:",
            "artifact_cd",
            [("Fast (0.05x)", self.set_instant_artifact), ("Reset (1.0x)", self.reset_artifact_cd)],
        )

        self.lbl_pot_cd = self.add_row(
            f,
            4,
            "Potion Cooldown:",
            "potion_base_cd_cur",
            [("Instant (0.1s)", self.set_instant_potion), ("Reset (30s)", self.reset_potion)],
            custom_entry=True,
            setter=self.set_potion_cd,
        )

        # Infinite Potions Toggle Row
        pot_frame = tk.Frame(f, bg="#131e2c", pady=2)
        pot_frame.grid(row=5, column=0, columnspan=5, sticky="w")
        self.btn_infinite_potions = tk.Button(
            pot_frame,
            text="INFINITE POTIONS (OFF)",
            font=("Segoe UI", 9, "bold"),
            bg="#223146",
            fg="#f58a92",
            padx=12,
            pady=4,
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

        self.lbl_crit = self.add_row(
            f,
            6,
            "Critical Hit Chance (1.0=100%):",
            "crit_chance",
            [
                ("100% Crit", lambda: self.mem.write_float("crit_chance", 1.0)),
                ("500% Crit Dmg", lambda: self.mem.write_float("crit_multiplier", 5.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("crit_chance", v),
        )

        self.lbl_melee_spd = self.add_row(
            f,
            7,
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

        self.lbl_reach = self.add_row(
            f,
            8,
            "Melee Reach / Range:",
            "melee_reach",
            [
                ("Super (2500)", lambda: self.mem.write_float("melee_reach", 2500.0)),
                ("Reset (250)", lambda: self.mem.write_float("melee_reach", 250.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("melee_reach", v),
        )

        self.lbl_multi = self.add_row(
            f,
            9,
            "MultiShot (Chance & Arrows):",
            "multishot_chance",
            [("100% + 5 Arrows", self.enable_multishot)],
        )

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
        # 0.1s base cd and 0.05 multiplier = 5ms duration, safely triggering UE4 timer delegate
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
        if not self.infinite_potions_active:
            self.set_instant_potion()
        self.infinite_potions_active = not self.infinite_potions_active
        if self.infinite_potions_active:
            self.btn_infinite_potions.config(
                text="INFINITE POTIONS: ON", bg="#70ddb1", fg="#081c18"
            )
        else:
            self.btn_infinite_potions.config(
                text="INFINITE POTIONS (OFF)", bg="#223146", fg="#f58a92"
            )
            self.reset_potion()

    def apply_infinite_potions(self):
        self.mem.write_float("potion_max_charges_base", 5.0)
        self.mem.write_float("potion_max_charges_cur", 5.0)
        self.mem.write_float("potion_charges_base", 5.0)
        self.mem.write_float("potion_charges_cur", 5.0)

    def toggle_god_mode(self):
        if not self.god_mode_active:
            self.apply_god_mode()
        else:
            if self._god_original and self._god_original_pid == self.mem.pid:
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
            or self._god_original_pid != self.mem.pid
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

    # ==========================================
    # Tab 3: Movement
    # ==========================================
    def build_movement_tab(self):
        f = self.tab_movement

        # Movement Speed Multiplier (Writes both Base and Cur + Lock option)
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

        # Lock Speed Multiplier Toggle Row (prevents combat reset)
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

        # Jump Height (Jump Z Velocity)
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

        # Time Dilation (Player Speedhack)
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
        # 0.1s cooldown completes in 1-2 frames without getting stuck, and provides 5 charges
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
        if not self.infinite_roll_active:
            self.set_instant_roll()
        self.infinite_roll_active = not self.infinite_roll_active
        if self.infinite_roll_active:
            self.btn_infinite_roll.config(text="INFINITE ROLL: ON", bg="#70ddb1", fg="#081c18")
        else:
            self.btn_infinite_roll.config(text="INFINITE ROLL (OFF)", bg="#223146", fg="#f58a92")
            self.reset_roll()

    def apply_infinite_roll(self):
        self.mem.write_float("roll_max_charges_base", 5.0)
        self.mem.write_float("roll_max_charges_cur", 5.0)
        self.mem.write_float("roll_charges_base", 5.0)
        self.mem.write_float("roll_charges_cur", 5.0)

    def set_speed(self, val):
        val = finite_float(val)
        self.mem.write_float("move_mult_base", val)
        self.mem.write_float("move_mult_cur", val)
        self.locked_speed_val = val
        if self.lock_speed_active:
            self.btn_lock_speed.config(text=f"SPEED LOCKED ({val:.1f}x)")

    def toggle_lock_speed(self):
        if not self.lock_speed_active:
            self.locked_speed_val = self.mem.require_float("move_mult_cur")
            self.apply_lock_speed()
        self.lock_speed_active = not self.lock_speed_active
        if self.lock_speed_active:
            self.btn_lock_speed.config(
                text=f"SPEED LOCKED ({self.locked_speed_val:.1f}x)", bg="#70ddb1", fg="#081c18"
            )
        else:
            self.btn_lock_speed.config(text="LOCK SPEED (OFF)", bg="#223146", fg="#f58a92")

    def apply_lock_speed(self):
        self.mem.write_float("move_mult_base", self.locked_speed_val)
        self.mem.write_float("move_mult_cur", self.locked_speed_val)

    # ==========================================
    # Tab 4: Progression
    # ==========================================
    def build_progression_tab(self):
        f = self.tab_progression

        # Master Loot Multiplier (Synchronizes Drops + Duplication + Engine Payouts Cap)
        self.lbl_master_loot = self.add_row(
            f,
            0,
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
            1,
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

        # Max Loot Payouts Cap (Internal Engine Drop Iteration Limit)
        self.lbl_max_payouts = self.add_row(
            f,
            2,
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
            3,
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
            4,
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
            5,
            "Character Level:",
            "level",
            [
                ("Level 50", lambda: self.set_level(50.0)),
                ("Level 100", lambda: self.set_level(100.0)),
            ],
            custom_entry=True,
            setter=self.set_level,
        )

        # Current XP
        self.lbl_xp = self.add_row(
            f,
            6,
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
            7,
            "Vendor Upgrades & Restock:",
            "merchant_charges",
            [("Max All Vendors", self.max_all_vendors)],
        )

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
        cur_payouts = self.mem.require_float("max_payouts_cur")
        self.mem.write_float("drop_dup_base", val)
        self.mem.write_float("drop_duplication", val)
        # Ensure engine MaximumLootingPayouts is at least val + 1 so duplication isn't capped
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
    # Tab 5: Developer
    # ==========================================
    def build_developer_tab(self):
        f = self.tab_developer

        self.lbl_debug = self.add_row(
            f,
            0,
            "EnableDebug Flag (PC+0x94D):",
            "debug_flag",
            [
                ("Enable (1)", lambda: self.mem.write_byte("debug_flag", 1)),
                ("Disable (0)", lambda: self.mem.write_byte("debug_flag", 0)),
            ],
            is_byte=True,
        )

        self.lbl_debug_ui = self.add_row(
            f,
            1,
            "DebugUIControls (PC+0x748):",
            "debug_ui",
            [
                ("Enable (1)", lambda: self.mem.write_byte("debug_ui", 1)),
                ("Disable (0)", lambda: self.mem.write_byte("debug_ui", 0)),
            ],
            is_byte=True,
        )

        self.lbl_fov = self.add_row(
            f,
            2,
            "Camera FOV (Default: 90):",
            "camera_fov",
            [
                ("FOV 100", lambda: self.mem.write_float("camera_fov", 100.0)),
                ("FOV 110", lambda: self.mem.write_float("camera_fov", 110.0)),
                ("FOV 120", lambda: self.mem.write_float("camera_fov", 120.0)),
                ("Reset (90)", lambda: self.mem.write_float("camera_fov", 90.0)),
            ],
            custom_entry=True,
            setter=lambda v: self.mem.write_float("camera_fov", v),
        )

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

    def refresh_loop(self):
        try:
            self.refresh_values()
        except (MemoryAccessError, ValueError, OverflowError) as exc:
            self.set_session_view("unknown")
            self.status_lbl.config(text=str(exc), fg="#f58a92")
            self.clear_values()
        finally:
            self._refresh_job = self.after(250, self.refresh_loop)

    def refresh_values(self):
        if not self.mem.is_alive():
            self.set_session_view("disconnected")
            self.clear_values()
            if time.monotonic() >= self.next_connect_at:
                self.try_connect()
            if not self.mem.h_proc:
                self.status_lbl.config(text=self.mem.last_error, fg="#f58a92")
                return

        if self.mem.h_proc:
            kind = self.mem.session_kind()
            identity = (self.mem.pid, self.mem.resolve_chain(CHAINS["player_role"]))
            self.set_session_view(kind, identity)
            if kind == "loading":
                self.status_lbl.config(
                    text="Character unavailable: load a character or check game compatibility.",
                    fg="#edc58c",
                )
                self.clear_values()
                return
            session_error = self.mem.session_write_error()
            errors = []
            for active, apply in (
                (self.god_mode_active, self.apply_god_mode),
                (self.freeze_souls_active, self.apply_freeze_souls),
                (self.auto_refill_ammo_active, self.apply_auto_refill),
                (self.lock_speed_active, self.apply_lock_speed),
                (self.infinite_potions_active, self.apply_infinite_potions),
                (self.infinite_roll_active, self.apply_infinite_roll),
            ):
                if active and kind in ("local", "client") and not session_error:
                    try:
                        apply()
                    except (MemoryAccessError, ValueError, OverflowError) as exc:
                        errors.append(str(exc))

            unavailable = 0
            for lbl, key, is_byte in self.value_rows:
                if is_byte:
                    v = self.mem.read_byte(key)
                    lbl.config(text=str(v) if v is not None else "---")
                else:
                    v = self.mem.read_float(key)
                    if v is not None:
                        if key == "emerald_increase_cur":
                            mult_disp = v + 1.0
                            lbl.config(text=f"{mult_disp:.1f}x")
                        elif key in (
                            "emeralds_current",
                            "springstone_current",
                            "ench_points_cur",
                            "level",
                            "ammo_current",
                            "health_current",
                        ):
                            lbl.config(text=f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}")
                        elif abs(v) >= 10:
                            lbl.config(text=f"{v:,.1f}")
                        else:
                            lbl.config(text=f"{v:.2f}")
                    else:
                        lbl.config(text="---")
                if v is None:
                    unavailable += 1
            if errors:
                self.status_lbl.config(text=errors[0], fg="#f58a92")
            elif kind == "client":
                suffix = f" · {unavailable} unavailable readings" if unavailable else ""
                self.status_lbl.config(
                    text=f"Connected (PID {self.mem.pid}) · Multiplayer controls available{suffix}",
                    fg="#64d8cb",
                )
            elif session_error or kind == "unknown":
                self.status_lbl.config(
                    text="Connected · session compatibility not confirmed", fg="#edc58c"
                )
            elif unavailable:
                self.status_lbl.config(
                    text=f"Connected; {unavailable} unavailable readings. Check game compatibility.",
                    fg="#edc58c",
                )
            else:
                self.status_lbl.config(text=f"Connected (PID {self.mem.pid})", fg="#70ddb1")


if __name__ == "__main__":
    app = TrainerApp()
    app.mainloop()
