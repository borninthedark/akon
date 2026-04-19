"""Tests for tools/profiles.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.profiles import (
    ProfileValidationError,
    list_kernel_profiles,
    list_module_profiles,
    load_kernel_profile,
    load_module_profile,
    load_profile,
    main,
)


class TestLoadProfile:
    def test_valid_kernel_profile(self, tmp_path):
        p = tmp_path / "test.yml"
        p.write_text(
            "apiVersion: akon/v1alpha1\n"
            "kind: KernelProfile\n"
            "metadata:\n"
            "  name: test\n"
            "  description: test\n"
            "spec:\n"
            "  source: fedora-srpm\n"
        )
        data = load_profile(p)
        assert data["apiVersion"] == "akon/v1alpha1"
        assert data["kind"] == "KernelProfile"

    def test_valid_module_profile(self, tmp_path):
        p = tmp_path / "zfs.yml"
        p.write_text(
            "apiVersion: akon/v1alpha1\n"
            "kind: ModuleProfile\n"
            "metadata:\n"
            "  name: zfs\n"
            "  description: ZFS\n"
            "spec:\n"
            "  source: oci-artifact\n"
        )
        data = load_profile(p)
        assert data["kind"] == "ModuleProfile"

    def test_wrong_api_version(self, tmp_path):
        p = tmp_path / "bad.yml"
        p.write_text(
            "apiVersion: v2\n"
            "kind: KernelProfile\n"
            "metadata:\n"
            "  name: bad\n"
            "spec: {}\n"
        )
        with pytest.raises(ProfileValidationError, match="apiVersion"):
            load_profile(p)

    def test_wrong_kind(self, tmp_path):
        p = tmp_path / "bad.yml"
        p.write_text(
            "apiVersion: akon/v1alpha1\n"
            "kind: Unknown\n"
            "metadata:\n"
            "  name: bad\n"
            "spec: {}\n"
        )
        with pytest.raises(ProfileValidationError, match="kind"):
            load_profile(p)

    def test_missing_metadata(self, tmp_path):
        p = tmp_path / "bad.yml"
        p.write_text(
            "apiVersion: akon/v1alpha1\n"
            "kind: KernelProfile\n"
            "spec: {}\n"
        )
        with pytest.raises(ProfileValidationError, match="metadata"):
            load_profile(p)

    def test_missing_spec(self, tmp_path):
        p = tmp_path / "bad.yml"
        p.write_text(
            "apiVersion: akon/v1alpha1\n"
            "kind: KernelProfile\n"
            "metadata:\n"
            "  name: bad\n"
        )
        with pytest.raises(ProfileValidationError, match="spec"):
            load_profile(p)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_profile(tmp_path / "nonexistent.yml")


class TestLoadKernelProfile:
    def test_load_by_name(self, kernel_profile_dir):
        data = load_kernel_profile("test", base_dir=kernel_profile_dir)
        assert data["metadata"]["name"] == "test"

    def test_not_found(self, tmp_path):
        (tmp_path / "profiles" / "kernels").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            load_kernel_profile("nonexistent", base_dir=tmp_path)


class TestLoadModuleProfile:
    def test_load_by_name(self, module_profile_dir):
        data = load_module_profile("zfs", base_dir=module_profile_dir)
        assert data["metadata"]["name"] == "zfs"


class TestListProfiles:
    def test_list_kernel_profiles(self, kernel_profile_dir):
        names = list_kernel_profiles(base_dir=kernel_profile_dir)
        assert "test" in names

    def test_list_module_profiles(self, module_profile_dir):
        names = list_module_profiles(base_dir=module_profile_dir)
        assert "zfs" in names

    def test_empty_dir(self, tmp_path):
        (tmp_path / "profiles" / "kernels").mkdir(parents=True)
        assert list_kernel_profiles(base_dir=tmp_path) == []


class TestRealProfiles:
    """Validate the actual profile YAML files in the repo."""

    REPO_ROOT = Path(__file__).resolve().parent.parent

    @pytest.mark.parametrize(
        "name",
        ["fedora-default", "cachyos", "mainline", "stable", "longterm", "next", "gentoo-kernel"],
    )
    def test_kernel_profiles_valid(self, name):
        data = load_kernel_profile(name, base_dir=self.REPO_ROOT)
        assert data["apiVersion"] == "akon/v1alpha1"
        assert data["kind"] == "KernelProfile"
        assert "spec" in data

    def test_zfs_module_profile_valid(self):
        data = load_module_profile("zfs", base_dir=self.REPO_ROOT)
        assert data["apiVersion"] == "akon/v1alpha1"
        assert data["kind"] == "ModuleProfile"


class TestProfilesCLI:
    def test_resolve_kernel(self, capsys):
        rc = main(["resolve", "kernel", "mainline"])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"apiVersion": "akon/v1alpha1"' in out

    def test_resolve_module(self, capsys):
        rc = main(["resolve", "module", "zfs"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ModuleProfile" in out

    def test_resolve_missing(self):
        rc = main(["resolve", "kernel", "nonexistent"])
        assert rc == 1

    def test_list_kernels(self, capsys):
        rc = main(["list", "kernel"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "mainline" in out
        assert "gentoo-kernel" in out

    def test_default_version_module(self, capsys):
        rc = main(["default-version", "module", "zfs"])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.strip() == "2.4.1"

    def test_list_modules(self, capsys):
        rc = main(["list", "module"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "zfs" in out

    def test_no_command(self):
        rc = main([])
        assert rc == 2
