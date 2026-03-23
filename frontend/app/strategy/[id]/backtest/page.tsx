import { BacktestReportPageClient } from "@/components/BacktestReportPageClient";

export default async function StrategyBacktestPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BacktestReportPageClient id={id} />;
}
