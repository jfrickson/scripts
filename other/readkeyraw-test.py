#!/usr/bin/env python3

import argparse
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.local/lib/python3/site-packages"))

from readkeyraw import ReadKeyRaw


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive tester for readkeyraw.py")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Timeout in seconds for each key read (default: 1.0)",
    )
    args = parser.parse_args()

    print("readkeyraw test")
    print("Press keys to see translated tokens.")
    print("Press Esc twice quickly or Ctrl-C to exit.")
    print(f"Timeout token appears every {args.timeout}s if no key is pressed.\n")

    prev = ""
    with ReadKeyRaw() as rkr:
        rkr.set_debug(args.debug)
        while True:
            key = rkr.read_key_raw(timeout=args.timeout)
            display = key.replace("\n", r"\n").replace("\t", r"\t")
            print(display)

            if key == "#C-C":
                break
            if key == "#ESC" and prev == "#ESC":
                break
            prev = key

    print("exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
