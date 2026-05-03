import type {
  BacktestResult,
  CompiledStrategy,
  PaperDeployment,
  StrategyDraft,
  StrategyDraftSession,
  StrategySpec,
  ValidationResult,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // Keep default message.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function parsePrompt(prompt: string): Promise<{
  strategy_spec: StrategySpec;
  assumptions: string[];
  warnings: string[];
}> {
  return request("/api/strategy/parse", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function startStrategyDraft(prompt: string): Promise<StrategyDraftSession> {
  return request("/api/strategy/draft/start", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export async function answerStrategyDraft(
  draft: StrategyDraft,
  questionKey: string,
  answer: string,
): Promise<StrategyDraftSession> {
  return request("/api/strategy/draft/answer", {
    method: "POST",
    body: JSON.stringify({
      draft,
      question_key: questionKey,
      answer,
    }),
  });
}

export async function finalizeStrategyDraft(draft: StrategyDraft): Promise<{
  strategy_spec: StrategySpec;
  assumptions: string[];
  warnings: string[];
}> {
  return request("/api/strategy/draft/finalize", {
    method: "POST",
    body: JSON.stringify({ draft }),
  });
}

export async function validateStrategy(strategySpec: StrategySpec): Promise<ValidationResult> {
  return request("/api/strategy/validate", {
    method: "POST",
    body: JSON.stringify({ strategy_spec: strategySpec }),
  });
}

export async function compileStrategy(strategySpec: StrategySpec): Promise<CompiledStrategy> {
  return request("/api/strategy/compile", {
    method: "POST",
    body: JSON.stringify({ strategy_spec: strategySpec }),
  });
}

export async function runBacktest(
  compiledStrategy: CompiledStrategy,
  strategySpec: StrategySpec | null,
  marketData: Array<Record<string, unknown>>,
): Promise<BacktestResult> {
  return request("/api/backtest/run", {
    method: "POST",
    body: JSON.stringify({
      compiled_strategy: compiledStrategy,
      strategy_spec: strategySpec,
      market_data: marketData,
    }),
  });
}

export async function startPaperDeployment(
  compiledStrategy: CompiledStrategy,
): Promise<PaperDeployment> {
  return request("/api/deployments/start", {
    method: "POST",
    body: JSON.stringify({
      compiled_strategy: compiledStrategy,
    }),
  });
}
