#!/usr/bin/env python3
"""Deploy/inspect a badge.team Pixel/CZ2019 badge over its serial REPL.

The badge serves a MicroPython "Python shell" once you select it from the
launcher menu. This drives that shell to push files and launch apps.

Usage:
    uv run tools/badge.py deploy            # push app/ha_energy/* -> apps/ha_energy/
    uv run tools/badge.py launch ha_energy  # start an app (reboots into it)
    uv run tools/badge.py exec "print(1+1)"
    uv run tools/badge.py put <local> <remote>

Default port is the CH340 by-id path; override with --port or $BADGE_PORT.
"""

import argparse
import glob
import os
import pathlib
import sys
import time

import serial  # pyserial

DEFAULT_PORT = os.environ.get("BADGE_PORT", "/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0")
PROMPT = b">>> "
ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_FILES = ["metadata.json", "version", "icon.py", "config.json", "__init__.py"]


def open_shell(port):
    """Reset the badge and land on the MicroPython '>>> ' prompt."""
    s = serial.Serial(port, 115200, timeout=1)
    s.setDTR(False)
    s.setRTS(True)
    time.sleep(0.15)
    s.setRTS(False)  # reset into the launcher
    time.sleep(2.5)
    s.reset_input_buffer()
    for _ in range(4):  # Enter selects menu item 0 = "Python shell"
        s.write(b"\r")
        time.sleep(1.0)
        if PROMPT in s.read(4000):
            break
    s.write(b"\x03")  # Ctrl-C to a clean prompt
    time.sleep(0.3)
    s.reset_input_buffer()
    return s


def run(s, code, timeout=15):
    """Run a snippet via paste mode; return captured stdout text."""
    s.reset_input_buffer()
    s.write(b"\x05")  # Ctrl-E: paste mode
    time.sleep(0.2)
    s.read(400)
    s.write(code.replace("\n", "\r\n").encode() + b"\r\n\x04")  # body + Ctrl-D
    buf = bytearray()
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = s.read(512)
        if chunk:
            buf += chunk
            if buf.endswith(PROMPT):  # ">>> " ends with a space — don't rstrip it
                break
    return buf.decode("utf-8", "replace")


def put(s, local, remote):
    data = pathlib.Path(local).read_bytes()
    hexs = data.hex()
    parent = remote.rsplit("/", 1)[0] if "/" in remote else ""
    setup = "import ubinascii,os\n"
    acc = ""
    for part in parent.split("/"):
        if not part:
            continue
        acc = acc + "/" + part if acc else part
        setup += "try:\n    os.mkdir(%r)\nexcept Exception:\n    pass\n" % acc
    setup += "f=open(%r,'wb')\n" % remote
    run(s, setup, timeout=10)
    for i in range(0, len(hexs), 1024):
        run(s, "f.write(ubinascii.unhexlify(%r))\n" % hexs[i : i + 1024], timeout=10)
    run(s, "f.close()\n", timeout=10)
    print("put %d bytes -> %s" % (len(data), remote))


def cmd_deploy_lib(s, _args):
    for local in sorted(glob.glob(str(ROOT / "lib" / "pixelbadge" / "*.py"))):
        remote = "lib/pixelbadge/" + os.path.basename(local)
        put(s, local, remote)


def cmd_deploy(s, _args):
    src = ROOT / "app" / "ha_energy"
    for name in APP_FILES:
        f = src / name
        if f.exists():
            put(s, str(f), "apps/ha_energy/" + name)
        elif name == "config.json":
            print(
                "WARNING: app/ha_energy/config.json missing — "
                "copy config.example.json and add your token"
            )


def cmd_launch(s, args):
    s.write(b"import system\r\n")
    time.sleep(0.3)
    s.write(("system.start(%r)\r\n" % args.name).encode())
    time.sleep(0.3)
    print("launching %r (badge reboots into it)" % args.name)


def cmd_exec(s, args):
    print(run(s, args.code))


def cmd_put(s, args):
    put(s, args.local, args.remote)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", default=DEFAULT_PORT)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("deploy").set_defaults(func=cmd_deploy)
    sub.add_parser("deploy-lib").set_defaults(func=cmd_deploy_lib)
    lp = sub.add_parser("launch")
    lp.add_argument("name")
    lp.set_defaults(func=cmd_launch)
    ep = sub.add_parser("exec")
    ep.add_argument("code")
    ep.set_defaults(func=cmd_exec)
    pp = sub.add_parser("put")
    pp.add_argument("local")
    pp.add_argument("remote")
    pp.set_defaults(func=cmd_put)
    args = p.parse_args()

    s = open_shell(args.port)
    try:
        args.func(s, args)
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
