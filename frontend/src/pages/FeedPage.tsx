import { SourceBadge } from "../components/SourceBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import feedNoUpdatesIllustration from "../assets/states/feed/feed-no-updates.svg";
import type { SubscriptionItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  deletePending: boolean;
  selectedSubscriptionId: string | null;
  subscriptions: SubscriptionItem[];
  viewer: ViewerPayload["user"];
  onDeleteSubscription: (subscriptionId: string) => void;
  onSelectSubscription: (subscriptionId: string) => void;
};

export function FeedPage({
  deletePending,
  selectedSubscriptionId,
  subscriptions,
  viewer,
  onDeleteSubscription,
  onSelectSubscription,
}: FeedPageProps) {
  const selectedSubscription =
    subscriptions.find((item) => item.subscriptionId === selectedSubscriptionId) ?? null;
  const hasSubscriptions = subscriptions.length > 0;
  const introCopy = hasSubscriptions
    ? "Track the repositories you selected from Explore and open each subscription for its monitoring context."
    : "Monitor changes from repositories you choose to follow across every supported source.";

  return (
    <main className="app-shell feed-shell">
      <section className="page-intro">
        <div className="page-intro-main">
          <h1 className="page-title">My Feed</h1>
          <p className="section-copy">{introCopy}</p>
        </div>
      </section>

      {!viewer || !hasSubscriptions ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">
              {viewer ? "No Subscriptions Yet" : "Sign In to Build Your Feed"}
            </h2>
            <p className="empty-state-copy">
              {viewer
                ? "Save repositories from Explore and they will appear here for ongoing monitoring."
                : "Use Google sign-in to save repositories from Explore and monitor them here."}
            </p>
          </article>
        </section>
      ) : (
        <section className="feed-layout">
          <aside className="subscription-rail">
            <div className="rail-header">
              <p className="section-kicker">Subscriptions</p>
              <div className="results-title-row">
                <h2 className="section-title">Saved Repositories</h2>
                <span className="results-count-badge">{subscriptions.length} total</span>
              </div>
            </div>

            <div className="subscription-list">
              {subscriptions.map((subscription) => (
                <div
                  key={subscription.subscriptionId}
                  className={
                    subscription.subscriptionId === selectedSubscriptionId
                      ? "subscription-card subscription-card-active"
                      : "subscription-card"
                  }
                >
                  <button
                    className="subscription-select"
                    onClick={() => onSelectSubscription(subscription.subscriptionId)}
                    type="button"
                  >
                    <strong className="subscription-card-title">
                      {subscription.repository.fullName}
                    </strong>
                    <p>{subscription.selectedQuery || "No Query Snapshot Saved."}</p>
                    <span className="subscription-card-meta">
                      {subscription.repository.source}
                    </span>
                  </button>
                  <button
                    className="subscription-delete"
                    disabled={deletePending}
                    onClick={() => onDeleteSubscription(subscription.subscriptionId)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          </aside>

          <section className="subscription-detail">
            {selectedSubscription ? (
              <>
                <p className="section-kicker">Selected Repository</p>
                <h2 className="section-title">{selectedSubscription.repository.fullName}</h2>
                <p className="section-copy">
                  This subscription keeps the repository in your feed for ongoing monitoring.
                </p>

                <div className="detail-panel-block">
                  <h4>Repository</h4>
                  <SourceBadge
                    href={selectedSubscription.repository.url}
                    source={selectedSubscription.repository.source}
                  />
                </div>

                <div className="detail-panel-block">
                  <h4>Selected Query</h4>
                  <p className="detail-copy">
                    {selectedSubscription.selectedQuery || "No Query Snapshot Saved."}
                  </p>
                </div>

                <div className="detail-panel-block">
                  <h4>Updates</h4>
                  <div className="feed-updates-placeholder">
                    <img
                      alt=""
                      aria-hidden="true"
                      className="empty-state-illustration feed-updates-illustration"
                      src={feedNoUpdatesIllustration}
                    />
                    <div className="feed-updates-copy">
                      <p className="empty-state-title">No Updates Surfaced Yet</p>
                      <p className="detail-copy">
                        New monitored changes for this repository will appear here when
                        SciScope detects them.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="feed-detail-empty">
                <p className="section-kicker">Selected Repository</p>
                <h3 className="section-title">Pick a Saved Repository</h3>
                <p className="section-copy">
                  Choose a subscription from the rail to open its monitoring view.
                </p>
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  );
}
