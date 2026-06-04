from tools.universe import (
    get_stock_by_ticker,
    get_universe_path,
    list_all_stocks,
    list_sectors,
    list_stocks_by_sector,
    resolve_symbols_for_sector,
    validate_symbols,
)


def test_universe_file_is_found():
    assert get_universe_path().name == "us_stocks_only_universe.json"


def test_universe_loader_groups_sectors():
    sectors = list_sectors()

    assert "Technology" in sectors
    assert sectors == sorted(sectors)


def test_list_stocks_by_sector_returns_compact_metadata():
    stocks = list_stocks_by_sector("Technology")

    assert any(stock["ticker"] == "AAPL" for stock in stocks)
    assert all(stock["sector"] == "Technology" for stock in stocks)
    assert "metadata" not in stocks[0]
    assert {"ticker", "name", "sector", "risk_level", "market_cap"}.issubset(stocks[0])


def test_list_all_stocks_returns_unfiltered_universe():
    all_stocks = list_all_stocks()
    technology_stocks = list_stocks_by_sector("Technology")

    assert len(all_stocks) > len(technology_stocks)
    assert any(stock["sector"] != "Technology" for stock in all_stocks)


def test_resolve_symbols_for_sector_returns_tickers():
    symbols = resolve_symbols_for_sector("Technology")

    assert symbols
    assert "AAPL" in symbols
    assert all(":" not in symbol for symbol in symbols)


def test_validate_symbols_returns_known_tickers_only():
    assert validate_symbols(["AAPL", "NASDAQ:MSFT", "NOTREAL"]) == ["AAPL", "MSFT"]
    assert get_stock_by_ticker("aapl")["ticker"] == "AAPL"
