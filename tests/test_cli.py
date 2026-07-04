"""Tests for csr_factory.cli."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest

from csr_factory.cli import main, parse_args, run
from csr_factory.logging_config import setup_logging


def make_input_sequence(answers: list[str]) -> Callable[[str], str]:
    """Return an input_fn that yields answers in order."""
    iterator = iter(answers)

    def _input(_prompt: str = "") -> str:
        return next(iterator)

    return _input


def test_parse_args_default() -> None:
    args = parse_args([])
    assert args.servers_dir == "servers"
    assert args.tmp_key_dir == "tmp"
    assert args.verbose is False


def test_parse_args_custom() -> None:
    args = parse_args(["/some/path", "--tmp-key-dir", "/tmp/keys", "-v"])
    assert args.servers_dir == "/some/path"
    assert args.tmp_key_dir == "/tmp/keys"
    assert args.verbose is True


def test_setup_logging_default() -> None:
    logger = setup_logging()
    assert logger.level == logging.INFO


def test_setup_logging_verbose() -> None:
    logger = setup_logging(logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_run_servers_dir_not_found(tmp_path: Path, caplog) -> None:
    code = run(tmp_path / "nope", tmp_path / "keys")
    assert code == 1
    assert any("not found" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


def test_run_no_servers(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    root.mkdir()
    code = run(root, tmp_path / "keys")
    assert code == 1
    assert any("No servers found" in rec.message for rec in caplog.records)


def test_run_select_all(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )

    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["0", ""]),
    )

    assert code == 0
    assert (srv / "request.csr").exists()
    assert not (tmp_path / "keys" / "srv.key").exists()
    assert not (tmp_path / "keys").exists() or not any((tmp_path / "keys").iterdir())
    assert any("Done." in rec.message for rec in caplog.records)


def test_run_select_by_tag(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    for name, tag in [("a", "alpha"), ("b", "beta")]:
        srv = root / name
        srv.mkdir(parents=True)
        (srv / "meta.yaml").write_text(
            f"name: {name}\ntags:\n  - {tag}\nalgorithm: rsa 2048\n",
            encoding="utf-8",
        )
        (srv / "server.cnf").write_text(
            f"[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = {name}\n",
            encoding="utf-8",
        )

    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["2", ""]),  # tag beta is index 2
    )

    assert code == 0
    assert (root / "b" / "request.csr").exists()
    assert not (root / "a" / "request.csr").exists()
    assert not (tmp_path / "keys" / "a.key").exists()
    assert not (tmp_path / "keys" / "b.key").exists()


def test_run_select_by_server(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    for name in ["a", "b"]:
        srv = root / name
        srv.mkdir(parents=True)
        (srv / "meta.yaml").write_text(
            f"name: {name}\nalgorithm: rsa 2048\n", encoding="utf-8"
        )
        (srv / "server.cnf").write_text(
            f"[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = {name}\n",
            encoding="utf-8",
        )

    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["2", ""]),  # server b is index 2
    )

    assert code == 0
    assert (root / "b" / "request.csr").exists()
    assert not (root / "a" / "request.csr").exists()
    assert not (tmp_path / "keys" / "a.key").exists()
    assert not (tmp_path / "keys" / "b.key").exists()


def test_run_invalid_choice(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )
    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["99"]),
    )
    assert code == 1
    assert any("Invalid choice" in rec.message for rec in caplog.records)


def test_run_overwrite_no(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )
    existing_csr = srv / "request.csr"
    existing_csr.write_text("existing")

    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["0", "no"]),
    )

    assert code == 0
    assert existing_csr.read_text(encoding="utf-8") == "existing"
    assert any("Skipping srv" in rec.message for rec in caplog.records)


def test_run_overwrite_yes(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )
    existing_csr = srv / "request.csr"
    existing_csr.write_text("existing")

    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["0", "yes", ""]),
    )

    assert code == 0
    assert existing_csr.exists()
    assert existing_csr.read_text(encoding="utf-8") != "existing"
    assert not (tmp_path / "keys" / "srv.key").exists()


def test_run_algorithm_error(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: bad\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )
    code = run(
        root,
        tmp_path / "keys",
        input_fn=make_input_sequence(["0"]),
    )
    assert code == 1
    assert any("Unsupported algorithm" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


def test_main_keyboard_interrupt(tmp_path: Path, caplog) -> None:
    with patch("csr_factory.cli.run") as mock_run:
        mock_run.side_effect = KeyboardInterrupt()
        code = main([str(tmp_path / "servers")])
    assert code == 130
    assert any("Interrupted by user" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "INFO" for rec in caplog.records)


def test_main_unexpected_error(tmp_path: Path, caplog) -> None:
    with patch("csr_factory.cli.run") as mock_run:
        mock_run.side_effect = RuntimeError("boom")
        code = main([str(tmp_path / "servers")])
    assert code == 1
    assert any("Unexpected error" in rec.message for rec in caplog.records)
    assert any(rec.levelname == "CRITICAL" for rec in caplog.records)


def test_run_bulk_uses_named_key_files(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    for name in ["a", "b"]:
        srv = root / name
        srv.mkdir(parents=True)
        (srv / "meta.yaml").write_text(
            f"name: {name}\nalgorithm: rsa 2048\n", encoding="utf-8"
        )
        (srv / "server.cnf").write_text(
            f"[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = {name}\n",
            encoding="utf-8",
        )

    keys_dir = tmp_path / "keys"
    code = run(
        root,
        keys_dir,
        input_fn=make_input_sequence(["0", "", ""]),
    )

    assert code == 0
    assert (root / "a" / "request.csr").exists()
    assert (root / "b" / "request.csr").exists()
    assert not (keys_dir / "a.key").exists()
    assert not (keys_dir / "b.key").exists()


def test_run_cleans_up_leftover_key_files(tmp_path: Path) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )

    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(parents=True)
    leftover = keys_dir / "orphan.key"
    leftover.write_text("leftover-secret", encoding="utf-8")

    code = run(
        root,
        keys_dir,
        input_fn=make_input_sequence(["0", ""]),
    )

    assert code == 0
    assert not leftover.exists()
    assert not (keys_dir / "srv.key").exists()


def test_run_only_key(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text(
        "name: srv\nalgorithm: rsa 2048\nonly_key: true\n", encoding="utf-8"
    )
    # No server.cnf is required when only_key is true.

    keys_dir = tmp_path / "keys"
    code = run(
        root,
        keys_dir,
        input_fn=make_input_sequence(["0"]),
    )

    assert code == 0
    assert (keys_dir / "srv.key").exists()
    assert "PRIVATE KEY" in (keys_dir / "srv.key").read_text(encoding="utf-8")
    assert not (srv / "request.csr").exists()
    assert any("Private key created" in rec.message for rec in caplog.records)


def test_run_only_key_and_regular_together(tmp_path: Path) -> None:
    root = tmp_path / "servers"

    key_only = root / "keyonly"
    key_only.mkdir(parents=True)
    (key_only / "meta.yaml").write_text(
        "name: keyonly\nalgorithm: rsa 2048\nonly_key: true\n", encoding="utf-8"
    )

    regular = root / "regular"
    regular.mkdir(parents=True)
    (regular / "meta.yaml").write_text(
        "name: regular\nalgorithm: rsa 2048\n", encoding="utf-8"
    )
    (regular / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = regular\n",
        encoding="utf-8",
    )

    keys_dir = tmp_path / "keys"
    code = run(
        root,
        keys_dir,
        input_fn=make_input_sequence(["0", ""]),
    )

    assert code == 0
    assert (keys_dir / "keyonly.key").exists()
    assert (regular / "request.csr").exists()
    assert not (keys_dir / "regular.key").exists()


def test_parse_args_no_cleanup() -> None:
    args = parse_args(["/some/path", "--no-cleanup"])
    assert args.no_cleanup is True


def test_run_no_cleanup_keeps_regular_key_files(tmp_path: Path, caplog) -> None:
    root = tmp_path / "servers"
    srv = root / "srv"
    srv.mkdir(parents=True)
    (srv / "meta.yaml").write_text("name: srv\nalgorithm: rsa 2048\n", encoding="utf-8")
    (srv / "server.cnf").write_text(
        "[ req ]\nprompt = no\ndistinguished_name = req_dn\n\n[ req_dn ]\nCN = srv\n",
        encoding="utf-8",
    )

    keys_dir = tmp_path / "keys"
    code = run(
        root,
        keys_dir,
        input_fn=make_input_sequence(["0", ""]),
        no_cleanup=True,
    )

    assert code == 0
    assert (srv / "request.csr").exists()
    assert (keys_dir / "srv.key").exists()
    assert any("Skipping temporary key cleanup" in rec.message for rec in caplog.records)


def test_main_verbose_calls_setup_logging_with_debug() -> None:
    root = Path(__file__).parent.parent / "example" / "servers"
    with patch("csr_factory.cli.setup_logging") as mock_setup:
        with patch("csr_factory.cli.run", return_value=0):
            code = main([str(root), "-v"])
    assert code == 0
    mock_setup.assert_called_once_with(logging.DEBUG)
