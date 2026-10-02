#!/usr/bin/env python3
"""Stage a verified private RIL candidate for immutable GSI packaging."""
import argparse
import hashlib
from pathlib import Path

SHA256 = "f61f59dba68563eb9a037b6ac1c42bd3788724fdf9b94a52badc737624aeda8d"


def stage(aosp, candidate=None):
    target = aosp / "device/kickpi/k11c-gsi/private/librk-ril.so"
    source = candidate if candidate is not None else target
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Unsupported private RIL payload; no output produced")
    if target.exists() and target.read_bytes() != data:
        raise ValueError("Refusing to overwrite a different private payload")
    if source != target:
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o600)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aosp", required=True, type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    stage(args.aosp, args.candidate)
    print("Verified private RIL payload staged; no device writes performed.")


if __name__ == "__main__":
    main()
