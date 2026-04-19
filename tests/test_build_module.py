"""Tests for tools/build_module.py."""

from __future__ import annotations

import pytest

from tools.build_module import build_container_script, main, validate_inputs


class TestValidateInputs:
    def test_valid_zfs(self):
        validate_inputs(module="zfs", kernel_version="6.14.2", zfs_version="2.3.1")

    def test_unknown_module(self):
        with pytest.raises(ValueError, match="Unknown module"):
            validate_inputs(module="nvidia", kernel_version="6.14.2")

    def test_zfs_requires_version(self):
        with pytest.raises(ValueError, match="zfs_version"):
            validate_inputs(module="zfs", kernel_version="6.14.2")

    @pytest.mark.parametrize(
        "module",
        ["; rm -rf /", "$(whoami)", "`id`"],
    )
    def test_rejects_injection_in_module(self, module):
        with pytest.raises(ValueError, match="module"):
            validate_inputs(module=module, kernel_version="6.14.2")

    @pytest.mark.parametrize(
        "version",
        ["; rm -rf /", "$(whoami)", "`id`"],
    )
    def test_rejects_injection_in_kernel_version(self, version):
        with pytest.raises(ValueError, match="kernel_version"):
            validate_inputs(module="zfs", kernel_version=version, zfs_version="2.3.1")

    @pytest.mark.parametrize(
        "version",
        ["; rm -rf /", "$(whoami)", "`id`"],
    )
    def test_rejects_injection_in_zfs_version(self, version):
        with pytest.raises(ValueError, match="zfs_version"):
            validate_inputs(module="zfs", kernel_version="6.14.2", zfs_version=version)


class TestBuildContainerScript:
    def test_zfs_script(self):
        script = build_container_script(
            module="zfs",
            kernel_version="6.14.2",
            zfs_version="2.3.1",
            fedora="43",
        )
        assert "set -euo pipefail" in script
        assert "zfs-2.3.1" in script
        assert "./configure" in script
        assert "rpm-utils rpm-kmod" in script

    def test_script_installs_kernel_rpms(self):
        script = build_container_script(
            module="zfs",
            kernel_version="6.14.2",
            zfs_version="2.3.1",
            fedora="43",
        )
        assert "/kernel-rpms/" in script

    def test_script_checks_requested_kernel_version(self):
        script = build_container_script(
            module="zfs",
            kernel_version="6.14.2",
            zfs_version="2.3.1",
            fedora="43",
        )
        assert "grep -F '6.14.2'" in script
        assert "installed kernel headers do not match requested kernel version 6.14.2" in script

    def test_script_copies_to_output(self):
        script = build_container_script(
            module="zfs",
            kernel_version="6.14.2",
            zfs_version="2.3.1",
            fedora="43",
        )
        assert "/output/" in script


class TestBuildModuleMain:
    def test_missing_module_exits(self):
        rc = main(["--kernel-version", "6.14.2"])
        assert rc != 0

    def test_missing_kernel_version_exits(self):
        rc = main(["--module", "zfs"])
        assert rc != 0

    def test_valid_args_calls_runner(self, monkeypatch, fake_rpm_dir):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.build_module.detect_runtime", lambda: "podman")

        rc = main([
            "--module", "zfs",
            "--kernel-version", "6.14.2",
            "--zfs-version", "2.3.1",
            "--fedora", "43",
            "--kernel-rpms", str(fake_rpm_dir),
            "--output", str(fake_rpm_dir.parent / "module-out"),
        ])
        assert rc == 0
        assert len(calls) >= 1

    def test_missing_kernel_rpms_fails(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tools.build_module.detect_runtime", lambda: "podman")

        rc = main([
            "--module", "zfs",
            "--kernel-version", "6.14.2",
            "--zfs-version", "2.3.1",
            "--kernel-rpms", str(tmp_path / "nonexistent"),
        ])
        assert rc != 0

    def test_emit_script(self, capsys):
        rc = main([
            "--module", "zfs",
            "--kernel-version", "6.14.2",
            "--zfs-version", "2.3.1",
            "--fedora", "43",
            "--emit-script",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "set -euo pipefail" in out
        assert "zfs-2.3.1" in out

    def test_emit_script_validates(self):
        rc = main([
            "--module", "zfs",
            "--kernel-version", "; rm -rf /",
            "--zfs-version", "2.3.1",
            "--emit-script",
        ])
        assert rc == 1
