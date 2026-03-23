export type StrategySpec = Record<string, unknown>;

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

export type StrategyArtifact = {
  id: string;
  prompt: string;
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
