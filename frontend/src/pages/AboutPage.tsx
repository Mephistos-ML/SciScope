export function AboutPage() {
  return (
    <main className="app-shell about-shell">
      <section className="page-intro about-intro">
        <div className="page-intro-main">
          <h1 className="page-title">SciScope</h1>
          <p className="section-copy">
            Scientific repository intelligence for researchers.
          </p>
        </div>
      </section>

      <section className="about-grid">
        <article className="about-panel about-panel-hero">
          <h2 className="section-title">Scientific repository intelligence</h2>
          <p className="section-copy">
            SciScope helps researchers discover relevant scientific software
            repositories, understand the existing implementation landscape and keep
            track of the repositories that matter to their work.
          </p>
          <p className="section-copy">
            It was created during Ernest Borysenko&apos;s PhD work in computational
            quantum chemistry, where repository awareness became essential for
            understanding what had already been built, identifying competing work and
            focusing on genuine novelty.
          </p>
          <p className="section-copy">
            The same need appears in literature review, topic mapping, early-stage
            research planning and software design, where repository awareness can be
            as important as paper awareness.
          </p>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Workflow</h2>
          <div className="about-flow-list">
            <div className="about-flow-item">
              <strong>Explore</strong>
              <p>
                Describe a topic, method, workflow or software area and review matched
                repositories across supported hosts.
              </p>
            </div>
            <div className="about-flow-item">
              <strong>Subscribe</strong>
              <p>
                Save only the repositories that matter instead of monitoring every
                result from a search.
              </p>
            </div>
            <div className="about-flow-item">
              <strong>My Feed</strong>
              <p>
                Keep subscribed repositories in a dedicated feed so important changes
                can be surfaced in one place.
              </p>
            </div>
          </div>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Capabilities</h2>
          <ul className="about-list">
            <li>Cross-host repository discovery for scientific software.</li>
            <li>AI-generated search queries based on the user topic description.</li>
            <li>Repository-level subscriptions chosen directly from Explore results.</li>
            <li>Feed views centered on repositories that the user explicitly follows.</li>
            <li>Links back to the original repository host from source badges.</li>
          </ul>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Audience</h2>
          <p className="section-copy">
            SciScope is designed for researchers, research engineers, scientific
            software users and technically oriented teams who need a better way to find
            and track relevant repositories.
          </p>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Coverage</h2>
          <ul className="about-list">
            <li>Repository discovery across GitHub, GitLab, Gitee, GitCode and GitVerse.</li>
            <li>Repository links preserved through source badges and subscription records.</li>
            <li>Feed entries built from repositories explicitly selected in Explore.</li>
            <li>Search and monitoring centered on repositories as the primary unit.</li>
          </ul>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Author</h2>
          <p className="section-copy">
            SciScope is created and authored by Ernest Borysenko.
          </p>
        </article>

        <article className="about-panel">
          <h2 className="section-title">Contact</h2>
          <a className="about-contact-link" href="mailto:contact@sciscope.uk">
            contact@sciscope.uk
          </a>
        </article>
      </section>
    </main>
  );
}
