"""Thin helpers over the `docker` command line.

Everything here shells out to `docker`; it only reads state, except the rehearsal
module which starts and stops the demo's own containers through compose.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class DockerError(RuntimeError):
    """A docker command failed."""


def docker(*args: str, check: bool = True, timeout: float = 600, input: str | None = None) -> subprocess.CompletedProcess:
    completed = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, input=input)
    if check and completed.returncode != 0:
        raise DockerError(f"docker {' '.join(args[:3])} failed ({completed.returncode}): {(completed.stderr or completed.stdout).strip()[-400:]}")
    return completed


def available() -> tuple[bool, str]:
    """Is a Docker daemon answering? Returns (ok, reason)."""
    try:
        completed = docker("info", "--format", "{{.ServerVersion}}", check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"{type(error).__name__}: {error}"
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout).strip().splitlines()[-1][:300]
    return True, completed.stdout.strip()


def daemon_facts() -> dict:
    fields = {
        "server_version": "{{.ServerVersion}}",
        "operating_system": "{{.OperatingSystem}}",
        "architecture": "{{.Architecture}}",
        "cpus": "{{.NCPU}}",
        "memory_bytes": "{{.MemTotal}}",
        "storage_driver": "{{.Driver}}",
    }
    facts = {}
    for name, template in fields.items():
        facts[name] = docker("info", "--format", template).stdout.strip()
    facts["cpus"] = int(facts["cpus"])
    facts["memory_bytes"] = int(facts["memory_bytes"])
    facts["client_version"] = docker("version", "--format", "{{.Client.Version}}").stdout.strip()
    return facts


def image_identity(reference: str) -> dict:
    """Content-addressed identity of a local image: its id is a SHA-256 of its config and cannot change."""
    (item,) = json.loads(docker("image", "inspect", reference).stdout)
    config = item.get("Config") or {}
    return {
        "reference": reference,
        "id": item["Id"],
        "repo_tags": item.get("RepoTags") or [],
        "architecture": item.get("Architecture"),
        "os": item.get("Os"),
        "size_bytes": item.get("Size"),
        "created": item.get("Created"),
        "user": config.get("User"),
        "exposed_ports": sorted((config.get("ExposedPorts") or {}).keys()),
        "healthcheck": (config.get("Healthcheck") or {}).get("Test"),
        "layers": len((item.get("RootFS") or {}).get("Layers") or []),
    }


def container_facts(name: str) -> dict:
    (item,) = json.loads(docker("inspect", name).stdout)
    host = item["HostConfig"]
    return {
        "name": item["Name"].lstrip("/"),
        "image_id": item["Image"],
        "status": item["State"]["Status"],
        "health": (item["State"].get("Health") or {}).get("Status"),
        "read_only_root_filesystem": host.get("ReadonlyRootfs"),
        "cpus": (host.get("NanoCpus") or 0) / 1e9 or None,
        "memory_limit_bytes": host.get("Memory") or None,
        "cap_drop": host.get("CapDrop"),
        "security_opt": host.get("SecurityOpt"),
        "user": item["Config"].get("User"),
        "published_ports": {port: [f"{binding['HostIp']}:{binding['HostPort']}" for binding in bindings] for port, bindings in (host.get("PortBindings") or {}).items()},
        "mounts": [{"destination": mount["Destination"], "read_write": mount["RW"], "type": mount["Type"]} for mount in item.get("Mounts", [])],
    }


def exec_json(name: str, *command: str) -> dict:
    """Run a command in a running container and parse its JSON output."""
    completed = docker("exec", name, *command)
    text = completed.stdout
    return json.loads(text[text.index("{") :])


def peak_memory_bytes(name: str) -> int | None:
    """The container cgroup's peak memory, when the kernel reports it."""
    for path in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        completed = docker("exec", name, "cat", path, check=False)
        if completed.returncode == 0 and re.fullmatch(r"\d+", completed.stdout.strip()):
            return int(completed.stdout.strip())
    return None


def image_environment(reference: str, constraints: Path | None = None, platform: str | None = None) -> dict:
    """The interpreter and packages inside an image, from a throwaway container of it."""
    command = ["run", "--rm", "--entrypoint", "python"]
    if platform:
        command += ["--platform", platform]
    arguments = ["-m", "med_deploy", "environment"]
    if constraints is not None:
        command += ["-v", f"{Path(constraints).resolve()}:/constraints.txt:ro"]
        arguments += ["--constraints", "/constraints.txt"]
    text = docker(*command, reference, *arguments).stdout
    return json.loads(text[text.index("{") :])
