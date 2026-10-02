#!/usr/bin/env python3
"""Run probes on an explicitly selected device; captures remain local and private."""
import argparse
import json
from pathlib import Path
import subprocess
import datetime

FEATURES = ("inventory", "storage", "keystore", "gpu", "network", "video-hardware",
            "video-software", "audio-decode", "audio-play", "audio-record", "webview",
            "sensor", "animation", "video-hardware-1080p60-surface", "video-hardware-1080p60-bounded")

def probe_status(text, feature, exit_code):
    """Instrumentation may exit zero even when the probe reports FAIL."""
    for line in reversed(text.splitlines()):
        try:
            report = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(report, dict) and report.get("test") == feature:
            if exit_code == 0 and report.get("status") == "PASS":
                return {"status": "PASS"}
            return {"status": "FAIL", "error": report.get("error", "probe or instrumentation failed")}
    return {"status": "FAIL", "error": "missing probe JSON result"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="Your device serial; never commit it")
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--bluetooth-scan", action="store_true", help="Requires Bluetooth already enabled")
    options = parser.parse_args()
    default = Path(__file__).resolve().parents[1] / "artifacts" / datetime.datetime.now(datetime.timezone.utc).strftime("diagnostics-%Y%m%dT%H%M%SZ")
    out = options.out or default
    out.mkdir(parents=True, exist_ok=False)
    adb = ["adb", "-s", options.serial]
    package = "org.kickpi.diagnostics"
    installed_packages = subprocess.check_output(adb + ["shell", "pm", "list", "packages", package], text=True).splitlines()
    if "package:" + package in installed_packages:
        raise SystemExit("Refusing to replace an existing diagnostics installation")
    installed = False
    results = {}
    try:
        subprocess.run(adb + ["install", str(options.apk)], check=True)
        installed = True
        permissions = ["RECORD_AUDIO"]
        if options.bluetooth_scan:
            permissions.extend(["BLUETOOTH_CONNECT", "BLUETOOTH_SCAN"])
        for permission in permissions:
            subprocess.run(adb + ["shell", "pm", "grant", package, "android.permission." + permission], check=True)
        for feature in FEATURES + (("bluetooth-scan",) if options.bluetooth_scan else ()):
            try:
                run = subprocess.run(adb + ["shell", "am", "instrument", "-w", "-e", "test", feature, package + "/.Probe"], capture_output=True, text=True, timeout=45)
                text = run.stdout + run.stderr
                results[feature] = {"exit_code": run.returncode}
                results[feature].update(probe_status(text, feature, run.returncode))
                (out / (feature + ".txt")).write_text(text)
            except subprocess.TimeoutExpired:
                results[feature] = {"status": "FAIL", "timeout_seconds": 45}
            finally:
                subprocess.run(adb + ["shell", "am", "force-stop", package], check=True)
    finally:
        if installed:
            subprocess.run(adb + ["uninstall", package], check=True)
        (out / "run-status.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Captures saved locally. Review and extract public metrics; do not publish raw results.")

if __name__ == "__main__":
    main()
