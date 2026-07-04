"""Core logic for loading server metadata and generating keys/CSRs."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)

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
    logger.debug("Validating algorithm: %s", algorithm)
    if algorithm not in ALGORITHMS:
        supported = ", ".join(sorted(ALGORITHMS))
        raise AlgorithmError(
            f"Unsupported algorithm '{algorithm}'. Supported: {supported}"
        )


def _read_meta(path: Path) -> dict:
    logger.debug("Reading meta.yaml: %s", path)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_servers(servers_dir: Path) -> list[ServerMeta]:
    """Load server metadata from subdirectories of ``servers_dir``.

    Only subdirectories containing both ``meta.yaml`` and ``server.cnf`` are
    considered. Warnings are logged for directories that are missing required
    files or have malformed metadata.

    Args:
        servers_dir: Root directory containing per-server subdirectories.

    Returns:
        A sorted list of ``ServerMeta`` objects by server name.
    """
    logger.info("Loading servers from: %s", servers_dir)
    if not servers_dir.is_dir():
        logger.error("Servers directory not found: %s", servers_dir)
        raise FileNotFoundError(f"Servers directory not found: {servers_dir}")

    servers: list[ServerMeta] = []
    for entry in sorted(servers_dir.iterdir()):
        if not entry.is_dir():
            logger.debug("Skipping non-directory entry: %s", entry.name)
            continue

        meta_path = entry / "meta.yaml"
        cnf_path = entry / "server.cnf"

        if not meta_path.is_file():
            logger.warning("%s: missing meta.yaml", entry.name)
            continue
        if not cnf_path.is_file():
            logger.warning("%s: missing server.cnf", entry.name)
            continue

        try:
            meta = _read_meta(meta_path)
        except Exception as exc:
            logger.warning("%s: failed to read meta.yaml: %s", entry.name, exc)
            continue

        name = meta.get("name") or entry.name
        tags = tuple(sorted(str(t) for t in (meta.get("tags") or [])))
        algorithm = meta.get("algorithm", "rsa 2048")

        logger.debug(
            "Loaded server: name=%s tags=%s algorithm=%s dir=%s",
            name,
            tags,
            algorithm,
            entry,
        )
        servers.append(
            ServerMeta(
                name=name,
                tags=tags,
                algorithm=algorithm,
                server_dir=entry,
            )
        )

    logger.info("Loaded %d server(s)", len(servers))
    return sorted(servers, key=lambda s: s.name)


def collect_tags(servers: Iterable[ServerMeta]) -> list[str]:
    """Return a sorted list of unique tags across all servers."""
    tags = {tag for server in servers for tag in server.tags}
    logger.debug("Collected tags: %s", tags)
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
    logger.debug("User choice: %r", choice)
    if choice == "0":
        logger.info("Selected all servers")
        selected = list(servers)
    elif choice in tag_menu:
        tag = tag_menu[choice]
        logger.info("Selected tag: %s", tag)
        selected = [s for s in servers if tag in s.tags]
    elif choice in server_menu:
        name = server_menu[choice]
        logger.info("Selected server: %s", name)
        selected = [s for s in servers if s.name == name]
    else:
        logger.error("Invalid menu choice: %r", choice)
        raise ValueError(f"Invalid choice: {choice!r}")

    logger.info("%d server(s) selected", len(selected))
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
    logger.info("Generating private key with algorithm: %s", algorithm)
    logger.debug("Running command: %s", " ".join(cmd))
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.error("OpenSSL failed to generate key: %s", exc.stderr.strip())
        raise
    except OSError as exc:
        logger.error("Failed to run OpenSSL for key generation: %s", exc)
        raise
    key_path.chmod(0o600)
    logger.debug("Private key saved: %s", key_path)


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
    logger.info("Generating CSR: %s", csr_path)
    logger.debug("Running command: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.error("OpenSSL failed to generate CSR: %s", exc.stderr.strip())
        raise
    except OSError as exc:
        logger.error("Failed to run OpenSSL for CSR generation: %s", exc)
        raise
    logger.debug("CSR saved: %s", csr_path)


def secure_unlink(path: Path, *, passes: int = 1) -> None:
    """Securely erase and remove a file.

    The file content is overwritten with zeros before unlinking so that the
    original data cannot be recovered from the storage medium by casual means.
    If the file does not exist this function is a no-op.

    Args:
        path: Path to the file to erase.
        passes: Number of overwrite passes (default: 1).
    """
    if not path.exists():
        logger.debug("Secure unlink: file does not exist: %s", path)
        return

    logger.debug("Securely erasing: %s", path)
    try:
        file_size = path.stat().st_size
        if file_size > 0:
            with open(path, "rb+") as fh:
                for _ in range(max(1, passes)):
                    fh.seek(0)
                    fh.write(b"\x00" * file_size)
                    fh.flush()
                    os.fsync(fh.fileno())
                fh.seek(0)
                fh.truncate(0)
                fh.flush()
                os.fsync(fh.fileno())
    except OSError as exc:
        logger.error("Failed to overwrite file contents for %s: %s", path, exc)

    try:
        path.unlink()
        logger.debug("Securely removed: %s", path)
    except OSError as exc:
        logger.error("Failed to remove file %s: %s", path, exc)
