export function SourcesPage() {
  return (
    <main className="page-shell">
      <section className="hero compact-hero">
        <div>
          <p className="eyebrow">Source inventory</p>
          <h1>Sources</h1>
          <p className="hero-copy">
            What SciScope watches right now, what is planned next, and what is intentionally not in
            scope yet.
          </p>
        </div>
      </section>

      <section className="feature-grid">
        <article className="feature-card">
          <p className="panel-kicker">Live now</p>
          <h2>GitHub releases</h2>
          <p>
            `Mephistos-ML/paranmr` release events published after monitoring starts. This is the
            current proof-of-concept source.
          </p>
        </article>
        <article className="feature-card">
          <p className="panel-kicker">Local validation</p>
          <h2>Replay fixtures</h2>
          <p>
            Manually curated JSON events used for testing relevance, UI behavior, and matching
            quality without publishing real signals.
          </p>
        </article>
        <article className="feature-card">
          <p className="panel-kicker">Planned next</p>
          <h2>ChemRxiv and curated pages</h2>
          <p>
            The next source layer is expected to include preprints and handpicked research-community
            pages once the ingestion path is stable.
          </p>
        </article>
      </section>
    </main>
  );
}
