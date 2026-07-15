"""Tests for card batch persistence and serialization."""

from database.models import (
    save_card_batch, list_card_batches, get_card_batch, delete_card_batch,
)
from core.card_models import CardData, serialize_cards, deserialize_cards


SAMPLE_CARDS = [
    CardData(username="u1", password="p1", card_number=1, profile="10GB", limit_bytes="1000", comment="batch"),
    CardData(username="u2", password="", card_number=2, profile="10GB", limit_bytes="2000"),
]


def test_save_and_get_card_batch_roundtrip():
    batch_id = save_card_batch(
        router_key="discovered_1",
        name="hotspot_test",
        batch_type="hotspot",
        profile="10GB",
        comment_prefix="t",
        cards=serialize_cards(SAMPLE_CARDS),
        created_by=724730774,
    )
    assert isinstance(batch_id, int) and batch_id > 0

    batch = get_card_batch(batch_id)
    assert batch is not None
    assert batch["name"] == "hotspot_test"
    assert batch["batch_type"] == "hotspot"
    assert batch["count"] == 2
    assert batch["created_by"] == 724730774
    # cards are decrypted and returned as list of dicts
    assert isinstance(batch["cards"], list)
    assert batch["cards"][0]["username"] == "u1"
    assert "cards_json" not in batch


def test_list_card_batches_filters_by_router():
    save_card_batch("discovered_1", "a", "hotspot", cards=serialize_cards(SAMPLE_CARDS))
    save_card_batch("discovered_2", "b", "userman", cards=serialize_cards(SAMPLE_CARDS))

    r1 = list_card_batches("discovered_1")
    assert len(r1) >= 1
    assert all(b["router_key"] == "discovered_1" for b in r1)
    # list rows must not leak the encrypted payload
    assert "cards_json" not in r1[0]


def test_delete_card_batch():
    bid = save_card_batch("discovered_1", "del", "hotspot", cards=serialize_cards(SAMPLE_CARDS))
    assert delete_card_batch(bid) == 1
    assert get_card_batch(bid) is None


def test_serialize_deserialize_roundtrip():
    js = serialize_cards(SAMPLE_CARDS)
    cards = deserialize_cards(js)
    assert len(cards) == 2
    assert cards[0].username == "u1"
    assert cards[1].limit_bytes == "2000"
    assert isinstance(cards[0], CardData)


def test_deserialize_handles_bad_input():
    assert deserialize_cards("") == []
    assert deserialize_cards("not-json") == []
