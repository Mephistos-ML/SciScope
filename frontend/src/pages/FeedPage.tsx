import { SourceBadge } from "../components/SourceBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
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

  if (!viewer || !hasSubscriptions) {
    return (
      <main className="app-shell feed-shell">
        <section className="page-intro">
          <div className="page-intro-main">
            <h1 className="page-title">My Feed</h1>
            <p className="section-copy">
              Monitor changes from repositories you choose to follow across every supported source.
            </p>
          </div>
        </section>

        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">
              {viewer ? "No subscriptions yet" : "Sign in to build your feed"}
            </h2>
            <p className="empty-state-copy">
              {viewer
                ? "Save repositories from Explore and they will appear here for ongoing monitoring."
                : "Use Google sign-in to save repositories from Explore and monitor them here."}
            </p>
          </article>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="feed-layout">
        <aside className="subscription-rail">
          <div className="rail-header">
            <p className="section-kicker">Subscriptions</p>
            <h2 className="section-title">My Feed</h2>
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
                    <strong>{subscription.repository.fullName}</strong>
                    <p>{subscription.selectedQuery || subscription.repository.source}</p>
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
              <p className="section-kicker">Selected subscription</p>
              <h3 className="section-title">{selectedSubscription.repository.fullName}</h3>

              <div className="detail-panel-block">
                <h4>Repository</h4>
                <SourceBadge
                  href={selectedSubscription.repository.url}
                  source={selectedSubscription.repository.source}
                />
              </div>

              <div className="detail-panel-block">
                <h4>Selected query</h4>
                <p>{selectedSubscription.selectedQuery || "No query snapshot saved."}</p>
              </div>

              <div className="detail-panel-block">
                <h4>Updates</h4>
                <p>Updates for this repository will appear here.</p>
              </div>
            </>
          ) : (
            <>
              <p className="section-kicker">Selected subscription</p>
              <h3 className="section-title">Pick a saved topic</h3>
              <p className="section-copy">Choose a subscription to open its update stream.</p>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
