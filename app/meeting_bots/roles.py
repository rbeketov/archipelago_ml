_ALLOWED_ROLES = [
    "обычный",
    "гопник",
    "пират",
]

_DEFAULT_ROLE = _ALLOWED_ROLES[0]


def default_role() -> str:
    return _DEFAULT_ROLE


def check_role(role: str) -> bool:
    if role in _ALLOWED_ROLES:
        return True

    return False
