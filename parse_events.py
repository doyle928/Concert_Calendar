"""Turn the scraped Edmtrain markdown into a list of events.

Each event is a dict: date, artists, venue, city, url, event_id.
Run directly to parse data/latest.md and print one line per event.
"""

import json
import re
import sys
from pathlib import Path

# A date header line such as "Fri, Nov 13" (tolerates leading #, quotes, spaces)
DATE_RE = r"^\W*(?P<date>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), [A-Z][a-z]{2} \d{1,2})\s*$"

# An event card: [![](image) ...text... ](https://edmtrain.com/<city>/<slug>-<id>)
# - the text between may not contain "](" so a match can never swallow a
#   neighbouring link
# - "/tours/" links (artist pages) are excluded
EVENT_RE = (
    r"\[!\[\]\([^)]*\)"
    r"(?P<inner>(?:(?!\]\().)*?)"
    r"\]\((?P<url>https://edmtrain\.com/(?!tours/|news/)[^/)\s]+/[^)\s]+?-(?P<id>\d+))\)"
)

# "Venue Name - City, ST" with an optional glued-on age limit, e.g. "...MI18+"
VENUE_LINE_RE = re.compile(
    r"^(?P<venue>.+) - (?P<city>[^,]+, [A-Z]{2})(?P<age>\d{1,2}\+|All Ages)?$"
)

TOKEN_RE = re.compile(f"(?:{DATE_RE})|(?:{EVENT_RE})", re.MULTILINE | re.DOTALL)


def clean_lines(inner: str) -> list[str]:
    """Strip markdown line-break backslashes and blank lines."""
    lines = [
        line.replace("\\", "").replace("\u00a0", " ").strip()
        for line in inner.splitlines()
    ]
    return [line for line in lines if line]


def parse_events(markdown: str) -> list[dict]:
    events = []
    seen_ids = set()
    current_date = None

    for m in TOKEN_RE.finditer(markdown):
        if m.group("date"):
            current_date = m.group("date")
            continue

        # The top of the page has a compact "featured" strip with its own
        # card layout (no city, date inside the card). Every one of those
        # events also appears under its date header further down, so we only
        # read cards that come after the first date header.
        if current_date is None:
            continue

        # Safety net: never emit the same event twice
        if m.group("id") in seen_ids:
            continue
        seen_ids.add(m.group("id"))

        lines = clean_lines(m.group("inner"))
        if len(lines) < 2:
            continue  # not a real event card

        artists = lines[0]

        # The venue is the line shaped like "Venue - City, ST" (optionally
        # followed by an age limit such as "18+"). Other lines in the card
        # (descriptions, "Added by", "new") are not the venue.
        venue = city = age = ""
        notes = []
        for line in lines[1:]:
            vm = VENUE_LINE_RE.match(line)
            if vm and not venue:
                venue = vm.group("venue").strip()
                city = vm.group("city").strip()
                age = vm.group("age") or ""
            else:
                notes.append(line)

        if not venue:
            print(f"Warning: no venue found for {m.group('url')}", file=sys.stderr)

        events.append(
            {
                "date": current_date,
                "artists": artists,
                "venue": venue,
                "city": city,
                "age": age,
                "url": m.group("url"),
                "event_id": m.group("id"),
            }
        )
    return events


def format_event(e: dict) -> str:
    return f'{e["date"]} / {e["artists"]} / {e["venue"]}'


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/latest.md")
    found = parse_events(path.read_text(encoding="utf-8"))
    for e in found:
        print(format_event(e))
    print(f"\n{len(found)} events", file=sys.stderr)
    Path("data").mkdir(exist_ok=True)
    Path("data/events.json").write_text(json.dumps(found, indent=2), encoding="utf-8")