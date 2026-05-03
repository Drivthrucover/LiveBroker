"use client";

type StrategyPromptFormProps = {
  prompt: string;
  manualSpec: string;
  mode: "prompt" | "manual";
  isWorking: boolean;
  status: string;
  error: string | null;
  primaryActionLabel: string;
  onPromptChange: (value: string) => void;
  onManualSpecChange: (value: string) => void;
  onModeChange: (mode: "prompt" | "manual") => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export function StrategyPromptForm({
  prompt,
  manualSpec,
  mode,
  isWorking,
  status,
  error,
  primaryActionLabel,
  onPromptChange,
  onManualSpecChange,
  onModeChange,
  onSubmit,
}: StrategyPromptFormProps) {
  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-5">
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => onModeChange("prompt")}
          className={`rounded-full px-4 py-2 text-sm font-semibold ${
            mode === "prompt" ? "bg-ink text-white" : "border border-black/10 bg-white text-ink"
          }`}
        >
          Prompt Mode
        </button>
        <button
          type="button"
          onClick={() => onModeChange("manual")}
          className={`rounded-full px-4 py-2 text-sm font-semibold ${
            mode === "manual" ? "bg-ink text-white" : "border border-black/10 bg-white text-ink"
          }`}
        >
          Manual JSON
        </button>
      </div>

      <label className="block">
        <span className="mb-2 block text-sm font-medium text-ink">Strategy prompt</span>
        <textarea
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          className="min-h-40 w-full rounded-[1.4rem] border border-black/10 bg-[#f6f4ee] px-5 py-4 text-sm outline-none ring-0 transition focus:border-olive"
          placeholder="Create a weekly momentum strategy on US large cap stocks..."
        />
      </label>

      {mode === "manual" ? (
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-ink">
            StrategySpec JSON fallback
          </span>
          <textarea
            value={manualSpec}
            onChange={(event) => onManualSpecChange(event.target.value)}
            className="min-h-72 w-full rounded-[1.4rem] border border-black/10 bg-[#111827] px-5 py-4 font-mono text-xs text-white outline-none transition focus:border-gold"
            placeholder='{"schema_version":"1.0.0", ... }'
          />
        </label>
      ) : (
        <div className="rounded-[1.4rem] border border-gold/40 bg-gold/10 p-4 text-sm text-black/75">
          Prompt mode now uses the backend parser to turn natural language into a StrategySpec.
          Manual JSON remains available as a fallback for deterministic testing.
        </div>
      )}

      {error ? (
        <div className="rounded-[1.2rem] border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={isWorking}
        className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-olive disabled:cursor-not-allowed disabled:bg-black/40"
      >
        {isWorking ? status : primaryActionLabel}
      </button>
    </form>
  );
}
