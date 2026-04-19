#!/usr/bin/env python3
"""Generate README.md from live project state.

Reads kernel/module profiles and project structure to produce an
up-to-date README. Run via pre-commit hook or `make readme`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.profiles import list_kernel_profiles, list_module_profiles, load_kernel_profile, load_module_profile


def _kernel_profiles_table(root: Path) -> str:
    """Generate markdown table of kernel profiles."""
    names = list_kernel_profiles(base_dir=root)
    if not names:
        return "*No kernel profiles defined.*"

    rows = ["| Profile | Source | COPR | Description |", "|---------|--------|------|-------------|"]
    for name in names:
        data = load_kernel_profile(name, base_dir=root)
        spec = data.get("spec", {})
        meta = data.get("metadata", {})
        source = spec.get("source", "")
        copr = spec.get("copr", "")
        desc = meta.get("description", "").replace("\n", " ").strip()
        # Truncate long descriptions
        if len(desc) > 80:
            desc = desc[:77] + "..."
        rows.append(f"| `{name}` | {source} | {copr or '—'} | {desc} |")

    return "\n".join(rows)


def _module_profiles_table(root: Path) -> str:
    """Generate markdown table of module profiles."""
    names = list_module_profiles(base_dir=root)
    if not names:
        return "*No module profiles defined.*"

    rows = ["| Module | Source | Packages | Boot Integration |", "|--------|--------|----------|------------------|"]
    for name in names:
        data = load_module_profile(name, base_dir=root)
        spec = data.get("spec", {})
        source = spec.get("source", "")
        pkgs = ", ".join(f"`{p}`" for p in spec.get("packages", []))
        boot = spec.get("boot", {})
        boot_items = []
        if boot.get("depmod"):
            boot_items.append("depmod")
        if boot.get("dracut_modules"):
            boot_items.append("dracut")
        if boot.get("modules_load"):
            boot_items.append("modules-load")
        if boot.get("enable_units"):
            boot_items.append("systemd")
        if boot.get("initramfs_rebuild"):
            boot_items.append("initramfs")
        boot_str = ", ".join(boot_items) or "—"
        rows.append(f"| `{name}` | {source} | {pkgs} | {boot_str} |")

    return "\n".join(rows)


def _project_structure() -> str:
    """Generate project structure tree."""
    return """\
```text
akon/
├── .github/workflows/
│   └── build.yml              # CI: resolve, build, publish, dispatch
├── profiles/
│   ├── kernels/                # Kernel profile definitions (v1alpha1)
│   └── modules/                # Module profile definitions (v1alpha1)
├── tools/
│   ├── build_kernel.py         # Kernel RPM builder
│   ├── build_module.py         # Module RPM builder
│   ├── constants.py            # Enums, defaults, validation patterns
│   ├── container.py            # Runtime abstraction (podman/docker)
│   ├── dry_check.py            # DRY enforcement
│   ├── generate_readme.py      # This file
│   ├── profiles.py             # Profile YAML loader + CLI
│   └── publish.py              # OCI artifact publisher
├── tests/                      # pytest suite (TDD)
├── Makefile                    # Local build targets
├── SECURITY.md                 # Security policy
└── pyproject.toml              # Python project config
```"""


def generate_readme(root: Path) -> str:
    """Generate complete README content."""
    kernel_table = _kernel_profiles_table(root)
    module_table = _module_profiles_table(root)
    structure = _project_structure()

    return f"""\
# Akon

