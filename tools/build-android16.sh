#!/usr/bin/env bash
set -eo pipefail
aosp="${AOSP_ROOT:?Set AOSP_ROOT to your Android16 AOSP checkout}"
jobs="${JOBS:-12}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 1; }
cd "$aosp"
source build/envsetup.sh
lunch aosp_arm64-bp4a-userdebug
m -j"$jobs" systemimage
echo 'Build completed; device validation remains. No flashing performed.'
