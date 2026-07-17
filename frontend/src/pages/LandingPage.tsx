import { AppLink } from "../lib/router";

type LandingPageProps = {
  navigate: (href: string) => void;
};

export function LandingPage({ navigate }: LandingPageProps) {
  return (
    <main className="page-shell">
      <section className="hero landing-hero">
        <div>
          <p className="eyebrow">Research intelligence for narrow fields</p>
          <h1>SciScope</h1>
          <p className="hero-copy">
            Follow the edge of your field without manually watching GitHub, niche software
            releases, workshops, and other research signals one tab at a time.
          </p>
          <div className="hero-actions">
            <AppLink className="primary-link-button" href="/dashboard" onNavigate={navigate}>
              Open dashboard
            </AppLink>
            <AppLink className="secondary-link-button" href="/sources" onNavigate={navigate}>
              See current sources
            </AppLink>
          </div>
        </div>
        <div className="landing-callout">
          <p className="panel-kicker">Current v0</p>
          <h2>Paramagnetic NMR first</h2>
          <p>
            The current validation path is built around pNMR and monitors new release-level
            software signals from `Mephistos-ML/paranmr`.
          </p>
        </div>
      </section>

      <section className="feature-grid">
        <article className="feature-card">
          <p className="panel-kicker">Problem</p>
          <h2>Niche signals get missed</h2>
          <p>
            Big papers are visible. Small but important community events, software releases, and
            technical updates often are not.
          </p>
        </article>
        <article className="feature-card">
          <p className="panel-kicker">Approach</p>
          <h2>Continuous monitoring</h2>
          <p>
            SciScope turns narrow research monitoring into an always-on workflow instead of a
            manual search habit.
          </p>
        </article>
        <article className="feature-card">
          <p className="panel-kicker">Output</p>
          <h2>Signals with reasons</h2>
          <p>
            Each surfaced item is matched against a topic profile, scored, and explained with
            grounded terms instead of vague AI summaries.
          </p>
        </article>
      </section>
    </main>
  );
}
