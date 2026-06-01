import { memo, useMemo } from "react";
import type { BacktestResult } from "../../api/client";
import { deriveBuyHoldReturn } from "../../lib/chartTransforms";
import { signedColor } from "../../lib/colorScales";
import { formatCurrency, formatNumber, formatPercent } from "../../lib/numberFormatters";

type MetricsStripProps = {
  result: BacktestResult;
};

function MetricsStrip({ result }: MetricsStripProps) {
  const buyHold = useMemo(() => result.metrics?.buy_hold_return_pct ?? deriveBuyHoldReturn(result.charts?.price || []), [result]);
  const totalReturn = result.metrics?.total_return_pct;
  const alpha = result.metrics?.alpha_vs_buy_hold_pct ?? (typeof totalReturn === "number" && typeof buyHold === "number" ? totalReturn - buyHold : null);
  const items = [
    { label: "Total Return", value: formatPercent(totalReturn), raw: totalReturn, tip: "Strategy total return over selected lookback." },
    { label: "Buy & Hold", value: formatPercent(buyHold), raw: buyHold, tip: "Derived from first and last close when backend does not provide it." },
    { label: "Alpha", value: formatPercent(alpha), raw: alpha, tip: "Strategy return minus buy-and-hold return." },
    { label: "Sharpe", value: formatNumber(result.metrics?.sharpe_ratio), raw: result.metrics?.sharpe_ratio, tip: "Risk-adjusted return reported by VectorBT." },
    { label: "Max DD", value: formatPercent(result.metrics?.max_drawdown_pct), raw: -(result.metrics?.max_drawdown_pct || 0), tip: "Worst peak-to-trough drawdown." },
    { label: "Win Rate", value: formatPercent(result.metrics?.win_rate_pct), raw: result.metrics?.win_rate_pct, tip: "Share of closed trades that were profitable." },
    { label: "Trades", value: formatNumber(result.metrics?.total_trades, 0), raw: null, tip: "Total closed trades." },
    { label: "Final Value", value: formatCurrency(result.metrics?.final_value), raw: result.metrics?.final_value, tip: "Final portfolio value." },
    { label: "MC Positive", value: formatPercent(result.summary?.probability_positive_return_pct), raw: result.summary?.probability_positive_return_pct, tip: "Bootstrap probability of positive forward return." },
    { label: "MC Expected", value: formatPercent(result.summary?.monte_carlo_expected_return_pct), raw: result.summary?.monte_carlo_expected_return_pct, tip: "Average simulated forward return." },
  ];

  return (
    <section className="grid grid-cols-2 gap-2 md:grid-cols-5 xl:grid-cols-10">
      {items.map((item) => (
        <div key={item.label} className="border border-line bg-panel px-3 py-2" title={item.tip}>
          <div className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{item.label}</div>
          <div className="mt-1 truncate text-lg font-semibold" style={{ color: item.raw === null ? undefined : signedColor(item.raw) }}>
            {item.value}
          </div>
        </div>
      ))}
    </section>
  );
}

export default memo(MetricsStrip);
