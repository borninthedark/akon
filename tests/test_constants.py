"""Tests for tools/constants.py."""

from __future__ import annotations

import pytest

from tools.constants import (
    COPR_REPO_PATTERN,
    DEFAULT_FEDORA_VERSION,
    DEFAULT_OWNER,
    DEFAULT_REGISTRY,
    MODULE_NAME_PATTERN,
    VERSION_PATTERN,
    ArtifactType,
    ContainerRuntime,
    KernelSource,
)


class TestKernelSource:
    def test_values(self):
        assert KernelSource.FEDORA_SRPM == "fedora-srpm"
        assert KernelSource.COPR == "copr"
        assert KernelSource.UPSTREAM == "upstream"

    def test_from_string(self):
        assert KernelSource("fedora-srpm") is KernelSource.FEDORA_SRPM


class TestArtifactType:
    def test_values(self):
        assert ArtifactType.KERNEL == "kernel"
        assert ArtifactType.MODULE == "module"


class TestContainerRuntime:
    def test_values(self):
        assert ContainerRuntime.PODMAN == "podman"
        assert ContainerRuntime.DOCKER == "docker"


class TestDefaults:
    def test_defaults(self):
        assert DEFAULT_FEDORA_VERSION == "43"
        assert DEFAULT_REGISTRY == "ghcr.io"
        assert DEFAULT_OWNER == "borninthedark"


class TestVersionPattern:
    @pytest.mark.parametrize(
        "valid",
        ["6.14.2", "6.14", "6.14.2.1", "5.10.100"],
    )
    def test_valid_versions(self, valid):
        assert VERSION_PATTERN.fullmatch(valid)

    @pytest.mark.parametrize(
        "invalid",
        [
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "6.14.2; echo pwned",
            "6.14.2\necho pwned",
            "",
            "abc",
            "../../../etc/passwd",
        ],
    )
    def test_invalid_versions(self, invalid):
        assert VERSION_PATTERN.fullmatch(invalid) is None


class TestCoprRepoPattern:
    @pytest.mark.parametrize(
        "valid",
        [
            "bieszczaders/kernel-cachyos",
            "@kernel-vanilla/stable",
            "@kernel-vanilla/mainline",
            "user/repo-name",
        ],
    )
    def test_valid_copr(self, valid):
        assert COPR_REPO_PATTERN.fullmatch(valid)

    @pytest.mark.parametrize(
        "invalid",
        [
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "no-slash",
            "",
            "a/b; echo pwned",
        ],
    )
    def test_invalid_copr(self, invalid):
        assert COPR_REPO_PATTERN.fullmatch(invalid) is None


class TestModuleNamePattern:
    @pytest.mark.parametrize("valid", ["zfs", "nvidia", "v4l2loopback"])
    def test_valid_modules(self, valid):
        assert MODULE_NAME_PATTERN.fullmatch(valid)

    @pytest.mark.parametrize(
        "invalid",
        [
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "",
            "mod name",
            "../etc",
        ],
    )
    def test_invalid_modules(self, invalid):
        assert MODULE_NAME_PATTERN.fullmatch(invalid) is None
