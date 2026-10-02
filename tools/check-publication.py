#!/usr/bin/env python3
"""Check publishable files and optionally all Git history; never echo matched values."""
import argparse
import ipaddress
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "personal-home-path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+"),
    "email": re.compile(r"[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "mac-address": re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}(?![\w:])"),
    "hardcoded-adb-serial": re.compile(r"\badb\s+(?:[^\n]*\s)?-s\s+['\"]?[a-z0-9]{8,}"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "private-key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6 = re.compile(r"(?<!\w)(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?!\w)")
DOC_NETWORKS = tuple(ipaddress.ip_network(x) for x in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"))
FORBIDDEN_SUFFIXES = {".img", ".apk", ".jks", ".keystore", ".log", ".pcap", ".pcapng", ".png", ".jpg", ".jpeg", ".mp4", ".tar", ".gz", ".zip", ".pem", ".key", ".p12", ".pfx"}
FORBIDDEN_PARTS = {"artifacts", "evidence", "private", "raw", ".repo", "out", "build"}

def findings(text):
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in RULES.items():
            for match in pattern.finditer(line):
                if name == "email" and match.group().endswith("@users.noreply.github.com"):
                    continue
                result.append((number, name))
        for pattern in (IPV4, IPV6):
            for match in pattern.finditer(line):
                try:
                    address = ipaddress.ip_address(match.group())
                except ValueError:
                    continue
                if not (address.is_loopback or address.is_unspecified or any(address.version == network.version and address in network for network in DOC_NETWORKS)):
                    result.append((number, "network-address"))
    return sorted(set(result))

def path_allowed(path):
    return not (set(path.parts) & FORBIDDEN_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES
                or path.name.startswith(".env") or path.name in {".netrc", ".gitcookies"}
                or path.name.startswith("adbkey"))

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

def inspect(path, content):
    errors = []
    if not path_allowed(Path(path)):
        errors.append((path, 0, "forbidden-path-or-filetype"))
    try:
        text = content.decode("utf-8")
        if "\0" in text:
            errors.append((path, 0, "binary-content"))
        errors.extend((path, line, rule) for line, rule in findings(text))
    except UnicodeDecodeError:
        errors.append((path, 0, "non-text-content"))
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    options = parser.parse_args()
    errors = []
    if (ROOT / ".git").exists():
        files = sorted(set(p.decode() for p in git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0") if p))
    else:
        files = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts)
    for name in files:
        path = ROOT / name
        if path.is_symlink():
            errors.append((name, 0, "symlink-needs-review"))
        elif path.exists():
            errors.extend(inspect(name, path.read_bytes()))
    if options.history and (ROOT / ".git").exists():
        for line, rule in findings(git("log", "--all", "--format=%an <%ae>%n%cn <%ce>%n%B").decode()):
            errors.append(("Git metadata", line, rule))
        seen = set()
        for line in git("rev-list", "--objects", "--all").decode().splitlines():
            fields = line.split(" ", 1)
            if len(fields) != 2 or fields[0] in seen:
                continue
            oid, path = fields
            seen.add(oid)
            if git("cat-file", "-t", oid).strip() == b"blob":
                errors.extend(inspect("history/" + path, git("cat-file", "blob", oid)))
    if errors:
        for path, line, rule in errors:
            print(f"{path}:{line}: {rule}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Publication check passed: {len(files)} text files; history={'checked' if options.history else 'not requested'}")

if __name__ == "__main__":
    main()
