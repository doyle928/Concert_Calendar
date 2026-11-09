"""Which venues you care about, and how to fold sub-rooms into the main venue.

Each key is the name you want to see. Each value is a list of lowercase
fragments; if any fragment appears in the scraped venue name, the show counts
as that venue. This is how "Elevation at The Intersection" and "Stache at The
Intersection" both become "The Intersection".
"""

WANTED_VENUES = {
    "Elektricity": ["elektricity"],
    "Detroit Masonic Temple": ["detroit masonic temple"],
    "Russell Industrial Center": ["russell industrial center"],
    "Royal Oak Theatre": ["royal oak theatre"],
    "The Intersection": ["intersection"],
    "Majestic Theatre Detroit": ["majestic theatre"],
    "Crofoot Ballroom": ["crofoot"],  # also catches "Pike Room at Crofoot"
}


def canonical_venue(raw_venue: str) -> str | None:
    """Return the main venue name if raw_venue is one you want, else None."""
    lowered = raw_venue.lower()
    for name, fragments in WANTED_VENUES.items():
        if any(fragment in lowered for fragment in fragments):
            return name
    return None


def filter_events(events: list[dict]) -> list[dict]:
    """Keep only wanted venues, renaming rooms to the main venue.

    The original name is kept as `venue_detail` when it differs, so you can
    still see which room the show is in.
    """
    kept = []
    for e in events:
        main = canonical_venue(e["venue"])
        if main is None:
            continue
        item = dict(e)
        item["venue"] = main
        item["venue_detail"] = e["venue"] if e["venue"] != main else ""
        kept.append(item)
    return kept