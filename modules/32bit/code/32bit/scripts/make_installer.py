#!/usr/bin/env python3
"""Build firmware and prepare a release bundle for the ESP Web Tools installer."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path


CHIP_FAMILY_MAP = {
    "esp32": "ESP32",
    "esp32s2": "ESP32-S2",
    "esp32s3": "ESP32-S3",
    "esp32c3": "ESP32-C3",
    "esp32c2": "ESP32-C2",
    "esp32c6": "ESP32-C6",
    "esp32h2": "ESP32-H2",
    "esp32c5": "ESP32-C5",
}

RESET = "\033[0m"
COLORS = {
    "task": "\033[96m",
    "info": "\033[90m",
    "error": "\033[91m",
    "success": "\033[92m",
}
USE_COLOR = sys.stdout.isatty()


def colorize(message: str, tone: str) -> str:
    if USE_COLOR:
        return f"{COLORS[tone]}{message}{RESET}"
    return message


def print_task(message: str) -> None:
    print(colorize(f"==> {message}", "task"))


def print_info(message: str) -> None:
    print(colorize(message, "info"))


def print_success(message: str) -> None:
    print(colorize(message, "success"))


def stream_subprocess_output(stream, tone: str) -> None:
    try:
        for line in iter(stream.readline, ""):
            print(colorize(line.rstrip("\n"), tone))
    finally:
        stream.close()


def run_idf_build(executable: str, project_root: Path, app_name: str = None) -> None:
    build_cmd = [executable, "build"]
    if app_name:
        build_cmd.extend(["-D", f"APP_NAME={app_name}"])
        print_task(f"Running {executable} build for app: {app_name}")
    else:
        print_task(f"Running {executable} build")
    process = subprocess.Popen(
        build_cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threads = [
        threading.Thread(target=stream_subprocess_output, args=(process.stdout, "info"), daemon=True),
        threading.Thread(target=stream_subprocess_output, args=(process.stderr, "error"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    return_code = process.wait()
    for thread in threads:
        thread.join()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, process.args)
    print()


def run_idf_fullclean(executable: str, project_root: Path) -> None:
    """Run idf.py fullclean to clean the build directory."""
    print_task(f"Cleaning build directory")
    process = subprocess.Popen(
        [executable, "fullclean"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    threads = [
        threading.Thread(target=stream_subprocess_output, args=(process.stdout, "info"), daemon=True),
        threading.Thread(target=stream_subprocess_output, args=(process.stderr, "error"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    return_code = process.wait()
    for thread in threads:
        thread.join()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, process.args)
    print()


def load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing expected file: {path}") from exc


def copy_flash_files(build_dir: Path, entries: dict, output_dir: Path) -> list:
    parts = []
    for offset_hex, relative_path in entries.items():
        offset = int(offset_hex, 16)
        source = build_dir / relative_path
        dest = output_dir / relative_path
        if not source.exists():
            raise SystemExit(f"Flash file {source} does not exist. Run the build again.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        parts.append({"path": relative_path.replace("\\", "/"), "offset": offset})
        print_info(f"Copied {source.relative_to(build_dir)} -> {dest.relative_to(output_dir)}")
    parts.sort(key=lambda item: item["offset"])
    return parts


def build_manifest(project_info: dict, flasher_args: dict, parts: list, app_name: str = None) -> dict:
    flash_settings = flasher_args.get("flash_settings", {})
    chip_raw = flasher_args.get("extra_esptool_args", {}).get("chip", "")
    chip_family = CHIP_FAMILY_MAP.get(chip_raw.lower(), chip_raw.upper())

    # Use app_name directly, or fallback to project name if no app specified
    manifest_name = app_name if app_name else project_info.get("project_name", "ESP32 Project")

    return {
        "name": manifest_name,
        "version": project_info.get("project_version", "0.0.0"),
        "builds": [
            {
                "chipFamily": chip_family,
                "parts": parts,
                "flashSettings": {
                    "flashMode": flash_settings.get("flash_mode"),
                    "flashSize": flash_settings.get("flash_size"),
                    "flashFreq": flash_settings.get("flash_freq"),
                },
            }
        ],
    }


def write_manifest(output_dir: Path, manifest: dict) -> Path:
    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    print_info(f"Wrote manifest to {manifest_path}")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the firmware and prepare release assets.")
    parser.add_argument("--idfpy", default="idf.py", help="idf.py executable to run (default: %(default)s)")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip running idf.py build and only package existing artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist"),
        help="Base directory (relative to project root) where release folders will be written.",
    )
    return parser.parse_args()


def read_version(project_root: Path) -> str:
    version_path = project_root.parent.parent / "VERSION"
    if version_path.exists():
        version = version_path.read_text(encoding="utf-8").strip()
        if version:
            return version
    raise SystemExit(f"Unable to read version from {version_path}")


def get_available_apps(project_root: Path) -> list:
    """Detect available apps by reading CMakeLists.txt"""
    cmake_path = project_root / "main" / "CMakeLists.txt"
    if not cmake_path.exists():
        raise SystemExit(f"CMakeLists.txt not found at {cmake_path}")
    
    try:
        content = cmake_path.read_text(encoding="utf-8")
        # Look for VALID_APPS definition: set(VALID_APPS "fxrack" "reverb")
        match = re.search(r'set\(VALID_APPS\s+"([^"]+)"\s+"([^"]+)"', content)
        if match:
            return [match.group(1), match.group(2)]
        else:
            raise SystemExit(f"Could not find VALID_APPS definition in {cmake_path}")
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"Error reading CMakeLists.txt: {exc}")


def build_and_package_app(
    args: argparse.Namespace,
    project_root: Path,
    app_name: str,
    version: str,
    output_root: Path,
    app_index: int,
    total_apps: int,
) -> Path:
    """Build and package a single app firmware."""
    build_dir = project_root / "build"
    
    # Build the firmware for this app
    if not args.skip_build:
        try:
            print_task(f"Building app {app_index} of {total_apps}: {app_name}")
            run_idf_build(args.idfpy, project_root, app_name)
        except FileNotFoundError:
            print(colorize("idf.py not found. Re-run from an ESP-IDF terminal or pass --skip-build.", "error"))
            sys.exit(1)
    
    # Load build artifacts
    flasher_args = load_json(build_dir / "flasher_args.json")
    project_desc = load_json(build_dir / "project_description.json")
    
    # Create release directory for this app (without project prefix)
    release_dir = output_root / f"{app_name}_{version}"
    
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    print_task(f"Preparing release folder for {app_name}: {release_dir.relative_to(project_root)}")
    
    project_desc["project_version"] = version
    
    parts = copy_flash_files(build_dir, flasher_args.get("flash_files", {}), release_dir)
    manifest = build_manifest(project_desc, flasher_args, parts, app_name)
    write_manifest(release_dir, manifest)
    print()
    
    return release_dir


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_root = args.output if args.output.is_absolute() else project_root / args.output
    
    # Get available apps
    apps = get_available_apps(project_root)
    total_apps = len(apps)
    print_task(f"Building {total_apps} app(s): {', '.join(apps)}")
    print()
    
    version = read_version(project_root)
    release_dirs = []
    
    # Build and package each app
    for index, app_name in enumerate(apps, start=1):
        try:
            release_dir = build_and_package_app(
                args, project_root, app_name, version, output_root, index, total_apps
            )
            release_dirs.append(release_dir)
        except Exception as exc:
            print(colorize(f"Failed to build app '{app_name}': {exc}", "error"))
            if not args.skip_build:
                raise
    
    # Summary
    print()
    print_success(f"\nSuccessfully built {len(release_dirs)} firmware(s):\n")
    for release_dir in release_dirs:
        rel_output = release_dir.relative_to(project_root)
        print_success(f"  - {rel_output}")
    print()
    
    # Clean build directory
    if not args.skip_build:
        try:
            run_idf_fullclean(args.idfpy, project_root)
        except FileNotFoundError:
            print(colorize("idf.py not found. Skipping clean step.", "error"))
        except Exception as exc:
            print(colorize(f"Warning: Failed to clean build directory: {exc}", "error"))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
