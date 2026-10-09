import { FeedUpdateCard } from "../components/FeedUpdateCard";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import type { FeedGroupItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  feedHasMore: boolean;
  feedLoadPending: boolean;
  feedState: "all" | "unread";
  feedSubscriptionId: string | null;
  unreadFeedCount: number;
  feedUpdatePending: boolean;
  feedGroups: FeedGroupItem[];
  onLoadOlder: () => void;
  onMarkAllRead: () => void;
  onMarkRead: (groupId: string) => void;
  onStateChange: (state: "all" | "unread") => void;
  viewer: ViewerPayload["user"];
};

export function FeedPage({
  feedUpdatePending,
  feedHasMore,
  feedLoadPending,
  feedState,
  feedSubscriptionId,
  unreadFeedCount,
  feedGroups,
  onLoadOlder,
  onMarkAllRead,
  onMarkRead,
  onStateChange,
  viewer,
}: FeedPageProps) {
  const hasUpdates = feedGroups.length > 0;

  return (
    <main className="app-shell feed-shell">
      <section className="page-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Feed</h1>
          <p className="section-copy">
            Releases and grouped commits from your subscribed repositories.
          </p>
        </div>
      </section>

      {!viewer ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">Sign In to View Your Feed</h2>
            <p className="empty-state-copy">
              Use Google sign-in to save repositories from Explore and keep their updates here.
            </p>
          </article>
        </section>
      ) : !hasUpdates && !feedLoadPending && feedState === "all" ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">No Updates Yet</h2>
            <p className="empty-state-copy">
              New releases and groups of commits from your subscribed repositories will appear here.
            </p>
          </article>
        </section>
      ) : (
        <section className="results-panel">
          <article className="info-panel repository-results-panel">
            <div className="results-header">
              <div className="results-header-main">
                <p className="section-kicker">Feed</p>
                <div className="results-title-row">
                  <h3 className="panel-title">{feedSubscriptionId ? "Repository Updates" : "Recent Repository Updates"}</h3>
                  <span className="results-count-badge">{feedGroups.length} updates</span>
                </div>
              </div>
              <div className="feed-actions">
                <div aria-label="Feed visibility" className="feed-filter" role="group">
                  <button
                    aria-pressed={feedState === "all"}
                    className={feedState === "all" ? "feed-filter-button feed-filter-button-active" : "feed-filter-button"}
                    disabled={feedLoadPending || feedUpdatePending}
                    onClick={() => onStateChange("all")}
                    type="button"
                  >
                    All
                  </button>
                  <button
                    aria-pressed={feedState === "unread"}
                    className={feedState === "unread" ? "feed-filter-button feed-filter-button-active" : "feed-filter-button"}
                    disabled={feedLoadPending || feedUpdatePending}
                    onClick={() => onStateChange("unread")}
                    type="button"
                  >
                    Unread {unreadFeedCount > 0 ? `(${unreadFeedCount})` : ""}
                  </button>
                </div>
                <button
                  className="outline-button"
                  disabled={feedUpdatePending || feedLoadPending || unreadFeedCount === 0}
                  onClick={onMarkAllRead}
                  type="button"
                >
                  Mark all read
                </button>
              </div>
            </div>

            <div className="repository-table feed-repository-table">
              <div className="repository-table-head">
                <span>Update</span>
                <span>Repository</span>
                <span>When</span>
                <span>State</span>
              </div>

              <div className="repository-table-body">
                {feedGroups.map((group) => (
                  <FeedUpdateCard group={group} key={group.groupId} onMarkRead={onMarkRead} readPending={feedUpdatePending || feedLoadPending} />
                ))}
                {feedLoadPending ? <p className="feed-filter-empty" role="status">Loading updates…</p> : null}
                {feedGroups.length === 0 && !feedLoadPending ? (
                  <div className="feed-filter-empty">No unread updates.</div>
                ) : null}
                {feedHasMore ? (
                  <div className="feed-load-more">
                    <button
                      className="outline-button"
                      disabled={feedLoadPending || feedUpdatePending}
                      onClick={onLoadOlder}
                      type="button"
                    >
                      {feedLoadPending ? "Loading…" : "Load older updates"}
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </article>
        </section>
      )}
    </main>
  );
}
