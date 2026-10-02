#!/usr/bin/env python3
"""Stage a verified private RIL candidate for immutable GSI packaging."""
import argparse
import hashlib
from pathlib import Path

SHA256 = {"16": "f61f59dba68563eb9a037b6ac1c42bd3788724fdf9b94a52badc737624aeda8d",
          "17": "9f82653c2da377bd96416cee9f32a9574cb5e73a1249e4f37b606c123fa70010"}


def stage(aosp, candidate=None, android_release="16"):
    if android_release not in SHA256:
        raise ValueError("Unsupported Android release; no output produced")
    target = aosp / "device/kickpi/k11c-gsi/private/librk-ril.so"
    source = candidate if candidate is not None else target
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256[android_release]:
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
    parser.add_argument("--android-release", choices=SHA256, default="16")
    args = parser.parse_args()
    stage(args.aosp, args.candidate, args.android_release)
    print("Verified private RIL payload staged; no device writes performed.")


if __name__ == "__main__":
    main()
