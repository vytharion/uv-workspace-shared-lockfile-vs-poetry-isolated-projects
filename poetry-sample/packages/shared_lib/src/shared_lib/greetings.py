from __future__ import annotations


def greet(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return "Hello, friend!"
    return f"Hello, {cleaned}!"
