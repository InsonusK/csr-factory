"""Command-line interface for create-csr."""

from __future__ import annotations

import argparse
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
    return parser.parse_args(argv)


def run(
    servers_dir: Path,
    tmp_key_path: Path,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[..., None] = print,
) -> int:
    """Run the interactive CSR generation workflow.

    Args:
        servers_dir: Root directory containing per-server subdirectories.
        tmp_key_path: Where to write the temporary private key.
        input_fn: Callable used to read user input (for testing).
        print_fn: Callable used for output (for testing).

    Returns:
        Exit code.
    """
    try:
        servers = load_servers(servers_dir)
    except FileNotFoundError as exc:
        print_fn(f"Error: {exc}", file=sys.stderr)
        return 1

    if not servers:
        print_fn(
            f"Error: no servers found in {servers_dir} with meta.yaml and server.cnf.",
            file=sys.stderr,
        )
        return 1

    tags = collect_tags(servers)
    menu_text, tag_menu, server_menu = build_menu(servers, tags)

    print_fn(menu_text)
    choice = prompt_choice("Your choice: ", input_fn=input_fn)

    try:
        selected = select_servers(servers, choice, tag_menu, server_menu)
    except ValueError as exc:
        print_fn(f"Error: {exc}", file=sys.stderr)
        return 1

    if not selected:
        print_fn("No servers selected.", file=sys.stderr)
        return 1

    with TmpKeyManager(tmp_key_path):
        for server in selected:
            if not _process_server(server, tmp_key_path, input_fn, print_fn):
                return 1

    print_fn("")
    print_fn("=== Done. ===")
    return 0


def _process_server(
    server: ServerMeta,
    tmp_key_path: Path,
    input_fn: Callable[[str], str],
    print_fn: Callable[..., None],
) -> bool:
    """Process a single server: generate key, wait, generate CSR.

    Returns:
        ``True`` if processing should continue, ``False`` on fatal error.
    """
    print_fn("")
    print_fn(f"=== Server: {server.name} (algorithm: {server.algorithm}) ===")

    if server.csr_path.exists():
        overwrite = prompt_yes_no(
            f"CSR already exists: {server.csr_path}. Overwrite? (yes/no): ",
            input_fn=input_fn,
        )
        if not overwrite:
            print_fn(f"Skipping {server.name}.")
            return True

    print_fn("Generating private key...")
    try:
        generate_key(server.algorithm, tmp_key_path)
    except AlgorithmError as exc:
        print_fn(f"Error: {exc}", file=sys.stderr)
        return False
    except OSError as exc:
        print_fn(f"Error: failed to generate key: {exc}", file=sys.stderr)
        return False

    print_fn(f"Private key saved to: {tmp_key_path}")
    wait_for_enter(
        "Copy it to your password manager and press Enter to create the CSR...",
        input_fn=input_fn,
    )

    try:
        generate_csr(tmp_key_path, server.config_path, server.csr_path)
    except OSError as exc:
        print_fn(f"Error: failed to generate CSR: {exc}", file=sys.stderr)
        return False

    # Ensure the temporary key is removed immediately after the CSR is created,
    # even though the context manager will also clean it up on exit.
    tmp_key_path.unlink(missing_ok=True)
    print_fn(f"CSR created: {server.csr_path}")
    return True


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``create-csr`` CLI."""
    args = parse_args(argv)
    servers_dir = Path(args.servers_dir)
    tmp_key_path = Path(args.tmp_key)

    try:
        return run(servers_dir, tmp_key_path)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
