import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

privacy = load("privacy", "check-publication.py")
boot = load("boot", "prepare-boot.py")
runner = load("runner", "run-diagnostics.py")
ril = load("ril", "prepare-vendor-ril.py")
enforcing_boot = load("enforcing_boot", "prepare-enforcing-boot.py")
payload = load("payload", "stage-ril-payload.py")

class PayloadTests(unittest.TestCase):
    def test_unknown_payload_creates_no_aosp_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.so"
            candidate.write_bytes(b"unknown firmware")
            with self.assertRaises(ValueError):
                payload.stage(root / "aosp", candidate)
            self.assertFalse((root / "aosp").exists())

    def test_missing_payload_creates_no_aosp_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "aosp"
            with self.assertRaises(FileNotFoundError):
                payload.stage(root)
            self.assertFalse(root.exists())

def cpio(name, payload):
    fields = [1, 0o100644, 0, 0, 1, 0, len(payload), 0, 0, 0, 0, len(name) + 1, 0]
    prefix = b"070701" + b"".join(f"{value:08x}".encode() for value in fields) + name.encode() + b"\0"
    prefix += b"\0" * (-len(prefix) % 4)
    return prefix + payload + b"\0" * (-len(payload) % 4)

def archive(fstab):
    return cpio("init", b"unchanged payload") + cpio("fstab.rk30board", fstab) + cpio("TRAILER!!!", b"")

FSTAB = b"system /system erofs ro wait,logical,first_stage_mount\nsystem /system ext4 ro wait,logical,first_stage_mount\nvendor /vendor ext4 ro wait,logical,first_stage_mount\n"

class PrivacyTests(unittest.TestCase):
    def test_actual_identifiers_rejected_without_echoing(self):
        value = "/" + "Users" + "/example\n" + "person" + "@" + "mail.example\n" + ":".join(["ab"] * 6)
        rules = {rule for _, rule in privacy.findings(value)}
        self.assertTrue({"personal-home-path", "email", "mac-address"} <= rules)

    def test_private_and_public_addresses_rejected(self):
        for chunks in (("10", "2", "3", "4"), ("8", "8", "8", "8")):
            self.assertIn("network-address", {rule for _, rule in privacy.findings(".".join(chunks))})

    def test_placeholders_and_noreply_are_allowed(self):
        text = "/path/to/aosp16 192.0.2.1 " + "123+example" + "@users.noreply.github.com"
        self.assertEqual(privacy.findings(text), [])

    def test_secrets_and_capture_files_rejected(self):
        self.assertTrue(privacy.findings("gh" + "p_" + "x" * 30))
        self.assertFalse(privacy.path_allowed(Path("docs/raw/trace.txt")))
        self.assertFalse(privacy.path_allowed(Path("system.img")))

class BootTests(unittest.TestCase):
    def test_only_system_fstab_changes_and_payload_metadata_preserved(self):
        before = list(boot.entries(archive(FSTAB)))
        after = list(boot.entries(boot.patch_ramdisk(archive(FSTAB))))
        self.assertEqual(before[0], after[0])
        self.assertEqual(after[1][3].count(b",avb=vbmeta"), 2)
        self.assertIn(b"vendor /vendor ext4 ro wait,logical,first_stage_mount\n", after[1][3])

    def test_unexpected_or_already_patched_layout_fails(self):
        for fstab in (FSTAB.splitlines(keepends=True)[0], FSTAB.replace(b"first_stage_mount", b"first_stage_mount,avb=vbmeta")):
            with self.assertRaises(ValueError):
                boot.patch_ramdisk(archive(fstab))

    def test_truncated_or_missing_fstab_fails(self):
        for raw in (archive(FSTAB)[:50], cpio("TRAILER!!!", b"")):
            with self.assertRaises(ValueError):
                boot.patch_ramdisk(raw)

    def test_oversized_output_is_rejected(self):
        with self.assertRaises(ValueError):
            boot.pad_to_original(b"larger", b"small")

