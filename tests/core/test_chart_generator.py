"""Tests for core/chart_generator.py — chart generation utilities."""


def _s(date, active, total, b_in, b_out):  # type: ignore[reportMissingParameterType]
    return {
        "snapshot_date": date,
        "active_users": active,
        "total_users": total,
        "bytes_in": b_in,
        "bytes_out": b_out,
    }


class TestGenerateTrendChart:
    def test_returns_png_bytes(self):
        from core.chart_generator import generate_trend_chart

        result = generate_trend_chart([  # type: ignore[reportArgumentType]
            _s("2025-01-01", 5, 10, 1000, 500),
            _s("2025-01-02", 8, 12, 2000, 800),
        ])
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_empty_snapshots_uses_defaults(self):
        from core.chart_generator import generate_trend_chart

        result = generate_trend_chart([])
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_single_snapshot(self):
        from core.chart_generator import generate_trend_chart

        result = generate_trend_chart([_s("day1", 3, 7, 100, 50)])  # type: ignore[reportArgumentType]
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_custom_title(self):
        from core.chart_generator import generate_trend_chart

        result = generate_trend_chart(
            [_s("d1", 1, 2, 0, 0)],  # type: ignore[reportArgumentType]
            title="عنوان مخصص",
        )
        assert isinstance(result, bytes)

    def test_none_values_treated_as_zero(self):
        from core.chart_generator import generate_trend_chart

        result = generate_trend_chart(
            [_s("d1", None, None, None, None)]  # type: ignore[reportArgumentType]
        )
        assert isinstance(result, bytes)


class TestGenerateSalesChart:
    def test_returns_png_bytes_with_data(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart([
            {"profile": "Basic", "count": 10},
            {"profile": "Premium", "count": 5},
        ])
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_empty_batches_uses_placeholder(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart([])
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_profiles_aggregated(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart([
            {"profile": "Basic", "count": 3},
            {"profile": "Basic", "count": 7},
            {"profile": "Premium", "count": 5},
        ])
        assert isinstance(result, bytes)

    def test_missing_profile_defaults_to_unspecified(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart([{"count": 2}])
        assert isinstance(result, bytes)

    def test_missing_count_defaults_to_zero(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart([{"profile": "P1"}])
        assert isinstance(result, bytes)

    def test_custom_title(self):
        from core.chart_generator import generate_sales_chart

        result = generate_sales_chart(
            [{"profile": "A", "count": 1}],
            title="مبيعات مخصصة",
        )
        assert isinstance(result, bytes)


class TestConfigureDarkStyle:
    def test_applies_style_without_error(self):
        import matplotlib.pyplot as plt

        from core.chart_generator import _configure_dark_style  # type: ignore[reportPrivateUsage]

        fig, ax = plt.subplots()
        try:
            _configure_dark_style(fig, ax)
            assert fig.get_facecolor() is not None
            assert ax.get_facecolor() is not None
        finally:
            plt.close(fig)
