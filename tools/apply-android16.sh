#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
aosp="${1:?Usage: apply-android16.sh /path/to/aosp16}"
aosp="$(cd "$aosp" && pwd)"
tag=android-16.0.0_r4
projects=(frameworks/av build/make system/core frameworks/native build/make build/make build/make build/make build/make)
patches=(0001-avc-high10-overflow-and-tests.patch 0002-k11c-framework-matrix.patch 0003-k11c-ueventd-import.patch 0004-gpuwork-missing-map-and-test.patch 0005-k11c-ril-integration.patch 0006-k11c-enforcing-domain.patch 0007-k11c-no-device-sensors.patch 0008-k11c-gsi-image-labels.patch 0009-k11c-immutable-ril-payload.patch)
pending=()
for i in "${!projects[@]}"; do
  project="$aosp/${projects[$i]}"
  patch="$repo_root/patches/android16/${patches[$i]}"
  expected="$(git -C "$project" rev-parse "$tag^{commit}")"
  actual="$(git -C "$project" rev-parse HEAD)"
  if [[ "$actual" != "$expected" ]]; then
    echo "Refusing ${projects[$i]}: HEAD differs from $tag" >&2
    exit 1
  fi
  if git -C "$project" apply --reverse --check "$patch" 2>/dev/null; then
    printf 'Already applied: %s\n' "${patches[$i]}"
  else
    git -C "$project" apply --check "$patch"
    pending+=("$i")
  fi
done
overlay=device/kickpi/k11c-gsi
overlay_files=(Android.bp compatibility_matrix.k11c.xml ueventd.bluetooth.fragment overlay/AndroidManifest.xml overlay/res/values/config.xml ril/k11c-ril-compat.cpp ril/k11c-ril-compat.rc sepolicy/k11c_ril_compat.te sepolicy/file_contexts sepolicy/property_contexts sensors/empty.c rtc/timer.cpp rtc/timer.rc sepolicy/k11c_rtc_timer.te sepolicy/genfs_contexts sepolicy/k11c_bluetooth.te)
for file in "${overlay_files[@]}"; do
  if [[ -e "$aosp/$overlay/$file" ]] && ! cmp -s "$repo_root/$overlay/$file" "$aosp/$overlay/$file"; then
    # Only exact previously committed versions may be upgraded.
    if ! python3 - "$aosp/$overlay/$file" "$file" <<'PYUPGRADE'
import hashlib, sys
from pathlib import Path
allowed = {'Android.bp': ['3ea84f860ca8e59d651bb66d25bb16f8f43d5df65044e61cf4793d223df5520e'], 'ril/k11c-ril-compat.cpp': ['512a6ffddf8d9f3d5a6f45ca20c0c485795525ed7493d4e285085c9c86d20096'], 'ril/k11c-ril-compat.rc': ['067caddf3834084cc769701e3f84aef88bbc6794143338177a4907aff3b13901']}
allowed['Android.bp'].append('117f1df36603a7ecbb65f580d03d8bde34c621715b474188710506c97ea7d806')
actual = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
raise SystemExit(0 if actual in allowed.get(sys.argv[2], []) else 1)
PYUPGRADE
    then
      echo "Refusing to overwrite differing overlay: $overlay/$file" >&2
      exit 1
    fi
  fi
done
for file in "${overlay_files[@]}"; do
  mkdir -p "$(dirname "$aosp/$overlay/$file")"
  cp "$repo_root/$overlay/$file" "$aosp/$overlay/$file"
done
for i in "${pending[@]}"; do
  git -C "$aosp/${projects[$i]}" apply "$repo_root/patches/android16/${patches[$i]}"
  printf 'Applied: %s\n' "${patches[$i]}"
done
echo 'Android16 adaptation ready; no build or flashing performed.'
