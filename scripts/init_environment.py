#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import os
import subprocess

def run_cmd(cmd):
    try: os.system(cmd)
    except: pass

def install_uv():
    os_name = os.name
    print("System OS:", os_name)
    if os_name == "posix":
        print("Installing uv on Linux/macOS...")
        os.system("wget -qO- https://astral.sh/uv/install.sh | sh")
    elif os_name == "nt":
        print("Installing uv on Windows...")
        os.system('powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
    print("uv installation complete.")

def create_environment(out_dir: Path, find_links: str | None = None) -> None:
    os.chdir(out_dir)

    if not (out_dir/"pyproject.toml").is_file():
        print("Create project")
        run_cmd('uv init --python 3.12')
        if not (out_dir/"pyproject.toml").is_file():
            print("Cannot create project with `uv init --python 3.12`")
            return
    
    if not (out_dir/".venv").is_dir():
        print("Creating venv")
        run_cmd("uv venv")
        if not (out_dir/".venv").is_dir():
            print("Cannot create venv with `uv venv`")
            return
    
    install_cmd = "uv add pyrite-sdk"
    if find_links:
        install_cmd += f' --find-links "{find_links}"'
    run_cmd(install_cmd)
    print(f"Created environment directory at {out_dir}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Create an environment for PyriteSDK plugin development.")
    parser.add_argument("--output", "-o", required=True, help="Environment output directory.")
    parser.add_argument(
        "--find_links",
        "--find-links",
        dest="find_links",
        help="Optional package index link or wheel directory for transition builds before PyPI release.",
    )
    args = parser.parse_args()
    out_dir = Path(args.output).expanduser().resolve()

    try:
        uv_version = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        print("uv is already installed. Version:", uv_version.stdout.strip())
    except FileNotFoundError:
        print("uv is not installed. Installing uv...")
        install_uv()

    create_environment(out_dir, args.find_links)
    print(f"Created environment at {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
