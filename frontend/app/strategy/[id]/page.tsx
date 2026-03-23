import { StrategyDetailPageClient } from "@/components/StrategyDetailPageClient";

export default async function StrategyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <StrategyDetailPageClient id={id} />;
}
