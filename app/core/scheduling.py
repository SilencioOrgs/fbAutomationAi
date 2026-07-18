"""
Region-based post scheduling with peak-hour targeting.
All region/timezone/peak-hour data comes from config — nothing is hardcoded.
"""

import logging
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo

from db.db import Database
from db.models import Status

logger = logging.getLogger(__name__)


def _parse_time(t: str) -> dt_time:
    """Parse 'HH:MM' into a time object."""
    parts = t.strip().split(":")
    return dt_time(int(parts[0]), int(parts[1]))


def _get_scheduling_config(config: dict) -> dict:
    """Extract the scheduling section from the full config."""
    return config.get("scheduling", {})


def suggest_slot(region: str, db: Database, config: dict) -> datetime:
    """
    Find the next available UTC datetime inside the given region's
    peak-hour windows that satisfies:
      - At least min_interval_minutes from every other queued post (globally)
      - No more than max_posts_per_24h in the rolling 24h window (globally)

    If today's windows are full, advance to the next day.

    Args:
        region: Key into config["scheduling"]["regions"], e.g. "US".
        db:     Database instance.
        config: Full prompt_templates config dict.

    Returns:
        datetime in UTC (timezone-aware).

    Raises:
        ValueError: If region is not in config or no slot found within 7 days.
    """
    sched = _get_scheduling_config(config)
    regions = sched.get("regions", {})
    if region not in regions:
        raise ValueError(
            f"Unknown region '{region}'. Available: {list(regions.keys())}"
        )

    region_cfg = regions[region]
    tz = ZoneInfo(region_cfg["timezone"])
    peak_windows = region_cfg.get("peak_hours_local", [])
    min_interval = timedelta(minutes=sched.get("min_interval_minutes", 120))
    max_per_day = sched.get("max_posts_per_24h", 4)

    now_utc = datetime.now(ZoneInfo("UTC"))
    now_local = now_utc.astimezone(tz)

    # Search up to 7 days ahead
    for day_offset in range(8):
        candidate_date = (now_local + timedelta(days=day_offset)).date()

        for window in peak_windows:
            if len(window) != 2:
                continue
            win_start = _parse_time(window[0])
            win_end = _parse_time(window[1])

            # Build the candidate start time in local tz
            local_start = datetime.combine(candidate_date, win_start, tzinfo=tz)
            local_end = datetime.combine(candidate_date, win_end, tzinfo=tz)

            # If this window is already past for today, skip it
            if local_end <= now_local and day_offset == 0:
                continue

            # Start from now if we're inside the window today
            if day_offset == 0 and local_start < now_local < local_end:
                # Round up to next minute
                candidate_local = now_local.replace(second=0, microsecond=0) + timedelta(minutes=1)
            elif local_start <= now_local and day_offset == 0:
                continue
            else:
                candidate_local = local_start

            # Try every minute within this window
            while candidate_local < local_end:
                candidate_utc = candidate_local.astimezone(ZoneInfo("UTC"))

                # Check rolling 24h global cap
                window_start_str = (candidate_utc - timedelta(hours=24)).strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
                window_end_str = candidate_utc.strftime("%Y-%m-%dT%H:%M:%S")
                existing = db.get_queued_posts_in_window(
                    window_start_str, window_end_str
                )

                if len(existing) >= max_per_day:
                    # This whole day might be full — try next window/day
                    break

                # Check min_interval from all queued posts
                conflict = False
                for post in existing:
                    post_time = datetime.strptime(
                        post["scheduled_time_utc"], "%Y-%m-%dT%H:%M:%S"
                    ).replace(tzinfo=ZoneInfo("UTC"))
                    if abs(candidate_utc - post_time) < min_interval:
                        conflict = True
                        break

                if not conflict:
                    return candidate_utc

                # Advance by 5 minutes to avoid excessive iteration
                candidate_local += timedelta(minutes=5)

    raise ValueError(
        f"Could not find an available slot for region '{region}' within the next 7 days."
    )


def schedule_post(
    content_item_id: int,
    region: str,
    db: Database,
    config: dict,
) -> dict:
    """
    1. Call suggest_slot() to compute the target time.
    2. Insert a row into scheduled_posts.
    3. Update content_items status to SCHEDULED.
    4. Return a dict with scheduling details.
    """
    slot_utc = suggest_slot(region, db, config)

    # Format for DB storage
    scheduled_time_str = slot_utc.strftime("%Y-%m-%dT%H:%M:%S")

    # Insert scheduled_posts row
    post_id = db.insert_scheduled_post(
        content_item_id=content_item_id,
        target_region=region,
        scheduled_time_utc=scheduled_time_str,
    )

    # Update content_item status
    db.update_status(content_item_id, Status.SCHEDULED)

    # Format human-readable time in the region's timezone
    sched = _get_scheduling_config(config)
    region_cfg = sched.get("regions", {}).get(region, {})
    tz_name = region_cfg.get("timezone", "UTC")
    tz = ZoneInfo(tz_name)
    local_time = slot_utc.astimezone(tz)
    formatted_time = local_time.strftime("%B %d, %I:%M %p %Z")

    result = {
        "scheduled_post_id": post_id,
        "content_item_id": content_item_id,
        "region": region,
        "timezone": tz_name,
        "scheduled_time_utc": scheduled_time_str,
        "formatted_time": formatted_time,
    }

    logger.info(
        "Scheduled item #%d for %s (%s) → %s",
        content_item_id, region, tz_name, formatted_time,
    )
    return result
