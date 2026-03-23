"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StrategySpecViewer } from "@/components/StrategySpecViewer";
import { getArtifactById } from "@/lib/storage";
import type { StrategyArtifact } from "@/lib/types";

type StrategyDetailPageClientProps = {
  id: string;
};

export function StrategyDetailPageClient({ id }: StrategyDetailPageClientProps) {
  const [artifact, setArtifact] = useState<StrategyArtifact | null>(null);

  useEffect(() => {
    setArtifact(getArtifactById(id));
  }, [id]);

  if (!artifact) {
    return (
      <main className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <h1 className="text-3xl font-semibold text-ink">Strategy not found</h1>
        <p className="mt-3 text-sm text-black/65">
          This frontend currently stores strategy artifacts in browser local storage until backend
          persistence exists.
        </p>
        <Link href="/strategy/new" className="mt-6 inline-block text-sm font-semibold">
          Create a new strategy
        </Link>
      </main>
    );
  }

  return (
    <main className="space-y-8">
      <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
              Strategy detail
            </p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink">
              Artifact {artifact.id.slice(0, 8)}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-black/65">
              {artifact.prompt || "Manual JSON submission"}
            </p>
          </div>
          <Link
            href={`/strategy/${artifact.id}/backtest`}
            className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-olive"
          >
            Run Backtest
          </Link>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
          <div className="text-xs uppercase tracking-[0.16em] text-black/55">Validation</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {artifact.validation?.valid ? "Valid" : "Issues"}
          </div>
        </div>
        <div className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
          <div className="text-xs uppercase tracking-[0.16em] text-black/55">Warnings</div>
          <div className="mt-3 text-3xl font-semibold text-ink">{artifact.warnings.length}</div>
        </div>
        <div className="rounded-[1.5rem] border border-black/10 bg-white/80 p-5 shadow-panel">
          <div className="text-xs uppercase tracking-[0.16em] text-black/55">Assumptions</div>
          <div className="mt-3 text-3xl font-semibold text-ink">{artifact.assumptions.length}</div>
        </div>
      </section>

      {artifact.validation && artifact.validation.errors.length > 0 ? (
        <section className="rounded-[1.5rem] border border-red-200 bg-red-50 p-5 text-sm text-red-700 shadow-panel">
          <h2 className="text-base font-semibold">Validation errors</h2>
          <ul className="mt-3 space-y-2">
            {artifact.validation.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {artifact.validation && artifact.validation.warnings.length > 0 ? (
        <section className="rounded-[1.5rem] border border-gold/40 bg-gold/10 p-5 text-sm text-black/75 shadow-panel">
          <h2 className="text-base font-semibold">Validation warnings</h2>
          <ul className="mt-3 space-y-2">
            {artifact.validation.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <StrategySpecViewer title="StrategySpec JSON" data={artifact.strategySpec} />
        <StrategySpecViewer title="CompiledStrategy JSON" data={artifact.compiledStrategy} />
      </div>
    </main>
  );
}