class EnforcingBootTests(unittest.TestCase):
    def test_unknown_boot_is_rejected_without_modifying_input(self):
        original = b"unknown boot revision"
        with self.assertRaisesRegex(ValueError, "Unsupported boot baseline"):
            enforcing_boot.prepare(original)
        self.assertEqual(original, b"unknown boot revision")

    def test_rejected_boot_creates_no_candidate_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "boot.img"
            original.write_bytes(b"unsupported firmware")
            output = Path(directory) / "candidate"
            args = ["prepare-enforcing-boot.py", "--boot", str(original), "--out", str(output)]
            with mock.patch("sys.argv", args), self.assertRaises(ValueError):
                enforcing_boot.main()
            self.assertFalse(output.exists())
            self.assertEqual(original.read_bytes(), b"unsupported firmware")

class RilCandidateTests(unittest.TestCase):
    def test_unknown_library_is_rejected_without_modifying_input(self):
        raw = bytearray(b"unrecognized vendor library")
        before = bytes(raw)
        with self.assertRaisesRegex(ValueError, "Unsupported factory library"):
            ril.prepare(raw)
        self.assertEqual(bytes(raw), before)

    def test_failed_preparation_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "factory.so"
            original.write_bytes(b"wrong firmware revision")
            output = Path(directory) / "candidate"
            args = ["prepare-vendor-ril.py", "--factory-library", str(original), "--out", str(output)]
            with mock.patch("sys.argv", args), self.assertRaises(ValueError):
                ril.main()
            self.assertFalse(output.exists())
            self.assertEqual(original.read_bytes(), b"wrong firmware revision")

class RunnerTests(unittest.TestCase):
    def test_probe_fail_with_successful_instrumentation_is_failure(self):
        report = '{"test":"inventory","status":"FAIL","error":"actual failure"}'
        self.assertEqual(runner.probe_status(report, "inventory", 0), {"status": "FAIL", "error": "actual failure"})

    def test_pass_requires_matching_json_and_successful_exit(self):
        report = '{"test":"inventory","status":"PASS"}'
        self.assertEqual(runner.probe_status(report, "inventory", 0), {"status": "PASS"})
        for text, feature, code in ((report, "gpu", 0), ("no JSON", "inventory", 0), (report, "inventory", 1)):
            self.assertEqual(runner.probe_status(text, feature, code)["status"], "FAIL")

    def invoke(self, output, packages="", timeout=False):
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            if timeout and "instrument" in command:
                raise subprocess.TimeoutExpired(command, 45)
            return subprocess.CompletedProcess(command, 0, "probe output", "")
        args = ["run-diagnostics.py", "--serial", "DOCUMENTATION_DEVICE", "--apk", "local.apk", "--out", str(output)]
        with mock.patch("sys.argv", args), mock.patch.object(runner, "FEATURES", ("inventory",)), mock.patch.object(runner.subprocess, "check_output", return_value=packages) as listing, mock.patch.object(runner.subprocess, "run", side_effect=run), mock.patch("builtins.print"):
            runner.main()
            self.assertEqual(listing.call_args.args[0][-4:], ["pm", "list", "packages", "org.kickpi.diagnostics"])
        return commands

    def test_absent_package_is_installed_and_cleaned_up(self):
        with tempfile.TemporaryDirectory() as directory:
            commands = self.invoke(Path(directory) / "captures")
            self.assertTrue(any("install" in command for command in commands))
            self.assertEqual(commands[-1][-2:], ["uninstall", "org.kickpi.diagnostics"])

    def test_existing_package_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["run-diagnostics.py", "--serial", "DOCUMENTATION_DEVICE", "--apk", "local.apk", "--out", str(Path(directory) / "captures")]
            with mock.patch("sys.argv", args), mock.patch.object(runner.subprocess, "check_output", return_value="package:org.kickpi.diagnostics\n"), mock.patch.object(runner.subprocess, "run") as run:
                with self.assertRaises(SystemExit):
                    runner.main()
                run.assert_not_called()

    def test_timeout_stops_probe_and_uninstalls_package(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "captures"
            commands = self.invoke(output, timeout=True)
            self.assertEqual(commands[-2][-2:], ["force-stop", "org.kickpi.diagnostics"])
            self.assertEqual(commands[-1][-2:], ["uninstall", "org.kickpi.diagnostics"])
            self.assertIn('"timeout_seconds": 45', (output / "run-status.json").read_text())

if __name__ == "__main__":
    unittest.main()
