#!/usr/bin/env python3
# gpio_toolkit.py
# A unified GPIO toolkit for Raspberry Pi (RPi.GPIO)
# Features:
# - Status dashboard (table)
# - Edge monitoring with debounce (CSV/JSON logging support)
# - Read / Write / Pulse
# - Setup / Cleanup
# - Numbering mode toggle (BCM/BOARD)
# - 40-pin mapping helper
# - Profiles loader (JSON or YAML) to define named pin sets and defaults
# - Curses TUI dashboard for live status
#
# Usage: python3 gpio_toolkit.py -h
#
# Notes:
# - YAML profiles require PyYAML; JSON works out-of-the-box.
# - Run with sudo for full GPIO access on Raspberry Pi.

import argparse
import os
import sys
import time
import signal
import json
import csv
from typing import List, Sequence, Optional, Dict, Any, Tuple

try:
    import RPi.GPIO as GPIO
except Exception as e:
    print("ERROR: RPi.GPIO not available. Run on a Raspberry Pi or install the library.")
    print(e)
    sys.exit(1)

# Optional YAML support
try:
    import yaml  # type: ignore
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False

# ======================= 40-pin header map (common) =========================
PIN40_MAP = {
    1:  ("3V3", None),       2:  ("5V", None),
    3:  ("GPIO2 (SDA1)", 2), 4:  ("5V", None),
    5:  ("GPIO3 (SCL1)", 3), 6:  ("GND", None),
    7:  ("GPIO4", 4),        8:  ("GPIO14 (TXD)", 14),
    9:  ("GND", None),       10: ("GPIO15 (RXD)", 15),
    11: ("GPIO17", 17),      12: ("GPIO18", 18),
    13: ("GPIO27", 27),      14: ("GND", None),
    15: ("GPIO22", 22),      16: ("GPIO23", 23),
    17: ("3V3", None),       18: ("GPIO24", 24),
    19: ("GPIO10 (MOSI)", 10),20: ("GND", None),
    21: ("GPIO9  (MISO)", 9),22: ("GPIO25", 25),
    23: ("GPIO11 (SCLK)", 11),24: ("GPIO8 (CE0)", 8),
    25: ("GND", None),       26: ("GPIO7 (CE1)", 7),
    27: ("ID_SD", None),     28: ("ID_SC", None),
    29: ("GPIO5", 5),        30: ("GND", None),
    31: ("GPIO6", 6),        32: ("GPIO12", 12),
    33: ("GPIO13", 13),      34: ("GND", None),
    35: ("GPIO19", 19),      36: ("GPIO16", 16),
    37: ("GPIO26", 26),      38: ("GPIO20", 20),
    39: ("GND", None),       40: ("GPIO21", 21),
}

def phys_from_bcm(bcm: int) -> Optional[int]:
    for phys, (_, b) in PIN40_MAP.items():
        if bcm == b:
            return phys
    return None

# ============================== Utilities ===================================
def set_numbering(mode: str):
    mode = mode.upper()
    if mode not in ("BCM", "BOARD"):
        raise ValueError("mode must be BCM or BOARD")
    GPIO.setwarnings(False)
    if mode == "BCM":
        GPIO.setmode(GPIO.BCM)
    else:
        GPIO.setmode(GPIO.BOARD)

def parse_pins(pins: Sequence[str]) -> List[int]:
    out: List[int] = []
    for p in pins:
        out.append(int(p))
    return out

def pretty_label_for_pin(pin: int, mode: str) -> str:
    if mode == "BCM":
        phys = phys_from_bcm(pin)
        suffix = f" (phys {phys})" if phys else ""
        return f"GPIO{pin}{suffix}"
    else:
        item = PIN40_MAP.get(pin)
        if not item:
            return f"PIN {pin}"
        label, bcm = item
        suffix = f" [BCM {bcm}]" if bcm is not None else ""
        return f"{label} (phys {pin}){suffix}"

def ensure_root():
    if os.geteuid() != 0:
        print("NOTE: Not running as root; some operations may fail (try sudo).", file=sys.stderr)

def load_profile(path: Optional[str]) -> Dict[str, Any]:
    """
    Load a profile file (JSON or YAML) describing default mode and named pin sets.
    Schema example (JSON):
    {
      "mode": "BCM",
      "default_pins": [14,16,4],
      "sets": {
        "garage": [14,16],
        "spi": [10,9,11,8,7]
      }
    }
    """
    if not path:
        return {}
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Profile file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data_str = f.read()
    data: Dict[str, Any]
    if _HAVE_YAML and (path.endswith(".yml") or path.endswith(".yaml")):
        data = yaml.safe_load(data_str) or {}
    else:
        data = json.loads(data_str)
    if not isinstance(data, dict):
        raise ValueError("Profile file must contain a JSON/YAML object")
    return data

