# Akon -- Kernel & Module Artifact Builder

> 12th Division, Calendula -- *Despair in Your Heart*

Builds custom kernel and kernel-module RPMs from source, packages them as
scratch OCI images, and pushes to GHCR. These artifacts are consumed by
[Exousia](https://github.com/borninthedark/exousia) via `COPY --from` during
image assembly.

## How It Works

```text
Source (SRPM / COPR / tarball)
    |
    v
Fedora container (rpmbuild)
    |
    v
RPM artifacts
    |
    v
Scratch OCI image (FROM scratch, COPY *.rpm /rpms/)
    |
    v
ghcr.io/borninthedark/<name>-rpms:<tag>
    |
    v
Exousia image build (COPY --from=ghcr.io/... /rpms/ /tmp/...)
```

## Usage

### Build kernel RPMs

```bash
# From Fedora SRPM, patch to specific version
./scripts/build-kernel.sh --source fedora-srpm --version 6.14.2 --fedora 43

# From COPR (e.g. CachyOS)
./scripts/build-kernel.sh --source copr --copr bieszczaders/kernel-cachyos --fedora 43

# From upstream tarball
./scripts/build-kernel.sh --source upstream \
  --url https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.14.2.tar.xz \
  --fedora 43
```

### Build module RPMs

```bash
# ZFS modules matched to a kernel
./scripts/build-module.sh --module zfs --zfs-version 2.3.1 --kernel-version 6.14.2 --fedora 43
```

### Publish to GHCR

```bash
# Package and push kernel RPMs
./scripts/publish.sh --type kernel --version 6.14.2 --fedora 43

# Package and push module RPMs
./scripts/publish.sh --type module --module zfs --version 6.14.2-zfs-2.3.1 --fedora 43
```

### CI (GitHub Actions)

Trigger via `workflow_dispatch` in the Actions tab. Inputs:

| Input | Description | Required |
|-------|-------------|----------|
| `kernel_source` | `fedora-srpm`, `copr`, or `upstream-tarball` | Yes |
| `kernel_version` | Target version (e.g. `6.14.2`) | Yes |
| `fedora_version` | Fedora release to build against | Yes |
| `copr_repo` | COPR repo slug (for `copr` source) | No |
| `upstream_url` | Tarball URL (for `upstream-tarball` source) | No |
| `build_modules` | Comma-separated module list (e.g. `zfs`) | No |
| `zfs_version` | ZFS version (when building `zfs`) | No |
| `dry_run` | Build only, skip push | No |

## Artifact Naming

| Artifact | GHCR Image | Tag Format |
|----------|-----------|------------|
| Kernel RPMs | `ghcr.io/borninthedark/kernel-rpms` | `<kernel_version>-fc<fedora>` |
| ZFS module RPMs | `ghcr.io/borninthedark/zfs-kmod-rpms` | `<kernel_version>-zfs-<zfs_version>` |

## Consuming Artifacts in Exousia

Add an entry to `overlays/base/packages/common/rpm-overrides.yml`:

```yaml
spec:
  overrides:
    - package: kernel
      version: ">= 6.14.2"
      image: ghcr.io/borninthedark/kernel-rpms:6.14.2-fc43
      reason: Custom kernel build
      replaces:
        - kernel
        - kernel-core
        - kernel-modules
        - kernel-modules-core
        - kernel-modules-extra
```

Or define a kernel profile in `overlays/base/packages/kernels/`.

## Project Structure

```text
akon/
├── .github/workflows/
│   └── build.yml          # CI: build, package, push
├── profiles/
│   ├── kernels/            # Kernel profile definitions
│   │   ├── fedora-default.yml
│   │   ├── cachyos.yml
│   │   └── mainline.yml
│   └── modules/            # Module profile definitions
│       └── zfs.yml
├── scripts/
│   ├── build-kernel.sh     # Local kernel RPM build
│   ├── build-module.sh     # Local module RPM build
│   └── publish.sh          # Package as OCI + push to GHCR
└── README.md
```

## Required Secrets

| Name | Purpose |
|------|---------|
| `GHCR_PAT` | GHCR personal access token (`packages:write`) |

## Related

- [Exousia](https://github.com/borninthedark/exousia) -- image assembly pipeline
- [Exousia kernel plan](https://github.com/borninthedark/exousia/blob/main/docs/zfs-implementation-plan.md) -- architecture and task breakdown

## License

MIT
