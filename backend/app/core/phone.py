"""Contact phone checks shared by customer and checkout flows."""

import re


def valid_contact_phone(value: str) -> bool:
    digits = value.lstrip("+")
    return bool(re.fullmatch(r"\+?[0-9]{9,15}", value)) and len(set(digits)) > 1
