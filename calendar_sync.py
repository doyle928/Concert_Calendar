"""Sync data/my_events.json to a Google Calendar as all-day events.

Env vars (not needed for --dry-run):
  GOOGLE_SERVICE_ACCOUNT_JSON  - the full contents of the service account key file
  GOOGLE_CALENDAR_ID           - the calendar's ID (Calendar settings -> Integrate calendar)

Usage:
  python calendar_sync.py --dry-run   # print what would happen, touch nothing
  python calendar_sync.py             # create / update events

Each show gets a fixed calendar event ID built from its Edmtrain event ID, so
running this every day updates existing events instead of creating copies.
Events you delete from your calendar are left deleted.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

EVENTS_FILE = Path("data/my_events.json")


def infer_date(date_str: str, today: date) -> date | None:
    weekday, rest = [part.strip() for part in date_str.split(",", 1)]
    for year in (today.year, today.year + 1):
        try:
            candidate = datetime.strptime(f"{rest} {year}", "%b %d %Y").date()
        except ValueError:
            continue
        if candidate.strftime("%a") == weekday and candidate >= today - timedelta(days=1):
            return candidate
    return None


def calendar_event_id(event_id: str) -> str:
    # Google requires lowercase a-v and digits; "edmtrain" qualifies.
    return f"edmtrain{event_id}"


def build_body(e: dict, day: date) -> dict:
    lines = [e["artists"]]
    if e.get("venue_detail"):
        lines.append(f'Room: {e["venue_detail"]}')
    if e.get("age"):
        lines.append(f'Age: {e["age"]}')
    lines.append(e["url"])
    return {
        "id": calendar_event_id(e["event_id"]),
        "summary": e["artists"],
        "location": f'{e["venue"]}, {e["city"]}' if e.get("city") else e["venue"],
        "description": "\n".join(lines),
        "start": {"date": day.isoformat()},
        "end": {"date": (day + timedelta(days=1)).isoformat()},  # all-day end is exclusive
        "status": "confirmed",
    }


def differs(existing: dict, body: dict) -> bool:
    return any(
        existing.get(k) != body[k]
        for k in ("summary", "location", "description")
    ) or existing.get("start", {}).get("date") != body["start"]["date"]


def get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    today = date.fromisoformat(os.environ["TODAY"]) if os.environ.get("TODAY") else date.today()

    if not EVENTS_FILE.exists():
        print(f"{EVENTS_FILE} not found. Run scrape.py first.", file=sys.stderr)
        return 1
    events = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))

    planned = []
    for e in events:
        day = infer_date(e["date"], today)
        if day is None:
            if e["date"]:
                print(f'Skipping "{e["artists"]}": could not work out the date from "{e["date"]}"', file=sys.stderr)
            continue
        planned.append((e, day, build_body(e, day)))

    if dry_run:
        for e, day, body in planned:
            print(f'{day.isoformat()}  {body["summary"]}  @ {body["location"]}  [{body["id"]}]')
        print(f"\nDRY RUN: {len(planned)} events would be synced. Nothing was changed.")
        return 0

    from googleapiclient.errors import HttpError

    service = get_service()
    calendar_id = os.environ["GOOGLE_CALENDAR_ID"]
    created = updated = unchanged = skipped_deleted = 0

    for e, day, body in planned:
        try:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            created += 1
            continue
        except HttpError as err:
            if err.resp.status != 409:  # 409 = this event ID already exists
                raise

        existing = service.events().get(calendarId=calendar_id, eventId=body["id"]).execute()
        if existing.get("status") == "cancelled":
            skipped_deleted += 1  # you deleted it; leave it deleted
        elif differs(existing, body):
            service.events().update(calendarId=calendar_id, eventId=body["id"], body=body).execute()
            updated += 1
        else:
            unchanged += 1

    print(
        f"Calendar sync: {created} created, {updated} updated, "
        f"{unchanged} unchanged, {skipped_deleted} skipped (deleted by you)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())