# Minecraft Dungeons II Game Pass - Standalone Native Trainer v1.0.4

A lightweight, standalone native GUI trainer for Minecraft Dungeons II on Game Pass (`Dungeons-WinGDK-Shipping.exe`), designed for offline singleplayer use. It accesses game memory directly via Win32 Virtual Memory APIs without attaching debuggers, injecting DLLs, or triggering anti-tamper termination.

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
- Python 3.10+ (standard library only; zero external packages or pip dependencies required)
- Minecraft Dungeons II (`Dungeons-WinGDK-Shipping.exe`)

---

## How to Run

1. Launch Minecraft Dungeons II and load into camp or a mission.
2. Run `run_trainer.bat` (or execute `python trainer_gui.py` in terminal).
3. The trainer will automatically detect and attach to the game process.

---

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability arising from the use of or inability to use this software. Intended strictly for singleplayer offline use.
