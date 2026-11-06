#!/usr/bin/env python3
"""Drift test for the vendored diagnostic-event schema (review finding C43).

schemas/diagnostic-event.schema.json is a byte-for-byte copy of cloud-catcher's
index/diagnostic-event.schema.json (ADR-0006 and its amendment A1). This test pins
the cloud-catcher commit the copy was taken from and the file's SHA-256:

- the local copy must hash to PINNED_SHA256, so an edit here fails CI until the
  pin is moved together with a new copy from cloud-catcher;
- when a cloud-catcher checkout is available (CLOUD_CATCHER_DIR, else a sibling
  ../cloud-catcher), the pinned commit's file must equal the local copy, and the
  checkout's current file must still hash to the pin, so a schema change upstream
  fails until both sides are updated together. Without a checkout (as on CI) that
  half is reported as skipped.

To update: copy the new upstream file byte for byte, then set PINNED_COMMIT and
PINNED_SHA256 to the upstream commit and the new hash in the same change.
Run: python tests/test-diagnostic-schema-drift.py
"""
import hashlib
import os
import pathlib
import subprocess
import sys

PINNED_COMMIT = "8487390ce85d4f3a6441c96013f6265c923be38f"
PINNED_SHA256 = "792503daaeab7d161ffa27fdcc72300c8ae4a86c66869e604bd6ef9abefeb79f"
UPSTREAM_PATH = "index/diagnostic-event.schema.json"

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL = ROOT / "schemas" / "diagnostic-event.schema.json"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def upstream_checkout() -> pathlib.Path | None:
    configured = os.environ.get("CLOUD_CATCHER_DIR")
    candidates = [pathlib.Path(configured)] if configured else [ROOT.parent / "cloud-catcher"]
    for candidate in candidates:
        if (candidate / UPSTREAM_PATH).is_file():
            return candidate
    return None


def main() -> int:
    local = LOCAL.read_bytes()
    digest = hashlib.sha256(local).hexdigest()
    check(digest == PINNED_SHA256, f"vendored schema hashes to the pin ({digest[:16]}... vs {PINNED_SHA256[:16]}...)")
    check(b"\r\n" not in local, "vendored schema keeps LF line endings (a CRLF checkout would change the bytes)")

    checkout = upstream_checkout()
    if checkout is None:
        print("SKIP: no cloud-catcher checkout (set CLOUD_CATCHER_DIR); upstream comparison not run")
    else:
        shown = subprocess.run(
            ["git", "-C", str(checkout), "show", f"{PINNED_COMMIT}:{UPSTREAM_PATH}"],
            capture_output=True,
            check=False,
        )
        if shown.returncode != 0:
            print(f"SKIP: commit {PINNED_COMMIT[:12]} not in {checkout}; pinned-commit comparison not run")
        else:
            check(shown.stdout == local, f"vendored schema equals cloud-catcher {PINNED_COMMIT[:12]}:{UPSTREAM_PATH}")
        current = (checkout / UPSTREAM_PATH).read_bytes()
        check(
            hashlib.sha256(current).hexdigest() == PINNED_SHA256,
            "cloud-catcher's current schema still matches the pin (else copy it and move the pin together)",
        )

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
