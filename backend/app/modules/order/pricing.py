"""Integer VND allocation and stable fingerprints shared by quote and checkout."""

import json

from app.core.security import hash_token


def fingerprint(body) -> str:
    data = body.model_dump(mode="json", exclude={"idempotency_key", "quote_id"})
    return hash_token(json.dumps(data, sort_keys=True, separators=(",", ":")))


def allocate_discount(line_totals: list[int], discount: int) -> list[int]:
    subtotal = sum(line_totals)
    if not 0 <= discount <= subtotal or any(n < 0 for n in line_totals):
        raise ValueError("Invalid discount allocation")
    cumulative = previous = 0
    result = []
    for total in line_totals:
        cumulative += total
        allocated = discount * cumulative // subtotal if subtotal else 0
        result.append(allocated - previous)
        previous = allocated
    return result
