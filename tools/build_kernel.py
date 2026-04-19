#!/usr/bin/env python3
"""Build kernel RPMs inside a container.

Replaces scripts/build-kernel.sh with input validation and runtime abstraction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.constants import (
    COPR_REPO_PATTERN,
    DEFAULT_FEDORA_VERSION,
    URL_PATTERN,
    VERSION_PATTERN,
    KernelSource,
)
from tools.container import ContainerRunner, detect_runtime


def validate_inputs(
    source: KernelSource,
    version: str,
    copr_repo: str | None = None,
    upstream_url: str | None = None,
) -> None:
    """Validate build inputs against injection-safe patterns."""
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid version: {version!r}")

    if source == KernelSource.COPR:
        if not copr_repo:
            raise ValueError("copr_repo is required for copr source")
        if not COPR_REPO_PATTERN.fullmatch(copr_repo):
            raise ValueError(f"Invalid copr_repo: {copr_repo!r}")

    if source == KernelSource.UPSTREAM:
        if not upstream_url:
            raise ValueError("upstream_url is required for upstream source")
        if not URL_PATTERN.fullmatch(upstream_url):
            raise ValueError(f"Invalid upstream_url: {upstream_url!r}")


def build_container_script(
    source: KernelSource,
    version: str,
    fedora: str,
    copr_repo: str | None = None,
    upstream_url: str | None = None,
) -> str:
    """Return the bash script to run inside the build container.

    Pure function — no side effects, fully testable.
    """
    lines = [
        "set -euo pipefail",
        "",
        "dnf install -y \\",
        "  rpm-build rpmdevtools dnf-plugins-core \\",
        "  gcc gcc-c++ make flex bison \\",
        "  openssl-devel elfutils-devel \\",
        "  perl-generators perl-interpreter \\",
        "  bc diffutils findutils git-core \\",
        "  python3 python3-devel dwarves",
        "",
        "rpmdev-setuptree",
        "",
    ]

    if source == KernelSource.FEDORA_SRPM:
        lines.extend([
            f"dnf download --source kernel --releasever '{fedora}'",
            "rpm -ivh kernel-*.src.rpm",
            'SPEC="$HOME/rpmbuild/SPECS/kernel.spec"',
            "CURRENT=$(grep '^Version:' \"$SPEC\" | awk '{print $2}')",
            f'if [ "$CURRENT" != \'{version}\' ]; then',
            f"  echo \"Patching kernel.spec: ${{CURRENT}} -> {version}\"",
            f"  sed -i 's/^Version:.*/Version: {version}/' \"$SPEC\"",
            "fi",
        ])
    elif source == KernelSource.COPR:
        lines.extend([
            f"dnf copr enable -y '{copr_repo}'",
            f"dnf download --source kernel --enablerepo='copr:*' --releasever '{fedora}'",
            "rpm -ivh kernel-*.src.rpm",
        ])
    elif source == KernelSource.UPSTREAM:
        lines.extend([
            f"dnf download --source kernel --releasever '{fedora}'",
            "rpm -ivh kernel-*.src.rpm",
            "cd ~/rpmbuild/SOURCES",
            f"curl -fLO '{upstream_url}'",
            'SPEC="$HOME/rpmbuild/SPECS/kernel.spec"',
            f"sed -i 's/^Version:.*/Version: {version}/' \"$SPEC\"",
        ])

    lines.extend([
        "",
        "dnf builddep -y ~/rpmbuild/SPECS/kernel.spec",
        "",
        "cd ~/rpmbuild/SPECS",
        "rpmbuild -bb \\",
        "  --define 'debug_package %{nil}' \\",
        "  --without debug \\",
        "  --without debuginfo \\",
        "  --without perf \\",
        "  --without tools \\",
        "  --without bpftool \\",
        "  --target x86_64 \\",
        "  kernel.spec",
        "",
        "cp ~/rpmbuild/RPMS/x86_64/kernel-*.rpm /output/",
        "echo '==> Kernel RPMs written to /output/'",
        "ls -lh /output/",
    ])

    return "\n".join(lines)


def build_kernel(
    source: KernelSource,
    version: str,
    fedora: str,
    output_dir: Path,
    copr_repo: str | None = None,
    upstream_url: str | None = None,
) -> int:
    """Build kernel RPMs. Returns 0 on success."""
    validate_inputs(source, version, copr_repo, upstream_url)
    output_dir.mkdir(parents=True, exist_ok=True)

    script = build_container_script(source, version, fedora, copr_repo, upstream_url)
    image = f"registry.fedoraproject.org/fedora:{fedora}"

    runner = ContainerRunner(detect_runtime())
    print(f"==> Building kernel {version} from {source} against Fedora {fedora}")

    rc, stdout, stderr = runner.run(
        image=image,
        cmd=script,
        volumes={str(output_dir): "/output"},
    )

    if stdout:
        print(stdout, end="")
    if rc != 0:
        print(f"ERROR: build failed (rc={rc})", file=sys.stderr)
        if stderr:
            print(stderr, file=sys.stderr)
    else:
        print(f"==> Kernel RPMs in: {output_dir}")

    return rc


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build kernel RPMs in a container")
    parser.add_argument("--profile", type=str, help="Kernel profile name (resolves source/copr)")
    parser.add_argument("--source", type=str, help="Kernel source: fedora-srpm, copr, upstream")
    parser.add_argument("--version", type=str, help="Target kernel version (e.g. 6.14.2)")
    parser.add_argument("--fedora", type=str, default=DEFAULT_FEDORA_VERSION)
    parser.add_argument("--copr", type=str, default=None, help="COPR repo slug")
    parser.add_argument("--url", type=str, default=None, help="Upstream tarball URL")
    parser.add_argument("--output", type=str, default="output/kernel-rpms")
    parser.add_argument(
        "--emit-script", action="store_true",
        help="Print the build script to stdout instead of running it in a container",
    )

    args = parser.parse_args(argv)

    if not args.version:
        parser.print_usage(sys.stderr)
        return 2

    # Resolve source from profile or explicit --source
    copr = args.copr
    url = args.url

    if args.profile:
        from tools.profiles import load_kernel_profile

        try:
            profile = load_kernel_profile(args.profile)
        except (FileNotFoundError, Exception) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        spec = profile["spec"]
        profile_source = spec["source"]
        source_map = {"repo": "fedora-srpm", "fedora-srpm": "fedora-srpm",
                      "copr": "copr", "upstream": "upstream"}
        try:
            source = KernelSource(source_map.get(profile_source, profile_source))
        except ValueError:
            print(f"ERROR: unsupported profile source: {profile_source!r}", file=sys.stderr)
            return 1
        copr = copr or spec.get("copr")
    elif args.source:
        try:
            source = KernelSource(args.source)
        except ValueError:
            print(f"ERROR: invalid source: {args.source!r}", file=sys.stderr)
            return 2
    else:
        print("ERROR: --profile or --source is required", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2

    try:
        validate_inputs(source, args.version, copr, url)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.emit_script:
        print(build_container_script(source, args.version, args.fedora, copr, url))
        return 0

    try:
        return build_kernel(
            source=source,
            version=args.version,
            fedora=args.fedora,
            output_dir=Path(args.output),
            copr_repo=copr,
            upstream_url=url,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
