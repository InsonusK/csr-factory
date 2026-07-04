"""Core logic for loading server metadata and generating keys/CSRs."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

ALGORITHMS = {
    "rsa 2048": ["openssl", "genrsa", "-out", "{key}", "2048"],
    "rsa 4096": ["openssl", "genrsa", "-out", "{key}", "4096"],
    "ECC P-256": ["openssl", "ecparam", "-genkey", "-name", "prime256v1", "-out", "{key}"],
    "ECC P-384": ["openssl", "ecparam", "-genkey", "-name", "secp384r1", "-out", "{key}"],
}


class AlgorithmError(ValueError):
    """Raised when an unsupported algorithm is requested."""


@dataclass(frozen=True)
class ServerMeta:
    """Metadata for a single server."""

    name: str
    tags: tuple[str, ...]
    algorithm: str
    server_dir: Path

    @property
    def config_path(self) -> Path:
        return self.server_dir / "server.cnf"

    @property
    def csr_path(self) -> Path:
        return self.server_dir / "request.csr"


def validate_algorithm(algorithm: str) -> None:
    """Validate that ``algorithm`` is supported.

    Raises:
        AlgorithmError: If the algorithm is not supported.
    """
    if algorithm not in ALGORITHMS:
        supported = ", ".join(sorted(ALGORITHMS))
        raise AlgorithmError(
            f"Unsupported algorithm '{algorithm}'. Supported: {supported}"
        )


def _read_meta(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_servers(servers_dir: Path) -> list[ServerMeta]:
    """Load server metadata from subdirectories of ``servers_dir``.

    Only subdirectories containing both ``meta.yaml`` and ``server.cnf`` are
    considered. Warnings are printed to stderr for directories that are missing
    required files or have malformed metadata.

    Args:
        servers_dir: Root directory containing per-server subdirectories.

    Returns:
        A sorted list of ``ServerMeta`` objects by server name.
    """
    if not servers_dir.is_dir():
        raise FileNotFoundError(f"Servers directory not found: {servers_dir}")

    servers: list[ServerMeta] = []
    for entry in sorted(servers_dir.iterdir()):
        if not entry.is_dir():
            continue

        meta_path = entry / "meta.yaml"
        cnf_path = entry / "server.cnf"

        if not meta_path.is_file():
            print(f"WARN|{entry.name}|missing meta.yaml", file=sys.stderr)
            continue
        if not cnf_path.is_file():
            print(f"WARN|{entry.name}|missing server.cnf", file=sys.stderr)
            continue

        try:
            meta = _read_meta(meta_path)
        except Exception as exc:  # pragma: no cover - exercised but hard to assert
            print(
                f"WARN|{entry.name}|failed to read meta.yaml: {exc}",
                file=sys.stderr,
            )
            continue

        name = meta.get("name") or entry.name
        tags = tuple(sorted(str(t) for t in (meta.get("tags") or [])))
        algorithm = meta.get("algorithm", "rsa 2048")

        servers.append(
            ServerMeta(
                name=name,
                tags=tags,
                algorithm=algorithm,
                server_dir=entry,
            )
        )

    return sorted(servers, key=lambda s: s.name)


def collect_tags(servers: Iterable[ServerMeta]) -> list[str]:
    """Return a sorted list of unique tags across all servers."""
    tags = {tag for server in servers for tag in server.tags}
    return sorted(tags)


def select_servers(
    servers: list[ServerMeta],
    choice: str,
    tag_menu: dict[str, str],
    server_menu: dict[str, str],
) -> list[ServerMeta]:
    """Select servers based on the user's menu ``choice``.

    Args:
        servers: All loaded servers, sorted by name.
        choice: The user's raw input.
        tag_menu: Mapping from menu index to tag name.
        server_menu: Mapping from menu index to server name.

    Returns:
        A sorted list of selected servers.

    Raises:
        ValueError: If the choice does not match any menu item.
    """
    if choice == "0":
        selected = list(servers)
    elif choice in tag_menu:
        tag = tag_menu[choice]
        selected = [s for s in servers if tag in s.tags]
    elif choice in server_menu:
        name = server_menu[choice]
        selected = [s for s in servers if s.name == name]
    else:
        raise ValueError(f"Invalid choice: {choice!r}")

    return sorted(selected, key=lambda s: s.name)


def generate_key(algorithm: str, key_path: Path) -> None:
    """Generate a private key using OpenSSL.

    Args:
        algorithm: One of the supported algorithm identifiers.
        key_path: Where to write the private key.

    Raises:
        AlgorithmError: If the algorithm is not supported.
        subprocess.CalledProcessError: If OpenSSL fails.
    """
    validate_algorithm(algorithm)
    cmd = [arg.format(key=str(key_path)) for arg in ALGORITHMS[algorithm]]
    key_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    key_path.chmod(0o600)


def generate_csr(key_path: Path, config_path: Path, csr_path: Path) -> None:
    """Generate a CSR from an existing private key and OpenSSL config.

    Args:
        key_path: Path to the private key.
        config_path: Path to the OpenSSL config (``server.cnf``).
        csr_path: Where to write the CSR.

    Raises:
        subprocess.CalledProcessError: If OpenSSL fails.
    """
    csr_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "openssl",
        "req",
        "-new",
        "-key",
        str(key_path),
        "-out",
        str(csr_path),
        "-config",
        str(config_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


class TmpKeyManager:
    """Context manager that owns a temporary private key file.

    The file is removed when the context exits, even if an exception is raised.
    """

    def __init__(self, tmp_key_path: Path) -> None:
        self.tmp_key_path = tmp_key_path

    def __enter__(self) -> Path:
        self.tmp_key_path.parent.mkdir(parents=True, exist_ok=True)
        return self.tmp_key_path

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.remove()

    def remove(self) -> None:
        """Remove the temporary key file if it exists."""
        if self.tmp_key_path.exists():
            self.tmp_key_path.unlink()
