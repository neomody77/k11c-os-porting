#!/usr/bin/env python3
"""Build and verify an exact K11C native super image offline. Never access a device."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

FACTORY_SHA256 = '2fc3bccf4456c5bccbb5ae8f7d20232bf951d5f41748ca03f532d9abc825d218'
SUPER_BYTES = 3263168512
GROUP_BYTES = 3258974208
PARTITIONS = ('system', 'system_dlkm', 'system_ext', 'vendor', 'vendor_dlkm', 'odm', 'odm_dlkm', 'product')
GROUP = 'rockchip_dynamic_partitions'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_inputs(factory, system, expected_system):
    if factory.stat().st_size != SUPER_BYTES or digest(factory) != FACTORY_SHA256:
        raise ValueError('Unsupported factory super; no candidate generated')
    if len(expected_system) != 64 or any(c not in '0123456789abcdef' for c in expected_system):
        raise ValueError('Expected a full lowercase system SHA256')
    if digest(system) != expected_system or system.stat().st_size % 4096:
        raise ValueError('System image hash or alignment mismatch')
    if system.stat().st_size > GROUP_BYTES:
        raise ValueError('System image exceeds partition group')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--factory-super', required=True, type=Path)
    p.add_argument('--system', required=True, type=Path)
    p.add_argument('--system-sha256', required=True)
    p.add_argument('--tools-dir', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Output directory must be new')
    validate_inputs(a.factory_super, a.system, a.system_sha256)
    a.out.mkdir(parents=True)
    original = a.out / 'factory-partitions'
    original.mkdir()
    subprocess.run([str(a.tools_dir / 'lpunpack'), str(a.factory_super), str(original)], check=True)
    if {f.stem for f in original.glob('*.img')} != set(PARTITIONS):
        raise ValueError('Unexpected factory logical partitions')
    inputs = {name: a.system if name == 'system' else original / (name + '.img') for name in PARTITIONS}
    total = sum(path.stat().st_size for path in inputs.values())
    if total > GROUP_BYTES:
        raise ValueError('Logical images exceed existing super group')
    image = a.out / 'super.img'
    command = [str(a.tools_dir / 'lpmake'), '--metadata-size', '65536', '--metadata-slots', '2',
               '--device', 'super:' + str(SUPER_BYTES), '--super-name', 'super',
               '--group', GROUP + ':' + str(GROUP_BYTES), '--force-full-image', '--output', str(image)]
    for name, path in inputs.items():
        command += ['--partition', f'{name}:readonly:{path.stat().st_size}:{GROUP}', '--image', name + '=' + str(path)]
    subprocess.run(command, check=True)
    if image.stat().st_size != SUPER_BYTES:
        raise ValueError('Unexpected super output size')
    verified = a.out / 'verified-partitions'
    verified.mkdir()
    subprocess.run([str(a.tools_dir / 'lpunpack'), str(image), str(verified)], check=True)
    records = {}
    for name, source in inputs.items():
        target = verified / (name + '.img')
        expected = digest(source)
        if target.stat().st_size != source.stat().st_size or digest(target) != expected:
            raise ValueError('Super readback mismatch: ' + name)
        records[name] = {'bytes': source.stat().st_size, 'sha256': expected,
                         'factory_content_preserved': name != 'system'}
    dump = subprocess.check_output([str(a.tools_dir / 'lpdump'), str(image)], text=True)
    (a.out / 'super-layout.txt').write_text(dump)
    result = {'factory_super_sha256': FACTORY_SHA256, 'super_sha256': digest(image), 'super_bytes': SUPER_BYTES,
              'group_bytes': GROUP_BYTES, 'logical_image_bytes': total, 'group_free_bytes': GROUP_BYTES - total,
              'metadata_slots': 2, 'partitions': records, 'device_access': False, 'flashing_performed': False}
    (a.out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    (a.out / 'SHA256SUMS').write_text(result['super_sha256'] + '  super.img\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
