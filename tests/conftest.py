"""Shared fixtures for akon tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def fake_rpm_dir(tmp_path: Path) -> Path:
    """Create a temp directory with fake RPM files."""
    for name in [
        "kernel-6.14.2-200.fc43.x86_64.rpm",
        "kernel-core-6.14.2-200.fc43.x86_64.rpm",
        "kernel-modules-6.14.2-200.fc43.x86_64.rpm",
        "kernel-devel-6.14.2-200.fc43.x86_64.rpm",
    ]:
        (tmp_path / name).write_bytes(b"\x00" * 64)
    return tmp_path


@pytest.fixture()
def fake_module_rpm_dir(tmp_path: Path) -> Path:
    """Create a temp directory with fake module RPM files."""
    for name in [
        "kmod-zfs-6.14.2-1.fc43.x86_64.rpm",
        "zfs-2.3.1-1.fc43.x86_64.rpm",
    ]:
        (tmp_path / name).write_bytes(b"\x00" * 64)
    return tmp_path


@pytest.fixture()
def kernel_profile_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a test kernel profile."""
    profiles = tmp_path / "profiles" / "kernels"
    profiles.mkdir(parents=True)
    (profiles / "test.yml").write_text(
        "apiVersion: akon/v1alpha1\n"
        "kind: KernelProfile\n"
        "metadata:\n"
        "  name: test\n"
        "  description: test profile\n"
        "spec:\n"
        "  source: fedora-srpm\n"
        "  packages:\n"
        "    - kernel\n"
    )
    return tmp_path


@pytest.fixture()
def module_profile_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a test module profile."""
    profiles = tmp_path / "profiles" / "modules"
    profiles.mkdir(parents=True)
    (profiles / "zfs.yml").write_text(
        "apiVersion: akon/v1alpha1\n"
        "kind: ModuleProfile\n"
        "metadata:\n"
        "  name: zfs\n"
        "  description: ZFS module\n"
        "spec:\n"
        "  source: oci-artifact\n"
        "  packages:\n"
        "    - kmod-zfs\n"
    )
    return tmp_path
