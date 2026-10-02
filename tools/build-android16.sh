#!/usr/bin/env bash
set -eo pipefail
aosp="${AOSP_ROOT:?Set AOSP_ROOT to your Android16 AOSP checkout}"
jobs="${JOBS:-12}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be a positive integer' >&2; exit 1; }
payload_args=(--aosp "$aosp")
if [[ -n "${K11C_RIL_LIBRARY:-}" ]]; then
  payload_args+=(--candidate "$K11C_RIL_LIBRARY")
fi
python3 "$(dirname "$0")/stage-ril-payload.py" "${payload_args[@]}"
cd "$aosp"
source build/envsetup.sh
lunch aosp_arm64-bp4a-userdebug
m -j"$jobs" systemimage
image="$(get_build_var PRODUCT_OUT)/system.img"
# GSI embeds system_ext under /system. Compilation alone does not prove image labels.
for service in k11c-ril-compat k11c-rtc-timer; do
  case "$service" in
    k11c-ril-compat) label=k11c_ril_compat_exec ;;
    k11c-rtc-timer) label=k11c_rtc_timer_exec ;;
  esac
  debugfs -R "ea_list /system/system_ext/bin/$service" "$image" 2>/dev/null |
    grep -F "u:object_r:$label:s0" >/dev/null || {
      echo "Refusing candidate: $service image label is incorrect" >&2
      exit 1
    }
done
for library in k11c/librk-ril.so sensors.k11c-empty.so; do
  debugfs -R "ea_list /system/system_ext/lib64/$library" "$image" 2>/dev/null |
    grep -F 'u:object_r:system_lib_file:s0' >/dev/null || {
      echo "Refusing candidate: immutable library image label is incorrect" >&2
      exit 1
    }
done
echo 'Build completed; device validation remains. No flashing performed.'
