#!/usr/bin/env python3
"""Offline K11C boot-image preparation. Never accesses a connected device."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

def entries(blob):
    offset = 0
    while offset + 110 <= len(blob):
        header = blob[offset:offset + 110]
        if header[:6] != b"070701":
            raise ValueError("Only newc without CRC is supported")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        if namesize < 1 or offset + 110 + namesize > len(blob):
            raise ValueError("Invalid CPIO filename")
        dataoff = (offset + 110 + namesize + 3) & ~3
        end = (dataoff + size + 3) & ~3
        if end > len(blob) or blob[offset + 110 + namesize - 1] != 0:
            raise ValueError("Truncated CPIO entry")
        name = blob[offset + 110:offset + 110 + namesize - 1].decode()
        yield name, fields, blob[offset:dataoff], blob[dataoff:dataoff + size], offset, end
        offset = end
        if name == "TRAILER!!!":
            return
    raise ValueError("CPIO trailer missing")

def patch_ramdisk(raw):
    before = list(entries(raw))
    pieces, changed, lastend = [], [], 0
    for name, fields, prefix, payload, start, end in before:
        lastend = end
        if name == "fstab.rk30board":
            lines = payload.decode().splitlines(keepends=True)
            count = 0
            for i, line in enumerate(lines):
                tokens = line.split()
                if len(tokens) >= 5 and tokens[0:2] == ["system", "/system"]:
                    if tokens[4] != "wait,logical,first_stage_mount":
                        raise ValueError("Unexpected system fs_mgr flags; no candidate generated")
                    lines[i] = line.replace(tokens[4], tokens[4] + ",avb=vbmeta")
                    count += 1
            if count != 2:
                raise ValueError("Expected exactly two system fstab entries")
            payload = "".join(lines).encode()
            prefix = prefix[:54] + f"{len(payload):08x}".encode() + prefix[62:]
            changed.append(name)
            pieces.append(prefix + payload + b"\0" * (-len(payload) % 4))
        else:
            pieces.append(raw[start:end])
    if changed != ["fstab.rk30board"]:
        raise ValueError("Expected one fstab.rk30board")
    patched = b"".join(pieces) + raw[lastend:]
    patched += b"\0" * (-len(patched) % 512)
    after = list(entries(patched))
    if [e[0] for e in before] != [e[0] for e in after]:
        raise ValueError("CPIO entry ordering changed")
    for old, new in zip(before, after):
        if old[1][:6] + old[1][7:] != new[1][:6] + new[1][7:]:
            raise ValueError("CPIO metadata changed")
        if old[0] != "fstab.rk30board" and old[3] != new[3]:
            raise ValueError("Unrelated ramdisk payload changed")
    return patched

NATIVE_BASE_SHA256 = "0b4f45d963ee65296b16ea0161add3cc92168890b97f30969113163b2090b52f"
NATIVE_BASE_BYTES = 41943040


def patch_native_ramdisk(raw):
    before = list(entries(raw))
    pieces, changed, lastend = [], [], 0
    for name, fields, prefix, payload, start, end in before:
        lastend = end
        if name != "fstab.rk30board":
            pieces.append(raw[start:end])
            continue
        kept, removed, system = [], [], 0
        for line in payload.decode().splitlines(keepends=True):
            tokens = line.split()
            if tokens and tokens[0] in ("system_ext", "product"):
                if (len(tokens) != 5 or tokens[1] != "/" + tokens[0] or
                        tokens[2] not in ("erofs", "ext4") or
                        tokens[4] != "wait,logical,first_stage_mount"):
                    raise ValueError("Unexpected native mount layout")
                removed.append((tokens[0], tokens[2]))
                continue
            if len(tokens) >= 5 and tokens[:2] == ["system", "/system"]:
                if tokens[4] != "wait,logical,first_stage_mount,avb=vbmeta":
                    raise ValueError("Native boot must retain existing system AVB fix")
                system += 1
            kept.append(line)
        if sorted(removed) != [("product", "erofs"), ("product", "ext4"),
                               ("system_ext", "erofs"), ("system_ext", "ext4")] or system != 2:
            raise ValueError("Expected four legacy mounts and two AVB system entries")
        payload = "".join(kept).encode()
        prefix = prefix[:54] + f"{len(payload):08x}".encode() + prefix[62:]
        pieces.append(prefix + payload + b"\0" * (-len(payload) % 4))
        changed.append(name)
    if changed != ["fstab.rk30board"]:
        raise ValueError("Expected one fstab.rk30board")
    patched = b"".join(pieces) + raw[lastend:]
    patched += b"\0" * (-len(patched) % 512)
    after = list(entries(patched))
    if [e[0] for e in before] != [e[0] for e in after]:
        raise ValueError("CPIO entry ordering changed")
    for old, new in zip(before, after):
        if old[1][:6] + old[1][7:] != new[1][:6] + new[1][7:]:
            raise ValueError("CPIO metadata changed")
        if old[0] != "fstab.rk30board" and old[3] != new[3]:
            raise ValueError("Unrelated ramdisk payload changed")
    return patched


def pad_to_original(payload, original):
    if len(payload) > len(original):
        raise ValueError("Repacked image exceeds original image size")
    return payload + b"\0" * (len(original) - len(payload))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot-mode", choices=("dsu", "native"), default="dsu")
    parser.add_argument("--factory-boot", required=True, type=Path)
    parser.add_argument("--mkbootimg-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args()
    orig, tools, dest = options.factory_boot.resolve(), options.mkbootimg_dir.resolve(), options.out.resolve()
    if dest.exists():
        raise ValueError("Output directory must be new; never overwrite prior captures")
    original = orig.read_bytes()
    if options.boot_mode == "native" and (len(original) != NATIVE_BASE_BYTES or
            hashlib.sha256(original).hexdigest() != NATIVE_BASE_SHA256):
        raise ValueError("Unsupported native boot baseline; no candidate generated")
    dest.mkdir(parents=True)
    unpacked = dest / "original-unpacked"
    unpacked.mkdir()
    args = shlex.split(subprocess.check_output([
        sys.executable, str(tools / "unpack_bootimg.py"), "--boot_img", str(orig),
        "--out", str(unpacked), "--format=mkbootimg"], text=True))
    baseline = dest / "baseline.img"
    subprocess.run([sys.executable, str(tools / "mkbootimg.py"), *args, "--output", str(baseline)], check=True)
    if pad_to_original(baseline.read_bytes(), original) != original:
        raise ValueError("Baseline repacking is not byte-identical")
    raw = gzip.decompress((unpacked / "ramdisk").read_bytes())
    patched = patch_native_ramdisk(raw) if options.boot_mode == "native" else patch_ramdisk(raw)
    ramdisk = dest / "ramdisk"
    ramdisk.write_bytes(gzip.compress(patched, compresslevel=9, mtime=0))
    new_args = args.copy()
    new_args[new_args.index("--ramdisk") + 1] = str(ramdisk)
    out = dest / "boot.img"
    subprocess.run([sys.executable, str(tools / "mkbootimg.py"), *new_args, "--output", str(out)], check=True)
    out.write_bytes(pad_to_original(out.read_bytes(), original))
    checkdir = dest / "verified-unpacked"
    checkdir.mkdir()
    subprocess.run([sys.executable, str(tools / "unpack_bootimg.py"), "--boot_img", str(out), "--out", str(checkdir)], check=True, stdout=subprocess.DEVNULL)
    for name in ("kernel", "second", "dtb"):
        first, second = unpacked / name, checkdir / name
        if first.exists() != second.exists() or (first.exists() and first.read_bytes() != second.read_bytes()):
            raise ValueError("Boot component changed: " + name)
    if gzip.decompress((checkdir / "ramdisk").read_bytes()) != patched:
        raise ValueError("Ramdisk readback mismatch")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    result = {"baseline_repack": "byte-identical", "changed_ramdisk_files": ["fstab.rk30board"],
              "boot_mode": options.boot_mode,
              "changed_fstab_entries": 4 if options.boot_mode == "native" else 2,
              "legacy_system_ext_product_mounts_removed": options.boot_mode == "native", "image_bytes": len(original), "patched_boot_sha256": digest,
              "kernel_second_dtb": "unchanged", "device_access": False, "flashing_performed": False}
    (dest / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    (dest / "SHA256SUMS").write_text(digest + "  boot.img\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
