# Exousia Integration

How Akon kernel/module artifacts flow into the Exousia bootc image pipeline.

## Architecture

```text
Akon (build)                         Exousia (assemble)
─────────────                        ──────────────────
workflow_dispatch                    repository_dispatch
      │                              (kernel-artifact-published)
      ▼                                      │
build-kernel ─► build-modules                │
      │              │                       ▼
      └──────┬───────┘               urahara.yml (orchestrator)
             ▼                               │
      publish to GHCR ──── curl ────►  hiyori.yml (build)
             │                               │
  ghcr.io/borninthedark/                     ▼
    kernel-rpms:<tag>              transpile action
    zfs-kmod-rpms:<tag>                      │
                                             ▼
                                   COPY --from=ghcr.io/...
                                   dnf install --allowerasing
                                   boot integration (ZFS)
```

## Trigger Flow

### 1. Akon publishes artifacts

When Akon's `build.yml` publish job succeeds (and `dry_run` is false),
it sends a `repository_dispatch` to Exousia:

```json
POST https://api.github.com/repos/borninthedark/exousia/dispatches
{
  "event_type": "kernel-artifact-published",
  "client_payload": {
    "kernel_version": "7.0.1",
    "fedora_version": "43",
    "kernel_source": "copr",
    "copr_repo": "@kernel-vanilla/stable",
    "enable_zfs": "true",
    "zfs_version": "2.3.1"
  }
}
```

### 2. Exousia rebuilds

Urahara picks up `repository_dispatch` type `kernel-artifact-published`
and maps `client_payload` fields to Hiyori inputs:

| Payload field | Maps to |
|---------------|---------|
| `fedora_version` | `distro_version` |
| `kernel_source` | `kernel_profile` |
| `enable_zfs` | `enable_zfs` |

### 3. Containerfile generation

The transpiler reads `kernel-config.yml` and generates:

- **COPR kernel**: `dnf copr enable` + `dnf install --allowerasing`
- **OCI kernel**: `COPY --from=ghcr.io/.../kernel-rpms:<tag> /rpms/`
- **ZFS module**: `COPY --from=ghcr.io/.../zfs-kmod-rpms:<tag> /rpms/`
  plus boot integration (depmod, dracut, modules-load, systemd units,
  initramfs rebuild)

## Secrets

### Akon repo

| Secret | Purpose |
|--------|---------|
| `GHCR_PAT` | Push OCI artifacts to ghcr.io |
| `EXOUSIA_PAT` | Trigger `repository_dispatch` on exousia repo |

### Exousia repo

| Secret | Purpose |
|--------|---------|
| `GHCR_PAT` | Pull OCI artifacts from ghcr.io during build |

### Creating the PATs

Both PATs need `repo` scope (for dispatch) or `read:packages` / `write:packages`
(for GHCR). Recommended setup:

1. **GHCR_PAT** — fine-grained PAT with `read:packages` + `write:packages`
   on the user account. Shared across both repos.

2. **EXOUSIA_PAT** — fine-grained PAT with `contents:write` on the
   `borninthedark/exousia` repo only. Set as a secret in the Akon repo.

```bash
# Add secrets via GitHub CLI (or the web UI)
# In the akon repo:
gh secret set GHCR_PAT
gh secret set EXOUSIA_PAT

# In the exousia repo:
gh secret set GHCR_PAT
```

## Exousia Configuration

### kernel-config.yml

Located at `overlays/base/packages/common/kernel-config.yml` in exousia.
Controls which kernel to install and which modules to layer.

```yaml
spec:
  source: copr                        # default | copr | oci
  copr:
    profile: stable
    repo: "@kernel-vanilla/stable"
  kernel_packages:
    - kernel
    - kernel-core
    - kernel-modules
    - kernel-modules-core
    - kernel-modules-extra
  modules:
    - name: zfs
      source: oci
      image: ghcr.io/borninthedark/zfs-kmod-rpms:7.0.1-fc43-zfs-2.3.1
      packages:
        - kmod-zfs
        - zfs
      boot:
        depmod: true
        dracut_modules: [zfs]
        modules_load: [zfs]
        enable_units: [zfs.target, zfs-import-scan.service]
        initramfs_rebuild: true
```

### Manual dispatch

Trigger a build from the GitHub UI or CLI:

```bash
# Dispatch urahara with kernel + ZFS
gh workflow run urahara.yml \
  -f kernel_profile=stable \
  -f enable_zfs=true \
  -R borninthedark/exousia
```

## OCI Artifact Naming

| Artifact | Image | Tag format |
|----------|-------|------------|
| Kernel RPMs | `ghcr.io/borninthedark/kernel-rpms` | `<kernel_version>-fc<fedora>` |
| ZFS kmod RPMs | `ghcr.io/borninthedark/zfs-kmod-rpms` | `<kernel_version>-fc<fedora>-zfs-<zfs_version>` |
| Module RPMs | `ghcr.io/borninthedark/module-rpms` | `<kernel_version>-fc<fedora>` |

## Testing Locally

Before pushing to GHCR, test the full flow against the local registry:

```bash
# 1. Build kernel (akon)
make build-kernel VERSION=7.0.1 SOURCE=copr COPR="@kernel-vanilla/stable"

# 2. Publish to local registry
make publish-local-kernel VERSION=7.0.1

# 3. Update exousia kernel-config.yml to point at localhost:5000
#    image: localhost:5000/borninthedark/kernel-rpms:7.0.1-fc43

# 4. Generate Containerfile (exousia)
uv run python tools/yaml-to-containerfile.py \
  --config adnyeus.yml \
  --kernel-profile stable \
  --output Dockerfile.test

# 5. Verify COPY --from line points to local registry
grep "COPY --from=" Dockerfile.test
```
