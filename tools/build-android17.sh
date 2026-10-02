#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail
aosp="${AOSP_ROOT:?Set AOSP_ROOT to your Android17 AOSP checkout}"
jobs="${JOBS:-12}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 1; }
memory_limit="${K11C_SOONG_MEMORY_LIMIT:-24GiB}"
gc_percent="${K11C_SOONG_GC_PERCENT:-50}"
[[ "$memory_limit" =~ ^[1-9][0-9]*(MiB|GiB)$ ]] || { echo 'Invalid Go memory budget' >&2; exit 1; }
[[ "$gc_percent" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid Go GC percentage' >&2; exit 1; }
export GOMEMLIMIT="$memory_limit" GOGC="$gc_percent"
payload_args=(--aosp "$aosp" --android-release 17)
if [[ -n "${K11C_RIL_LIBRARY:-}" ]]; then payload_args+=(--candidate "$K11C_RIL_LIBRARY"); fi
python3 "$(dirname "$0")/stage-ril-payload.py" "${payload_args[@]}"
cd "$aosp"
source build/envsetup.sh
lunch aosp_arm64-cp2a-userdebug
[[ "$(get_build_var PLATFORM_SDK_VERSION)" == 37 ]] || { echo 'Refusing an unexpected API level' >&2; exit 1; }
m -j"$jobs" systemimage CodecCapabilitiesTest k11c_gpuwork_regression_test
image="$(get_build_var PRODUCT_OUT)/system.img"
for service in k11c-ril-compat k11c-rtc-timer; do
  case "$service" in
    k11c-ril-compat) label=k11c_ril_compat_exec ;;
    k11c-rtc-timer) label=k11c_rtc_timer_exec ;;
  esac
  debugfs -R "ea_list /system/system_ext/bin/$service" "$image" 2>/dev/null |
    grep -F "u:object_r:$label:s0" >/dev/null || { echo "Incorrect label: $service" >&2; exit 1; }
done
for library in k11c/librk-ril.so sensors.k11c-empty.so; do
  debugfs -R "ea_list /system/system_ext/lib64/$library" "$image" 2>/dev/null |
    grep -F 'u:object_r:system_lib_file:s0' >/dev/null || { echo "Incorrect label: $library" >&2; exit 1; }
done
echo 'Android17 candidate compiled and labels checked; runtime/device validation remains.'
