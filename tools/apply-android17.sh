#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
aosp="${1:?Usage: apply-android17.sh /path/to/aosp17}"
aosp="$(cd "$aosp" && pwd)"
tag=android-17.0.0_r1
projects=(frameworks/av build/make system/core build/soong frameworks/native)
patches=(0001-avc-high10-overflow-and-tests.patch 0002-k11c-board-integration.patch 0003-k11c-ueventd-import.patch 0004-soong-runtime-memory-controls.patch 0005-gpuwork-missing-map-regression.patch)
pending=()
for i in "${!projects[@]}"; do
  project="$aosp/${projects[$i]}"
  patch="$repo_root/patches/android17/${patches[$i]}"
  expected="$(git -C "$project" rev-parse "$tag^{commit}")"
  [[ "$(git -C "$project" rev-parse HEAD)" == "$expected" ]] || {
    echo "Refusing ${projects[$i]}: HEAD differs from $tag" >&2; exit 1;
  }
  if git -C "$project" apply --reverse --check "$patch" 2>/dev/null; then
    printf 'Already applied: %s\n' "${patches[$i]}"
  else
    git -C "$project" apply --check "$patch"
    pending+=("$i")
  fi
done
overlay=device/kickpi/k11c-gsi
while IFS= read -r -d '' source; do
  relative="${source#"$repo_root/"}"
  if [[ -e "$aosp/$relative" ]] && ! cmp -s "$source" "$aosp/$relative"; then
    echo "Refusing to overwrite differing board source: $relative" >&2; exit 1;
  fi
done < <(find "$repo_root/$overlay" -path "$repo_root/$overlay/private" -prune -o -type f -print0)
while IFS= read -r -d '' source; do
  relative="${source#"$repo_root/"}"
  mkdir -p "$(dirname "$aosp/$relative")"
  cp "$source" "$aosp/$relative"
done < <(find "$repo_root/$overlay" -path "$repo_root/$overlay/private" -prune -o -type f -print0)
for i in "${pending[@]}"; do
  git -C "$aosp/${projects[$i]}" apply "$repo_root/patches/android17/${patches[$i]}"
  printf 'Applied: %s\n' "${patches[$i]}"
done
echo 'Android17 adaptation staged; no build or device writes performed.'
