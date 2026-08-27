import { SourceBadge } from "../components/SourceBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import feedNoUpdatesIllustration from "../assets/states/feed/feed-no-updates.svg";
import type { SubscriptionItem, ViewerPayload } from "../types/api";

type SubscriptionsPageProps = {
  deletePending: boolean;
  selectedSubscriptionId: string | null;
  subscriptions: SubscriptionItem[];
  viewer: ViewerPayload["user"];
  onDeleteSubscription: (subscriptionId: string) => void;
  onSelectSubscription: (subscriptionId: string) => void;
};

export function SubscriptionsPage({
  deletePending,
  selectedSubscriptionId,
  subscriptions,
  viewer,
  onDeleteSubscription,
  onSelectSubscription,
}: SubscriptionsPageProps) {
  const selectedSubscription =
    subscriptions.find((item) => item.subscriptionId === selectedSubscriptionId) ?? null;
  const hasSubscriptions = subscriptions.length > 0;

  return (
    <main className="app-shell feed-shell">
      <section className="page-intro">
        <div className="page-intro-main">
          <h1 className="page-title">My Subscriptions</h1>
          <p className="section-copy">
            Review the repositories you chose in Explore and manage ongoing monitoring.
          </p>
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
              {viewer ? "No Subscriptions Yet" : "Sign In to Manage Subscriptions"}
            </h2>
            <p className="empty-state-copy">
              {viewer
                ? "Save repositories from Explore and they will appear here for ongoing monitoring."
                : "Use Google sign-in to save repositories from Explore and manage them here."}
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
                      {subscription.repository.source} · Subscribed{" "}
                      {formatSubscriptionDate(subscription.createdAt)}
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
                  This subscription keeps the repository under monitoring and its future events in your feed.
                </p>

                <div className="detail-panel-block">
                  <h4>Repository</h4>
                  <SourceBadge
                    href={selectedSubscription.repository.url}
                    source={selectedSubscription.repository.source}
                  />
                </div>

                <div className="detail-panel-block">
                  <h4>Subscribed</h4>
                  <p className="detail-copy">
                    {formatSubscriptionDate(selectedSubscription.createdAt)}
                  </p>
                </div>

                <div className="detail-panel-block">
                  <h4>Selected Query</h4>
                  <p className="detail-copy">
                    {selectedSubscription.selectedQuery || "No Query Snapshot Saved."}
                  </p>
                </div>

                <div className="detail-panel-block">
                  <h4>Feed Behavior</h4>
                  <div className="feed-updates-placeholder">
                    <img
                      alt=""
                      aria-hidden="true"
                      className="empty-state-illustration feed-updates-illustration"
                      src={feedNoUpdatesIllustration}
                    />
                    <div className="feed-updates-copy">
                      <p className="empty-state-title">Feed Events Persist</p>
                      <p className="detail-copy">
                        Releases and default-branch commits found after subscription are added to Feed and stay there.
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
                  Choose a subscription from the rail to inspect its monitoring context.
                </p>
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  );
}

function formatSubscriptionDate(value: string): string {
  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsedDate);
}
