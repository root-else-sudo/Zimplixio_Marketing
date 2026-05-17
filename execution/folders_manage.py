# folders_manage.py
# Manages the posts/ folder structure for LinkedIn draft storage
# - Creates all missing day folders from April 1st to today
# - Creates next month's folder on the last day of each month
# - Safe to run multiple times — skips folders that already exist

import os
from datetime import date, timedelta
from calendar import monthrange


POSTS_ROOT = "posts"
BACKLOG_START = date(2026, 4, 1)


def get_all_dates(start: date, end: date):
    """Generate all dates from start to end inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def folder_path_for_date(d: date) -> str:
    """Return the folder path for a given date."""
    month_folder = d.strftime("%Y-%m")
    day_folder = d.strftime("%Y-%m-%d")
    return os.path.join(POSTS_ROOT, month_folder, day_folder)


def create_folder(path: str):
    """Create folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"  Created: {path}")
    else:
        print(f"  Exists:  {path}")


def create_next_month_folder_if_needed(today: date):
    """On the last day of the month, create next month's folder."""
    last_day = monthrange(today.year, today.month)[1]
    if today.day == last_day:
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        next_month_folder = os.path.join(
            POSTS_ROOT, next_month.strftime("%Y-%m")
        )
        create_folder(next_month_folder)
        print(f"  Next month folder ready: {next_month_folder}")


def main():
    today = date.today()
    print(f"folders_manage.py — running for {today}")
    print(f"Building folder structure from {BACKLOG_START} to {today}...\n")

    # Create posts root if needed
    create_folder(POSTS_ROOT)

    # Create all day folders from backlog start to today
    for d in get_all_dates(BACKLOG_START, today):
        path = folder_path_for_date(d)
        create_folder(path)

    # Check if today is last day of month — create next month folder
    print("\nChecking if next month folder is needed...")
    create_next_month_folder_if_needed(today)

    print("\nDone. Folder structure is ready.")


if __name__ == "__main__":
    main()