#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
aosp="${1:?Usage: apply-android16.sh /path/to/aosp16}"
aosp="$(cd "$aosp" && pwd)"
tag=android-16.0.0_r4
projects=(frameworks/av build/make system/core frameworks/native build/make)
patches=(0001-avc-high10-overflow-and-tests.patch 0002-k11c-framework-matrix.patch 0003-k11c-ueventd-import.patch 0004-gpuwork-missing-map-and-test.patch 0005-k11c-ril-integration.patch)
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
overlay_files=(Android.bp compatibility_matrix.k11c.xml ueventd.bluetooth.fragment overlay/AndroidManifest.xml overlay/res/values/config.xml ril/k11c-ril-compat.cpp ril/k11c-ril-compat.rc)
for file in "${overlay_files[@]}"; do
  if [[ -e "$aosp/$overlay/$file" ]] && ! cmp -s "$repo_root/$overlay/$file" "$aosp/$overlay/$file"; then
    # Permit upgrading only the exact previously shipped module definition.
    if [[ "$file" != Android.bp ]] || ! python3 - "$aosp/$overlay/$file" <<'PY'
import hashlib, sys
from pathlib import Path
expected = '117f1df36603a7ecbb65f580d03d8bde34c621715b474188710506c97ea7d806'
raise SystemExit(0 if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() == expected else 1)
PY
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
