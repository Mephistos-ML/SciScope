import { useEffect, useId, useRef, useState } from "react";

import dropdownIcon from "../assets/buttons/sciscope-dropdown.svg";

import { FeedUpdateKindBadge } from "./FeedUpdateKindBadge";
import { fetchFeedGroup } from "../lib/api";
import { getSourceLogo } from "../lib/sourceLogos";
import type { FeedGroupDetailPayload, FeedGroupItem } from "../types/api";

type FeedUpdateCardProps = {
  group: FeedGroupItem;
  readPending: boolean;
  onMarkRead: (groupId: string) => void;
};

export function FeedUpdateCard({ group, readPending, onMarkRead }: FeedUpdateCardProps) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState<FeedGroupDetailPayload | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const request = useRef<AbortController | null>(null);
  const detailsId = useId();
  const headingId = useId();
  const logo = getSourceLogo(group.repositorySource);

  useEffect(() => () => {
    requestVersion.current += 1;
    request.current?.abort();
  }, []);

  async function loadCommits(cursor?: string) {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    const version = ++requestVersion.current;
    setPending(true);
    setError(null);
    try {
      const page = await fetchFeedGroup(group.groupId, { cursor, signal: controller.signal });
      if (version !== requestVersion.current) return;
      setDetails((current) => ({ ...page, commits: cursor && current
        ? [...current.commits, ...page.commits.filter((commit) => !current.commits.some((item) => item.eventId === commit.eventId))]
        : page.commits }));
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(failure instanceof Error ? failure.message : "Could not load commits. Please try again.");
      }
    } finally {
      if (version === requestVersion.current) {
        request.current = null;
        setPending(false);
      }
    }
  }

  function toggleCommits() {
    if (open) {
      requestVersion.current += 1;
      request.current?.abort();
      request.current = null;
      setPending(false);
      setOpen(false);
    } else {
      setOpen(true);
      if (!details) void loadCommits();
    }
  }

  const coverage = details ?? group;
  const commitLabel = coverage.commitCount === null ? "Commits" : `Commits (${coverage.commitCount})`;

  return (
    <article aria-labelledby={headingId} className={group.isRead ? "feed-update-card" : "feed-update-card feed-update-card-unread"}>
      <div className="repository-row">
        <div className="repository-main-cell">
          <div className="feed-update-heading">
            <FeedUpdateKindBadge kind={group.kind} />
            <a className="repository-title repository-inline-link" href={group.url} id={headingId} rel="noreferrer" target="_blank">
              {group.title}
            </a>
          </div>
          <p className="repository-description">
            {group.kind === "commits" ? `${group.commitCount} ${group.commitCount === 1 ? "commit" : "commits"} found in this update.` : group.summary || "No release description available."}
          </p>
        </div>
        <div className="repository-cell" data-label="Repository">
          <span className="repository-provider-link">
            {logo ? <img alt="" aria-hidden="true" src={logo} /> : null}
            <a className="repository-inline-link" href={group.repositoryUrl} rel="noreferrer" target="_blank">{group.repositoryFullName}</a>
          </span>
        </div>
        <div className="repository-cell repository-metadata-cell" data-label="When">
          <span className="repository-muted-value">{formatActivityDate(group.publishedAt)}</span>
        </div>
        <div className="repository-cell repository-metadata-cell" data-label="State">
          {group.isRead ? <span className="repository-muted-value">Read</span> : (
            <button aria-label={`Mark ${group.title} read`} className="feed-read-button" disabled={readPending} onClick={() => onMarkRead(group.groupId)} type="button">Mark read</button>
          )}
        </div>
      </div>
      <div className="feed-commits-disclosure">
        <button aria-controls={detailsId} aria-expanded={open} aria-label={commitLabel} className="feed-commits-toggle" onClick={toggleCommits} type="button">
          <img alt="" aria-hidden="true" className="feed-commits-chevron" src={dropdownIcon} />
          <span>Commits</span>
          {coverage.commitCount !== null ? <span aria-hidden="true" className="results-count-badge feed-commit-count">{coverage.commitCount}</span> : null}
        </button>
        <div aria-label={`Commits for ${group.title}`} className="feed-commit-details" hidden={!open} id={detailsId} role="region">
          {open ? <>
            {coverage.commitDetailsStatus === "unavailable" ? (
              <p className="feed-coverage-message">Commit details are unavailable. View the release on {group.repositorySource === "gitlab" ? "GitLab" : "GitHub"} for more information.</p>
            ) : coverage.commitDetailsStatus === "partial" ? (
              <p className="feed-coverage-message">{coverage.totalCommitCount === null
                ? "Only some commits are available for this release."
                : `${coverage.commitCount} of ${coverage.totalCommitCount} commits available for this release.`} View the release for the full context.</p>
            ) : null}
            {details?.commits.length ? (
              <ul className="feed-commit-list">
                {details.commits.map((commit) => (
                  <li key={commit.eventId}>
                    <div className="feed-commit-heading">
                      <a className="repository-inline-link feed-commit-link" href={commit.url} rel="noreferrer" target="_blank">
                        <svg aria-hidden="true" className="feed-commit-icon" fill="none" focusable="false" viewBox="0 0 16 16">
                          <path d="M1.5 8H4.5M11.5 8H14.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
                          <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                        </svg>
                        <span>{commit.title}</span>
                      </a>
                      <time dateTime={commit.publishedAt ?? undefined}>{formatActivityDate(commit.publishedAt)}</time>
                    </div>
                  </li>
                ))}
              </ul>
            ) : details && coverage.commitDetailsStatus === "complete" ? <p>{group.kind === "release" ? "No commits in this release comparison." : "No retained commits for this update."}</p> : null}
            {pending ? <p role="status">Loading commits…</p> : null}
            {error ? (
              <div className="feed-commit-error">
                <p role="alert">{error}</p>
                <button className="outline-button" disabled={pending} onClick={() => void loadCommits(details?.nextCursor ?? undefined)} type="button">Retry commits</button>
              </div>
            ) : details?.hasMore ? (
              <button className="outline-button" disabled={pending} onClick={() => void loadCommits(details.nextCursor ?? undefined)} type="button">Load more commits</button>
            ) : null}
          </> : null}
        </div>
      </div>
    </article>
  );
}

function formatActivityDate(value: string | null): string {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric", hour: "2-digit", minute: "2-digit", month: "short", year: "numeric",
  }).format(date);
}
