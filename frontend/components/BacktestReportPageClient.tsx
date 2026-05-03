"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { BacktestMetricsPanel } from "@/components/BacktestMetricsPanel";
import { DrawdownChart } from "@/components/DrawdownChart";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { runBacktest, startPaperDeployment } from "@/lib/api";
import { getArtifactById, saveArtifact, saveDeployment } from "@/lib/storage";
import type { StrategyArtifact } from "@/lib/types";

type BacktestReportPageClientProps = {
  id: string;
};

const PAPER_TRADING_ENABLED = process.env.NEXT_PUBLIC_ENABLE_PAPER_TRADING === "true";

export function BacktestReportPageClient({ id }: BacktestReportPageClientProps) {
  const router = useRouter();
  const [artifact, setArtifact] = useState<StrategyArtifact | null>(null);
  const [marketDataJson, setMarketDataJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [useManualMarketData, setUseManualMarketData] = useState(false);
  const [isStartingDeployment, setIsStartingDeployment] = useState(false);

  useEffect(() => {
    const stored = getArtifactById(id);
    setArtifact(stored);
    setMarketDataJson(stored?.marketDataJson ?? "");
  }, [id]);

  const chartPayload = useMemo(() => {
    if (!artifact?.backtestResult) {
      return null;
    }

    return {
      dates: artifact.backtestResult.equity_curve.map((point) => point.date),
      equity: artifact.backtestResult.equity_curve.map((point) => point.value),
      benchmark: artifact.backtestResult.benchmark_curve.map((point) => point.value),
    };
  }, [artifact]);

  async function handleBacktestRun() {
    if (!artifact?.compiledStrategy) {
      setError("Compiled strategy not found. Return to the detail page and compile first.");
      return;
    }

    setError(null);
    setIsRunning(true);

    try {
      const parsedMarketData = useManualMarketData
        ? (JSON.parse(marketDataJson) as Array<Record<string, unknown>>)
        : [];
      const result = await runBacktest(
        artifact.compiledStrategy,
        artifact.strategySpec,
        parsedMarketData,
      );
      const nextArtifact = saveArtifact({
        ...artifact,
        marketDataJson: useManualMarketData ? marketDataJson : "",
        backtestResult: result,
      });
      setArtifact(nextArtifact);
    } catch (backtestError) {
      setError(
        backtestError instanceof Error
          ? backtestError.message
          : "Backtest run failed unexpectedly.",
      );
    } finally {
      setIsRunning(false);
    }
  }

  async function handleStartPaperTrading() {
    if (!artifact?.compiledStrategy) {
      setError("A compiled strategy is required before paper trading can start.");
      return;
    }
    if (!artifact.backtestResult) {
      setError("Run a backtest first before starting paper trading.");
      return;
    }

    setError(null);
    setIsStartingDeployment(true);

    try {
      const deployment = await startPaperDeployment(artifact.compiledStrategy);
      saveDeployment({
        artifactId: artifact.id,
        artifactLabel: artifact.prompt || `Artifact ${artifact.id.slice(0, 8)}`,
        deployment,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
      router.push("/deployments");
    } catch (deploymentError) {
      setError(
        deploymentError instanceof Error
          ? deploymentError.message
          : "Paper deployment failed unexpectedly.",
      );
    } finally {
      setIsStartingDeployment(false);
    }
  }

  if (!artifact) {
    return (
      <main className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <h1 className="text-3xl font-semibold text-ink">Backtest artifact not found</h1>
      </main>
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
          Backtest report
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink">
          Strategy {artifact.id.slice(0, 8)}
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-black/65">
          By default the backend fetches market data from Polygon and submits the compiled strategy
          to `POST /api/backtest/run`. No chart or metric math is computed locally.
        </p>

        <div className="mt-6 rounded-[1.4rem] border border-black/10 bg-[#f6f4ee] p-4">
          <label className="flex items-center gap-3 text-sm font-medium text-ink">
            <input
              type="checkbox"
              checked={useManualMarketData}
              onChange={(event) => setUseManualMarketData(event.target.checked)}
              className="h-4 w-4 rounded border-black/20"
            />
            Use manual market data override instead of Polygon
          </label>
          <p className="mt-2 text-sm text-black/60">
            Automatic fetch uses the compiled strategy first and will rehydrate from the original
            `StrategySpec` if those fields are missing from an older saved artifact.
          </p>
        </div>

        {useManualMarketData ? (
          <div className="mt-6 rounded-[1.4rem] border border-black/10 bg-[#0f1720] p-4">
            <div className="mb-2 text-xs uppercase tracking-[0.16em] text-white/50">
              Market data payload
            </div>
            <textarea
              value={marketDataJson}
              onChange={(event) => setMarketDataJson(event.target.value)}
              className="min-h-64 w-full resize-y bg-transparent font-mono text-xs leading-6 text-white outline-none"
              placeholder='[{"symbol":"AAPL","date":"2024-01-02","open":187.15,"high":188.44,"low":183.89,"close":185.64,"volume":82488700,"adjusted_close":185.64}]'
            />
          </div>
        ) : null}

        {error ? (
          <div className="mt-4 rounded-[1.2rem] border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          type="button"
          onClick={handleBacktestRun}
          disabled={isRunning}
          className="mt-6 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-olive disabled:cursor-not-allowed disabled:bg-black/40"
        >
          {isRunning ? "Running backtest..." : "Run Backtest"}
        </button>
      </section>

      {artifact.backtestResult ? (
        <>
          {PAPER_TRADING_ENABLED ? (
            <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
                Deployment
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink">
                Move from evaluation to paper trading
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-black/65">
                Once you are satisfied with the backtest output, send the compiled strategy to the
                IBKR paper deployment backend. This uses the same compiled artifact you just tested.
              </p>
              <button
                type="button"
                onClick={handleStartPaperTrading}
                disabled={isStartingDeployment}
                className="mt-6 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-olive disabled:cursor-not-allowed disabled:bg-black/40"
              >
                {isStartingDeployment ? "Starting Paper Trading..." : "Start Paper Trading"}
              </button>
            </section>
          ) : (
            <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
                Deployment
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink">
                Paper trading is disabled in this deployment
              </h2>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-black/65">
                This hosted environment supports research workflows only: prompt parsing,
                validation, compilation, backtesting, and charts. IBKR deployment can be enabled
                later in a persistent runtime environment.
              </p>
            </section>
          )}
          <BacktestMetricsPanel metrics={artifact.backtestResult.metrics} />
          {chartPayload ? (
            <EquityCurveChart
              dates={chartPayload.dates}
              equity={chartPayload.equity}
              benchmark={chartPayload.benchmark}
            />
          ) : null}
          <DrawdownChart points={artifact.backtestResult.drawdowns} />

          <section className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
            <h3 className="text-lg font-semibold text-ink">Trade Table</h3>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-black/55">
                  <tr>
                    <th className="pb-3 pr-6">Date</th>
                    <th className="pb-3 pr-6">Symbol</th>
                    <th className="pb-3 pr-6">Side</th>
                    <th className="pb-3 pr-6">Weight Change</th>
                    <th className="pb-3 pr-6">Target Weight</th>
                    <th className="pb-3 pr-6">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {artifact.backtestResult.trades.map((trade) => (
                    <tr
                      key={`${trade.date}-${trade.symbol}-${trade.side}`}
                      className="border-t border-black/5"
                    >
                      <td className="py-3 pr-6">{trade.date}</td>
                      <td className="py-3 pr-6">{trade.symbol}</td>
                      <td className="py-3 pr-6 capitalize">{trade.side}</td>
                      <td className="py-3 pr-6">{trade.weight_change.toFixed(4)}</td>
                      <td className="py-3 pr-6">{trade.target_weight.toFixed(4)}</td>
                      <td className="py-3 pr-6">{trade.price.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
