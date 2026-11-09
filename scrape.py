"""Daily scraper: loads a JavaScript-rendered page via Firecrawl with a cookie
attached, saves the result, and reports whether it changed since last run.

Required env vars:
  FIRECRAWL_API_KEY  - your Firecrawl API key
Optional:
  SITE_COOKIE        - full Cookie header value, e.g. "session=abc123; region=us"
  TARGET_URL         - overrides the URL below
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from firecrawl import Firecrawl

from parse_events import format_event, parse_events
from venues import filter_events

load_dotenv()  # reads .env locally; does nothing on GitHub Actions

# ---- Edit these ----------------------------------------------------------
TARGET_URL = os.environ.get("TARGET_URL", "https://example.com/page")
WAIT_MS = 3000  # extra time for JavaScript content to load before capture

# Optional page interactions, run in order before capture. Uncomment as needed.
ACTIONS = [
    # {"type": "wait", "milliseconds": 2000},
    # {"type": "click", "selector": "#load-more"},
    # {"type": "scroll", "direction": "down"},
]
# --------------------------------------------------------------------------

OUT_DIR = Path("data")
LATEST = OUT_DIR / "latest.md"
STATE = OUT_DIR / "state.json"


def field(doc, name):
    """Read a field whether the SDK returns an object or a dict."""
    if isinstance(doc, dict):
        return doc.get(name)
    return getattr(doc, name, None)


def main() -> int:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    cookie = os.environ.get("SITE_COOKIE")
    if not api_key:
        print("Missing FIRECRAWL_API_KEY", file=sys.stderr)
        return 1

    app = Firecrawl(api_key=api_key)

    kwargs = {
        "formats": ["markdown"],
        "wait_for": WAIT_MS,
        "only_main_content": False,  # keep the full page, not just the "main" block
    }
    if cookie:  # optional: only sent if SITE_COOKIE is set
        kwargs["headers"] = {"Cookie": cookie}
    if ACTIONS:
        kwargs["actions"] = ACTIONS

    doc = app.scrape(TARGET_URL, **kwargs)
    markdown = field(doc, "markdown")

    if not markdown or not markdown.strip():
        print("Scrape returned no content. The cookie may have expired.", file=sys.stderr)
        return 1

    new_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    OUT_DIR.mkdir(exist_ok=True)
    old_hash = None
    if STATE.exists():
        old_hash = json.loads(STATE.read_text()).get("hash")

    changed = new_hash != old_hash
    if changed:
        LATEST.write_text(markdown, encoding="utf-8")
        STATE.write_text(
            json.dumps(
                {"hash": new_hash, "updated": datetime.now(timezone.utc).isoformat()},
                indent=2,
            )
        )

    print("CHANGED" if changed else "NO CHANGE")

    events = parse_events(markdown)
    (OUT_DIR / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

    mine = filter_events(events)
    (OUT_DIR / "my_events.json").write_text(json.dumps(mine, indent=2), encoding="utf-8")
    for e in mine:
        print(format_event(e))
    print(f"{len(events)} events parsed, {len(mine)} at your venues")
    if not events:
        print("Parsed 0 events. The page layout may have changed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())