#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
aosp="${1:?Usage: prepare-android17.sh /path/to/aosp17 [existing-aosp-reference]}"
reference="${2:-}"
jobs="${SYNC_JOBS:-2}"
tag=android-17.0.0_r1
manifest_commit=5bc9a7ce1cd78dd53613bbfd0ebf506e1e4adb0f
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'SYNC_JOBS must be a positive integer' >&2; exit 1; }
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  echo 'Use a Linux x86_64 build machine.' >&2; exit 1;
}
for tool in repo git python3 flock df; do command -v "$tool" >/dev/null; done
if [[ -n "$reference" ]]; then
  reference="$(cd "$reference" && pwd -P)"
  [[ -d "$reference/.repo/project-objects" ]] || { echo 'Invalid AOSP reference checkout.' >&2; exit 1; }
  [[ ! -f "$reference/.repo/manifests.git/shallow" ]] || {
    echo 'A shallow manifest is unsafe as a reference; omit the reference argument.' >&2; exit 1;
  }
fi
mkdir -p "$aosp"
aosp="$(cd "$aosp" && pwd -P)"
[[ "$aosp" != "$reference" ]] || { echo 'Use a separate Android17 checkout.' >&2; exit 1; }
exec 9>"$aosp/.k11c-prepare.lock"
flock -n 9 || { echo 'Android17 preparation is already running.' >&2; exit 1; }
if [[ -d "$aosp/.repo" ]]; then
  [[ "$(git -C "$aosp/.repo/manifests" rev-parse HEAD)" == "$manifest_commit" ]] || {
    echo 'Refusing a checkout with a different manifest.' >&2; exit 1;
  }
else
  python3 - "$aosp" <<'PY'
import sys
from pathlib import Path
entries = [p for p in Path(sys.argv[1]).iterdir() if p.name != '.k11c-prepare.lock']
if entries:
    raise SystemExit('Refusing a nonempty directory without the expected manifest.')
PY
fi
available="$(df -PB1 "$aosp" | awk 'NR==2 {print $4}')"
(( available >= 400 * 1024 * 1024 * 1024 )) || {
  echo 'Require at least 400 GiB free for a separate source and build workspace.' >&2; exit 1;
}
cd "$aosp"
init_args=(-u https://android.googlesource.com/platform/manifest -b "$tag" --depth=1 --no-clone-bundle)
if [[ -n "$reference" ]]; then init_args+=(--reference "$reference"); fi
repo init "${init_args[@]}"
[[ "$(git -C .repo/manifests rev-parse HEAD)" == "$manifest_commit" ]] || {
  echo 'Official manifest differs from the verified Android17 baseline.' >&2; exit 1;
}
synced=false
for attempt in 1 2 3 4 5; do
  if repo sync -c -j"$jobs" --fail-fast --no-clone-bundle; then
    synced=true
    break
  fi
  if (( attempt < 5 )); then
    delay=$((30 * (2 ** (attempt - 1))))
    echo "Source sync failed (attempt $attempt/5); retrying in ${delay}s."
    sleep "$delay"
  fi
done
[[ "$synced" == true ]] || { echo 'Source synchronization did not complete.' >&2; exit 1; }
mkdir -p "$aosp/.repo/k11c"
repo manifest -r -o "$aosp/.repo/k11c/android17-pinned-manifest.xml"
echo 'Android17 source synchronized and revisions recorded. No patches, build or flashing performed.'
