"""Extended tests for database/repositories/card_batches.py — cover
decode paths, update_batch_payment, get_sales_summary, and edge cases."""

from unittest.mock import patch

from database.repositories.card_batches import (
    _decode_batch_cards,
    get_card_batch,
    get_card_batches_count,
    get_sales_summary,
    list_card_batches,
    save_card_batch,
    update_batch_payment,
)


class TestDecodeBatchCards:
    def test_empty_string(self):
        assert _decode_batch_cards("") == []

    def test_invalid_encrypted(self):
        assert _decode_batch_cards("not-encrypted-data") == []

    def test_decrypt_returns_none(self):
        with patch("database.repositories.card_batches.decrypt_data", return_value=None):
            assert _decode_batch_cards("something") == []

    def test_non_list_json(self):
        from utils.crypto import encrypt_data

        encrypted = encrypt_data('{"key": "value"}')
        assert _decode_batch_cards(encrypted) == []

    def test_invalid_json(self):
        from utils.crypto import encrypt_data

        encrypted = encrypt_data("not-json")
        assert _decode_batch_cards(encrypted) == []

    def test_valid_list(self):
        from utils.crypto import encrypt_data

        data = [{"name": "u1"}, {"name": "u2"}]
        encrypted = encrypt_data(
            __import__("json").dumps(data, ensure_ascii=False)
        )
        result = _decode_batch_cards(encrypted)
        assert len(result) == 2
        assert result[0]["name"] == "u1"


class TestSaveCardBatchExtended:
    def test_save_with_list_of_dicts(self):
        cards = [{"username": "u1", "password": "p1"}, {"username": "u2", "password": "p2"}]
        batch_id = save_card_batch(
            "discovered_1",
            "test_batch",
            "hotspot",
            cards=cards,
            unit_price=5.0,
        )
        assert isinstance(batch_id, int) and batch_id > 0

    def test_save_with_none_cards(self):
        batch_id = save_card_batch(
            "discovered_1",
            "empty_batch",
            "hotspot",
            cards=None,
        )
        assert isinstance(batch_id, int)

    def test_save_with_string_cards(self):
        import json

        cards_str = json.dumps([{"username": "u1"}])
        batch_id = save_card_batch(
            "discovered_1",
            "str_batch",
            "hotspot",
            cards=cards_str,
        )
        assert isinstance(batch_id, int)

    def test_save_with_invalid_string_cards(self):
        batch_id = save_card_batch(
            "discovered_1",
            "bad_batch",
            "hotspot",
            cards="not-valid-json",
        )
        assert isinstance(batch_id, int)


class TestListCardBatchesExtended:
    def test_list_without_router_key(self):
        from utils.crypto import encrypt_data

        save_card_batch("discovered_1", "a", "hotspot", cards=encrypt_data("[]"))
        save_card_batch("discovered_2", "b", "hotspot", cards=encrypt_data("[]"))
        result = list_card_batches()
        assert len(result) >= 2

    def test_list_with_pagination(self):
        result = list_card_batches(limit=1, offset=0)
        assert len(result) <= 1


class TestGetCardBatchesCount:
    def test_count_with_router_key(self):
        save_card_batch("discovered_99", "cnt", "hotspot")
        count = get_card_batches_count("discovered_99")
        assert count >= 1

    def test_count_without_router_key(self):
        count = get_card_batches_count()
        assert count >= 0


class TestGetCardBatchExtended:
    def test_non_existing_batch(self):
        result = get_card_batch(999999)
        assert result is None


class TestUpdateBatchPayment:
    def test_paid_status(self):
        bid = save_card_batch("discovered_1", "pay", "hotspot")
        result = update_batch_payment(bid, "paid", "John", 50.0)
        assert result is True

    def test_unpaid_status(self):
        bid = save_card_batch("discovered_1", "unpay", "hotspot")
        result = update_batch_payment(bid, "unpaid")
        assert result is True

    def test_deferred_status(self):
        bid = save_card_batch("discovered_1", "def", "hotspot")
        result = update_batch_payment(bid, "deferred")
        assert result is True

    def test_invalid_status(self):
        bid = save_card_batch("discovered_1", "inv", "hotspot")
        result = update_batch_payment(bid, "invalid")
        assert result is False

    def test_update_non_existing(self):
        result = update_batch_payment(999999, "paid", "Nobody")
        assert result is False


class TestGetSalesSummary:
    def test_with_days(self):
        result = get_sales_summary(days=30)
        assert "total_batches" in result
        assert "paid_count" in result
        assert "total_revenue" in result

    def test_without_days(self):
        result = get_sales_summary(days=0)
        assert "total_batches" in result

    def test_empty_database(self):
        result = get_sales_summary(days=1)
        assert result["total_batches"] == 0

    def test_with_paid_batch(self):
        bid = save_card_batch(
            "discovered_1", "sale", "hotspot",
            cards=[{"u": "1"}], unit_price=10.0,
        )
        update_batch_payment(bid, "paid", "Customer", 10.0)
        result = get_sales_summary(days=30)
        assert result["paid_count"] >= 1
        assert result["total_revenue"] >= 10.0
