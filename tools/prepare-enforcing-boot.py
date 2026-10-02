#!/usr/bin/env python3
"""Prepare an exact K11C enforcing boot copy offline; never access a device."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

BASE_SHA256 = '5081f1f69552e3314ff039a288544d9edc99b826c2dd94c575d587309940fba4'
BASE_BYTES = 41943040


def prepare(original):
    if len(original) != BASE_BYTES or hashlib.sha256(original).hexdigest() != BASE_SHA256:
        raise ValueError('Unsupported boot baseline; no candidate generated')
    if original[:8] != b'ANDROID!' or struct.unpack_from('<I', original, 40)[0] != 2:
        raise ValueError('Expected Android boot header v2')
    old = original[64:576].split(b'\0')[0]
    tokens = old.split()
    if tokens.count(b'androidboot.selinux=permissive') != 1:
        raise ValueError('Expected exactly one permissive boot parameter')
    new = old.replace(b'androidboot.selinux=permissive', b'androidboot.selinux=enforcing')
    expected = [b'androidboot.selinux=enforcing' if t == b'androidboot.selinux=permissive' else t for t in tokens]
    if new.split() != expected or len(new) >= 512:
        raise ValueError('Unexpected command line change')
    candidate = original[:64] + new.ljust(512, b'\0') + original[576:]
    assert candidate[:64] == original[:64] and candidate[576:] == original[576:]
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Output directory must be new')
    candidate = prepare(args.boot.read_bytes())
    args.out.mkdir(parents=True)
    (args.out / 'boot.img').write_bytes(candidate)
    result = {'input_sha256': BASE_SHA256, 'output_sha256': hashlib.sha256(candidate).hexdigest(),
              'bytes': len(candidate), 'only_changed_field': 'boot header primary command line',
              'changed_parameter': 'androidboot.selinux: permissive -> enforcing',
              'kernel_ramdisk_second_dtb_and_all_other_bytes_unchanged': True,
              'previous_dsu_avb_fstab_fix_retained': True, 'flashing_performed': False}
    (args.out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
