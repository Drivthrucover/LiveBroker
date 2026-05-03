"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getAllDeployments } from "@/lib/storage";
import type { SavedDeployment } from "@/lib/types";

const PAPER_TRADING_ENABLED = process.env.NEXT_PUBLIC_ENABLE_PAPER_TRADING === "true";

export default function DeploymentsPage() {
  const [deployments, setDeployments] = useState<SavedDeployment[]>([]);

  useEffect(() => {
    setDeployments(getAllDeployments());
  }, []);

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">Deployments</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink">
          Paper trading console
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-black/65">
          Deployments are created from compiled strategies. This page shows the latest paper-session
          status returned by the backend and stored locally in the browser until persistence exists.
        </p>
      </section>

      {!PAPER_TRADING_ENABLED ? (
        <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
          <h2 className="text-2xl font-semibold text-ink">Paper trading disabled</h2>
          <p className="mt-3 text-sm text-black/65">
            This hosted deployment only exposes the research workflow. IBKR paper trading requires a
            persistent runtime and is intentionally disabled here.
          </p>
        </section>
      ) : null}

      {PAPER_TRADING_ENABLED && deployments.length === 0 ? (
        <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
          <h2 className="text-2xl font-semibold text-ink">No deployments yet</h2>
          <p className="mt-3 text-sm text-black/65">
            Start paper trading from a strategy detail page after validating and compiling a
            strategy.
          </p>
          <Link href="/strategy/new" className="mt-6 inline-block text-sm font-semibold text-ink">
            Create a strategy
          </Link>
        </section>
      ) : PAPER_TRADING_ENABLED ? (
        <section className="grid gap-6">
          {deployments.map((entry) => (
            <article
              key={entry.deployment.deployment_id}
              className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs uppercase tracking-[0.16em] text-black/55">
                    Deployment {entry.deployment.deployment_id.slice(0, 8)}
                  </div>
                  <h2 className="mt-2 text-2xl font-semibold text-ink">{entry.artifactLabel}</h2>
                  <p className="mt-3 text-sm text-black/65">
                    State: <span className="font-semibold text-ink">{entry.deployment.status.state}</span>
                    {entry.deployment.status.detail ? ` - ${entry.deployment.status.detail}` : ""}
                  </p>
                  {entry.deployment.last_error ? (
                    <p className="mt-2 text-sm text-red-700">{entry.deployment.last_error}</p>
                  ) : null}
                </div>
                <Link
                  href={`/strategy/${entry.artifactId}`}
                  className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:border-olive hover:text-olive"
                >
                  Open strategy
                </Link>
              </div>

              <div className="mt-6 grid gap-4 md:grid-cols-3">
                <MetricCard
                  label="Buying Power"
                  value={formatCurrency(entry.deployment.account_summary?.buying_power)}
                />
                <MetricCard
                  label="Net Liquidation"
                  value={formatCurrency(entry.deployment.account_summary?.net_liquidation)}
                />
                <MetricCard
                  label="Open Orders"
                  value={String(entry.deployment.pending_orders.length)}
                />
              </div>

              <div className="mt-6 grid gap-6 xl:grid-cols-2">
                <section className="rounded-[1.5rem] border border-black/10 bg-[#f6f4ee] p-5">
                  <h3 className="text-base font-semibold text-ink">Positions</h3>
                  {entry.deployment.positions.length === 0 ? (
                    <p className="mt-3 text-sm text-black/65">No positions reported yet.</p>
                  ) : (
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="text-left text-black/55">
                          <tr>
                            <th className="pb-2 pr-4 font-medium">Symbol</th>
                            <th className="pb-2 pr-4 font-medium">Qty</th>
                            <th className="pb-2 pr-4 font-medium">Avg Price</th>
                          </tr>
                        </thead>
                        <tbody className="text-ink">
                          {entry.deployment.positions.map((position) => (
                            <tr key={`${entry.deployment.deployment_id}-${position.symbol}`}>
                              <td className="py-2 pr-4">{position.symbol}</td>
                              <td className="py-2 pr-4">{position.quantity}</td>
                              <td className="py-2 pr-4">{position.avg_price.toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="rounded-[1.5rem] border border-black/10 bg-[#13201b] p-5 text-white">
                  <h3 className="text-base font-semibold">Submitted Orders</h3>
                  {entry.deployment.pending_orders.length === 0 ? (
                    <p className="mt-3 text-sm text-white/70">No orders submitted yet.</p>
                  ) : (
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="text-left text-white/60">
                          <tr>
                            <th className="pb-2 pr-4 font-medium">Order ID</th>
                            <th className="pb-2 pr-4 font-medium">Symbol</th>
                            <th className="pb-2 pr-4 font-medium">Side</th>
                            <th className="pb-2 pr-4 font-medium">Qty</th>
                            <th className="pb-2 pr-4 font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {entry.deployment.pending_orders.map((order) => (
                            <tr key={order.order_id}>
                              <td className="py-2 pr-4">{order.order_id}</td>
                              <td className="py-2 pr-4">{order.symbol}</td>
                              <td className="py-2 pr-4">{order.side}</td>
                              <td className="py-2 pr-4">{order.quantity}</td>
                              <td className="py-2 pr-4">{order.status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
      <div className="text-xs uppercase tracking-[0.16em] text-black/55">{label}</div>
      <div className="mt-3 text-3xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) {
    return "N/A";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
