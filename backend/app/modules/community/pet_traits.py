"""Pet vocabulary and accent-insensitive, literal search normalization."""

import re
import unicodedata

BREEDS = {
    "cat": [
        ("Mèo ta", ["meo nha"]),
        ("Mèo Anh lông ngắn", ["aln", "anh long ngan", "british shorthair"]),
        ("Mèo Anh lông dài", ["ald", "anh long dai", "british longhair"]),
        ("Mèo Ba Tư", ["persian"]),
        ("Mèo Xiêm", ["siamese"]),
        ("Mèo Ragdoll", ["ragdoll"]),
        ("Mèo Maine Coon", ["maine coon"]),
        ("Mèo Bengal", ["bengal"]),
        ("Mèo Scottish Fold", ["scottish fold"]),
        ("Mèo Munchkin", ["munchkin"]),
        ("Mèo Sphynx", ["sphynx"]),
    ],
    "dog": [
        ("Chó ta", ["cho co"]),
        ("Chó Poodle", ["poodle"]),
        ("Chó Corgi", ["corgi"]),
        ("Chó Phốc sóc", ["pomeranian", "pom"]),
        ("Chó Chihuahua", ["chihuahua"]),
        ("Chó Pug", ["pug"]),
        ("Chó Shiba", ["shiba inu", "shiba"]),
        ("Chó Husky", ["husky"]),
        ("Chó Alaska", ["alaskan malamute", "alaska"]),
        ("Chó Golden Retriever", ["golden", "golden retriever"]),
        ("Chó Labrador", ["labrador"]),
        ("Chó Samoyed", ["samoyed"]),
        ("Chó Becgie", ["bec gie", "german shepherd"]),
        ("Chó Phú Quốc", ["phu quoc"]),
    ],
    "other": [],
}
COLORS = {
    "white": "Trắng",
    "black": "Đen",
    "gray": "Xám",
    "yellow": "Vàng",
    "brown": "Nâu",
    "orange": "Cam",
    "cream": "Kem",
}
PATTERNS = {
    "solid": "Một màu",
    "tabby": "Vằn / mướp",
    "spotted": "Đốm",
    "bicolor": "Hai màu",
    "tricolor": "Tam thể",
    "tortoiseshell": "Đồi mồi",
}
COATS = {"short": "Ngắn", "medium": "Vừa", "long": "Dài", "hairless": "Không lông"}
SEXES = {"male": "Đực", "female": "Cái"}
SIZES = {"small": "Nhỏ", "medium": "Vừa", "large": "Lớn"}
ACCENTED = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
PLAIN = "a" * 17 + "e" * 11 + "i" * 5 + "o" * 17 + "u" * 11 + "y" * 5 + "d"


def normalize_search(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return " ".join(value.split())


def canonical_breed(value: str | None, pet_type: str) -> str | None:
    if not value or not value.strip():
        return None
    normalized = normalize_search(value)
    for name, aliases in BREEDS.get(pet_type, []):
        if normalized in [normalize_search(name), *aliases]:
            return name
    return value.strip()


def expand_search(value: str) -> str:
    normalized = normalize_search(value)
    aliases_by_name = {}
    for breeds in BREEDS.values():
        for name, aliases in breeds:
            canonical = normalize_search(name)
            aliases_by_name[canonical] = canonical
            for alias in aliases:
                aliases_by_name[alias] = canonical
    # A single pass avoids repeatedly expanding aliases inside their canonical name.
    pattern = (
        r"(?<!\w)(?:"
        + "|".join(re.escape(a) for a in sorted(aliases_by_name, key=len, reverse=True))
        + r")(?!\w)"
    )
    return re.sub(pattern, lambda match: aliases_by_name[match.group(0)], normalized)


def search_document(values: dict) -> str:
    details = values.get("pet_details") or {}
    parts = [values.get(k) or "" for k in ("title", "description", "breed", "color")]
    parts += [{"cat": "Mèo", "dog": "Chó", "other": "Khác"}.get(values.get("pet_type") or "", "")]
    parts += [details.get("markings") or ""]
    parts += [COLORS.get(c, "") for c in details.get("colors", [])]
    parts += [PATTERNS.get(details.get("pattern") or "", "")]
    return normalize_search(" ".join(parts))


def pet_options() -> dict:
    return {
        "breeds": {
            key: [name for name, _ in breeds] + ["Lai", "Không rõ", "Khác"]
            for key, breeds in BREEDS.items()
        },
        "colors": COLORS,
        "patterns": PATTERNS,
        "coat_lengths": COATS,
        "sexes": SEXES,
        "sizes": SIZES,
    }
