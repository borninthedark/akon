"""Container runtime abstraction — podman locally, docker in CI."""

from __future__ import annotations

import os
import shutil
import subprocess

from tools.constants import ContainerRuntime


def detect_runtime() -> ContainerRuntime:
    """Detect the container runtime to use.

    Priority: CONTAINER_RUNTIME env var > podman on PATH > docker on PATH.
    """
    env = os.environ.get("CONTAINER_RUNTIME")
    if env:
        try:
            return ContainerRuntime(env)
        except ValueError:
            raise ValueError(
                f"Invalid CONTAINER_RUNTIME={env!r}; expected 'podman' or 'docker'"
            )

    if shutil.which("podman"):
        return ContainerRuntime.PODMAN
    if shutil.which("docker"):
        return ContainerRuntime.DOCKER

    raise RuntimeError(
        "No container runtime found. Install podman or docker, "
        "or set CONTAINER_RUNTIME env var."
    )


def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


class ContainerRunner:
    """Thin wrapper around a container runtime CLI."""

    def __init__(self, runtime: ContainerRuntime | None = None):
        self.runtime = runtime or detect_runtime()

    def run(
        self,
        image: str,
        cmd: str,
        volumes: dict[str, str] | None = None,
        timeout: int = 7200,
    ) -> tuple[int, str, str]:
        """Run a command in a container. Defaults to 7200s for kernel builds."""
        args = [self.runtime, "run", "--rm"]
        for host, container in (volumes or {}).items():
            args.extend(["-v", f"{host}:{container}:z"])
        args.extend([image, "bash", "-c", cmd])
        return run_command(args, timeout=timeout)

    def build(self, tag: str, context: str) -> tuple[int, str, str]:
        """Build a container image."""
        return run_command([self.runtime, "build", "-t", tag, context])

    def push(self, image: str) -> tuple[int, str, str]:
        """Push an image to a registry."""
        return run_command([self.runtime, "push", image])

    def login(self, registry: str) -> tuple[int, str, str]:
        """Login to a container registry."""
        return run_command([self.runtime, "login", registry])

    def images(self, reference: str) -> tuple[int, str, str]:
        """List images matching a reference."""
        return run_command([self.runtime, "images", reference])
