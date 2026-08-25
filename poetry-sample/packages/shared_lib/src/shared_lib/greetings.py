from __future__ import annotations


def greet(name: str, salutation: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return f"{salutation}, friend!"
    return f"{salutation}, {cleaned}!"
