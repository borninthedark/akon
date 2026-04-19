# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in akon, please report it
responsibly:

1. **Do not** open a public issue.
2. Email **borninthedark** via GitHub private vulnerability reporting
   at <https://github.com/borninthedark/akon/security/advisories/new>.
3. Include a description of the vulnerability, steps to reproduce, and
   any relevant logs or screenshots.

You should receive an acknowledgment within 48 hours.

## Security Model

Akon builds kernel and kernel-module RPMs inside rootless containers.
Key security properties:

- **Input validation**: All user-supplied values (versions, COPR repo
  slugs, module names, URLs) are validated against strict regex
  allowlists before being interpolated into container scripts. Shell
  metacharacters (`; $ \` | &`) are rejected.
- **Rootless containers**: All builds run via rootless podman (or
  docker in CI). No elevated privileges are required or used.
- **No hardcoded secrets**: Credentials are injected via environment
  variables or direnv `.envrc` files, never stored in source.
- **Secret scanning**: Gitleaks runs as a pre-commit hook and in CI
  to prevent accidental credential commits.
- **Dependency pinning**: Python dependencies are locked via `uv.lock`.

## Supply Chain

- Base build images come from `registry.fedoraproject.org/fedora`.
- ZFS source tarballs are fetched from the official OpenZFS GitHub
  releases.
- OCI artifacts are published to GHCR (`ghcr.io/borninthedark/*`).
