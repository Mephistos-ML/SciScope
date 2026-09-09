import { useState } from "react";

import { SourceBadge } from "../components/SourceBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import type { FeedEventItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  feedUpdatePending: boolean;
  feedEvents: FeedEventItem[];
  onMarkAllRead: () => void;
  onMarkRead: (eventId: string) => void;
  viewer: ViewerPayload["user"];
};

export function FeedPage({
  feedUpdatePending,
  feedEvents,
  onMarkAllRead,
  onMarkRead,
  viewer,
}: FeedPageProps) {
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const hasEvents = feedEvents.length > 0;
  const unreadCount = feedEvents.filter((event) => event.readAt === null).length;
  const visibleEvents = showUnreadOnly
    ? feedEvents.filter((event) => event.readAt === null)
    : feedEvents;

  return (
    <main className="app-shell feed-shell">
      <section className="page-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Feed</h1>
          <p className="section-copy">
            Repository updates collected after you subscribed, across releases and default-branch commits.
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
      ) : !hasEvents ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">No Feed Events Yet</h2>
            <p className="empty-state-copy">
              New releases and default-branch commits from your subscribed repositories will appear here.
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
                  <h3 className="panel-title">Recent Repository Events</h3>
                  <span className="results-count-badge">{visibleEvents.length} events</span>
                </div>
              </div>
              <div className="feed-actions">
                <div aria-label="Feed visibility" className="feed-filter" role="group">
                  <button
                    className={showUnreadOnly ? "feed-filter-button" : "feed-filter-button feed-filter-button-active"}
                    onClick={() => setShowUnreadOnly(false)}
                    type="button"
                  >
                    All
                  </button>
                  <button
                    className={showUnreadOnly ? "feed-filter-button feed-filter-button-active" : "feed-filter-button"}
                    onClick={() => setShowUnreadOnly(true)}
                    type="button"
                  >
                    Unread {unreadCount > 0 ? `(${unreadCount})` : ""}
                  </button>
                </div>
                <button
                  className="outline-button"
                  disabled={feedUpdatePending || unreadCount === 0}
                  onClick={onMarkAllRead}
                  type="button"
                >
                  Mark all read
                </button>
              </div>
            </div>

            <div className="repository-table feed-repository-table">
              <div className="repository-table-head">
                <span>Event</span>
                <span>Repository</span>
                <span>Source</span>
                <span>Type</span>
                <span>When</span>
                <span>State</span>
              </div>

              <div className="repository-table-body">
                {visibleEvents.map((event) => (
                  <div
                    className={event.readAt === null ? "repository-row repository-row-unread" : "repository-row"}
                    key={event.eventId}
                  >
                    <div className="repository-main-cell">
                      <p className="repository-title">{event.title}</p>
                      <p className="repository-description">
                        {event.summary || "No event summary available."}
                      </p>
                    </div>

                    <div className="repository-cell" data-label="Repository">
                      <a
                        className="repository-inline-link"
                        href={event.repositoryUrl}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {event.repositoryFullName}
                      </a>
                    </div>

                    <div className="repository-cell" data-label="Source">
                      <SourceBadge href={event.url} source={event.source} />
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="Type">
                      <span className="repository-muted-value">
                        {formatSignalKind(event.signalKind)}
                      </span>
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="When">
                      <span className="repository-muted-value">
                        {formatEventDate(event.publishedAt || event.createdAt)}
                      </span>
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="State">
                      {event.readAt === null ? (
                        <button
                          className="feed-read-button"
                          disabled={feedUpdatePending}
                          onClick={() => onMarkRead(event.eventId)}
                          type="button"
                        >
                          Mark read
                        </button>
                      ) : (
                        <span className="repository-muted-value">Read</span>
                      )}
                    </div>
                  </div>
                ))}
                {visibleEvents.length === 0 ? (
                  <div className="feed-filter-empty">No unread Feed events.</div>
                ) : null}
              </div>
            </div>
          </article>
        </section>
      )}
    </main>
  );
}

function formatSignalKind(value: string): string {
  if (value === "release") {
    return "Release";
  }
  if (value === "commit") {
    return "Commit";
  }
  return value;
}

function formatEventDate(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

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
