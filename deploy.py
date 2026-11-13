#!/usr/bin/env python3
"""
deploy.py — Portable deployment script for SWARM_CONSOLIDATED.

Usage:
    python3 deploy.py              # install deps + verify
    python3 deploy.py --install    # same as above
    python3 deploy.py --test       # run smoke test
    python3 deploy.py --all        # install + test
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"[+] {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def install_requirements() -> None:
    req = REPO_ROOT / "requirements.txt"
    if not req.exists():
        print("[!] requirements.txt not found, skipping pip install")
        return

    # Try normal install first, fall back to --break-system-packages for PEP 668 systems
    try:
        run([sys.executable, "-m", "pip", "install", "-r", str(req)])
    except subprocess.CalledProcessError:
        print("[!] Direct pip install failed, trying --break-system-packages...")
        run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", str(req)])


def copy_env_example() -> None:
    example = REPO_ROOT / ".env.example"
    env = REPO_ROOT / ".env"
    if env.exists():
        print("[=] .env already exists, skipping")
        return
    if example.exists():
        shutil.copy(example, env)
        print("[+] Created .env from .env.example — edit it with your API keys")
    else:
        print("[!] .env.example not found")


def run_smoke_test() -> None:
    print("[+] Running smoke test...")
    result = subprocess.run(
        [sys.executable, "swarm_unified.py", "test", "--architecture", "combine",
         "--model", "ULTRA_FREE_CLOUD_FAST", "--tier", "free"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print("[!] Smoke test failed")
        sys.exit(1)
    print("[+] Smoke test passed")


def main() -> None:
    ap = argparse.ArgumentParser(description="Deploy SWARM_CONSOLIDATED")
    ap.add_argument("--install", action="store_true", help="Install requirements + copy .env")
    ap.add_argument("--test", action="store_true", help="Run smoke test")
    ap.add_argument("--all", action="store_true", help="Install + test")
    args = ap.parse_args()

    if not any([args.install, args.test, args.all]):
        args.install = True
        args.test = True

    if args.install or args.all:
        print("=== Installing SWARM_CONSOLIDATED ===")
        install_requirements()
        copy_env_example()
        print("[+] Install complete\n")

    if args.test or args.all:
        print("=== Running smoke test ===")
        run_smoke_test()
        print("[+] All done\n")


if __name__ == "__main__":
    main()
