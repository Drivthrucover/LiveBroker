"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type EquityCurveChartProps = {
  dates: string[];
  equity: number[];
  benchmark: number[];
};

export function EquityCurveChart({ dates, equity, benchmark }: EquityCurveChartProps) {
  const data = dates.map((date, index) => ({
    date,
    equity: equity[index] ?? null,
    benchmark: benchmark[index] ?? null,
  }));

  return (
    <div className="h-80 w-full rounded-[1.5rem] border border-black/10 bg-white/80 p-4 shadow-panel">
      <h3 className="mb-4 text-lg font-semibold text-ink">Equity vs Benchmark</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
          <XAxis dataKey="date" minTickGap={28} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#5d7a52"
            strokeWidth={3}
            dot={false}
            name="Strategy"
          />
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="#bc754b"
            strokeWidth={2}
            dot={false}
            name="Benchmark"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
