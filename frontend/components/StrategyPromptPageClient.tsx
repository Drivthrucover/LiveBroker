"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { StrategyPromptForm } from "@/components/StrategyPromptForm";
import {
  answerStrategyDraft,
  compileStrategy,
  finalizeStrategyDraft,
  startStrategyDraft,
  validateStrategy,
} from "@/lib/api";
import { createEmptyArtifact, saveArtifact } from "@/lib/storage";
import type { StrategyDraftSession, StrategySpec } from "@/lib/types";

export function StrategyPromptPageClient() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [manualSpec, setManualSpec] = useState("");
  const [draftAnswer, setDraftAnswer] = useState("");
  const [draftSession, setDraftSession] = useState<StrategyDraftSession | null>(null);
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
        setStatus("Starting guided strategy draft...");
        const startedDraft = await startStrategyDraft(prompt);
        setDraftSession(startedDraft);
        return;
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

  async function handleDraftAnswerSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draftSession?.next_question) {
      return;
    }

    setError(null);
    setIsWorking(true);
    try {
      setStatus("Updating strategy draft...");
      const updated = await answerStrategyDraft(
        draftSession.draft,
        draftSession.next_question.key,
        draftAnswer,
      );
      setDraftSession(updated);
      setDraftAnswer("");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "The strategy draft update failed unexpectedly.",
      );
    } finally {
      setIsWorking(false);
      setStatus("Idle");
    }
  }

  async function handleDraftFinalize() {
    if (!draftSession) {
      return;
    }

    setError(null);
    setIsWorking(true);
    const artifact = createEmptyArtifact();
    artifact.prompt = prompt;
    artifact.draftSession = draftSession;

    try {
      setStatus("Finalizing StrategySpec from draft...");
      const parsed = await finalizeStrategyDraft(draftSession.draft);
      artifact.strategySpec = parsed.strategy_spec;
      artifact.assumptions = parsed.assumptions;
      artifact.warnings = parsed.warnings;

      setStatus("Validating strategy on backend...");
      artifact.validation = await validateStrategy(parsed.strategy_spec);

      setStatus("Compiling strategy on backend...");
      artifact.compiledStrategy = await compileStrategy(parsed.strategy_spec);

      saveArtifact(artifact);
      router.push(`/strategy/${artifact.id}`);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "The strategy draft finalization failed unexpectedly.",
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
          primaryActionLabel={mode === "prompt" ? "Start Guided Draft" : "Validate and Compile"}
          onPromptChange={setPrompt}
          onManualSpecChange={setManualSpec}
          onModeChange={(nextMode) => {
            setMode(nextMode);
            setDraftSession(null);
            setDraftAnswer("");
            setError(null);
          }}
          onSubmit={handleSubmit}
        />

        {mode === "prompt" && draftSession ? (
          <section className="mt-8 rounded-[1.6rem] border border-black/10 bg-[#13201b] p-6 text-white shadow-panel">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-white/55">
                  Guided Strategy Draft
                </div>
                <div className="mt-2 text-2xl font-semibold">
                  {draftSession.completion_percent}% complete
                </div>
              </div>
              <div className="w-40 rounded-full bg-white/10">
                <div
                  className="h-2 rounded-full bg-gold transition-all"
                  style={{ width: `${draftSession.completion_percent}%` }}
                />
              </div>
            </div>

            <div className="mt-5 text-sm text-white/78">
              Completed: {draftSession.completed_sections.join(", ") || "none yet"}
            </div>
            <div className="mt-1 text-sm text-white/62">
              Remaining: {draftSession.missing_sections.join(", ") || "ready to finalize"}
            </div>

            {draftSession.next_question ? (
              <form onSubmit={handleDraftAnswerSubmit} className="mt-6 space-y-4">
                <div className="rounded-[1.2rem] bg-white/8 p-4">
                  <div className="text-xs uppercase tracking-[0.16em] text-white/50">
                    Next question
                  </div>
                  <div className="mt-2 text-base font-medium">{draftSession.next_question.prompt}</div>
                  <div className="mt-2 text-sm text-white/65">
                    {draftSession.next_question.rationale}
                  </div>
                </div>
                <textarea
                  value={draftAnswer}
                  onChange={(event) => setDraftAnswer(event.target.value)}
                  className="min-h-28 w-full rounded-[1.2rem] border border-black/10 bg-white px-4 py-3 text-sm text-ink caret-ink outline-none transition focus:border-gold"
                  placeholder="Answer naturally. The model will infer the structured details."
                  autoFocus
                />
                <div className="flex flex-wrap gap-3">
                  <button
                    type="submit"
                    disabled={isWorking || !draftAnswer.trim()}
                    className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-gold disabled:cursor-not-allowed disabled:bg-white/40"
                  >
                    {isWorking ? status : "Submit Answer"}
                  </button>
                  {draftSession.can_finalize ? (
                    <button
                      type="button"
                      onClick={handleDraftFinalize}
                      disabled={isWorking}
                      className="rounded-full border border-white/20 px-4 py-2 text-sm font-semibold text-white transition hover:border-gold hover:text-gold disabled:cursor-not-allowed disabled:text-white/40"
                    >
                      Finalize Strategy
                    </button>
                  ) : null}
                </div>
              </form>
            ) : (
              <div className="mt-6">
                <button
                  type="button"
                  onClick={handleDraftFinalize}
                  disabled={isWorking}
                  className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-gold disabled:cursor-not-allowed disabled:bg-white/40"
                >
                  {isWorking ? status : "Finalize Strategy"}
                </button>
              </div>
            )}
          </section>
        ) : null}

        <div className="mt-5">
          <Link href="/" className="text-sm font-medium text-black/60">
            Back to landing page
          </Link>
        </div>
      </section>

      <section className="rounded-[2rem] border border-black/10 bg-[#13201b] p-8 text-white shadow-panel">
        <h2 className="text-2xl font-semibold">Expected backend flow</h2>
        <ol className="mt-6 space-y-4 text-sm text-white/78">
          <li>1. Start a guided draft or paste StrategySpec JSON manually.</li>
          <li>2. Answer adaptive follow-up questions until the draft is complete.</li>
          <li>3. Finalize into StrategySpec, then validate and compile on the backend.</li>
          <li>4. Navigate to strategy detail page with the returned artifacts.</li>
        </ol>
      </section>
    </main>
  );
}