def resolve_pins_from_args_or_profile(args, profile: Dict[str, Any], mode: str) -> List[int]:
    if args.pins:
        return parse_pins(args.pins)
    if getattr(args, "set_name", None):
        sets = profile.get("sets", {}) if profile else {}
        if args.set_name not in sets:
            raise SystemExit(f"Set '{args.set_name}' not found in profile.")
        return list(map(int, sets[args.set_name]))
    if profile and "default_pins" in profile:
        return list(map(int, profile["default_pins"]))
    return list(range(1, 41)) if mode == "BOARD" else [2,3,4,14,15,16,17,18,27,22,23,24,25,5,6,12,13,19,26,20,21]

def cmd_map(args):
    print("\nRaspberry Pi 40-pin Header Map\n")
    print("Phys | Label              | BCM")
    print("-----+--------------------+-----")
    for phys in range(1, 41):
        label, bcm = PIN40_MAP.get(phys, ("(unknown)", None))
        bcm_str = str(bcm) if bcm is not None else "-"
        print(f"{phys:>4} | {label:<18} | {bcm_str:>3}")
    print("")

def cmd_setup(args):
    mode = args.mode.upper()
    set_numbering(mode)
    pin = args.pin
    direction = args.direction.upper()
    pull = (args.pull.upper() if args.pull else "OFF")
    if direction == "IN":
        pud = GPIO.PUD_OFF
        if pull == "UP":
            pud = GPIO.PUD_UP
        elif pull == "DOWN":
            pud = GPIO.PUD_DOWN
        GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
        print(f"Configured {pretty_label_for_pin(pin, mode)} as INPUT (pull {pull})")
    elif direction == "OUT":
        GPIO.setup(pin, GPIO.OUT)
        if args.initial is not None:
            val = GPIO.HIGH if args.initial.upper() in ("1", "HIGH", "ON", "TRUE") else GPIO.LOW
            GPIO.output(pin, val)
            print(f"Configured {pretty_label_for_pin(pin, mode)} as OUTPUT (initial {args.initial.upper()})")
        else:
            print(f"Configured {pretty_label_for_pin(pin, mode)} as OUTPUT")
    else:
        raise SystemExit("direction must be IN or OUT")

def cmd_status(args):
    mode = args.mode.upper()
    profile = load_profile(args.profile) if args.profile else {}
    if not args.mode and profile.get("mode"):
        mode = str(profile["mode"]).upper()
    set_numbering(mode)

    pins = resolve_pins_from_args_or_profile(args, profile, mode)

    for p in pins:
        try:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        except Exception:
            pass

    # compute column width based on longest label
    labels = [pretty_label_for_pin(p, mode) for p in pins]
    max_label_len = max(len(lbl) for lbl in labels) if labels else 18
    label_width = max(24, max_label_len + 2)  # pad a bit
    state_width = 10

    def print_once():
        os.system("clear" if os.name == "posix" else "cls")
        header = f"📡 Current GPIO Status (mode: {mode})"
        if args.profile:
            header += f"  [profile: {os.path.basename(args.profile)}]"
        if getattr(args, 'set_name', None):
            header += f"  [set: {args.set_name}]"
        print("\n" + header + "\n")

        # top border
        print("╔" + "═" * label_width + "╦" + "═" * state_width + "╗")
        print(f"║ {'Pin':<{label_width-1}}║ {'State':<{state_width-1}}║")
        print("╠" + "═" * label_width + "╬" + "═" * state_width + "╣")

        for p, lbl in zip(pins, labels):
            try:
                state = GPIO.input(p)
                s = "HIGH (1)" if state else "LOW  (0)"
            except Exception:
                s = "n/a"
            print(f"║ {lbl:<{label_width-1}}║ {s:<{state_width-1}}║")

        print("╚" + "═" * label_width + "╩" + "═" * state_width + "╝")
        print("\n🔄 Press CTRL+C to exit.\n")

    interval = args.interval
    count = args.count
    i = 0
    try:
        while True:
            print_once()
            i += 1
            if count and i >= count:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        if args.cleanup:
            GPIO.cleanup()

