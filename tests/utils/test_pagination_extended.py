"""Tests for utils.pagination — comprehensive coverage of all Paginator branches."""

from utils.pagination import Paginator


class TestPaginator:
    def test_empty_list(self):
        p = Paginator([])
        assert p.total_pages == 1
        assert p.current_items == []
        assert p.slice_info == "لا توجد نتائج"
        assert p.has_prev() is False
        assert p.has_next() is False

    def test_single_page(self):
        p = Paginator([1, 2, 3], page_size=10)
        assert p.total_pages == 1
        assert p.current_items == [1, 2, 3]
        assert p.has_prev() is False
        assert p.has_next() is False
        assert p.slice_info == "1-3 من 3"

    def test_multiple_pages(self):
        p = Paginator(list(range(25)), page_size=10)
        assert p.total_pages == 3
        assert p.has_prev() is False
        assert p.has_next() is True

    def test_page_navigation(self):
        p = Paginator(list(range(25)), page=1, page_size=10)
        assert p.current_items == list(range(10, 20))
        assert p.has_prev() is True
        assert p.has_next() is True

    def test_last_page(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.current_items == [20, 21, 22, 23, 24]
        assert p.has_prev() is True
        assert p.has_next() is False

    def test_negative_page_becomes_zero(self):
        p = Paginator([1, 2, 3], page=-5)
        assert p.page == 0

    def test_page_beyond_total_clamped(self):
        p = Paginator([1, 2, 3], page=100, page_size=10)
        assert p.page == 0  # total_pages is 1, max(0, 1-1) = 0

    def test_prev_page(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.prev_page() == 1

    def test_prev_page_at_zero(self):
        p = Paginator([1, 2], page=0)
        assert p.prev_page() == 0

    def test_next_page(self):
        p = Paginator(list(range(25)), page=0, page_size=10)
        assert p.next_page() == 1

    def test_next_page_at_last(self):
        p = Paginator([1, 2], page=0)
        assert p.next_page() == 0

    def test_slice_info_middle_page(self):
        p = Paginator(list(range(25)), page=1, page_size=10)
        assert p.slice_info == "11-20 من 25"
