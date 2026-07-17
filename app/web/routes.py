"""Minimal local dashboard routes for SciScope V0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import threading
import time
from typing import Callable

from app.config import AUTO_SCAN_INTERVAL_SECONDS
from app.models.signal import RawSignal
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.services.profile_builder import PNMR_PROFILE, PNMR_TOPIC
from app.sources.replay import load_replay_signals
from app.storage.seen_signals import load_seen_signal_ids, upsert_raw_signals


@dataclass(frozen=True)
class SignalView:
    """Dashboard-friendly signal projection."""

    item_id: str
    title: str
    source: str
    signal_kind: str
    url: str
    matched: bool
    score: float
    reason: str
    matched_terms: tuple[str, ...]
    excluded_terms: tuple[str, ...]
    raw_text: str
    normalized_text: str
    metadata: dict[str, object]
    is_new: bool


SIGNALS: dict[str, SignalView] = {}
LAST_SCAN_AT: datetime | None = None
LAST_SCAN_ERROR: str | None = None
AUTO_SCAN_STARTED = False
AUTO_SCAN_THREAD: threading.Thread | None = None
SCAN_LOCK = threading.Lock()


def application(environ: dict, start_response: Callable) -> list[bytes]:
    """WSGI entrypoint for the local SciScope dashboard."""

    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/":
        return _html_response(start_response, render_dashboard())

    if method == "POST" and path == "/start":
        _start_auto_scan_loop()
        return _redirect_response(start_response, "/")

    if method == "GET" and path.startswith("/signals/"):
        item_id = path.removeprefix("/signals/")
        return _html_response(start_response, render_signal_detail(item_id))

    if method == "GET" and path == "/health":
        return _plain_response(start_response, "ok")

    return _not_found_response(start_response)


def render_dashboard() -> str:
    """Render the dashboard page."""

    last_scan = LAST_SCAN_AT.isoformat(timespec="seconds") if LAST_SCAN_AT else "Never"
    total_signals = len(SIGNALS)
    matched_signals = sum(1 for signal in SIGNALS.values() if signal.matched)
    auto_scan_status = "running" if AUTO_SCAN_STARTED else "idle"
    error_html = (
        f'<p style="color:#8a1c1c;"><strong>Scan warning:</strong> {escape(LAST_SCAN_ERROR)}</p>'
        if LAST_SCAN_ERROR
        else ""
    )

    rows = []
    for signal in sorted(SIGNALS.values(), key=lambda item: (-item.score, item.item_id)):
        badge = "matched" if signal.matched else "not-matched"
        new_badge = '<span class="badge new">new</span>' if signal.is_new else ""
        rows.append(
            f"""
            <tr>
              <td><a href="/signals/{escape(signal.item_id)}">{escape(signal.title)}</a></td>
              <td>{escape(signal.source)}</td>
              <td>{escape(signal.signal_kind)}</td>
              <td>{signal.score:.1f}</td>
              <td><span class="badge {badge}">{'matched' if signal.matched else 'not matched'}</span> {new_badge}</td>
              <td>{escape(signal.reason)}</td>
            </tr>
            """
        )

    rows_html = "\n".join(rows) or (
        '<tr><td colspan="6">No signals yet. Click <strong>Start</strong>.</td></tr>'
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>SciScope Dashboard</title>
    <style>
      body {{ font-family: sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; }}
      .header {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; }}
      .meta {{ display: flex; gap: 1rem; margin: 1rem 0 2rem; flex-wrap: wrap; }}
      .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; min-width: 180px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border-bottom: 1px solid #eee; padding: 0.75rem; text-align: left; vertical-align: top; }}
      .badge {{ display: inline-block; border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.85rem; }}
      .matched {{ background: #dff3e4; color: #116329; }}
      .not-matched {{ background: #f8e0e0; color: #8a1c1c; }}
      .new {{ background: #e3edff; color: #1e4db7; }}
      button {{ padding: 0.7rem 1rem; border: 1px solid #111; background: #111; color: white; border-radius: 6px; cursor: pointer; }}
      a {{ color: #0b57d0; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <div class="header">
      <div>
        <h1>SciScope</h1>
        <p>{escape(PNMR_TOPIC.label)} local dashboard</p>
      </div>
      <form method="post" action="/start">
        <button type="submit">Start</button>
      </form>
    </div>
    <div class="meta">
      <div class="card"><strong>Last scan</strong><br>{escape(last_scan)}</div>
      <div class="card"><strong>Total signals</strong><br>{total_signals}</div>
      <div class="card"><strong>Matched signals</strong><br>{matched_signals}</div>
      <div class="card"><strong>Topic</strong><br>{escape(PNMR_PROFILE.topic_slug)}</div>
      <div class="card"><strong>Auto-scan</strong><br>{escape(auto_scan_status)}</div>
      <div class="card"><strong>Interval</strong><br>{AUTO_SCAN_INTERVAL_SECONDS}s</div>
    </div>
    {error_html}
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Source</th>
          <th>Kind</th>
          <th>Score</th>
          <th>Match</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </body>
</html>"""


