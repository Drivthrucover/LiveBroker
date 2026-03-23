"use client";

import type { BacktestMetrics } from "@/lib/types";

const metricLabels: Record<keyof BacktestMetrics, string> = {
  cagr: "CAGR",
  sharpe: "Sharpe",
  sortino: "Sortino",
  max_drawdown: "Max Drawdown",
  turnover: "Turnover",
};

type MetricsSummaryProps = {
  metrics: BacktestMetrics;
};

export function MetricsSummary({ metrics }: MetricsSummaryProps) {
  return (
    <section className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
      <h3 className="text-lg font-semibold text-ink">Metrics Summary</h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {Object.entries(metrics).map(([key, value]) => (
          <div key={key} className="rounded-2xl bg-[#13201b] px-4 py-4 text-white">
            <div className="text-xs uppercase tracking-[0.16em] text-white/55">
              {metricLabels[key as keyof BacktestMetrics]}
            </div>
            <div className="mt-2 text-2xl font-semibold">{Number(value).toFixed(4)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
