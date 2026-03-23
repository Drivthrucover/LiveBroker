"use client";

import { useState } from "react";

type StrategySpecViewerProps = {
  title: string;
  data: unknown;
};

export function StrategySpecViewer({ title, data }: StrategySpecViewerProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="rounded-full border border-black/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-black/60"
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!collapsed ? (
        <pre className="mt-4 overflow-x-auto rounded-2xl bg-[#0f1720] p-4 text-xs leading-6 text-[#f4f7fb]">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
