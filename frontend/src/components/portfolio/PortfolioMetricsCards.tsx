import type { PortfolioResult } from "../../api/client";
import { formatNumber, formatPercent } from "../../lib/numberFormatters";

type PortfolioMetricsCardsProps = {
  result: PortfolioResult;
};

export default function PortfolioMetricsCards({ result }: PortfolioMetricsCardsProps) {
  const metrics = result.metrics || {};
  const cards = [
    { label: "Expected Return", value: formatPercent(metrics.expected_annual_return_pct) },
    { label: "Volatility", value: formatPercent(metrics.annual_volatility_pct) },
    { label: "Sharpe", value: formatNumber(metrics.sharpe_ratio, 2) },
    { label: "Assets", value: formatNumber(result.symbols?.length || Object.keys(result.weights || {}).length, 0) },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="border border-line bg-panel px-4 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{card.label}</div>
          <div className="mt-2 text-2xl font-semibold tracking-normal text-text">{card.value}</div>
        </div>
      ))}
    </div>
  );
}
