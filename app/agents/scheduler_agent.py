from celery import shared_task
from datetime import datetime, timedelta, timezone
from app.database import Database
from app.agents.scraper_agent import scrape_target

FREQUENCY_MAP = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1)
}

@shared_task
def run_scheduler():
    """Check all active targets and trigger scrapes if due."""
    db = Database.get_sync_db()  
    now = datetime.now(timezone.utc)
    
    targets = list(db.targets.find({"is_active": True}))
    
    print(f"📅 Scheduler running: {len(targets)} active targets to check")

    for target in targets:
        freq = target.get("frequency", "daily")
        last_checked = target.get("last_checked")
        url = target.get("url")
        t_type = target.get("type")

        # Determine if scraping is due
        due = False
        if not last_checked:
            due = True
        else:
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=timezone.utc)
            
            next_due = last_checked + FREQUENCY_MAP.get(freq, timedelta(days=1))
            if now >= next_due:
                due = True

        if due:
            print(f"🕒 Scheduling new scrape for {url} (frequency: {freq})")
            scrape_target.delay(str(target["_id"]), url, t_type)
        else:
            if last_checked:
                next_due = last_checked + FREQUENCY_MAP.get(freq, timedelta(days=1))
                time_remaining = next_due - now
                print(f"⏰ {url} - Next scrape in {time_remaining}")
