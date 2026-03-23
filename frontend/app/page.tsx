import Link from "next/link";

export default function HomePage() {
  return (
    <main className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-[2rem] border border-black/10 bg-white/75 p-8 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-clay">
          Backend-first workflow
        </p>
        <h1 className="mt-4 max-w-3xl text-5xl font-semibold tracking-tight text-ink">
          Describe a strategy, inspect the compiled artifact, then backtest it with server-side
          logic only.
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-7 text-black/70">
          This frontend does not compute signals, positions, or backtests locally. It sends prompt,
          spec, and market-data payloads to the backend and renders the results it gets back.
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            href="/strategy/new"
            className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-olive"
          >
            Create Strategy
          </Link>
        </div>
      </section>
      <section className="rounded-[2rem] border border-black/10 bg-[#13201b] p-8 text-white shadow-panel">
        <h2 className="text-xl font-semibold">Frontend pages in scope</h2>
        <ul className="mt-5 space-y-4 text-sm text-white/80">
          <li>`/strategy/new` for prompt submission, validation, and compilation.</li>
          <li>`/strategy/[id]` for strategy detail and compiled artifact review.</li>
          <li>`/strategy/[id]/backtest` for report charts, metrics, and trades.</li>
        </ul>
      </section>
    </main>
  );
}
