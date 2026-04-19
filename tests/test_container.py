"""Tests for tools/container.py."""

from __future__ import annotations

import subprocess

import pytest

from tools.constants import ContainerRuntime
from tools.container import ContainerRunner, detect_runtime, run_command


class TestDetectRuntime:
    def test_env_var_podman(self, monkeypatch):
        monkeypatch.setenv("CONTAINER_RUNTIME", "podman")
        assert detect_runtime() == ContainerRuntime.PODMAN

    def test_env_var_docker(self, monkeypatch):
        monkeypatch.setenv("CONTAINER_RUNTIME", "docker")
        assert detect_runtime() == ContainerRuntime.DOCKER

    def test_env_var_invalid(self, monkeypatch):
        monkeypatch.setenv("CONTAINER_RUNTIME", "rkt")
        with pytest.raises(ValueError, match="rkt"):
            detect_runtime()

    def test_fallback_podman(self, monkeypatch):
        monkeypatch.delenv("CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/podman" if cmd == "podman" else None)
        assert detect_runtime() == ContainerRuntime.PODMAN

    def test_fallback_docker(self, monkeypatch):
        monkeypatch.delenv("CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/docker" if cmd == "docker" else None)
        assert detect_runtime() == ContainerRuntime.DOCKER

    def test_nothing_found(self, monkeypatch):
        monkeypatch.delenv("CONTAINER_RUNTIME", raising=False)
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        with pytest.raises(RuntimeError, match="No container runtime"):
            detect_runtime()


class TestRunCommand:
    def test_success(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: fake,
        )
        rc, out, err = run_command(["echo", "ok"])
        assert rc == 0
        assert out == "ok\n"

    def test_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=["slow"], timeout=30)

        monkeypatch.setattr("subprocess.run", raise_timeout)
        rc, out, err = run_command(["slow"], timeout=30)
        assert rc == -1
        assert "timed out" in err.lower()

    def test_failure(self, monkeypatch):
        fake = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="fail")
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: fake)
        rc, out, err = run_command(["false"])
        assert rc == 1
        assert err == "fail"


class TestContainerRunner:
    @pytest.fixture()
    def runner(self, monkeypatch):
        """ContainerRunner with a captured command log."""
        commands = []

        def fake_run(cmd, timeout=30):
            commands.append(cmd)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        r = ContainerRunner(ContainerRuntime.PODMAN)
        r._commands = commands
        return r

    def test_run(self, runner):
        rc, _, _ = runner.run(
            image="fedora:43",
            cmd="echo hello",
            volumes={"/src": "/dst"},
        )
        assert rc == 0
        cmd = runner._commands[-1]
        assert cmd[0] == "podman"
        assert "run" in cmd
        assert "--rm" in cmd
        assert "fedora:43" in cmd

    def test_build(self, runner):
        rc, _, _ = runner.build(tag="test:latest", context="/tmp/ctx")
        assert rc == 0
        cmd = runner._commands[-1]
        assert "build" in cmd
        assert "-t" in cmd

    def test_push(self, runner):
        rc, _, _ = runner.push("ghcr.io/user/img:tag")
        assert rc == 0
        cmd = runner._commands[-1]
        assert "push" in cmd

    def test_login(self, runner):
        rc, _, _ = runner.login("ghcr.io")
        assert rc == 0
        cmd = runner._commands[-1]
        assert "login" in cmd

    def test_images(self, runner):
        rc, _, _ = runner.images("test:latest")
        assert rc == 0
        cmd = runner._commands[-1]
        assert "images" in cmd

    def test_run_default_timeout(self, runner, monkeypatch):
        """run() should use 7200s timeout for long kernel builds."""
        timeouts = []

        def fake_run(cmd, timeout=30):
            timeouts.append(timeout)
            return 0, "", ""

        monkeypatch.setattr("tools.container.run_command", fake_run)
        runner.run(image="fedora:43", cmd="make")
        assert timeouts[-1] == 7200

    def test_run_volumes(self, runner):
        runner.run(
            image="fedora:43",
            cmd="ls",
            volumes={"/a": "/b", "/c": "/d"},
        )
        cmd = runner._commands[-1]
        v_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
        assert "/a:/b:z" in v_args
        assert "/c:/d:z" in v_args
