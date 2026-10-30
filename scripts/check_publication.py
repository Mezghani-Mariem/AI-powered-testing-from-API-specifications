"""Inspect candidate/staged Git blobs without displaying secret values.

This check combines known credential formats with the actual configured API key.
It is a focused publication review, not a guarantee against every possible secret.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values


PATTERNS = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
    "github_token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "provider_token": re.compile(rb"\b(?:sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{25,})\b"),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(rb"\bAIza[A-Za-z0-9_-]{35}\b"),
    "jwt": re.compile(rb"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
}
ASSIGNMENT = re.compile(rb'''(?i)["']?(?:api_key|LLM_API_KEY|access_token|auth_token|client_secret|password)["']?\s*[:=]\s*["']([^"'\r\n\\]+)["']''')
SAFE_EXAMPLES = {b"", b"YOUR_KEY", b"YOUR_API_KEY", b"YOUR_AVAILABLE_MODEL", b"offline-test-key", b"private-test-key", b"ollama", b"test", b"dummy"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.staged:
        paths = git("ls-files", "-z").decode("utf-8").split("\0")
    else:
        paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    paths = sorted(set(path for path in paths if path))
    config = {**dotenv_values(".env"), **os.environ}
    api_key = config.get("LLM_API_KEY", "")
    exact_key = api_key.encode("utf-8") if api_key else b""
    if exact_key in SAFE_EXAMPLES:
        exact_key = b""
    findings = []
    total = 0
    for path in paths:
        data = git("show", ":" + path) if args.staged else Path(path).read_bytes()
        total += len(data)
        basename = Path(path).name
        if (basename == ".env" or basename.startswith(".env.")) and basename != ".env.example":
            findings.append({"path": path, "kind": "environment_file"})
        for kind, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append({"path": path, "kind": kind})
        for match in ASSIGNMENT.finditer(data):
            value = match.group(1)
            if value not in SAFE_EXAMPLES and len(value) >= 12 and not value.startswith((b"${", b"{", b"<")):
                findings.append({"path": path, "kind": "credential_assignment_needs_review"})
                break
        if exact_key and exact_key in data:
            findings.append({"path": path, "kind": "configured_api_key"})
    report = {"scope": "staged_index" if args.staged else "working_tree_candidates",
              "files_checked": len(paths), "bytes_checked": total, "findings": findings,
              "secret_values_printed": False,
              "limits": "Known token formats, credential assignments and configured API key; does not prove the absence of every secret."}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
