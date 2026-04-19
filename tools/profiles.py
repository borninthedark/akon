"""YAML profile loader for kernel and module profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

API_VERSION = "akon/v1alpha1"
VALID_KINDS = {"KernelProfile", "ModuleProfile"}


class ProfileValidationError(Exception):
    """Raised when a profile fails schema validation."""


def load_profile(path: Path) -> dict:
    """Load and validate a profile YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    data = yaml.safe_load(path.read_text())

    if data.get("apiVersion") != API_VERSION:
        raise ProfileValidationError(
            f"Invalid apiVersion: {data.get('apiVersion')!r}, expected {API_VERSION!r}"
        )
    if data.get("kind") not in VALID_KINDS:
        raise ProfileValidationError(
            f"Invalid kind: {data.get('kind')!r}, expected one of {VALID_KINDS}"
        )
    if "metadata" not in data:
        raise ProfileValidationError("Missing required field: metadata")
    if "spec" not in data:
        raise ProfileValidationError("Missing required field: spec")

    return data


def _profiles_dir(kind: str, base_dir: Path | None = None) -> Path:
    """Return the directory for a given profile kind."""
    root = base_dir or Path(__file__).resolve().parent.parent
    return root / "profiles" / kind


def load_kernel_profile(name: str, base_dir: Path | None = None) -> dict:
    """Load a kernel profile by name."""
    path = _profiles_dir("kernels", base_dir) / f"{name}.yml"
    return load_profile(path)


def load_module_profile(name: str, base_dir: Path | None = None) -> dict:
    """Load a module profile by name."""
    path = _profiles_dir("modules", base_dir) / f"{name}.yml"
    return load_profile(path)


def list_kernel_profiles(base_dir: Path | None = None) -> list[str]:
    """List available kernel profile names."""
    d = _profiles_dir("kernels", base_dir)
    return sorted(p.stem for p in d.glob("*.yml")) if d.exists() else []


def list_module_profiles(base_dir: Path | None = None) -> list[str]:
    """List available module profile names."""
    d = _profiles_dir("modules", base_dir)
    return sorted(p.stem for p in d.glob("*.yml")) if d.exists() else []


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for profile operations."""
    parser = argparse.ArgumentParser(description="Manage akon profiles")
    sub = parser.add_subparsers(dest="command")

    resolve_p = sub.add_parser("resolve", help="Resolve a profile to JSON")
    resolve_p.add_argument("kind", choices=["kernel", "module"])
    resolve_p.add_argument("name")

    list_p = sub.add_parser("list", help="List available profiles")
    list_p.add_argument("kind", choices=["kernel", "module"])

    default_p = sub.add_parser("default-version", help="Print a profile default version")
    default_p.add_argument("kind", choices=["kernel", "module"])
    default_p.add_argument("name")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_usage(sys.stderr)
        return 2

    if args.command == "resolve":
        try:
            loader = load_kernel_profile if args.kind == "kernel" else load_module_profile
            data = loader(args.name)
            json.dump(data, sys.stdout, indent=2)
            print()
            return 0
        except (FileNotFoundError, ProfileValidationError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.command == "list":
        lister = list_kernel_profiles if args.kind == "kernel" else list_module_profiles
        for name in lister():
            print(name)
        return 0

    if args.command == "default-version":
        try:
            loader = load_kernel_profile if args.kind == "kernel" else load_module_profile
            data = loader(args.name)
        except (FileNotFoundError, ProfileValidationError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        default_version = data.get("spec", {}).get("default_version")
        if not default_version:
            print(f"ERROR: profile {args.kind}/{args.name} has no default_version", file=sys.stderr)
            return 1

        print(default_version)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
