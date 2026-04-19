"""Constants and enums shared across akon tools."""

from __future__ import annotations

import re
from enum import StrEnum


class KernelSource(StrEnum):
    """Kernel source types."""

    FEDORA_SRPM = "fedora-srpm"
    COPR = "copr"
    UPSTREAM = "upstream"


class ArtifactType(StrEnum):
    """Build artifact types."""

    KERNEL = "kernel"
    MODULE = "module"


class ContainerRuntime(StrEnum):
    """Supported container runtimes."""

    PODMAN = "podman"
    DOCKER = "docker"


# Defaults
DEFAULT_FEDORA_VERSION = "43"
DEFAULT_REGISTRY = "ghcr.io"
DEFAULT_OWNER = "borninthedark"

# Validation patterns — reject shell metacharacters
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+(?:\.[0-9]+)*")
COPR_REPO_PATTERN = re.compile(r"@?[A-Za-z0-9_-]+/[A-Za-z0-9_-]+")
MODULE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*")
URL_PATTERN = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
