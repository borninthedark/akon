#!/usr/bin/env python3
"""Package RPMs as scratch OCI images and push to a registry.

Replaces scripts/publish.sh with input validation and runtime abstraction.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from tools.constants import DEFAULT_FEDORA_VERSION, DEFAULT_OWNER, DEFAULT_REGISTRY
from tools.container import ContainerRunner, detect_runtime


def derive_image_tag(
    artifact_type: str,
    version: str,
    fedora: str,
    module: str | None = None,
) -> tuple[str, str]:
    """Derive OCI image name and tag from build parameters.

    Pure function — no side effects, fully testable.
    """
    if artifact_type == "kernel":
        return "kernel-rpms", f"{version}-fc{fedora}"

    if artifact_type == "module":
        if not module:
            raise ValueError("module name is required for artifact_type=module")
        return f"{module}-kmod-rpms", version

    raise ValueError(f"Invalid artifact_type: {artifact_type!r}")


def create_staging_dir(rpm_dir: Path) -> str:
    """Create a temp staging directory with RPMs and a scratch Containerfile."""
    rpms = list(rpm_dir.glob("*.rpm"))
    if not rpms:
        raise FileNotFoundError(f"No RPMs found in {rpm_dir}")

    staging = tempfile.mkdtemp(prefix="akon-publish-")
    for rpm in rpms:
        shutil.copy2(rpm, staging)

    (Path(staging) / "Containerfile").write_text("FROM scratch\nCOPY *.rpm /rpms/\n")
    return staging


def _is_local_registry(registry: str) -> bool:
    """Check if a registry is local (skip login)."""
    return registry.startswith("localhost:") or registry.startswith("127.0.0.1:")


def publish(
    artifact_type: str,
    version: str,
    fedora: str,
    registry: str,
    owner: str,
    rpm_dir: Path,
    module: str | None = None,
    dry_run: bool = False,
    skip_login: bool = False,
) -> int:
    """Build a scratch OCI image from RPMs and optionally push it."""
    image_name, tag = derive_image_tag(artifact_type, version, fedora, module)
    image = f"{registry}/{owner}/{image_name}:{tag}"

    print(f"==> Packaging RPMs from {rpm_dir}")
    print(f"==> Target: {image}")

    try:
        staging = create_staging_dir(rpm_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    runner = ContainerRunner(detect_runtime())

    rc, stdout, stderr = runner.build(tag=image, context=staging)
    shutil.rmtree(staging, ignore_errors=True)

    if rc != 0:
        print(f"ERROR: build failed (rc={rc})", file=sys.stderr)
        if stderr:
            print(stderr, file=sys.stderr)
        return rc

    if dry_run:
        print("==> Dry run -- image built but not pushed")
        runner.images(image)
        return 0

    if not skip_login and not _is_local_registry(registry):
        print(f"==> Logging into {registry}")
        rc, _, stderr = runner.login(registry)
        if rc != 0:
            print(f"ERROR: login failed: {stderr}", file=sys.stderr)
            return rc

    rc, _, stderr = runner.push(image)
    if rc != 0:
        print(f"ERROR: push failed: {stderr}", file=sys.stderr)
        return rc

    print(f"==> Pushed: {image}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Package RPMs as OCI image and push")
    parser.add_argument("--type", type=str, dest="artifact_type", help="kernel or module")
    parser.add_argument("--module", type=str, default=None)
    parser.add_argument("--version", type=str, help="Version tag")
    parser.add_argument("--fedora", type=str, default=DEFAULT_FEDORA_VERSION)
    parser.add_argument("--registry", type=str, default=DEFAULT_REGISTRY)
    parser.add_argument("--owner", type=str, default=DEFAULT_OWNER)
    parser.add_argument("--rpm-dir", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-login",
        action="store_true",
        help="Assume the container runtime is already authenticated to the registry",
    )

    args = parser.parse_args(argv)

    if not args.artifact_type or not args.version:
        parser.print_usage(sys.stderr)
        return 2

    if args.artifact_type == "module" and not args.module:
        print("ERROR: --module required for type=module", file=sys.stderr)
        return 2

    if args.rpm_dir:
        rpm_dir = Path(args.rpm_dir)
    elif args.artifact_type == "kernel":
        rpm_dir = Path("output/kernel-rpms")
    else:
        rpm_dir = Path("output/module-rpms")

    try:
        return publish(
            artifact_type=args.artifact_type,
            version=args.version,
            fedora=args.fedora,
            registry=args.registry,
            owner=args.owner,
            rpm_dir=rpm_dir,
            module=args.module,
            dry_run=args.dry_run,
            skip_login=args.skip_login,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
