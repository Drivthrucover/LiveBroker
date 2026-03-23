"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { StrategyPromptForm } from "@/components/StrategyPromptForm";
import { compileStrategy, parsePrompt, validateStrategy } from "@/lib/api";
import { createEmptyArtifact, saveArtifact } from "@/lib/storage";
import type { StrategySpec } from "@/lib/types";

export function StrategyPromptPageClient() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [manualSpec, setManualSpec] = useState("");
  const [mode, setMode] = useState<"prompt" | "manual">("prompt");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("Idle");
  const [isWorking, setIsWorking] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsWorking(true);

    const artifact = createEmptyArtifact();
    artifact.prompt = prompt;

    try {
      let strategySpec: StrategySpec;
      let assumptions: string[] = [];
      let warnings: string[] = [];

      if (mode === "prompt") {
        setStatus("Calling backend parse endpoint...");
        const parsed = await parsePrompt(prompt);
        strategySpec = parsed.strategy_spec;
        assumptions = parsed.assumptions;
        warnings = parsed.warnings;
      } else {
        setStatus("Parsing manual StrategySpec JSON locally for transport...");
        strategySpec = JSON.parse(manualSpec) as StrategySpec;
      }

      artifact.strategySpec = strategySpec;
      artifact.assumptions = assumptions;
      artifact.warnings = warnings;

      setStatus("Validating strategy on backend...");
      artifact.validation = await validateStrategy(strategySpec);

      setStatus("Compiling strategy on backend...");
      artifact.compiledStrategy = await compileStrategy(strategySpec);

      saveArtifact(artifact);
      router.push(`/strategy/${artifact.id}`);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "The strategy request failed unexpectedly.",
      );
    } finally {
      setIsWorking(false);
      setStatus("Idle");
    }
  }

  return (
    <main className="grid gap-8 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
          Strategy submission
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink">Create a strategy</h1>
        <p className="mt-4 max-w-xl text-sm leading-7 text-black/65">
          The frontend only submits requests and renders backend artifacts. Validation and
          compilation are always done on the server.
        </p>

        <StrategyPromptForm
          prompt={prompt}
          manualSpec={manualSpec}
          mode={mode}
          isWorking={isWorking}
          status={status}
          error={error}
          onPromptChange={setPrompt}
          onManualSpecChange={setManualSpec}
          onModeChange={setMode}
          onSubmit={handleSubmit}
        />

        <div className="mt-5">
          <Link href="/" className="text-sm font-medium text-black/60">
            Back to landing page
          </Link>
        </div>
      </section>

      <section className="rounded-[2rem] border border-black/10 bg-[#13201b] p-8 text-white shadow-panel">
        <h2 className="text-2xl font-semibold">Expected backend flow</h2>
        <ol className="mt-6 space-y-4 text-sm text-white/78">
          <li>1. Send prompt to `/api/strategy/parse` or paste StrategySpec JSON.</li>
          <li>2. Submit StrategySpec to `/api/strategy/validate`.</li>
          <li>3. Submit StrategySpec to `/api/strategy/compile`.</li>
          <li>4. Navigate to strategy detail page with the returned artifacts.</li>
        </ol>
      </section>
    </main>
  );
}
