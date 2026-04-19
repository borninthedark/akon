"""Tests for tools/publish.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.publish import create_staging_dir, derive_image_tag, main, publish


class TestDeriveImageTag:
    def test_kernel(self):
        name, tag = derive_image_tag(
            artifact_type="kernel",
            version="6.14.2",
            fedora="43",
        )
        assert name == "kernel-rpms"
        assert tag == "6.14.2-fc43"

    def test_module_zfs(self):
        name, tag = derive_image_tag(
            artifact_type="module",
            version="6.14.2-zfs-2.3.1",
            fedora="43",
            module="zfs",
        )
        assert name == "zfs-kmod-rpms"
        assert tag == "6.14.2-zfs-2.3.1"

    def test_module_requires_name(self):
        with pytest.raises(ValueError, match="module"):
            derive_image_tag(artifact_type="module", version="1.0", fedora="43")


class TestCreateStagingDir:
    def test_creates_containerfile(self, fake_rpm_dir):
        staging = create_staging_dir(fake_rpm_dir)
        containerfile = Path(staging) / "Containerfile"
        assert containerfile.exists()
        content = containerfile.read_text()
        assert "FROM scratch" in content
        assert "COPY *.rpm /rpms/" in content

    def test_copies_rpms(self, fake_rpm_dir):
        staging = create_staging_dir(fake_rpm_dir)
        rpm_files = list(Path(staging).glob("*.rpm"))
        assert len(rpm_files) == 4

    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No RPMs"):
            create_staging_dir(tmp_path)


class TestPublish:
    def test_dry_run(self, monkeypatch, fake_rpm_dir):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.publish.detect_runtime", lambda: "podman")

        rc = publish(
            artifact_type="kernel",
            version="6.14.2",
            fedora="43",
            registry="ghcr.io",
            owner="borninthedark",
            rpm_dir=fake_rpm_dir,
            dry_run=True,
        )
        assert rc == 0
        # Should have build + images, but no push or login
        cmd_names = [c[1] for c in calls]
        assert "build" in cmd_names
        assert "push" not in cmd_names

    def test_local_registry_skips_login(self, monkeypatch, fake_rpm_dir):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.publish.detect_runtime", lambda: "podman")

        rc = publish(
            artifact_type="kernel",
            version="6.14.2",
            fedora="43",
            registry="localhost:5000",
            owner="borninthedark",
            rpm_dir=fake_rpm_dir,
        )
        assert rc == 0
        cmd_names = [c[1] for c in calls]
        assert "login" not in cmd_names
        assert "push" in cmd_names

    def test_ghcr_does_login(self, monkeypatch, fake_rpm_dir):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.publish.detect_runtime", lambda: "podman")

        rc = publish(
            artifact_type="kernel",
            version="6.14.2",
            fedora="43",
            registry="ghcr.io",
            owner="borninthedark",
            rpm_dir=fake_rpm_dir,
        )
        assert rc == 0
        cmd_names = [c[1] for c in calls]
        assert "login" in cmd_names


class TestPublishMain:
    def test_missing_type_exits(self):
        rc = main(["--version", "6.14.2"])
        assert rc != 0

    def test_missing_version_exits(self):
        rc = main(["--type", "kernel"])
        assert rc != 0

    def test_valid_dry_run(self, monkeypatch, fake_rpm_dir):
        calls = []

        def fake_run(cmd, timeout=30):
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        monkeypatch.setattr("tools.publish.detect_runtime", lambda: "podman")

        rc = main([
            "--type", "kernel",
            "--version", "6.14.2",
            "--fedora", "43",
            "--rpm-dir", str(fake_rpm_dir),
            "--dry-run",
        ])
        assert rc == 0