Builds custom kernel and kernel-module RPMs from source, packages them as
scratch OCI images, and pushes to GHCR. These artifacts are consumed by
[Exousia](https://github.com/borninthedark/exousia) via `COPY --from` during
image assembly.

## How It Works

```text
Source (SRPM / COPR / tarball)
    │
    ▼
Fedora container (rpmbuild)
    │
    ▼
RPM artifacts
    │
    ▼
Scratch OCI image (FROM scratch, COPY *.rpm /rpms/)
    │
    ▼
ghcr.io/borninthedark/<name>-rpms:<tag>
    │
    ▼
Exousia image build (COPY --from=ghcr.io/... /rpms/ /tmp/...)
```

## Usage

### Profile-driven builds

```bash
# Build kernel from a named profile
make build-kernel PROFILE=mainline VERSION=6.19.12

# Build kernel + ZFS module
make build-all PROFILE=stable VERSION=6.19.12 ZFS=2.3.1

# Build + publish to local registry (full pipeline)
make local PROFILE=fedora-default VERSION=6.19.12 ZFS=2.3.1

# List available profiles
make list-profiles
```

### Explicit source builds

```bash
# From Fedora SRPM
make build-kernel SOURCE=fedora-srpm VERSION=6.19.12

# From COPR
make build-kernel SOURCE=copr COPR=bieszczaders/kernel-cachyos VERSION=6.19.12

# From upstream tarball
make build-kernel SOURCE=upstream URL=https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.19.12.tar.xz VERSION=6.19.12
```

### Publish

```bash
# To GHCR
make publish-all VERSION=6.19.12 ZFS=2.3.1

# To local registry (localhost:5000)
make publish-local-all VERSION=6.19.12 ZFS=2.3.1
```

### CI (GitHub Actions)

Trigger via `workflow_dispatch` in the Actions tab.

| Input | Description | Default |
|-------|-------------|---------|
| `kernel_profile` | Profile name or `custom` | `fedora-default` |
| `kernel_version` | Target version (e.g. `6.19.12`) | — |
| `fedora_version` | Fedora release | `43` |
| `kernel_source` | Source type (custom only) | `fedora-srpm` |
| `copr_repo` | COPR slug (custom+copr only) | — |
| `upstream_url` | Tarball URL (custom+upstream only) | — |
| `build_modules` | Module list (e.g. `zfs`) | — |
| `zfs_version` | ZFS version | — |
| `dry_run` | Build only, skip push | `false` |
| `force_rebuild` | Rebuild even if artifacts exist | `false` |

The workflow checks GHCR for existing artifacts before building. Set
`force_rebuild` to override.

## Kernel Profiles

{kernel_table}

## Module Profiles

{module_table}

## Artifact Naming

| Artifact | GHCR Image | Tag Format |
|----------|-----------|------------|
| Kernel RPMs | `ghcr.io/borninthedark/kernel-rpms` | `<version>-fc<fedora>` |
| Module RPMs | `ghcr.io/borninthedark/<module>-kmod-rpms` | `<version>-fc<fedora>-<module>-<mod_version>` |

## Consuming Artifacts in Exousia

Exousia pulls these artifacts via `COPY --from` in the generated
Containerfile. Define a kernel profile in
`overlays/base/packages/kernels/` or a module profile in
`overlays/base/packages/modules/` with the OCI image reference.

## Project Structure

{structure}

## Development

```bash
# Run tests
make test

# Run linters + hooks
make lint

# Clean build output
make clean
```

## Required Secrets

| Name | Purpose |
|------|---------|
| `GHCR_PAT` | GHCR personal access token (`packages:write`) |
| `EXOUSIA_PAT` | Token to trigger Exousia rebuild via `repository_dispatch` |

## Related

- [Exousia](https://github.com/borninthedark/exousia) — image assembly
  pipeline
- [Implementation Plan](docs/implementation-plan.md) — architecture and
  task breakdown

## License

MIT
"""


def update_readme(root: Path | None = None) -> int:
    """Write README.md if content has changed. Returns 0 if unchanged, 1 if updated."""
    root = root or Path(__file__).resolve().parent.parent
    readme_path = root / "README.md"
    content = generate_readme(root)

    if readme_path.exists() and readme_path.read_text() == content:
        print("README.md is up to date")
        return 0

    readme_path.write_text(content)
    print("README.md updated")
    return 1


if __name__ == "__main__":
    sys.exit(update_readme())