def render_signal_detail(item_id: str) -> str:
    """Render one signal detail page."""

    signal = SIGNALS.get(item_id)
    if signal is None:
        return """<!doctype html><html><body><h1>Signal not found</h1><p><a href="/">Back</a></p></body></html>"""

    metadata_rows = "\n".join(
        f"<li><strong>{escape(str(key))}</strong>: {escape(str(value))}</li>"
        for key, value in signal.metadata.items()
    )
    matched_terms = ", ".join(signal.matched_terms) or "<none>"
    excluded_terms = ", ".join(signal.excluded_terms) or "<none>"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{escape(signal.title)} - SciScope</title>
    <style>
      body {{ font-family: sans-serif; margin: 2rem auto; max-width: 1000px; padding: 0 1rem; }}
      .badge {{ display: inline-block; border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.85rem; }}
      .matched {{ background: #dff3e4; color: #116329; }}
      .not-matched {{ background: #f8e0e0; color: #8a1c1c; }}
      pre {{ white-space: pre-wrap; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; background: #fafafa; }}
      a {{ color: #0b57d0; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <p><a href="/">Back to dashboard</a></p>
    <h1>{escape(signal.title)}</h1>
    <p>
      <strong>Source:</strong> {escape(signal.source)}<br>
      <strong>Kind:</strong> {escape(signal.signal_kind)}<br>
      <strong>Score:</strong> {signal.score:.1f}<br>
      <strong>New:</strong> {'yes' if signal.is_new else 'no'}<br>
      <strong>Match:</strong>
      <span class="badge {'matched' if signal.matched else 'not-matched'}">
        {'matched' if signal.matched else 'not matched'}
      </span>
    </p>
    <p><strong>Reason:</strong> {escape(signal.reason)}</p>
    <p><strong>Matched terms:</strong> {escape(matched_terms)}</p>
    <p><strong>Excluded terms:</strong> {escape(excluded_terms)}</p>
    <p><strong>URL:</strong> <a href="{escape(signal.url)}">{escape(signal.url)}</a></p>
    <h2>Metadata</h2>
    <ul>{metadata_rows}</ul>
    <h2>Raw Text</h2>
    <pre>{escape(signal.raw_text)}</pre>
    <h2>Normalized Text</h2>
    <pre>{escape(signal.normalized_text)}</pre>
  </body>
</html>"""


def _scan_seed_signals() -> None:
    """Populate the dashboard with the current seeded evaluation signals."""

    global LAST_SCAN_AT, LAST_SCAN_ERROR
    with SCAN_LOCK:
        _scan_seed_signals_unlocked()


def _scan_seed_signals_unlocked() -> None:
    """Populate the dashboard with the current seeded evaluation signals."""

    global LAST_SCAN_AT, LAST_SCAN_ERROR

    signals = []
    LAST_SCAN_ERROR = None

    try:
        replay_signals = load_replay_signals()
        signals.extend(_build_signal_view(raw_signal) for raw_signal in replay_signals)
    except Exception as exc:
        LAST_SCAN_ERROR = f"Replay fixtures failed to load: {exc}"

    SIGNALS.clear()
    signal_views: dict[str, SignalView] = {}
    raw_signals_to_store: list[RawSignal] = []
    for signal in signals:
        seen_ids = load_seen_signal_ids(signal.source)
        signal_views[signal.item_id] = SignalView(
            item_id=signal.item_id,
            title=signal.title,
            source=signal.source,
            signal_kind=signal.signal_kind,
            url=signal.url,
            matched=signal.matched,
            score=signal.score,
            reason=signal.reason,
            matched_terms=signal.matched_terms,
            excluded_terms=signal.excluded_terms,
            raw_text=signal.raw_text,
            normalized_text=signal.normalized_text,
            metadata=signal.metadata,
            is_new=signal.item_id not in seen_ids,
        )
        raw_signals_to_store.append(
            RawSignal(
                source=signal.source,
                source_type=str(signal.metadata.get("source_type", signal.signal_kind)),
                item_id=signal.item_id,
                title=signal.title,
                url=signal.url,
                published_at=None,
                raw_text=signal.raw_text,
                payload=signal.metadata,
            )
        )

    SIGNALS.update(signal_views)
    upsert_raw_signals(
        raw_signals_to_store
    )

    LAST_SCAN_AT = datetime.now(UTC)


def _start_auto_scan_loop() -> None:
    """Start the background auto-scan loop and run one immediate scan."""

    global AUTO_SCAN_STARTED, AUTO_SCAN_THREAD

    if not AUTO_SCAN_STARTED:
        AUTO_SCAN_STARTED = True
        AUTO_SCAN_THREAD = threading.Thread(
            target=_auto_scan_loop,
            name="sciscope-auto-scan",
            daemon=True,
        )
        AUTO_SCAN_THREAD.start()

    _scan_seed_signals()


def _auto_scan_loop() -> None:
    """Background loop that runs scans on a fixed interval."""

    while True:
        time.sleep(AUTO_SCAN_INTERVAL_SECONDS)
        _scan_seed_signals()


def _build_signal_view(raw_signal: RawSignal) -> SignalView:
    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, PNMR_PROFILE)

    return SignalView(
        item_id=normalized_signal.item_id,
        title=normalized_signal.title,
        source=normalized_signal.source,
        signal_kind=normalized_signal.signal_kind,
        url=normalized_signal.url,
        matched=match.matched,
        score=match.score,
        reason=match.reason,
        matched_terms=match.matched_terms,
        excluded_terms=match.excluded_terms,
        raw_text=raw_signal.raw_text,
        normalized_text=normalized_signal.normalized_text,
        metadata=normalized_signal.metadata,
        is_new=False,
    )


def _html_response(start_response: Callable, body: str) -> list[bytes]:
    data = body.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(data))),
        ],
    )
    return [data]


def _plain_response(start_response: Callable, body: str) -> list[bytes]:
    data = body.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(data))),
        ],
    )
    return [data]


def _redirect_response(start_response: Callable, location: str) -> list[bytes]:
    start_response("303 See Other", [("Location", location)])
    return [b""]


def _not_found_response(start_response: Callable) -> list[bytes]:
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not Found"]
