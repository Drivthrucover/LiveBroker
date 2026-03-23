export default function DeploymentsPage() {
  return (
    <main className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-panel">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-clay">
        Deployments
      </p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight text-ink">
        Active deployments will appear here
      </h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-black/65">
        The frontend route exists because it is part of the documented app surface. Backend
        deployment activation is still returning `501 Not Implemented`, so this page is currently a
        placeholder rather than a live deployment console.
      </p>
    </main>
  );
}
