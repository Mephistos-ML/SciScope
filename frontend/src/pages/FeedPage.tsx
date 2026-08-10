import type { AuthMode } from "../lib/config";
import type { SubscriptionItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  authMode: AuthMode;
  deletePending: boolean;
  selectedSubscriptionId: string | null;
  subscriptions: SubscriptionItem[];
  viewer: ViewerPayload["user"];
  onDeleteSubscription: (subscriptionId: string) => void;
  onSelectSubscription: (subscriptionId: string) => void;
};

export function FeedPage({
  authMode,
  deletePending,
  selectedSubscriptionId,
  subscriptions,
  viewer,
  onDeleteSubscription,
  onSelectSubscription,
}: FeedPageProps) {
  const selectedSubscription =
    subscriptions.find((item) => item.subscriptionId === selectedSubscriptionId) ?? null;

  if (!viewer) {
    return (
      <main className="app-shell">
        <section className="hero-panel">
          <div className="hero-copy-block">
            <p className="section-kicker">My Feed</p>
            <h2 className="section-title">Sign in to save topics and follow updates.</h2>
            <p className="section-copy">
              {authMode === "dev"
                ? "Your saved topics appear here as subscriptions with their own update streams."
                : "Authentication is disabled in this environment, so this feed stays locked until the real sign-in flow is added."}
            </p>
          </div>
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
            {subscriptions.length > 0 ? (
              subscriptions.map((subscription) => (
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
                    <strong>{subscription.topicDescription}</strong>
                    <p>{subscription.manualQueries.join(", ") || "No manual queries yet"}</p>
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
              ))
            ) : (
              <p className="empty-copy">No subscriptions yet. Save one from Explore first.</p>
            )}
          </div>
        </aside>

        <section className="subscription-detail">
          {selectedSubscription ? (
            <>
              <p className="section-kicker">Selected subscription</p>
              <h3 className="section-title">{selectedSubscription.topicDescription}</h3>

              <div className="detail-panel-block">
                <h4>Queries</h4>
                <p>{selectedSubscription.manualQueries.join(", ") || "No manual queries yet"}</p>
              </div>

              <div className="detail-panel-block">
                <h4>Updates</h4>
                <p>Updates for this topic will appear here.</p>
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
