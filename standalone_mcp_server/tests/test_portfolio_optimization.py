import math
import json

import pandas as pd

import tools.portfolio_optimization as optimizer


def synthetic_price_frame(symbols=None):
    columns = symbols or ["AAPL", "MSFT", "NVDA", "GOOGL"]
    dates = pd.date_range("2024-01-01", periods=120, freq="D", tz="UTC")
    data = {}
    for symbol_index, symbol in enumerate(columns):
        base_price = 80 + symbol_index * 7
        drift = 0.08 + symbol_index * 0.015
        cycle = 5 + (symbol_index % 6)
        data[symbol] = [
            base_price + index * drift + (index % cycle) * (0.03 + symbol_index * 0.004)
            for index in range(len(dates))
        ]
    return pd.DataFrame(data, index=dates)


def test_optimizer_returns_weights_summing_to_one():
    result = optimizer.optimize_max_sharpe(
        synthetic_price_frame(),
        risk_free_rate=0.0,
        allow_short=False,
        max_weight=0.7,
    )

    assert math.isclose(sum(result["weights"].values()), 1.0, abs_tol=1e-5)
    assert result["metrics"]["annual_volatility_pct"] >= 0
    assert "sharpe_ratio" in result["metrics"]


def test_efficient_frontier_and_correlation_matrix_are_returned():
    price_df = synthetic_price_frame()

    frontier = optimizer.generate_efficient_frontier(price_df, num_points=75, max_weight=0.7)
    random_portfolios = optimizer.generate_random_portfolios(price_df, num_portfolios=100, max_weight=0.7)
    correlation = optimizer.calculate_correlation_matrix(price_df)

    assert frontier
    assert random_portfolios
    assert {"portfolio_volatility", "portfolio_return", "sharpe_ratio"}.issubset(frontier[0])
    assert {"portfolio_volatility", "portfolio_return", "sharpe_ratio", "weights"}.issubset(random_portfolios[0])
    for point in [*frontier, *random_portfolios]:
        assert isinstance(point["portfolio_volatility"], float)
        assert isinstance(point["portfolio_return"], float)
        assert isinstance(point["sharpe_ratio"], float)
    assert [point["portfolio_volatility"] for point in frontier] == sorted(
        point["portfolio_volatility"] for point in frontier
    )
    assert len(correlation) == len(price_df.columns)
    assert correlation[0]["symbol"] in price_df.columns


def test_markowitz_core_saves_artifact_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MCP_PUBLIC_BASE_URL", "https://example.test/mcp")
    monkeypatch.setattr(
        optimizer,
        "fetch_multi_symbol_close_prices",
        lambda symbols, **_kwargs: synthetic_price_frame(symbols),
    )

    result = optimizer.run_markowitz_optimization_core(
        symbols=["AAPL", "MSFT", "NOTREAL"],
        num_frontier_portfolios=100,
        max_weight=0.7,
        finnhub_api_key="secret-key-not-stored",
    )

    assert result["status"] == "success"
    assert result["selection_mode"] == "symbols"
    assert result["sector"] is None
    assert result["symbols_used"] == ["AAPL", "MSFT"]
    assert result["rejected_symbols"] == ["NOTREAL"]
    assert result["artifact_id"].startswith("markowitz_")
    assert "secret-key-not-stored" not in str(result)
    artifact_text = (tmp_path / "results" / f"{result['artifact_id']}.json").read_text(encoding="utf-8")
    artifact = json.loads(artifact_text)
    expected_chart_keys = {
        "random_portfolios",
        "efficient_frontier",
        "min_volatility_portfolio",
        "max_sharpe_portfolio",
        "individual_assets",
        "correlation_matrix",
    }
    assert expected_chart_keys.issubset(artifact)
    assert artifact["random_portfolios"]
    assert artifact["random_portfolios"][0]["sharpe_ratio"] is not None
    assert artifact["efficient_frontier"]
    assert artifact["min_volatility_portfolio"]
    assert artifact["max_sharpe_portfolio"]
    assert artifact["correlation_matrix"]
    for key in ("min_volatility_portfolio", "max_sharpe_portfolio"):
        assert isinstance(artifact[key]["portfolio_volatility"], float)
        assert isinstance(artifact[key]["portfolio_return"], float)
        assert isinstance(artifact[key]["sharpe_ratio"], float)
    assert math.isclose(sum(artifact["max_sharpe_portfolio"]["weights"].values()), 1.0, abs_tol=1e-5)
    assert math.isclose(sum(artifact["min_volatility_portfolio"]["weights"].values()), 1.0, abs_tol=1e-5)
    assert "secret-key-not-stored" not in artifact_text


def test_markowitz_core_uses_sector_when_symbols_are_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        optimizer,
        "fetch_multi_symbol_close_prices",
        lambda symbols, **_kwargs: synthetic_price_frame(symbols),
    )

    result = optimizer.run_markowitz_optimization_core(
        symbols=[],
        sector="Technology",
        num_frontier_portfolios=100,
        max_weight=0.7,
    )

    assert result["status"] == "success"
    assert result["selection_mode"] == "sector"
    assert result["sector"] == "Technology"
    assert result["symbols_used"]
    assert "AAPL" in result["symbols_used"]


def test_markowitz_core_prefers_explicit_symbols_over_sector(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        optimizer,
        "fetch_multi_symbol_close_prices",
        lambda symbols, **_kwargs: synthetic_price_frame(symbols),
    )

    result = optimizer.run_markowitz_optimization_core(
        symbols=["AAPL", "MSFT"],
        sector="Technology",
        num_frontier_portfolios=100,
        max_weight=0.7,
    )

    assert result["status"] == "success"
    assert result["selection_mode"] == "symbols"
    assert result["sector"] is None
    assert result["symbols_used"] == ["AAPL", "MSFT"]
    assert "Explicit symbols were provided, so sector was ignored." in result["warnings"]


def test_markowitz_core_requires_symbols_or_sector():
    result = optimizer.run_markowitz_optimization_core(symbols=[], sector="")

    assert result == {
        "status": "error",
        "message": "Provide either symbols or a sector for portfolio optimization.",
        "errors": ["missing_symbols_or_sector"],
    }
