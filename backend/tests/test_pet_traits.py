"""Optional traits, vocabulary, and safe literal search validation."""

import pytest
from pydantic import ValidationError

from app.modules.community import schemas
from app.modules.community.pet_traits import canonical_breed, expand_search, normalize_search


def test_pet_details_are_optional_bounded_and_allow_multiple_colors():
    assert schemas.PetDetails().colors == []
    assert schemas.PetDetails().sex == "unknown"
    assert schemas.PetDetails(colors=["white", "black", "white"]).colors == ["white", "black"]
    for invalid in (
        {"colors": ["purple"]},
        {"weight_kg": float("nan")},
        {"weight_kg": 0},
        {"age_months": -1},
        {"coat_length": "fluffy"},
    ):
        with pytest.raises(ValidationError):
            schemas.PetDetails(**invalid)
    with pytest.raises(ValidationError):
        schemas.CommunityPostUpdateIn(version=1, pet_details=None)


def test_breed_aliases_vietnamese_and_combined_queries():
    assert canonical_breed(" ALN ", "cat") == "Mèo Anh lông ngắn"
    assert canonical_breed("british shorthair", "cat") == "Mèo Anh lông ngắn"
    assert canonical_breed("Giống địa phương", "cat") == "Giống địa phương"
    assert canonical_breed("ALN", "dog") == "ALN"
    assert normalize_search("  MÈO XÁM ĐUÔI CỤT  ") == "meo xam duoi cut"
    assert expand_search("ALN xám") == "meo anh long ngan xam"
    assert expand_search("mèo Anh lông ngắn") == "meo anh long ngan"


def test_feed_color_and_date_validation():
    assert schemas.CommunityFeedQs(colors="white,black").colors == "white,black"
    for params in (
        {"colors": "pink"},
        {"colors": "white,,black"},
        {"date_from": "2026-10-23", "date_to": "2026-10-22"},
        {"date_to": "9999-12-31"},
        {"q": "x" * 101},
    ):
        with pytest.raises(ValidationError):
            schemas.CommunityFeedQs(**params)
