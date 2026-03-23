"use client";

import type { StrategyArtifact } from "@/lib/types";

const STORAGE_KEY = "livebroker-strategy-artifacts";

function readAllArtifacts(): StrategyArtifact[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    return JSON.parse(raw) as StrategyArtifact[];
  } catch {
    return [];
  }
}

function writeAllArtifacts(artifacts: StrategyArtifact[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(artifacts));
}

export function createEmptyArtifact(): StrategyArtifact {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    prompt: "",
    strategySpec: null,
    assumptions: [],
    warnings: [],
    validation: null,
    compiledStrategy: null,
    backtestResult: null,
    marketDataJson: "",
    createdAt: now,
    updatedAt: now,
  };
}

export function saveArtifact(artifact: StrategyArtifact): StrategyArtifact {
  const artifacts = readAllArtifacts();
  const next = {
    ...artifact,
    updatedAt: new Date().toISOString(),
  };
  const filtered = artifacts.filter((item) => item.id !== next.id);
  writeAllArtifacts([next, ...filtered]);
  return next;
}

export function getArtifactById(id: string): StrategyArtifact | null {
  return readAllArtifacts().find((artifact) => artifact.id === id) ?? null;
}
