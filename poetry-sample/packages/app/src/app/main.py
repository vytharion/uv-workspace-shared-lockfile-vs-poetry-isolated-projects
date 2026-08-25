from __future__ import annotations

from shared_lib import greet


def welcome(name: str) -> str:
    return f"[app] {greet(name, 'Hello')}"


def run() -> None:
    print(welcome("world"))


if __name__ == "__main__":
    run()
