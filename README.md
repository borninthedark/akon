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

| Profile | Source | COPR | Description |
|---------|--------|------|-------------|
| `cachyos` | copr | bieszczaders/kernel-cachyos | CachyOS performance-optimized kernel with BORE scheduler. Requires x86-64-v3 ... |
| `fedora-default` | repo | — | Stock Fedora kernel from the base image. No-op profile — the kernel shipped i... |
| `longterm` | copr | @kernel-vanilla/longterm | Longterm (LTS) kernel from kernel.org via Fedora kernel-vanilla COPR. Extende... |
| `mainline` | copr | @kernel-vanilla/mainline | Mainline kernel from kernel.org via Fedora kernel-vanilla COPR. Tracks Linus'... |
| `next` | copr | @kernel-vanilla/next | linux-next integration kernel via Fedora kernel-vanilla COPR. Bleeding edge -... |
| `stable` | copr | @kernel-vanilla/stable | Latest stable kernel from kernel.org via Fedora kernel-vanilla COPR. Point re... |

## Module Profiles

| Module | Source | Packages | Boot Integration |
|--------|--------|----------|------------------|
| `zfs` | oci-artifact | `kmod-zfs`, `zfs` | depmod, dracut, modules-load, systemd, initramfs |

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
```

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