def _open_loggers(csv_path: Optional[str], json_path: Optional[str]):
    csv_writer = None
    csv_file = None
    json_file = None
    if csv_path:
        csv_file = open(csv_path, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if os.stat(csv_path).st_size == 0:
            csv_writer.writerow(["timestamp", "pin", "state"])
    if json_path:
        json_file = open(json_path, "a", encoding="utf-8")
    return csv_writer, csv_file, json_file

def _log_event(csv_writer, json_file, ts: float, pin: int, state: int):
    if csv_writer:
        csv_writer.writerow([int(ts), pin, int(state)])
    if json_file:
        rec = {"timestamp": int(ts), "pin": pin, "state": int(state)}
        json_file.write(json.dumps(rec) + "\n")

def cmd_monitor(args):
    mode = args.mode.upper()
    profile = load_profile(args.profile) if args.profile else {}
    if not args.mode and profile.get("mode"):
        mode = str(profile["mode"]).upper()
    set_numbering(mode)

    pins = resolve_pins_from_args_or_profile(args, profile, mode)
    edge_map = {"RISING": GPIO.RISING, "FALLING": GPIO.FALLING, "BOTH": GPIO.BOTH}
    edge = edge_map[args.edge.upper()]

    pull = (args.pull.upper() if args.pull else "DOWN")
    pud = GPIO.PUD_DOWN if pull == "DOWN" else (GPIO.PUD_UP if pull == "UP" else GPIO.PUD_OFF)
    for p in pins:
        GPIO.setup(p, GPIO.IN, pull_up_down=pud)

    bouncetime = args.bounce

    csv_writer, csv_file, json_file = _open_loggers(args.log_csv, args.log_json)
    print(f"🔍 Monitoring pins {pins} (mode {mode}, edge {args.edge}, pull {pull}, debounce {bouncetime}ms). CTRL+C to stop.")
    if args.log_csv:
        print(f"   → logging CSV to {args.log_csv}")
    if args.log_json:
        print(f"   → logging JSONL to {args.log_json}")

    def cb(channel):
        state = GPIO.input(channel)
        label = pretty_label_for_pin(channel, mode)
        ts = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] {label} -> {'HIGH (1)' if state else 'LOW (0)'}")
        _log_event(csv_writer, json_file, ts, channel, state)

    for p in pins:
        try:
            GPIO.remove_event_detect(p)
        except Exception:
            pass
        GPIO.add_event_detect(p, edge, callback=cb, bouncetime=bouncetime)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in pins:
            try:
                GPIO.remove_event_detect(p)
            except Exception:
                pass
        if csv_file:
            csv_file.close()
        if json_file:
            json_file.close()
        if args.cleanup:
            GPIO.cleanup()

def cmd_read(args):
    mode = args.mode.upper()
    set_numbering(mode)
    pin = args.pin
    pull = (args.pull.upper() if args.pull else "OFF")
    pud = GPIO.PUD_OFF if pull == "OFF" else (GPIO.PUD_UP if pull == "UP" else GPIO.PUD_DOWN)
    GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
    val = GPIO.input(pin)
    print(f"{pretty_label_for_pin(pin, mode)} = {'HIGH (1)' if val else 'LOW  (0)'}")
    if args.cleanup:
        GPIO.cleanup()

def cmd_write(args):
    mode = args.mode.upper()
    set_numbering(mode)
    pin = args.pin
    GPIO.setup(pin, GPIO.OUT)
    val = GPIO.HIGH if args.value.upper() in ("1","HIGH","ON","TRUE") else GPIO.LOW
    GPIO.output(pin, val)
    print(f"Wrote {args.value.upper()} to {pretty_label_for_pin(pin, mode)}")
    if args.cleanup:
        GPIO.cleanup()

def cmd_pulse(args):
    mode = args.mode.upper()
    set_numbering(mode)
    pin = args.pin
    width = args.width
    repeat = args.repeat
    gap = args.gap
    GPIO.setup(pin, GPIO.OUT)
    print(f"Pulsing {pretty_label_for_pin(pin, mode)}: width={width}s repeat={repeat} gap={gap}s")
    try:
        for i in range(repeat):
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(width)
            GPIO.output(pin, GPIO.LOW)
            if i < repeat - 1:
                time.sleep(gap)
    finally:
        if args.cleanup:
            GPIO.cleanup()

def cmd_cleanup(_args):
    GPIO.cleanup()
    print("GPIO cleaned up.")

