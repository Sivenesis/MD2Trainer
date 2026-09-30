# Minecraft Dungeons II - Standalone Native Trainer v1.0.1

A lightweight, standalone native GUI trainer for Minecraft Dungeons II (`Dungeons-WinGDK-Shipping.exe`), designed for offline singleplayer use. It accesses game memory directly via Win32 APIs without attaching a debugger or injecting DLLs.

---

## Features

- **Currencies**: Adjust Emeralds, Echo Shards, and Enchantment Points with custom balances or maximum caps; freeze Souls value; Currency Gain Multipliers (2x, 3x, 5x, 10x, and custom Nx for Emeralds and Souls).
- **Combat**: God Mode toggle (continuous health, shield, and invincibility lock), Infinite Potions toggle & instant potion cooldown (safe non-blocking recharge with full charges), fast artifact cooldown, guaranteed critical hits, and multishot.
- **Movement**: Movement speed multiplier with combat-lock (prevents attack animation resets), custom jump height, gravity scale, Infinite Roll toggle & instant roll cooldown (recharges charges cleanly), and time dilation.
- **Ammo**: Custom arrow ammo count, auto-refill toggle for infinite arrows, and rapid fire.
- **Progression & Loot**: Master loot multipliers (2x, 3x, 5x, 10x, and custom Nx), drop duplication, uncapped loot payout ceiling, 100% rare/unique drop rate, character level adjustments, and one-click vendor upgrades.

---

## Requirements

- Windows 10 or 11 (64-bit)
- **64-bit** Python 3.10+ with Tcl/Tk (standard library only; zero external packages or pip dependencies required)
- Minecraft Dungeons II (`Dungeons-WinGDK-Shipping.exe`)

---

## How to Run

1. Launch Minecraft Dungeons II and load into camp or a mission.
2. Run `run_trainer.bat` (or execute `python trainer_gui.py` in terminal).
3. The trainer will automatically detect and attach to the game process.

## Interface

- Compact horizontal navigation keeps the full window width available for controls. All categories remain accessible in recognized multiplayer sessions; the session banner explains any limitations.
- Overview presents balances, enchantment points, level, health and arrows in responsive cards. Session diagnostics can be copied from this page.
- Editing pages group each value and its presets in a card. Custom values can be applied with the Apply button or Enter; controls wrap when the window narrows.
- Use the mouse wheel to scroll long pages. The dashboard switches between two and three columns as the window resizes.

## Troubleshooting and compatibility

- **The interface adapts to the session.** A session banner distinguishes disconnected, loading, multiplayer client, local authority, and unknown states. The Overview tab shows live character readings and provides a button to copy session diagnostics. All editing tabs are available with a loaded character in a recognized local or multiplayer session. A local authority role cannot by itself distinguish offline solo from a local host; the interface labels this explicitly.
- **Multiplayer retains all commands and continuous effects.** The player reported working speed, jump and infinite arrows in multiplayer. A network role alone cannot establish which effects work, so client roles do not impose a blanket write restriction. Effects other than those reported still need gameplay validation. Live inspection found `Role = ROLE_AutonomousProxy` and `RemoteRole = ROLE_Authority`; writing client-side balance copies did not change the real balance. The session banner explains this limitation. A successful memory write does not prove that the server accepted the change or that it will persist. Unknown roles still block writes.
- The trainer uses a fixed engine offset (`0x0B0577C8`) and fixed pointer chains. Compatibility with a particular game build is **not verified**; a game update may invalidate these addresses. Successful process attachment alone does not validate them.
- Inspection of Microsoft package 1.1.1.0 matched displayed balances and progression, but writing these client-side attributes did not change the actual balance. These pointer chains do not establish a working balance/progression editor. Level writes do not run normal progression events.
- `Character unavailable` means the character health address could not be read. Load into camp or a mission; if the message persists, the pointer chains need verification for your game build.
- Failed writes now display an error. A command that changes several attributes may be partially applied before a failure; writes are not transactional.
- Emeralds, Echo Shards and Enchantment Points buttons change the balance once. They do **not** freeze these balances or make them infinite. Only explicitly labelled continuous toggles repeat writes (every 250 ms).
- Resetting potions or rolls also disables their continuous toggle. Switching these toggles off applies the displayed default cooldown and charge count, rather than recovering equipment-specific values.
- After the game exits, the trainer clears old readings and retries connection every three seconds. Continuous toggles switch off on reconnection, unavailable characters, unknown sessions, a switch between local and client modes, or a change of character. They must be enabled again manually after these transitions; they remain enabled during a stable multiplayer session. Switching them off this way stops repeated writes without restoring old memory values into another character. Closing the trainer also stops repeated writes without undoing previously written game values.

## Developer checks

The runtime uses only the standard library. Ruff is an optional development dependency:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest -v
```

Run tests on 64-bit Windows with Tcl/Tk installed. Native tests use buffers owned by the test process; GUI tests use a simulated memory manager. Tests never attach to the game and do not establish gameplay compatibility. GitHub Actions runs these checks on Windows.

### Project layout

- `trainer_gui.py`: application entry point, interface, and gameplay commands.
- `trainer_memory.py`: Win32 declarations, process lifecycle, validated reads/writes, and session detection.
- `trainer_offsets.py`: build-dependent pointer chains and engine offset.
- `test_trainer.py`: native-memory and GUI regression tests.
- `.local/`: ignored local diagnostics and inspection tools; never required to run the trainer.

Keep the Python modules together when copying or distributing the trainer. Launch it with `run_trainer.bat` or `python trainer_gui.py`.


---

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability arising from the use of or inability to use this software. Intended strictly for singleplayer offline use.
