export type StrategySpec = Record<string, unknown>;

export type DraftQuestionKey =
  | "universe"
  | "signal"
  | "selection"
  | "rebalance"
  | "backtest_window"
  | "benchmark";

export type ClarificationQuestion = {
  key: DraftQuestionKey;
  prompt: string;
  rationale: string;
};

export type StrategyDraft = {
  prompt: string;
  strategy_name?: string | null;
  strategy_description?: string | null;
  universe_scope?: "explicit_symbols" | "us_large_cap" | "us_mega_cap" | "us_broad_market" | null;
  symbols: string[];
  signal_kind?:
    | "momentum_return"
    | "sma_crossover"
    | "realized_volatility"
    | "rsi"
    | "exclude_earnings_window"
    | null;
  lookback_days?: number | null;
  fast_lookback_days?: number | null;
  slow_lookback_days?: number | null;
  window_days?: number | null;
  selection_top_n?: number | null;
  rebalance_frequency?: "daily" | "weekly" | "monthly" | null;
  rebalance_day_of_week?: "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | null;
  rebalance_day_of_month?: number | null;
  benchmark_symbol?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  initial_capital?: number | null;
  assumptions: string[];
  warnings: string[];
};

export type StrategyDraftSession = {
  draft: StrategyDraft;
  next_question: ClarificationQuestion | null;
  completion_percent: number;
  completed_sections: string[];
  missing_sections: string[];
  can_finalize: boolean;
};

export type ValidationResult = {
  valid: boolean;
  errors: string[];
  warnings: string[];
};

export type CompiledStrategy = {
  universe_plan: Record<string, unknown>;
  signal_plan: Record<string, unknown>;
  selection_plan: Record<string, unknown>;
  portfolio_plan: Record<string, unknown>;
  risk_plan: Record<string, unknown>;
  execution_plan: Record<string, unknown>;
  schedule: Record<string, unknown>;
  benchmark_symbol: string;
  initial_capital: number;
  backtest_start_date?: string | null;
  backtest_end_date?: string | null;
  data_requirements: Array<Record<string, unknown>>;
};

export type CurvePoint = {
  date: string;
  value: number;
};

export type DrawdownPoint = {
  date: string;
  drawdown: number;
};

export type TradeRecord = {
  date: string;
  symbol: string;
  side: string;
  weight_change: number;
  target_weight: number;
  price: number;
};

export type BacktestMetrics = {
  cagr: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  turnover: number;
};

export type BacktestResult = {
  equity_curve: CurvePoint[];
  benchmark_curve: CurvePoint[];
  trades: TradeRecord[];
  drawdowns: DrawdownPoint[];
  metrics: BacktestMetrics;
};

export type PositionSnapshot = {
  symbol: string;
  quantity: number;
  avg_price: number;
  market_price?: number | null;
  market_value?: number | null;
};

export type BrokerOrderResult = {
  order_id: string;
  status: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  order_type: string;
  broker_message?: string | null;
};

export type AccountSummary = {
  account_id?: string | null;
  currency: string;
  cash: number;
  buying_power: number;
  net_liquidation: number;
};

export type DeploymentStatus = {
  state: "created" | "paper_ready" | "paper_running" | "paper_error" | "stopped";
  detail?: string | null;
};

export type PaperDeployment = {
  deployment_id: string;
  mode: "paper";
  compiled_strategy: CompiledStrategy;
  status: DeploymentStatus;
  created_at: string;
  account_summary?: AccountSummary | null;
  positions: PositionSnapshot[];
  pending_orders: BrokerOrderResult[];
  last_error?: string | null;
};

export type SavedDeployment = {
  artifactId: string;
  artifactLabel: string;
  deployment: PaperDeployment;
  createdAt: string;
  updatedAt: string;
};

export type StrategyArtifact = {
  id: string;
  prompt: string;
  draftSession: StrategyDraftSession | null;
  strategySpec: StrategySpec | null;
  assumptions: string[];
  warnings: string[];
  validation: ValidationResult | null;
  compiledStrategy: CompiledStrategy | null;
  backtestResult: BacktestResult | null;
  marketDataJson: string;
  createdAt: string;
  updatedAt: string;
};
