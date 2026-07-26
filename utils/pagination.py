from typing import TypeVar

T = TypeVar("T")
PAGE_SIZE = 10


class Paginator[T]:
    """يقسم القائمة إلى صفحات مع أزرار التنقيء."""

    def __init__(self, items: list[T], page: int = 0, page_size: int = PAGE_SIZE):
        self.items = items
        self.page = max(0, page)
        self.page_size = page_size
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)
        if self.page >= self.total_pages:
            self.page = max(0, self.total_pages - 1)

    @property
    def current_items(self) -> list[T]:
        start = self.page * self.page_size
        return self.items[start : start + self.page_size]

    @property
    def slice_info(self) -> str:
        """معلومات الصفحة الحالية لعرضها في الرسالة."""
        if not self.items:
            return "لا توجد نتائج"
        start = self.page * self.page_size + 1
        end = min((self.page + 1) * self.page_size, len(self.items))
        return f"{start}-{end} من {len(self.items)}"

    def has_prev(self) -> bool:
        return self.page > 0

    def has_next(self) -> bool:
        return self.page < self.total_pages - 1

    def prev_page(self) -> int:
        return max(0, self.page - 1)

    def next_page(self) -> int:
        return min(self.total_pages - 1, self.page + 1)
