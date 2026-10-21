"""Versioned internal location IDs preserved from the existing posting form.

These IDs are Petshop legacy IDs, not carrier or official administrative codes.
"""

import json
from pathlib import Path

from fastapi import HTTPException

CATALOG = json.loads(Path(__file__).with_name("locations.json").read_text(encoding="utf-8"))
PROVINCES = {p["id"]: p["name"] for p in CATALOG["provinces"]}


def normalize_location(values):
    ident = values.get("province_id")
    if ident not in PROVINCES:
        raise HTTPException(422, "Khu vực không thuộc danh mục hỗ trợ")
    values["province_name"] = PROVINCES[ident]
    # No district registry has been configured: do not accept unvalidated IDs.
    if values.get("district_id") is not None:
        raise HTTPException(422, "Chưa hỗ trợ mã quận/huyện; hãy nhập tên khu vực")
    if values.get("ward_code") is not None:
        raise HTTPException(422, "Chưa hỗ trợ mã phường/xã; hãy nhập tên khu vực")
