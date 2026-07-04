"""Tests for csr_factory.console."""

from pathlib import Path

from csr_factory.console import (
    build_menu,
    prompt_choice,
    prompt_yes_no,
    wait_for_enter,
)
from csr_factory.core import ServerMeta


def test_build_menu_empty() -> None:
    text, tag_menu, server_menu = build_menu([], [])
    assert "0) All" in text
    assert tag_menu == {}
    assert server_menu == {}


def test_build_menu_with_servers_and_tags() -> None:
    servers = [
        ServerMeta("api1", ("api", "prod"), "ECC P-256", Path("/srv/api1")),
        ServerMeta("web1", ("web",), "rsa 2048", Path("/srv/web1")),
    ]
    text, tag_menu, server_menu = build_menu(servers, ["api", "prod", "web"])
    assert "0) All" in text
    assert "1) api" in text
    assert "2) prod" in text
    assert "3) web" in text
    assert "4) api1" in text
    assert "5) web1" in text
    assert tag_menu == {"1": "api", "2": "prod", "3": "web"}
    assert server_menu == {"4": "api1", "5": "web1"}


def test_prompt_choice() -> None:
    assert prompt_choice("> ", input_fn=lambda _: "  2 ") == "2"


def test_prompt_yes_no_yes() -> None:
    assert prompt_yes_no("> ", input_fn=lambda _: "yes") is True


def test_prompt_yes_no_no() -> None:
    assert prompt_yes_no("> ", input_fn=lambda _: "no") is False


def test_prompt_yes_no_case_insensitive() -> None:
    assert prompt_yes_no("> ", input_fn=lambda _: "YES") is True


def test_wait_for_enter() -> None:
    called = False

    def fake_input(_):
        nonlocal called
        called = True
        return ""

    wait_for_enter("Press enter", input_fn=fake_input)
    assert called
