"""Console / interactive helpers for create-csr."""

from __future__ import annotations

from typing import Callable

from csr_factory.core import ServerMeta


def build_menu(
    servers: list[ServerMeta], tags: list[str]
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Build the interactive selection menu.

    Returns:
        A tuple of ``(menu_text, tag_menu, server_menu)`` where the two mapping
        dictionaries map menu indices to tag/server names.
    """
    lines: list[str] = ["=== Create / update CSR ===", ""]
    tag_menu: dict[str, str] = {}
    server_menu: dict[str, str] = {}

    lines.append("  0) All")
    lines.append("--- by tag ---")

    index = 1
    for tag in tags:
        lines.append(f"  {index}) {tag}")
        tag_menu[str(index)] = tag
        index += 1

    lines.append("--- by server ---")
    for server in servers:
        lines.append(f"  {index}) {server.name}")
        server_menu[str(index)] = server.name
        index += 1

    return "\n".join(lines), tag_menu, server_menu


def prompt_choice(text: str, input_fn: Callable[[str], str] = input) -> str:
    """Prompt the user for a menu choice."""
    return input_fn(text).strip()


def prompt_yes_no(text: str, input_fn: Callable[[str], str] = input) -> bool:
    """Prompt the user with a yes/no question.

    Returns ``True`` only if the user answers exactly ``yes``.
    """
    return input_fn(text).strip().lower() == "yes"


def wait_for_enter(text: str, input_fn: Callable[[str], str] = input) -> None:
    """Wait for the user to press Enter."""
    input_fn(text)
