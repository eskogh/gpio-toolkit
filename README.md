<<<<<<< HEAD
# gpio-toolkit
A versatile Raspberry Pi GPIO toolkit with CLI and TUI support. Monitor, log, and control pins using BCM or BOARD numbering. Features live status tables, edge detection with CSV/JSON logging, read/write/pulse, profiles for pin sets, and a curses dashboard. Perfect for debugging and automation.
=======
# GPIO Toolkit (RPi.GPIO)

A single **Swiss‑army knife** for Raspberry Pi GPIO using `RPi.GPIO`:

- Status dashboard (table)
- Edge monitoring with debounce **(+ CSV / JSONL logging)**
- Read / Write / Pulse
- Setup / Cleanup
- Numbering mode toggle (BCM / BOARD)
- 40‑pin header mapping
- **Profiles** (JSON or YAML) to define default pins & named sets
- **Curses TUI** live dashboard

> YAML profiles are optional; JSON works without extra deps.

## Install

```bash
sudo apt update
sudo apt install -y python3-pip
# RPi.GPIO usually comes with Raspberry Pi OS; if not:
python3 -m pip install RPi.GPIO
```

*(Optional for YAML profiles)*
```bash
python3 -m pip install pyyaml
```

## Files

- `gpio_toolkit.py` – the CLI
- `profiles.json` – example profiles file

## Profile file

`profiles.json` example:
```json
{
  "mode": "BCM",
  "default_pins": [14, 16, 4],
  "sets": {
    "garage": [14, 16],
    "spi": [10, 9, 11, 8, 7]
  }
}
```

> YAML works too if you have PyYAML installed.

## Usage

General help:
```bash
python3 gpio_toolkit.py -h
```

Use a profile:
```bash
python3 gpio_toolkit.py --profile profiles.json status
```

Choose numbering mode (overrides profile mode):
```bash
python3 gpio_toolkit.py --mode BOARD status --count 5
```

### Commands

**Map the 40‑pin header**
```bash
python3 gpio_toolkit.py map
```

**Status table (auto-refresh)**
```bash
python3 gpio_toolkit.py status --interval 1.0 --count 10
# Use pins from profile set:
python3 gpio_toolkit.py --profile profiles.json status --set-name garage
```

**Monitor edges (with logging)**
```bash
python3 gpio_toolkit.py --profile profiles.json monitor --set-name garage \
  --edge BOTH --pull DOWN --bounce 100 \
  --log-csv events.csv --log-json events.jsonl
```

**Read a pin**
```bash
python3 gpio_toolkit.py read --pin 4 --pull UP --cleanup
```

**Write a pin**
```bash
python3 gpio_toolkit.py setup --pin 4 --direction OUT
python3 gpio_toolkit.py write --pin 4 --value HIGH
```

**Pulse a pin**
```bash
python3 gpio_toolkit.py pulse --pin 4 --width 0.5 --repeat 3 --gap 1 --cleanup
```

**Curses TUI (live dashboard)**
```bash
python3 gpio_toolkit.py --profile profiles.json tui --set-name garage --interval 0.25
# Keys: 'q' to quit, 'r' to refresh immediately
```

**Cleanup**
```bash
python3 gpio_toolkit.py cleanup
```

## Logging format

CSV header:
```
timestamp,pin,state
```

JSONL (one object per line):
```json
{"timestamp": 1735923000, "pin": 14, "state": 1}
```

## Tips

- Run as **root** (`sudo`) for full access.
- In **BOARD** mode, non‑GPIO physical pins (5V/3V3/GND) show as `n/a` in status.
- Debounce (`--bounce`) is in milliseconds.
- If your inputs float, set `--pull UP` or `--pull DOWN` appropriately.

## License

MIT
>>>>>>> 7f0baf4 (Initial commit: GPIO Toolkit with CLI, profiles, and TUI)
