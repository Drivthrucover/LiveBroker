"use client";

import type { BacktestMetrics } from "@/lib/types";

import { MetricsSummary } from "@/components/MetricsSummary";

type BacktestMetricsPanelProps = {
  metrics: BacktestMetrics;
};

export function BacktestMetricsPanel({ metrics }: BacktestMetricsPanelProps) {
  return <MetricsSummary metrics={metrics} />;
}
