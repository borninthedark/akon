"""Tests for tools/build_kernel.py."""

from __future__ import annotations

import pytest

from tools.build_kernel import build_container_script, main, validate_inputs
from tools.constants import KernelSource


class TestValidateInputs:
    def test_valid_fedora_srpm(self):
        validate_inputs(
            source=KernelSource.FEDORA_SRPM,
            version="6.14.2",
        )

    def test_valid_copr(self):
        validate_inputs(
            source=KernelSource.COPR,
            version="6.14.2",
            copr_repo="bieszczaders/kernel-cachyos",
        )

    def test_valid_upstream(self):
        validate_inputs(
            source=KernelSource.UPSTREAM,
            version="6.14.2",
            upstream_url="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.14.2.tar.xz",
        )

    def test_copr_requires_repo(self):
        with pytest.raises(ValueError, match="copr_repo"):
            validate_inputs(source=KernelSource.COPR, version="6.14.2")

    def test_upstream_requires_url(self):
        with pytest.raises(ValueError, match="upstream_url"):
            validate_inputs(source=KernelSource.UPSTREAM, version="6.14.2")

    @pytest.mark.parametrize(
        "version",
        ["; rm -rf /", "$(whoami)", "`id`", "6.14.2\necho pwned"],
    )
    def test_rejects_injection_in_version(self, version):
        with pytest.raises(ValueError, match="version"):
            validate_inputs(source=KernelSource.FEDORA_SRPM, version=version)

    @pytest.mark.parametrize(
        "copr",
        ["; rm -rf /", "$(whoami)", "`id`"],
    )
    def test_rejects_injection_in_copr(self, copr):
        with pytest.raises(ValueError, match="copr_repo"):
            validate_inputs(source=KernelSource.COPR, version="6.14.2", copr_repo=copr)


class TestBuildContainerScript:
    def test_fedora_srpm_script(self):
        script = build_container_script(
            source=KernelSource.FEDORA_SRPM,
            version="6.14.2",
            fedora="43",
        )
        assert "set -euo pipefail" in script
        assert "dnf download --source kernel" in script
        assert "6.14.2" in script
        assert "rpmbuild -bb" in script

    def test_copr_script(self):
        script = build_container_script(
            source=KernelSource.COPR,
            version="6.14.2",
            fedora="43",
            copr_repo="bieszczaders/kernel-cachyos",
        )
        assert "dnf copr enable -y" in script
        assert "bieszczaders/kernel-cachyos" in script

    def test_upstream_script(self):
        script = build_container_script(
            source=KernelSource.UPSTREAM,
            version="6.14.2",
            fedora="43",
            upstream_url="https://example.com/linux-6.14.2.tar.xz",
        )
        assert "curl -fLO" in script
        assert "https://example.com/linux-6.14.2.tar.xz" in script

    def test_script_copies_to_output(self):
        script = build_container_script(
            source=KernelSource.FEDORA_SRPM,
            version="6.14.2",
            fedora="43",
        )
        assert "cp" in script
        assert "/output/" in script

    def test_script_is_pure(self):
        """Same inputs produce the same output."""
        a = build_container_script(KernelSource.FEDORA_SRPM, "6.14.2", "43")
        b = build_container_script(KernelSource.FEDORA_SRPM, "6.14.2", "43")
        assert a == b


class TestBuildKernelMain:
    def test_missing_source_exits(self):
        rc = main(["--version", "6.14.2"])
        assert rc != 0

    def test_missing_version_exits(self):
        rc = main(["--source", "fedora-srpm"])
        assert rc != 0

    def test_valid_args_calls_runner(self, monkeypatch, tmp_path):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.build_kernel.detect_runtime", lambda: "podman")

        rc = main([
            "--source", "fedora-srpm",
            "--version", "6.14.2",
            "--fedora", "43",
            "--output", str(tmp_path),
        ])
        assert rc == 0
        assert len(calls) >= 1

    def test_emit_script(self, capsys):
        rc = main([
            "--source", "fedora-srpm",
            "--version", "6.14.2",
            "--fedora", "43",
            "--emit-script",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "set -euo pipefail" in out
        assert "rpmbuild -bb" in out

    def test_emit_script_validates(self):
        rc = main([
            "--source", "fedora-srpm",
            "--version", "; rm -rf /",
            "--emit-script",
        ])
        assert rc == 1

    def test_profile_mainline(self, monkeypatch, capsys):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.build_kernel.detect_runtime", lambda: "podman")

        rc = main([
            "--profile", "mainline",
            "--version", "6.14.2",
            "--emit-script",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "dnf copr enable -y" in out
        assert "@kernel-vanilla/mainline" in out

    def test_profile_fedora_default(self, capsys):
        rc = main([
            "--profile", "fedora-default",
            "--version", "6.14.2",
            "--emit-script",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "dnf download --source kernel" in out

    def test_profile_not_found(self):
        rc = main([
            "--profile", "nonexistent",
            "--version", "6.14.2",
        ])
        assert rc == 1

    def test_profile_overrides_source(self, capsys):
        """--profile takes precedence; --source is ignored."""
        rc = main([
            "--profile", "cachyos",
            "--source", "fedora-srpm",
            "--version", "6.14.2",
            "--emit-script",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "bieszczaders/kernel-cachyos" in out
