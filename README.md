# Minecraft Dungeons II Game Pass - Standalone Native Trainer v1.0.4

A lightweight, standalone native GUI trainer for Minecraft Dungeons II (`Dungeons-WinGDK-Shipping.exe`), designed for offline singleplayer use. It accesses game memory directly via Win32 APIs without attaching a debugger or injecting DLLs.

---

## Features

- **Currencies**: Adjust Emeralds, Echo Shards, and Enchantment Points with quick presets or custom balances; individual Freeze toggles for Emeralds, Echo Shards, and Enchantment Points to prevent depletion during shopping/enchanting, plus a Master Freeze All Currencies toggle; Currency Gain Multipliers (2x, 3x, 5x, 10x, and custom Nx).
- **Combat**: God Mode toggle (continuous health, shield, and invincibility lock), Player Damage Multiplier (2x, 5x, 10x, 50x, One-Hit Kill, and custom Nx with continuous animation lock), Health & Shield tuning, Infinite Potions toggle & instant potion cooldown, fast artifact cooldown, guaranteed critical hits, melee speed & reach, multishot, Souls (Soul Energy) adjustments and Soul Freeze toggle, Arrows (Ammo Count) refills and Auto-Refill toggle for infinite ammo, and Rapid Fire (Bow Speed).
- **Movement**: Movement speed multiplier with combat-lock (prevents attack animation resets), custom jump height, gravity scale, Infinite Roll toggle & instant roll cooldown (recharges charges cleanly), and time dilation.
- **Progression**: XP Gain Multiplier (2x, 5x, 10x, 25x, 50x, and custom Nx with continuous session lock), Master loot multipliers (2x, 3x, 5x, 10x, and custom Nx), drop duplication, uncapped loot payout ceiling, 100% rare/unique drop rate, character level and XP adjustments, and one-click vendor upgrades.
- **Gear & Talismans**:
  - **Talisman Growth Multiplier & Max Out**: Real-time combat XP scaling for equipped talismans (2x, 5x, 10x, 25x, 50x, custom Nx) and one-click Max Out (instant Rank 3 & 100,000 XP) for equipped talismans and inventory.
  - **Current Equipped Gear Editor**: Real-time inspection and customization of all equipped items (Melee Weapons, Ranged Weapons, Boots, Chest Armor, Helmets, Leggings, Artifacts, and Talismans). Customize individual Item Power (+10, +25, Set 50, 100, 250, custom), upgrade rarities (Unique/Special, Rare, Common), and batch max out equipped loadouts.

---

## Requirements

- Windows 10 or 11 (64-bit)
- **64-bit Python 3.10+** with Tcl/Tk (standard library only; no third-party runtime packages)
- Minecraft Dungeons II (`Dungeons-WinGDK-Shipping.exe`)

---

## How to Run

1. Launch Minecraft Dungeons II and load into camp or a mission.
2. Run `run_trainer.bat` (or execute `python trainer_gui.py` in terminal).
3. The trainer will automatically detect and attach to the game process.

Keep `trainer_gui.py`, `trainer_memory.py`, `trainer_offsets.py`, and `trainer_widgets.py` together when distributing the trainer.

## Interface and session behavior

- All five v1.0.4 tabs remain available. Option presets and gear toolbars wrap; pages scroll at the supported minimum window size of 880 × 720. Custom option values also accept Enter.
- The session banner distinguishes local authority (solo or host), multiplayer clients, loading and unknown sessions. Multiplayer alone does not disable commands. The server can still ignore client-side changes.
- Failed operations appear in the status area. A failed continuous effect stops itself while other effects and live readings continue.
- Reconnection, character changes and session-mode changes stop continuous effects and clear selected gear and talisman XP history. Re-enable effects for the new character. Reconnection attempts are limited to once every three seconds.
- Resetting potion/roll settings stops their continuous toggle. Turning these toggles off writes the displayed default settings, which may differ from equipment-specific values. Other disabled locks simply stop repeating writes.
- Closing the trainer stops polling and closes the process handle. It does not undo earlier game-memory changes. God Mode explicitly restores its captured resistance and relevant flag bit when turned off for the same character.

## Compatibility and limitations

- Offsets remain build-dependent. The session Role offset is restored to `0x168`, reflected in the inspected Microsoft package 1.1.1.0; it is not a guarantee of compatibility with future builds. Local authority cannot distinguish offline solo from hosting.
- Gear edits re-read the inventory and compare process/character, slot, address and item-name identity before writing. Inventory array sizes are bounded. Inventory talismans are recognized by their tags rather than a fixed slot number.
- Rarity presets are checked against the running FName table before writing. If an index no longer identifies the expected rarity, the operation fails explicitly. The legacy `Unique` alias maps to `Special`; the interface labels it Special.
- A successful memory write does **not** prove that gameplay events ran, perks unlocked, the server accepted a change, or a save persisted it. Earlier client-side balance/progression writes did not change the actual displayed balances. Currency freezes and new gear/talisman features still need build-specific in-game validation.
- Multi-value and batch edits are not atomic. If an operation fails midway, earlier writes may already have applied. Max Out talisman batches report how many items completed before failure. Revalidation reduces stale-address risks but cannot eliminate a game-side change occurring between the final check and the write.

## Development checks

Run on 64-bit Windows with Tcl/Tk installed:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest -v
```

Native tests use buffers in their own process. UI and inventory regression tests use simulated memory and never attach to the game. Passing tests verify trainer behavior, not in-game efficacy. Ruff is a development-only dependency.

`trainer_memory.py` owns Win32 access and validated item edits; `trainer_offsets.py` holds build-dependent addresses; `trainer_widgets.py` provides wrapping controls; `trainer_gui.py` contains the application and gameplay commands. `.local/` is ignored and contains only local development artifacts.

---

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability arising from the use of or inability to use this software. Intended strictly for singleplayer offline use.