def cmd_tui(args):
    mode = args.mode.upper()
    profile = load_profile(args.profile) if args.profile else {}
    if not args.mode and profile.get("mode"):
        mode = str(profile["mode"]).upper()
    set_numbering(mode)

    pins = resolve_pins_from_args_or_profile(args, profile, mode)

    for p in pins:
        try:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        except Exception:
            pass

    interval = max(0.1, args.interval)

    import curses

    def draw(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(True)
        last = 0.0
        while True:
            now = time.time()
            if now - last >= interval:
                stdscr.erase()
                title = f"GPIO TUI (mode: {mode})  profile: {os.path.basename(args.profile) if args.profile else '-'}  set: {getattr(args,'set_name',None) or '-'}"
                stdscr.addstr(0, 0, title)
                stdscr.addstr(1, 0, "Press 'q' to quit, 'r' to refresh")
                stdscr.addstr(3, 0, f"{'Pin':<22} State")
                row = 4
                for p in pins:
                    label = pretty_label_for_pin(p, mode)
                    try:
                        s = GPIO.input(p)
                        state = "HIGH" if s else "LOW "
                    except Exception:
                        state = "n/a "
                    stdscr.addstr(row, 0, f"{label:<22} {state}")
                    row += 1
                stdscr.refresh()
                last = now

            try:
                ch = stdscr.getch()
            except curses.error:
                ch = -1

            if ch == ord('q'):
                break
            elif ch == ord('r'):
                last = 0

            time.sleep(0.02)

    try:
        curses.wrapper(draw)
    finally:
        if args.cleanup:
            GPIO.cleanup()

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="GPIO Toolkit for Raspberry Pi (RPi.GPIO)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    p.add_argument("--mode", default="BCM", help="Numbering mode: BCM or BOARD")
    p.add_argument("--profile", help="JSON or YAML profile file defining default pins and named sets")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("map", help="Print 40-pin header mapping table")
    sp.set_defaults(func=cmd_map)

    sp = sub.add_parser("setup", help="Configure a pin as IN/OUT with optional pull/initial")
    sp.add_argument("--pin", type=int, required=True)
    sp.add_argument("--direction", required=True, choices=["IN","OUT"])
    sp.add_argument("--pull", choices=["UP","DOWN","OFF"])
    sp.add_argument("--initial", help="Initial value for OUT: HIGH/LOW/1/0/ON/OFF/TRUE/FALSE")
    sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser("status", help="Live table of pin states")
    sp.add_argument("--pins", nargs="+", help="Pins to read (default from profile or sensible set)")
    sp.add_argument("--set-name", help="Use a named set from profile (e.g., 'garage')")
    sp.add_argument("--interval", type=float, default=1.0, help="Refresh interval seconds")
    sp.add_argument("--count", type=int, help="Number of refreshes before exit (default: infinite)")
    sp.add_argument("--cleanup", action="store_true", help="Call GPIO.cleanup() on exit")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("monitor", help="Attach edge callbacks and print/log changes")
    sp.add_argument("--pins", nargs="+", help="Pins to monitor (or use --set-name / profile defaults)")
    sp.add_argument("--set-name", help="Use a named set from profile (e.g., 'garage')")
    sp.add_argument("--edge", choices=["RISING","FALLING","BOTH"], default="BOTH")
    sp.add_argument("--pull", choices=["UP","DOWN","OFF"], default="DOWN")
    sp.add_argument("--bounce", type=int, default=200, help="Debounce bouncetime (ms)")
    sp.add_argument("--log-csv", help="Append CSV log (timestamp,pin,state)")
    sp.add_argument("--log-json", help="Append JSONL log (one JSON record per line)")
    sp.add_argument("--cleanup", action="store_true", help="Call GPIO.cleanup() on exit")
    sp.set_defaults(func=cmd_monitor)

    sp = sub.add_parser("read", help="Read a single pin (as input)")
    sp.add_argument("--pin", type=int, required=True)
    sp.add_argument("--pull", choices=["UP","DOWN","OFF"], default="OFF")
    sp.add_argument("--cleanup", action="store_true")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("write", help="Write a single pin (as output)")
    sp.add_argument("--pin", type=int, required=True)
    sp.add_argument("--value", required=True, choices=["HIGH","LOW","1","0","ON","OFF","TRUE","FALSE"])
    sp.add_argument("--cleanup", action="store_true")
    sp.set_defaults(func=cmd_write)

    sp = sub.add_parser("pulse", help="Pulse a pin HIGH for a duration (repeatable)")
    sp.add_argument("--pin", type=int, required=True)
    sp.add_argument("--width", type=float, default=0.5, help="Pulse width seconds")
    sp.add_argument("--repeat", type=int, default=1, help="Number of pulses")
    sp.add_argument("--gap", type=float, default=0.5, help="Gap between pulses (seconds)")
    sp.add_argument("--cleanup", action="store_true")
    sp.set_defaults(func=cmd_pulse)

    sp = sub.add_parser("cleanup", help="GPIO.cleanup()")
    sp.set_defaults(func=cmd_cleanup)

    sp = sub.add_parser("tui", help="Curses TUI dashboard for live status")
    sp.add_argument("--pins", nargs="+", help="Pins to display (or use --set-name / profile defaults)")
    sp.add_argument("--set-name", help="Use a named set from profile (e.g., 'garage')")
    sp.add_argument("--interval", type=float, default=0.5, help="UI refresh interval seconds")
    sp.add_argument("--cleanup", action="store_true", help="Call GPIO.cleanup() on exit")
    sp.set_defaults(func=cmd_tui)

    return p

def main(argv: Optional[Sequence[str]] = None) -> int:
    ensure_root()
    parser = build_parser()
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
