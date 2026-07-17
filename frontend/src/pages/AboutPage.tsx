export function AboutPage() {
  return (
    <main className="page-shell">
      <section className="hero compact-hero">
        <div>
          <p className="eyebrow">Method and limits</p>
          <h1>About</h1>
          <p className="hero-copy">
            SciScope is currently a deterministic monitoring system with explicit topic matching.
            It is not yet a broad autonomous research agent.
          </p>
        </div>
      </section>

      <section className="stack-list">
        <article className="stack-card">
          <h2>Current pipeline</h2>
          <p>
            Source ingestion → normalization → deterministic topic matching → dashboard display →
            detail inspection.
          </p>
        </article>
        <article className="stack-card">
          <h2>Why deterministic first</h2>
          <p>
            Retrieval quality and observability matter more than adding an LLM early. The current
            system is deliberately built so every match is inspectable.
          </p>
        </article>
        <article className="stack-card">
          <h2>Current limits</h2>
          <p>
            One seeded topic, one live source, no auth, no saved user profiles, no email digest,
            and no ranking model beyond rule-based matching.
          </p>
        </article>
      </section>
    </main>
  );
}
