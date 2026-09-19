"""
Scan all git-tracked files for potential secrets.

Run before every commit:
    python scripts/scan_for_secrets.py

Exits with code 1 if anything suspicious is found.
Add to pre-commit hooks later for automatic enforcement.
"""

import re
import subprocess
import sys
from pathlib import Path


# Patterns that look like real secrets.
PATTERNS = [
    # Brave Search API keys
    (re.compile(r"BSA[A-Za-z0-9_\-]{20,}"), "Brave Search API key"),
    # Resend API keys
    (re.compile(r"re_[A-Za-z0-9]{20,}"), "Resend API key"),
    # Supabase JWT (anon or service_role)
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),
     "Supabase JWT"),
    # Generic AWS keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    # Generic OpenAI keys
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    # Google API key
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "Google API key"),
    # Private keys in PEM format
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "PEM private key"),
    # Slack tokens
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "Slack token"),
]

# Files whose contents we never scan (they're supposed to hold secrets or would false-positive)
SKIP_PATH_MARKERS = {
    ".env",                       # real secrets — never in git anyway
    ".env.example",               # documented placeholders
    ".gitignore",
    "scan_for_secrets.py",        # this file contains patterns
    "test_secrets_scanner.py",    # tests may use fake patterns
    "README.md",                  # docs may mention patterns
    "SECURITY.md",
}

# Substrings that mean "this line is a placeholder, not a real secret"
PLACEHOLDER_MARKERS = [
    "replace-me",
    "replace_me",
    "your-key-here",
    "your_key_here",
    "your-api-key",
    "example",
    "dummy",
    "fake",
    "test-key",
    "xxxxx",
    "yourdomain",
    "your-domain",
    "<your",
]


def get_tracked_files() -> list[Path]:
    """Return all git-tracked files, excluding .git internals."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: not a git repository, or git is not installed.")
        sys.exit(2)

    files = []
    for line in result.stdout.splitlines():
        p = Path(line)
        if p.is_file():
            files.append(p)
    return files


def should_skip(path: Path) -> bool:
    name = path.name
    if name in SKIP_PATH_MARKERS:
        return True
    parts = set(path.parts)
    # Never scan anything inside venv or node_modules
    if "venv" in parts or ".venv" in parts or "node_modules" in parts:
        return True
    return False


def looks_like_placeholder(line: str) -> bool:
    low = line.lower()
    return any(marker in low for marker in PLACEHOLDER_MARKERS)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, pattern_name, matched_snippet)."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        if looks_like_placeholder(line):
            continue
        for pattern, name in PATTERNS:
            match = pattern.search(line)
            if match:
                snippet = match.group(0)[:20] + "..."
                findings.append((lineno, name, snippet))
                break  # one finding per line is enough
    return findings


def main() -> int:
    files = get_tracked_files()
    total_findings = 0

    for path in files:
        if should_skip(path):
            continue
        findings = scan_file(path)
        if findings:
            total_findings += len(findings)
            print(f"\n[{path}]")
            for lineno, name, snippet in findings:
                print(f"  line {lineno}: possible {name} — {snippet}")

    print()
    if total_findings:
        print(f"❌ FOUND {total_findings} POTENTIAL SECRET(S).")
        print("   Review each file, remove the secret, and rotate the key if it was committed.")
        return 1
    else:
        print(f"✅ No secrets found across {len(files)} tracked files.")
        return 0


if __name__ == "__main__":
    sys.exit(main())