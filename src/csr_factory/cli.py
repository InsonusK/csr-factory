"""Command-line interface for create-csr."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Callable

from csr_factory.console import (
    build_menu,
    prompt_choice,
    prompt_yes_no,
    wait_for_enter,
)
from csr_factory.core import (
    AlgorithmError,
    ServerMeta,
    TmpKeyManager,
    collect_tags,
    generate_csr,
    generate_key,
    load_servers,
    select_servers,
)
from csr_factory.logging_config import setup_logging

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="create-csr",
        description="Generate private keys and CSRs for servers from a directory of server configs.",
    )
    parser.add_argument(
        "servers_dir",
        nargs="?",
        default="servers",
        help="Directory containing per-server subdirectories (default: %(default)s).",
    )
    parser.add_argument(
        "--tmp-key",
        default="pki/tmp/private.key",
        help="Path for the temporary private key (default: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def run(
    servers_dir: Path,
    tmp_key_path: Path,
    input_fn: Callable[[str], str] = input,
) -> int:
    """Run the interactive CSR generation workflow.

    Args:
        servers_dir: Root directory containing per-server subdirectories.
        tmp_key_path: Where to write the temporary private key.
        input_fn: Callable used to read user input (for testing).

    Returns:
        Exit code.
    """
    try:
        servers = load_servers(servers_dir)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    if not servers:
        logger.error("No servers found in %s with meta.yaml and server.cnf.", servers_dir)
        return 1

    tags = collect_tags(servers)
    menu_text, tag_menu, server_menu = build_menu(servers, tags)

    print(menu_text)
    choice = prompt_choice("Your choice: ", input_fn=input_fn)

    try:
        selected = select_servers(servers, choice, tag_menu, server_menu)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    if not selected:
        logger.error("No servers selected.")
        return 1

    with TmpKeyManager(tmp_key_path):
        for server in selected:
            if not _process_server(server, tmp_key_path, input_fn):
                return 1

    logger.info("Done.")
    return 0


def _process_server(
    server: ServerMeta,
    tmp_key_path: Path,
    input_fn: Callable[[str], str],
) -> bool:
    """Process a single server: generate key, wait, generate CSR.

    Returns:
        ``True`` if processing should continue, ``False`` on fatal error.
    """
    print("")
    logger.info("Server: %s (algorithm: %s)", server.name, server.algorithm)

    if server.csr_path.exists():
        overwrite = prompt_yes_no(
            f"CSR already exists: {server.csr_path}. Overwrite? (yes/no): ",
            input_fn=input_fn,
        )
        if not overwrite:
            logger.info("Skipping %s.", server.name)
            return True

    try:
        generate_key(server.algorithm, tmp_key_path)
    except AlgorithmError as exc:
        logger.error("%s", exc)
        return False
    except (subprocess.CalledProcessError, OSError):
        return False

    print(f"Private key saved to: {tmp_key_path}")
    wait_for_enter(
        "Copy it to your password manager and press Enter to create the CSR...",
        input_fn=input_fn,
    )

    try:
        generate_csr(tmp_key_path, server.config_path, server.csr_path)
    except (subprocess.CalledProcessError, OSError):
        return False

    # Ensure the temporary key is removed immediately after the CSR is created,
    # even though the context manager will also clean it up on exit.
    tmp_key_path.unlink(missing_ok=True)
    logger.info("CSR created: %s", server.csr_path)
    return True


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``create-csr`` CLI."""
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    servers_dir = Path(args.servers_dir)
    tmp_key_path = Path(args.tmp_key)

    try:
        return run(servers_dir, tmp_key_path)
    except KeyboardInterrupt:
        logger.critical("Interrupted by user.")
        return 130
    except Exception as exc:
        logger.critical("Unexpected error: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
