#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
aosp="${1:?Usage: apply-android16.sh /path/to/aosp16}"
aosp="$(cd "$aosp" && pwd)"
tag=android-16.0.0_r4
projects=(frameworks/av build/make)
patches=(0001-avc-high10-overflow-and-tests.patch 0002-k11c-framework-matrix.patch)
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
for file in Android.bp compatibility_matrix.k11c.xml; do
  if [[ -e "$aosp/$overlay/$file" ]] && ! cmp -s "$repo_root/$overlay/$file" "$aosp/$overlay/$file"; then
    echo "Refusing to overwrite differing overlay: $overlay/$file" >&2
    exit 1
  fi
done
mkdir -p "$aosp/$overlay"
cp "$repo_root/$overlay/Android.bp" "$repo_root/$overlay/compatibility_matrix.k11c.xml" "$aosp/$overlay/"
for i in "${pending[@]}"; do
  git -C "$aosp/${projects[$i]}" apply "$repo_root/patches/android16/${patches[$i]}"
  printf 'Applied: %s\n' "${patches[$i]}"
done
echo 'Android16 adaptation ready; no build or flashing performed.'
