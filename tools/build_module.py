#!/usr/bin/env python3
"""Build kernel module RPMs inside a container.

Replaces scripts/build-module.sh with input validation and runtime abstraction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.constants import (
    DEFAULT_FEDORA_VERSION,
    MODULE_NAME_PATTERN,
    VERSION_PATTERN,
    KernelSource,
)
from tools.container import ContainerRunner, detect_runtime

# Supported modules — add new modules here
SUPPORTED_MODULES = {"zfs"}


def validate_inputs(
    module: str,
    kernel_version: str,
    zfs_version: str | None = None,
) -> None:
    """Validate build inputs against injection-safe patterns."""
    if not MODULE_NAME_PATTERN.fullmatch(module):
        raise ValueError(f"Invalid module name: {module!r}")

    if module not in SUPPORTED_MODULES:
        raise ValueError(f"Unknown module: {module!r}. Supported: {SUPPORTED_MODULES}")

    if not VERSION_PATTERN.fullmatch(kernel_version):
        raise ValueError(f"Invalid kernel_version: {kernel_version!r}")

    if module == "zfs":
        if not zfs_version:
            raise ValueError("zfs_version is required for zfs module")
        if not VERSION_PATTERN.fullmatch(zfs_version):
            raise ValueError(f"Invalid zfs_version: {zfs_version!r}")


def build_container_script(
    module: str,
    kernel_version: str,
    fedora: str,
    zfs_version: str | None = None,
) -> str:
    """Return the bash script to run inside the build container.

    Pure function — no side effects, fully testable.
    """
    lines = [
        "set -euo pipefail",
        "",
        "# Install kernel headers from the built RPMs",
        "dnf install -y \\",
        "  /kernel-rpms/kernel-devel-*.rpm \\",
        "  /kernel-rpms/kernel-core-*.rpm \\",
        "  /kernel-rpms/kernel-modules-*.rpm",
        "",
        f"KVER=$(ls -1 /usr/src/kernels/ | grep -F '{kernel_version}' | head -1 || true)",
        'if [ -z "${KVER}" ]; then',
        f'  echo "ERROR: installed kernel headers do not match requested kernel version {kernel_version}" >&2',
        "  ls -1 /usr/src/kernels/ >&2 || true",
        "  exit 1",
        "fi",
        'echo "==> Kernel headers: ${KVER}"',
        "",
    ]

    if module == "zfs":
        lines.extend([
            "dnf install -y \\",
            "  rpm-build rpmdevtools \\",
            "  gcc make autoconf automake libtool \\",
            "  libuuid-devel libblkid-devel openssl-devel \\",
            "  zlib-devel libtirpc-devel elfutils-libelf-devel \\",
            "  libaio-devel libattr-devel \\",
            "  python3-devel python3-cffi python3-setuptools",
            "",
            f"curl -fLO 'https://github.com/openzfs/zfs/releases/download/zfs-{zfs_version}/zfs-{zfs_version}.tar.gz'",
            f"tar xf 'zfs-{zfs_version}.tar.gz'",
            f"cd 'zfs-{zfs_version}'",
            "",
            './configure --with-linux="/usr/src/kernels/${KVER}"',
            'make -j"$(nproc)" rpm-utils rpm-kmod KERNEL_VERSION="${KVER}"',
            "",
            "find . -name '*.rpm' \\",
            "  -not -name '*debug*' \\",
            "  -not -name '*src.rpm' \\",
            "  -exec cp {} /output/ \\;",
        ])

    lines.extend([
        "",
        "echo '==> Module RPMs written to /output/'",
        "ls -lh /output/",
    ])

    return "\n".join(lines)


def build_module(
    module: str,
    kernel_version: str,
    fedora: str,
    kernel_rpm_dir: Path,
    output_dir: Path,
    zfs_version: str | None = None,
) -> int:
    """Build module RPMs. Returns 0 on success."""
    validate_inputs(module, kernel_version, zfs_version)

    if not kernel_rpm_dir.is_dir() or not list(kernel_rpm_dir.glob("kernel-devel-*.rpm")):
        print(f"ERROR: kernel RPMs not found in {kernel_rpm_dir}", file=sys.stderr)
        print("Run build-kernel first.", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    script = build_container_script(module, kernel_version, fedora, zfs_version)
    image = f"registry.fedoraproject.org/fedora:{fedora}"

    runner = ContainerRunner(detect_runtime())
    print(f"==> Building {module} module for kernel {kernel_version} on Fedora {fedora}")

    rc, stdout, stderr = runner.run(
        image=image,
        cmd=script,
        volumes={
            str(kernel_rpm_dir): "/kernel-rpms",
            str(output_dir): "/output",
        },
    )

    if stdout:
        print(stdout, end="")
    if rc != 0:
        print(f"ERROR: build failed (rc={rc})", file=sys.stderr)
        if stderr:
            print(stderr, file=sys.stderr)
    else:
        print(f"==> Module RPMs in: {output_dir}")

    return rc


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build kernel module RPMs in a container")
    parser.add_argument("--module", type=str, help="Module to build (e.g. zfs)")
    parser.add_argument("--kernel-version", type=str, help="Kernel version the module targets")
    parser.add_argument("--fedora", type=str, default=DEFAULT_FEDORA_VERSION)
    parser.add_argument("--zfs-version", type=str, default=None)
    parser.add_argument("--kernel-rpms", type=str, default="output/kernel-rpms")
    parser.add_argument("--output", type=str, default="output/module-rpms")
    parser.add_argument(
        "--emit-script", action="store_true",
        help="Print the build script to stdout instead of running it in a container",
    )

    args = parser.parse_args(argv)

    if not args.module or not args.kernel_version:
        parser.print_usage(sys.stderr)
        return 2

    try:
        validate_inputs(args.module, args.kernel_version, args.zfs_version)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.emit_script:
        print(build_container_script(args.module, args.kernel_version, args.fedora, args.zfs_version))
        return 0

    try:
        return build_module(
            module=args.module,
            kernel_version=args.kernel_version,
            fedora=args.fedora,
            kernel_rpm_dir=Path(args.kernel_rpms),
            output_dir=Path(args.output),
            zfs_version=args.zfs_version,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
