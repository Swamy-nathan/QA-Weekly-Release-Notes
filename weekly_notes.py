import gspread
from google.oauth2.service_account import Credentials
from slack_sdk.webhook import WebhookClient
from datetime import datetime, timedelta
import os
# === CONFIG ===
SHEET_URL = 'https://docs.google.com/spreadsheets/d/14UtV_HHOh6Eg-C-xrqOLK-4CwNJ89TNwBfVQWP6nvy8/edit?usp=sharing'
JSON_KEYFILE = 'credentials.json'  # still needed on disk
SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK_URL')
SHEET_TABS = ['QA_Notes']  # ✅ Only QA Notes
DEFAULT_MESSAGE = "🕑 No updates or No Work has been Reported"
WEEKEND_MESSAGE = "🍿 Weekend 🎮"
# ==============

def get_last_week_range():
    today = datetime.today()
    last_saturday = today - timedelta(days=today.weekday() + 2)
    last_sunday = last_saturday - timedelta(days=6)
    return last_sunday.date(), last_saturday.date()

def parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%a, %b %d, %Y").date()
    except Exception:
        return None

def fetch_tab_records(client, sheet_name):
    try:
        worksheet = client.worksheet(sheet_name)
        return worksheet.get_all_records()
    except Exception as e:
        print(f"⚠️ Failed to fetch {sheet_name}: {e}")
        return []

def build_team_section(records, start_date, end_date, team_name):
    TEAM_HEADERS = {
        "QA NOTES": "QA Release Notes - <@U08HLCB6WC8>"
    }

    header = TEAM_HEADERS.get(team_name.upper(), f"{team_name} Release Notes")
    lines = [
        f"\n{team_name} *",
        f"_{header}_\n"
    ]

    date_map = {}
    for row in records:
        date_obj = parse_date(row.get("Date", ""))
        if not date_obj or not (start_date <= date_obj <= end_date):
            continue
        date_map.setdefault(date_obj, []).append(row)

    for i in range(7):
        day = start_date + timedelta(days=i)
        date_str = day.strftime("%a, %b %d, %Y")

        lines.append(f"\n 📅 *{date_str}*")

        if day in date_map:
            for row in date_map[day]:
                work = row.get("Work", "").strip()
                title = row.get("Title", "").strip()
                desc = row.get("Description", "").strip()

                lines.append(f" ●  *Work:*  {work or DEFAULT_MESSAGE}")
                lines.append(f"     *Title:*  {title or DEFAULT_MESSAGE}")
                lines.append(f"     *Description:*\n   {desc or DEFAULT_MESSAGE}\n")
        else:
            if day.weekday() in (5, 6):  # Saturday=5, Sunday=6
                lines.append(WEEKEND_MESSAGE + "\n")
            else:
                lines.append(DEFAULT_MESSAGE + "\n")

    return "\n".join(lines)

def post_to_slack(message):
    webhook = WebhookClient(SLACK_WEBHOOK)
    response = webhook.send(text=message)
    print("✅ Slack sent:", response.status_code)

def main():
    if datetime.today().weekday() != 1:  # Only run on Tuesday
        print("❌ This script only runs on Tuesdays. Today is not Tuesday.")
        return

    # Auth
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(JSON_KEYFILE, scopes=scope)
    client = gspread.authorize(creds).open_by_url(SHEET_URL)

    # Date range
    start_date, end_date = get_last_week_range()

    # Header message with dynamic dates
    message_lines = [
        " 🔸🔸🔸🔸 QA WEEKLY RELEASE NOTES 🔸🔸🔸🔸",
        f"📆 {start_date.strftime('%B %d')} – {end_date.strftime('%B %d, %Y')}\n"
    ]

    # QA Notes
    for tab in SHEET_TABS:
        records = fetch_tab_records(client, tab)
        section = build_team_section(records, start_date, end_date, tab.replace("_", " ").upper())
        message_lines.append(section)
        message_lines.append("")  # Spacer

    final_message = "\n".join([line for line in message_lines if line])
    post_to_slack(final_message)

if __name__ == "__main__":
    main()
