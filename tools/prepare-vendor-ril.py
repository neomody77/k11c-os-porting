#!/usr/bin/env python3
"""Prepare a local experimental Android16 RIL copy; never install or flash it."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

INPUT_SHA256 = "242fe86dfbdb5796674077ac55ffa4f6facc067c4b3e1bf519f0da5d2925ab5b"
OUTPUT_SHA256 = "f61f59dba68563eb9a037b6ac1c42bd3788724fdf9b94a52badc737624aeda8d"


def prepare(original):
    if hashlib.sha256(original).hexdigest() != INPUT_SHA256:
        raise ValueError("Unsupported factory library SHA256; no output produced")
    image = bytearray(original)
    if image[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", image, 18)[0] != 183:
        raise ValueError("Expected little-endian ARM64 ELF")
    phoff = struct.unpack_from("<Q", image, 32)[0]
    stride, count = struct.unpack_from("<HH", image, 54)

    def offset(address, size):
        for i in range(count):
            kind, _, pos, va, _, filesz, _, _ = struct.unpack_from("<IIQQQQQQ", image, phoff + i * stride)
            if kind == 1 and va <= address and address + size <= va + filesz:
                return pos + address - va
        raise ValueError("Instruction address outside file-backed ELF segment")

    regions = []

    def replace(pos, before, after):
        if len(before) != len(after) or image[pos:pos + len(before)] != before:
            raise ValueError("Unexpected instruction/string baseline")
        image[pos:pos + len(before)] = after
        regions.append({"file_offset": pos, "region_bytes": len(before)})

    # Use the existing vendor linker namespace to resolve the VNDK SONAMEs.
    # Existing /vendor library paths are retained. Do not enumerate /apex.
    for name in ("libnetutils.so", "libcutils.so"):
        before = ("/system/lib64/" + name).encode() + b"\0"
        if image.count(before) != 1:
            raise ValueError("Expected one fallback path")
        after = name.encode() + b"\0"
        replace(image.index(before), before, after + bytes(len(before) - len(after)))
    replace(offset(0x67310, 8), bytes.fromhex("f657bda9f44f01a9"),
            struct.pack("<II", 0x52800000, 0xD65F03C0))  # ql_find_libpath: return 0

    # Accept release 160 only, retaining actual Android16 properties and the
    # existing RIL function table. Other unsupported releases still return 0.
    # cmp w4,160; b.ne old_tail; mov w5,12; str w5,[x25]; b existing continuation.
    before = bytes.fromhex("420300f06303009042a43a9163e4339120008052")
    after = struct.pack("<IIIII", 0x7102809F, 0x540000C1, 0x52800185, 0xB9000325, 0x17FFFECF)
    replace(offset(0x2B560, len(before)), before, after)
    if hashlib.sha256(image).hexdigest() != OUTPUT_SHA256:
        raise ValueError("Candidate hash mismatch")
    return bytes(image), regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factory-library", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New private output directory")
    options = parser.parse_args()
    candidate, regions = prepare(options.factory_library.read_bytes())
    options.out.mkdir(parents=True, mode=0o700, exist_ok=False)
    (options.out / "librk-ril.so").write_bytes(candidate)
    report = {"input_sha256": INPUT_SHA256, "output_sha256": OUTPUT_SHA256,
              "changed_regions": regions, "supported_android_release": "16",
              "status": "experimental candidate; not installed", "flashing_performed": False,
              "limitations": ["No physical modem validation", "No enforcing SELinux validation",
                              "Not an Android17 workaround", "Proprietary output must remain private"]}
    (options.out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
