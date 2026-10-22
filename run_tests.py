"""
One-command test runner for Tony's automated test suite.

Usage:
    python run_tests.py

Equivalent to `pytest tests/` but also prints a short summary pointer to
the manual QA checklist for rows that require a real Windows machine with
LiveKit/hardware access.
"""

import subprocess
import sys


def main() -> int:
    print("Running Tony automated test suite (tests/)...\n")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])
    print(
        "\nNote: some test-matrix rows (real voice I/O, real Spotify/WhatsApp "
        "automation, real system power actions, real virus scans, Hindi/Hinglish "
        "voice parity) cannot be safely run in CI and require manual on-device "
        "verification. See tests/MANUAL_QA_CHECKLIST.md."
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
