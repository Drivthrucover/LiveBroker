"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type DrawdownChartProps = {
  points: Array<{
    date: string;
    drawdown: number;
  }>;
};

export function DrawdownChart({ points }: DrawdownChartProps) {
  return (
    <div className="h-72 w-full rounded-[1.5rem] border border-black/10 bg-white/80 p-4 shadow-panel">
      <h3 className="mb-4 text-lg font-semibold text-ink">Drawdown</h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
          <XAxis dataKey="date" minTickGap={28} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#d4a017"
            fill="rgba(212, 160, 23, 0.38)"
            name="Drawdown"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
