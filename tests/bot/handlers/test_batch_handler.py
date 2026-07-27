"""Comprehensive tests for bot.handlers.batch.

Card batch listing, detail, regen, payment, sales, and sharing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import telegram.error
from telegram.ext import ConversationHandler

from bot.handlers import batch as batch_module
from bot.handlers.constants import WAITING_SHARE_RECIPIENT
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _query(data="batch_regen:7"):
    q = MagicMock()
    q.answer = AsyncMock()
    q.data = data
    q.message = MagicMock()
    q.message.chat_id = 42
    q.edit_message_text = AsyncMock()
    q.from_user = MagicMock(id=ADMIN_ID)
    return q


def _update(callback_data=None, text=""):
    u = MagicMock()
    u.effective_user = MagicMock(id=ADMIN_ID)
    u.effective_chat = MagicMock(id=ADMIN_ID)
    if callback_data is not None:
        u.callback_query = _query(callback_data)
        u.message = None
    else:
        u.callback_query = None
        u.message = MagicMock()
        u.message.text = text
        u.message.reply_text = AsyncMock()
    u.get_bot = MagicMock()
    return u


def _ctx(user_data=None):
    c = MagicMock()
    c.user_data = user_data if user_data is not None else {}
    c.bot = MagicMock()
    c.bot.send_message = AsyncMock()
    c.bot.send_document = AsyncMock()
    return c


SAMPLE_BATCH = {
    "id": 5,
    "name": "TestBatch",
    "batch_type": "hotspot",
    "profile": "10GB",
    "count": 2,
    "created_at": "2026-01-15 10:00:00",
    "created_by": "admin",
    "payment_status": "unpaid",
    "customer_name": "Alice",
    "sold_at": "2026-01-16",
    "cards": [
        {"username": "u1", "password": "p1", "limit_bytes": "1000", "comment": ""},
        {"username": "u2", "password": "", "limit_bytes": "2000", "comment": ""},
    ],
}

USERMAN_BATCH = {
    "id": 6,
    "name": "UMBatch",
    "batch_type": "userman",
    "profile": "5GB",
    "count": 1,
    "created_at": "2026-02-01",
    "cards": [
        {"username": "um1", "password": "pw1", "limit_bytes": "500"},
    ],
}


# ===================================================================
# TestBatchLabel
# ===================================================================
class TestBatchLabel:
    def test_hotspot_type(self):
        assert "هوت سبوت" in batch_module._batch_label(SAMPLE_BATCH)

    def test_userman_type(self):
        assert "User Manager" in batch_module._batch_label(USERMAN_BATCH)

    def test_missing_keys_uses_defaults(self):
        label = batch_module._batch_label({"id": 1, "name": "X"})
        assert "#1" in label
        assert "X" in label
        assert "0 كارت" in label


# ===================================================================
# TestDump
# ===================================================================
class TestDump:
    def test_returns_json_string(self):
        import json

        result = batch_module._dump([{"a": 1}])
        assert json.loads(result) == [{"a": 1}]

    def test_empty_list(self):
        assert batch_module._dump([]) == "[]"

    def test_unicode(self):
        result = batch_module._dump([{"name": "عربي"}])
        assert "عربي" in result


# ===================================================================
# TestBatchesCommand
# ===================================================================
class TestBatchesCommand:
    @pytest.mark.asyncio
    async def test_with_callback(self):
        u = _update(callback_data="batches_list")
        c = _ctx({"router_key": "discovered_1"})
        mock_send = AsyncMock()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "cleanup_state"),
            patch.object(batch_module, "nav_set"),
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[0, []])),
            patch.object(batch_module, "send_step", new=mock_send),
        ):
            await batch_module.batches_command(u, c)
        u.callback_query.answer.assert_awaited()
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_callback(self):
        u = _update(text="/batches")
        c = _ctx({"router_key": "discovered_1"})
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "cleanup_state") as mock_cleanup,
            patch.object(batch_module, "nav_set"),
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=[1, [SAMPLE_BATCH]])
            ),
            patch.object(batch_module, "send_step", new=AsyncMock()),
        ):
            await batch_module.batches_command(u, c)
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_called(self):
        u = _update(callback_data="batches_list")
        c = _ctx({"router_key": "k"})
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "cleanup_state", new=MagicMock()) as mock_cleanup,
            patch.object(batch_module, "nav_set"),
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[0, []])),
            patch.object(batch_module, "send_step", new=AsyncMock()),
        ):
            await batch_module.batches_command(u, c)
        mock_cleanup.assert_called_once_with(ADMIN_ID, c.user_data)


# ===================================================================
# TestShowBatchesPage
# ===================================================================
class TestShowBatchesPage:
    @pytest.mark.asyncio
    async def test_no_router_key(self):
        u = _update(callback_data="batch_page:0")
        c = _ctx({})
        result = await batch_module._show_batches_page(u, c, page=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_batches(self):
        u = _update(text="")
        c = _ctx({"router_key": "k"})
        mock_send = AsyncMock()
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[0, []])),
            patch.object(batch_module, "send_step", new=mock_send),
        ):
            await batch_module._show_batches_page(u, c, page=0)
        mock_send.assert_awaited_once()
        text = mock_send.call_args.args[2]
        assert "لا توجد" in text

    @pytest.mark.asyncio
    async def test_with_batches(self):
        u = _update(text="")
        c = _ctx({"router_key": "k"})
        mock_send = AsyncMock()
        with (
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=[1, [SAMPLE_BATCH]])
            ),
            patch.object(batch_module, "send_step", new=mock_send),
            patch("bot.handlers.batch.get_batches_keyboard", return_value=MagicMock()),
        ):
            await batch_module._show_batches_page(u, c, page=0)
        mock_send.assert_awaited_once()
        text = mock_send.call_args.args[2]
        assert "الدفعات" in text

    @pytest.mark.asyncio
    async def test_callback_page_data_edits(self):
        u = _update(callback_data="batch_page:1")
        c = _ctx({"router_key": "k"})
        with (
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=[1, [SAMPLE_BATCH]])
            ),
            patch("bot.handlers.batch.get_batches_keyboard", return_value=MagicMock()),
        ):
            await batch_module._show_batches_page(u, c, page=1)
        u.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_sends_error(self):
        u = _update(text="")
        c = _ctx({"router_key": "k"})
        mock_send = AsyncMock()
        with (
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=OSError("db fail"))
            ),
            patch.object(batch_module, "send_step", new=mock_send),
        ):
            await batch_module._show_batches_page(u, c, page=0)
        mock_send.assert_awaited_once()
        text = mock_send.call_args.args[2]
        assert "فشل" in text


# ===================================================================
# TestBatchPageHandler
# ===================================================================
class TestBatchPageHandler:
    @pytest.mark.asyncio
    async def test_valid_page(self):
        u = _update(callback_data="batch_page:2")
        c = _ctx({"router_key": "k"})
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[5, []])),
            patch.object(batch_module, "send_step", new=AsyncMock()),
        ):
            await batch_module.batch_page_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_invalid_data_defaults_to_zero(self):
        u = _update(callback_data="batch_page:abc")
        c = _ctx({"router_key": "k"})
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[5, []])),
            patch.object(batch_module, "send_step", new=AsyncMock()),
        ):
            await batch_module.batch_page_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_missing_colon_defaults_to_zero(self):
        u = _update(callback_data="batch_pagebad")
        c = _ctx({"router_key": "k"})
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[5, []])),
            patch.object(batch_module, "send_step", new=AsyncMock()),
        ):
            await batch_module.batch_page_handler(u, c)
        u.callback_query.answer.assert_awaited()


# ===================================================================
# TestBatchSelect
# ===================================================================
class TestBatchSelect:
    @pytest.mark.asyncio
    async def test_valid_batch(self):
        u = _update(callback_data="batch_select:5")
        c = _ctx()
        batch = dict(SAMPLE_BATCH)
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=batch)),
            patch("bot.handlers.batch.get_batch_detail_keyboard", return_value=MagicMock()),
        ):
            await batch_module.batch_select(u, c)
        u.callback_query.edit_message_text.assert_awaited_once()
        text = u.callback_query.edit_message_text.call_args.args[0]
        assert "TestBatch" in text

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        u = _update(callback_data="batch_select:abc")
        c = _ctx()
        await batch_module.batch_select(u, c)
        u.callback_query.answer.assert_awaited()
        call_kwargs = u.callback_query.answer.call_args
        assert call_kwargs.kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_missing_colon(self):
        u = _update(callback_data="batch_selectbad")
        c = _ctx()
        await batch_module.batch_select(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_batch_not_found(self):
        u = _update(callback_data="batch_select:999")
        c = _ctx()
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=None)),
            patch("bot.handlers.batch.get_batches_keyboard", return_value=MagicMock()),
        ):
            await batch_module.batch_select(u, c)
        u.callback_query.edit_message_text.assert_awaited_once()
        text = u.callback_query.edit_message_text.call_args.args[0]
        assert "غير موجودة" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        u = _update(callback_data="batch_select:5")
        c = _ctx()
        with (
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=OSError("err"))
            ),
            patch("bot.handlers.batch.get_batches_keyboard", return_value=MagicMock()),
        ):
            await batch_module.batch_select(u, c)
        u.callback_query.edit_message_text.assert_awaited_once()
        text = u.callback_query.edit_message_text.call_args.args[0]
        assert "فشل" in text


# ===================================================================
# TestFormatBatchText
# ===================================================================
class TestFormatBatchText:
    def test_hotspot_batch(self):
        text = batch_module._format_batch_text(SAMPLE_BATCH)
        assert "هوت سبوت" in text
        assert "TestBatch" in text
        assert "#5" in text

    def test_userman_batch(self):
        text = batch_module._format_batch_text(USERMAN_BATCH)
        assert "User Manager" in text
        assert "UMBatch" in text

    def test_with_sold_at(self):
        text = batch_module._format_batch_text(SAMPLE_BATCH)
        assert "2026-01-16" in text

    def test_with_customer(self):
        text = batch_module._format_batch_text(SAMPLE_BATCH)
        assert "Alice" in text

    def test_created_by(self):
        text = batch_module._format_batch_text(SAMPLE_BATCH)
        assert "admin" in text

    def test_missing_optional_fields(self):
        minimal = {"id": 1, "name": "X", "cards": [], "batch_type": "hotspot"}
        text = batch_module._format_batch_text(minimal)
        assert "#1" in text
        assert "—" in text

    def test_invalid_limit_bytes(self):
        batch = {
            "id": 2,
            "name": "Bad",
            "batch_type": "hotspot",
            "cards": [{"limit_bytes": "not_a_number"}, {"limit_bytes": None}],
        }
        text = batch_module._format_batch_text(batch)
        assert "#2" in text

    def test_no_customer_name(self):
        batch = {
            "id": 3,
            "name": "NoCust",
            "batch_type": "hotspot",
            "cards": [],
            "customer_name": "",
        }
        text = batch_module._format_batch_text(batch)
        assert "العميل" not in text

    def test_no_sold_at(self):
        batch = {
            "id": 4,
            "name": "NoSold",
            "batch_type": "hotspot",
            "cards": [],
            "sold_at": None,
        }
        text = batch_module._format_batch_text(batch)
        assert "البيع" not in text

    def test_default_payment_status(self):
        batch = {"id": 7, "name": "X", "batch_type": "hotspot", "cards": []}
        text = batch_module._format_batch_text(batch)
        assert "غير مدفوع" in text


# ===================================================================
# TestBatchRegen
# ===================================================================
class TestBatchRegen:
    @pytest.mark.asyncio
    async def test_success(self):
        u = _update(callback_data="batch_regen:7")
        c = _ctx()
        batch = dict(SAMPLE_BATCH)
        with (
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, "/tmp/fake.pdf"]),
            ),
            patch.object(batch_module, "deserialize_cards", return_value=[MagicMock()]),
            patch("builtins.open", MagicMock()),
            patch("os.remove"),
            patch("os.path.exists", return_value=True),
        ):
            await batch_module.batch_regen(u, c)
        c.bot.send_document.assert_awaited_once()
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        u = _update(callback_data="batch_regen:abc")
        c = _ctx()
        await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()
        assert u.callback_query.answer.call_args.kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_batch_not_found(self):
        u = _update(callback_data="batch_regen:99")
        c = _ctx()
        with patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=None)):
            await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_cards(self):
        u = _update(callback_data="batch_regen:7")
        c = _ctx()
        batch = dict(SAMPLE_BATCH, cards=[])
        with (
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=batch)),
            patch.object(batch_module, "deserialize_cards", return_value=[]),
        ):
            await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_exception_during_load(self):
        u = _update(callback_data="batch_regen:7")
        c = _ctx()
        with patch.object(
            batch_module, "run_blocking", new=AsyncMock(side_effect=OSError("db"))
        ):
            await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_message(self):
        u = _update(callback_data="batch_regen:7")
        c = _ctx()
        batch = dict(SAMPLE_BATCH)
        with (
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, "/tmp/f.pdf"]),
            ),
            patch.object(batch_module, "deserialize_cards", return_value=[MagicMock()]),
            patch.object(batch_module, "get_query_message", return_value=None),
        ):
            await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_exception_during_pdf_generation(self):
        u = _update(callback_data="batch_regen:7")
        c = _ctx()
        batch = dict(SAMPLE_BATCH)
        with (
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, OSError("gen")]),
            ),
            patch.object(batch_module, "deserialize_cards", return_value=[MagicMock()]),
        ):
            await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_missing_colon(self):
        u = _update(callback_data="batch_regenbad")
        c = _ctx()
        await batch_module.batch_regen(u, c)
        u.callback_query.answer.assert_awaited()


# ===================================================================
# TestMarkBatchPaid
# ===================================================================
class TestMarkBatchPaid:
    @pytest.mark.asyncio
    async def test_success_paid(self):
        u = _update(callback_data="mark_paid:5")
        c = _ctx()
        batch = dict(SAMPLE_BATCH)
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[True, batch])),
            patch("bot.handlers.batch.get_batch_detail_keyboard", return_value=MagicMock()),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_success_paid_batch_not_found(self):
        u = _update(callback_data="mark_paid:5")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[True, None])),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_success_paid_exception_reloading(self):
        u = _update(callback_data="mark_paid:5")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[True, OSError("fail")]),
            ),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_invalid_data(self):
        u = _update(callback_data="mark_paid:abc")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_fails(self):
        u = _update(callback_data="mark_paid:5")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=False)),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_callback(self):
        u = _update(callback_data="mark_paid:5")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=True),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_unpaid(self):
        u = _update(callback_data="mark_unpaid:3")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "is_duplicate_callback", return_value=False),
            patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[True, None])),
        ):
            await batch_module.mark_batch_paid_handler(u, c)
        u.callback_query.answer.assert_awaited()


# ===================================================================
# TestSalesSummary
# ===================================================================
class TestSalesSummary:
    @pytest.mark.asyncio
    async def test_success(self):
        u = _update(callback_data="sales_summary")
        c = _ctx()
        summary = {
            "total_batches": 10,
            "paid_count": 5,
            "unpaid_count": 3,
            "deferred_count": 2,
            "total_revenue": 100.0,
        }
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=summary)),
            patch.object(batch_module, "send_step", new=AsyncMock()) as mock_send,
        ):
            await batch_module.show_sales_summary(u, c)
        mock_send.assert_awaited_once()
        text = mock_send.call_args.args[2]
        assert "10" in text

    @pytest.mark.asyncio
    async def test_exception(self):
        u = _update(callback_data="sales_summary")
        c = _ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=OSError("fail"))
            ),
            patch.object(batch_module, "send_step", new=AsyncMock()) as mock_send,
        ):
            await batch_module.show_sales_summary(u, c)
        mock_send.assert_awaited_once()
        text = mock_send.call_args.args[2]
        assert "0" in text

    @pytest.mark.asyncio
    async def test_without_callback(self):
        u = _update(text="/sales")
        c = _ctx()
        summary = {
            "total_batches": 2,
            "paid_count": 1,
            "unpaid_count": 1,
            "deferred_count": 0,
            "total_revenue": 50.5,
        }
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=summary)),
            patch.object(batch_module, "send_step", new=AsyncMock()) as mock_send,
        ):
            await batch_module.show_sales_summary(u, c)
        mock_send.assert_awaited_once()


# ===================================================================
# TestShareCardStart
# ===================================================================
class TestShareCardStart:
    @pytest.mark.asyncio
    async def test_success(self):
        u = _update(callback_data="share_card:10")
        c = _ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_start(u, c)
        assert result == WAITING_SHARE_RECIPIENT
        assert c.user_data["share_batch_id"] == 10
        u.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_data(self):
        u = _update(callback_data="share_card:abc")
        c = _ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_start(u, c)
        assert result == ConversationHandler.END
        u.callback_query.answer.assert_awaited()
        assert u.callback_query.answer.call_args.kwargs.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_missing_colon(self):
        u = _update(callback_data="share_cardbad")
        c = _ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_start(u, c)
        assert result == ConversationHandler.END


# ===================================================================
# TestShareCardSend
# ===================================================================
class TestShareCardSend:
    def _make_share_ctx(self, user_data=None):
        c = _ctx(user_data or {"share_batch_id": 123})
        return c

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        u = _update(text="not_a_number")
        c = self._make_share_ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_send(u, c)
        assert result == WAITING_SHARE_RECIPIENT
        u.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_batch_id_in_user_data(self):
        u = _update(text="12345")
        c = _ctx({})
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_batch_not_found(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=None)),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END
        u.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_loading_batch(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module, "run_blocking", new=AsyncMock(side_effect=OSError("db"))
            ),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_cards_in_batch(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        batch = dict(SAMPLE_BATCH, cards=[])
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=batch)),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_success_with_dns_ssid(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        batch = dict(SAMPLE_BATCH)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        u.get_bot = MagicMock(return_value=bot_mock)
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(
                    side_effect=[batch, {"hotspot_dns": "dns.example.com", "brand_name": "MySSID"}]
                ),
            ),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END
        bot_mock.send_message.assert_awaited_once()
        u.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_no_dns_no_ssid(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        batch = dict(SAMPLE_BATCH)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        u.get_bot = MagicMock(return_value=bot_mock)
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, {"hotspot_dns": "", "brand_name": ""}]),
            ),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END
        bot_mock.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_pdf_settings(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        batch = dict(SAMPLE_BATCH)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        u.get_bot = MagicMock(return_value=bot_mock)
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, OSError("settings")]),
            ),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END
        bot_mock.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_sending(self):
        u = _update(text="12345")
        c = self._make_share_ctx()
        batch = dict(SAMPLE_BATCH)
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock(side_effect=telegram.error.TelegramError("tg fail"))
        u.get_bot = MagicMock(return_value=bot_mock)
        with (
            patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),
            patch.object(
                batch_module,
                "run_blocking",
                new=AsyncMock(side_effect=[batch, {"hotspot_dns": "", "brand_name": ""}]),
            ),
        ):
            result = await batch_module.share_card_send(u, c)
        assert result == ConversationHandler.END
        u.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_empty_text(self):
        u = _update(text="")
        c = self._make_share_ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_send(u, c)
        assert result == WAITING_SHARE_RECIPIENT

    @pytest.mark.asyncio
    async def test_whitespace_text(self):
        u = _update(text="   ")
        c = self._make_share_ctx()
        with (patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]),):
            result = await batch_module.share_card_send(u, c)
        assert result == WAITING_SHARE_RECIPIENT
