from utils.pagination import Paginator


class TestPaginatorInit:
    def test_empty_list(self):
        p = Paginator([])
        assert p.items == []
        assert p.page == 0
        assert p.total_pages == 1

    def test_negative_page_clamps_to_zero(self):
        p = Paginator([1, 2], page=-5)
        assert p.page == 0

    def test_page_exceeding_total_clamps_to_last(self):
        p = Paginator([1, 2, 3], page=99, page_size=2)
        assert p.page == p.total_pages - 1

    def test_total_pages_calculation(self):
        p = Paginator(list(range(25)), page_size=10)
        assert p.total_pages == 3


class TestCurrentItems:
    def test_first_page(self):
        p = Paginator(list(range(25)), page=0, page_size=10)
        assert p.current_items == list(range(10))

    def test_last_page_partial(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.current_items == [20, 21, 22, 23, 24]

    def test_empty_list(self):
        p = Paginator([])
        assert p.current_items == []

    def test_single_item(self):
        p = Paginator([42], page=0, page_size=10)
        assert p.current_items == [42]


class TestSliceInfo:
    def test_empty_returns_no_results(self):
        p = Paginator([])
        assert "لا توجد نتائج" in p.slice_info

    def test_first_page_format(self):
        p = Paginator(list(range(25)), page=0, page_size=10)
        assert p.slice_info == "1-10 من 25"

    def test_last_page_format(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.slice_info == "21-25 من 25"


class TestNavigation:
    def test_has_prev_on_first_page(self):
        p = Paginator([1, 2, 3], page=0)
        assert p.has_prev() is False

    def test_has_prev_on_second_page(self):
        p = Paginator(list(range(25)), page=1, page_size=10)
        assert p.has_prev() is True

    def test_has_next_on_last_page(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.has_next() is False

    def test_has_next_on_first_page(self):
        p = Paginator(list(range(25)), page=0, page_size=10)
        assert p.has_next() is True

    def test_prev_page_does_not_go_below_zero(self):
        p = Paginator([1, 2, 3], page=0)
        assert p.prev_page() == 0

    def test_next_page_does_not_exceed_total(self):
        p = Paginator(list(range(25)), page=2, page_size=10)
        assert p.next_page() == 2

    def test_prev_page_from_middle(self):
        p = Paginator(list(range(25)), page=1, page_size=10)
        assert p.prev_page() == 0

    def test_next_page_from_middle(self):
        p = Paginator(list(range(25)), page=0, page_size=10)
        assert p.next_page() == 1


class TestSinglePage:
    def test_all_items_on_one_page(self):
        p = Paginator([1, 2, 3], page=0, page_size=10)
        assert p.current_items == [1, 2, 3]
        assert p.has_prev() is False
        assert p.has_next() is False
