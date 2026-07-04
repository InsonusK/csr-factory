"""Tests for csr_factory.core."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from csr_factory.core import (
    ALGORITHMS,
    AlgorithmError,
    ServerMeta,
    TmpKeyManager,
    collect_tags,
    generate_csr,
    generate_key,
    load_servers,
    select_servers,
    validate_algorithm,
)


@pytest.fixture
def servers_dir(tmp_path: Path) -> Path:
    """Create a populated servers directory."""
    root = tmp_path / "servers"

    api = root / "api1"
    api.mkdir(parents=True)
    (api / "meta.yaml").write_text(
        "name: api1\ntags:\n  - api\n  - prod\nalgorithm: ECC P-256\n",
        encoding="utf-8",
    )
    (api / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = api1\n",
        encoding="utf-8",
    )

    web = root / "web1"
    web.mkdir(parents=True)
    (web / "meta.yaml").write_text(
        "name: web1\ntags:\n  - web\nalgorithm: rsa 2048\n",
        encoding="utf-8",
    )
    (web / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = web1\n",
        encoding="utf-8",
    )

    return root


def test_validate_algorithm_supported(caplog) -> None:
    caplog.set_level("DEBUG")
    for algo in ALGORITHMS:
        validate_algorithm(algo)  # should not raise
    assert any("Validating algorithm" in rec.message for rec in caplog.records)


def test_validate_algorithm_unsupported() -> None:
    with pytest.raises(AlgorithmError):
        validate_algorithm("unsupported")


def test_load_servers_success(servers_dir: Path, caplog) -> None:
    servers = load_servers(servers_dir)
    assert len(servers) == 2
    assert servers[0].name == "api1"
    assert servers[0].tags == ("api", "prod")
    assert servers[0].algorithm == "ECC P-256"
    assert servers[1].name == "web1"
    assert servers[1].tags == ("web",)
    assert any("Loaded 2 server(s)" in rec.message for rec in caplog.records)


def test_load_servers_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_servers(tmp_path / "does-not-exist")


def test_load_servers_missing_meta(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    s = root / "srv"
    s.mkdir(parents=True)
    (s / "server.cnf").write_text("[ req ]\n", encoding="utf-8")

    servers = load_servers(root)
    assert servers == []
    assert any("missing meta.yaml" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "WARNING" for rec in caplog.records)


def test_load_servers_missing_cnf(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    s = root / "srv"
    s.mkdir(parents=True)
    (s / "meta.yaml").write_text("name: srv\n", encoding="utf-8")

    servers = load_servers(root)
    assert servers == []
    assert any("missing server.cnf" in rec.message for rec in caplog.records)


def test_load_servers_defaults(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    s = root / "srv"
    s.mkdir(parents=True)
    (s / "meta.yaml").write_text("tags: []\n", encoding="utf-8")
    (s / "server.cnf").write_text("[ req ]\n", encoding="utf-8")

    servers = load_servers(root)
    assert len(servers) == 1
    assert servers[0].name == "srv"
    assert servers[0].tags == ()
    assert servers[0].algorithm == "rsa 2048"


def test_load_servers_sorts_tags(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    s = root / "srv"
    s.mkdir(parents=True)
    (s / "meta.yaml").write_text(
        "name: srv\ntags:\n  - z\n  - a\n  - m\n", encoding="utf-8"
    )
    (s / "server.cnf").write_text("[ req ]\n", encoding="utf-8")

    servers = load_servers(root)
    assert servers[0].tags == ("a", "m", "z")


def test_collect_tags() -> None:
    servers = [
        ServerMeta("a", ("x", "y"), "rsa 2048", Path("/a")),
        ServerMeta("b", ("y", "z"), "rsa 2048", Path("/b")),
    ]
    assert collect_tags(servers) == ["x", "y", "z"]


def test_collect_tags_empty() -> None:
    assert collect_tags([]) == []


def test_select_servers_all(caplog) -> None:
    servers = [
        ServerMeta("a", ("x",), "rsa 2048", Path("/a")),
        ServerMeta("b", ("y",), "rsa 2048", Path("/b")),
    ]
    selected = select_servers(servers, "0", {"1": "x"}, {"2": "a", "3": "b"})
    assert [s.name for s in selected] == ["a", "b"]
    assert any("Selected all servers" in rec.message for rec in caplog.records)


def test_select_servers_by_tag(caplog) -> None:
    servers = [
        ServerMeta("a", ("x",), "rsa 2048", Path("/a")),
        ServerMeta("b", ("y",), "rsa 2048", Path("/b")),
        ServerMeta("c", ("x", "y"), "rsa 2048", Path("/c")),
    ]
    selected = select_servers(servers, "2", {"1": "x", "2": "y"}, {"3": "a"})
    assert [s.name for s in selected] == ["b", "c"]
    assert any("Selected tag: y" in rec.message for rec in caplog.records)


def test_select_servers_by_name() -> None:
    servers = [
        ServerMeta("a", ("x",), "rsa 2048", Path("/a")),
        ServerMeta("b", ("y",), "rsa 2048", Path("/b")),
    ]
    selected = select_servers(servers, "3", {"1": "x"}, {"2": "a", "3": "b"})
    assert [s.name for s in selected] == ["b"]


def test_select_servers_invalid(caplog) -> None:
    servers = [ServerMeta("a", ("x",), "rsa 2048", Path("/a"))]
    with pytest.raises(ValueError):
        select_servers(servers, "99", {}, {})
    assert any("Invalid menu choice" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


@pytest.mark.parametrize("algorithm", list(ALGORITHMS))
def test_generate_key_real_openssl(tmp_path: Path, algorithm: str, caplog) -> None:
    key_path = tmp_path / "key.pem"
    generate_key(algorithm, key_path)
    assert key_path.exists()
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert "PRIVATE KEY" in key_path.read_text(encoding="utf-8")
    assert any("Generating private key" in rec.message for rec in caplog.records)


def test_generate_key_invalid_algorithm(tmp_path: Path) -> None:
    with pytest.raises(AlgorithmError):
        generate_key("bad", tmp_path / "key.pem")


def test_generate_key_subprocess_error(tmp_path: Path, caplog) -> None:
    with patch("csr_factory.core.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("openssl failed")
        with pytest.raises(OSError, match="openssl failed"):
            generate_key("rsa 2048", tmp_path / "key.pem")
    assert any("Failed to run OpenSSL for key generation" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


def test_generate_csr_real_openssl(tmp_path: Path, servers_dir: Path, caplog) -> None:
    server = load_servers(servers_dir)[0]
    key_path = tmp_path / "key.pem"
    csr_path = tmp_path / "request.csr"
    generate_key(server.algorithm, key_path)
    generate_csr(key_path, server.config_path, csr_path)
    assert csr_path.exists()
    assert "CERTIFICATE REQUEST" in csr_path.read_text(encoding="utf-8")
    assert any("Generating CSR" in rec.message for rec in caplog.records)


def test_generate_csr_subprocess_error(tmp_path: Path, servers_dir: Path, caplog) -> None:
    server = load_servers(servers_dir)[0]
    with patch("csr_factory.core.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("openssl failed")
        with pytest.raises(OSError, match="openssl failed"):
            generate_csr(tmp_path / "key.pem", server.config_path, tmp_path / "req.csr")
    assert any("Failed to run OpenSSL for CSR generation" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


def test_tmp_key_manager_removes_file(tmp_path: Path, caplog) -> None:
    caplog.set_level("DEBUG")
    key = tmp_path / "private.key"
    key.write_text("secret")
    with TmpKeyManager(key):
        pass
    assert not key.exists()
    assert any("Removing temporary key" in rec.message for rec in caplog.records)


def test_tmp_key_manager_removes_on_exception(tmp_path: Path) -> None:
    key = tmp_path / "private.key"
    key.write_text("secret")
    with pytest.raises(RuntimeError):
        with TmpKeyManager(key):
            raise RuntimeError("boom")
    assert not key.exists()


def test_tmp_key_manager_remove_idempotent(tmp_path: Path) -> None:
    key = tmp_path / "private.key"
    manager = TmpKeyManager(key)
    manager.remove()
    assert not key.exists()
