from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import schedule
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

SLACK_BOT_TOKEN     = os.environ["SLACK_BOT_TOKEN"]   # xoxb-...
SLACK_APP_TOKEN     = os.environ["SLACK_APP_TOKEN"]    # xapp-...
ADMIN_USER_ID       = os.environ["ADMIN_USER_ID"]      # You — receives everything the teammate sends
TEAM_MEMBER_USER_ID = os.environ["TEAM_MEMBER_USER_ID"]  # Teammate the bot interviews about "bot details"
GROUP_CHANNEL_ID    = os.getenv("GROUP_CHANNEL_ID", "")  # Where daily recommendations get posted
SEND_TIME           = os.getenv("SEND_TIME", "09:00")    # 24-hr format, default 9am

CONFIG_PATH = Path(__file__).parent / "matcha_config.json"

# ── App setup ────────────────────────────────────────────────────────────────
app = App(token=SLACK_BOT_TOKEN)

# The DM channels between the bot and each person, once opened.
target_dm_channel_id = {"id": None}  # bot ↔ teammate (Nouf)
admin_dm_channel_id  = {"id": None}  # bot ↔ admin (you)

# ── Setup questions ──────────────────────────────────────────────────────────
# Matcha Bot DMs the teammate this "bot details" interview. Every reply and
# every reaction they give back gets relayed straight to the admin (you).
SETUP_QUESTIONS = (
    "Good morning Nouf! 🍵 Your matcha bot is cooking, list all of your "
    "requirements here! Reply however you'd like (text, emoji reactions, "
    "whatever), it all gets passed along, no fixed format needed."
)

# Placeholder menu — swap this out once the recommendation logic (question 4
# above) is decided.
PLACEHOLDER_MATCHA_MENU = [
    "Iced matcha latte 🍵🧊",
    "Hojicha latte 🌾",
    "Matcha with oat milk 🌱",
    "Strawberry matcha 🍓",
    "Classic hot matcha, no sweetener 🍃",
]


# ── Config / log helpers ─────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {"exchanges": [], "setup_sent": False}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def log_exchange(kind: str, detail: str) -> None:
    """Append every message/reaction from the teammate to a running log."""
    config = load_config()
    config["exchanges"].append({
        "type": kind,          # "message" or "reaction"
        "detail": detail,
        "at": datetime.now().isoformat(),
    })
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def get_dm_channel(user_id: str) -> str:
    """Open (or retrieve) a DM channel with a user and return its channel ID."""
    result = app.client.conversations_open(users=user_id)
    return result["channel"]["id"]


def forward_to_admin(text: str) -> None:
    """Relay something from the teammate straight to the admin."""
    admin_channel = get_dm_channel(ADMIN_USER_ID)
    app.client.chat_postMessage(channel=admin_channel, text=text)


def forward_to_teammate(text: str) -> None:
    """Relay something from the admin straight to the teammate."""
    channel = target_dm_channel_id["id"] or get_dm_channel(TEAM_MEMBER_USER_ID)
    target_dm_channel_id["id"] = channel
    app.client.chat_postMessage(channel=channel, text=text)


def _download_slack_file(file_info: dict) -> bytes | None:
    """Download a file Slack sent us (photos, videos, docs) using the bot token."""
    url = file_info.get("url_private_download") or file_info.get("url_private")
    if not url:
        print(f"File {file_info.get('name')} has no url_private — can't download it.")
        return None
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            # A missing/insufficient "files:read" scope makes Slack return an HTML
            # login page instead of the file, so guard against silently "succeeding".
            if data[:15].lstrip().lower().startswith(b"<!doctype html") or data[:5] == b"<html":
                print(f"Download of {file_info.get('name')} returned an HTML page, not the "
                      "file — this usually means the bot is missing the 'files:read' scope.")
                return None
            return data
    except Exception as e:
        print(f"Could not download file {file_info.get('name')}: {e}")
        return None


def forward_files(files: list, channel: str) -> list:
    """Re-upload files (photos/videos/docs) to another DM so they're actually viewable there,
    not just described as text. Returns the list of filenames that failed to forward."""
    failed = []
    for f in files:
        name = f.get("name", "file")
        data = _download_slack_file(f)
        if data is None:
            failed.append(name)
            continue
        try:
            app.client.files_upload_v2(
                channel=channel,
                content=data,
                filename=name,
            )
        except Exception as e:
            print(f"Could not upload file {name} to {channel}: {e}")
            failed.append(name)
    return failed


# ── Core actions ─────────────────────────────────────────────────────────────

def send_setup_questions(force: bool = False):
    """DM the teammate the 'bot details' interview — only once, even across restarts.

    Pass force=True (or delete "setup_sent" in matcha_config.json) to resend.
    """
    config = load_config()
    channel_id = get_dm_channel(TEAM_MEMBER_USER_ID)
    target_dm_channel_id["id"] = channel_id

    if config.get("setup_sent") and not force:
        print(f"[{datetime.now():%H:%M}] Setup questionnaire already sent to "
              f"<@{TEAM_MEMBER_USER_ID}> — skipping (pass force=True to resend).")
        return

    app.client.chat_postMessage(channel=channel_id, text=SETUP_QUESTIONS)
    print(f"[{datetime.now():%H:%M}] Sent setup questionnaire to <@{TEAM_MEMBER_USER_ID}>.")

    config["setup_sent"] = True
    save_config(config)

    forward_to_admin(
        f"🍵 Sent the Matcha Bot setup questionnaire to <@{TEAM_MEMBER_USER_ID}>. "
        "I'll forward their replies and reactions here as they come in. "
        "Anything you DM me, I'll pass straight on to them too."
    )


def open_admin_dm():
    """Open (and remember) the DM channel with the admin, so incoming DMs can be matched."""
    admin_dm_channel_id["id"] = get_dm_channel(ADMIN_USER_ID)


def send_matcha_recommendation():
    """Post today's matcha recommendation to the group channel (weekdays only)."""
    if datetime.now().weekday() in (5, 6):  # Saturday=5, Sunday=6
        print(f"[{datetime.now():%H:%M}] Weekend — skipping matcha recommendation.")
        return

    if not GROUP_CHANNEL_ID:
        print("GROUP_CHANNEL_ID is not set — skipping recommendation. "
              "Fill this in once you know which channel to post to.")
        return

    # TODO: replace this placeholder pick with whatever recommendation logic
    # the teammate described (see matcha_config.json for their answers).
    pick = random.choice(PLACEHOLDER_MATCHA_MENU)

    app.client.chat_postMessage(
        channel=GROUP_CHANNEL_ID,
        text=(
            f"🍵 *Today's matcha recommendation:* {pick}\n\n"
            "React with ✅ if you're in, and I'll get an order started!"
        ),
    )
    print(f"[{datetime.now():%H:%M}] Posted matcha recommendation to {GROUP_CHANNEL_ID}: {pick}")


# ── Event listeners ───────────────────────────────────────────────────────────

def _extract_message_text(event: dict) -> str:
    """Build a readable message from whatever was sent — text, photo, video, or file."""
    text  = event.get("text", "").strip()
    files = event.get("files", [])

    parts = []
    if text:
        parts.append(text)
    for f in files:
        mimetype = f.get("mimetype", "")
        name     = f.get("name", "file")
        if mimetype.startswith("image/"):
            parts.append(f"📷 [photo: {name}]")
        elif mimetype.startswith("video/"):
            parts.append(f"🎥 [video: {name}]")
        else:
            parts.append(f"📎 [file: {name}]")
    return " ".join(parts)


@app.event("message")
def handle_message(event, say):
    """Relay DMs both ways: teammate → admin, and admin → teammate."""
    if event.get("bot_id"):
        return
    if event.get("channel_type") != "im":
        return

    channel_id = event.get("channel")
    user_id    = event.get("user")
    files      = event.get("files", [])
    message    = _extract_message_text(event)
    if not message:
        return

    # Teammate (Nouf) replying in her DM with the bot → forward to admin
    if channel_id == target_dm_channel_id["id"] and user_id == TEAM_MEMBER_USER_ID:
        log_exchange("message", message)
        forward_to_admin(f"🍵 <@{TEAM_MEMBER_USER_ID}> said: {message}")
        if files:
            failed = forward_files(files, get_dm_channel(ADMIN_USER_ID))
            if failed:
                forward_to_admin(
                    f"⚠️ Couldn't forward the actual file(s) ({', '.join(failed)}) — the bot "
                    "probably needs the 'files:read' bot scope added (OAuth & Permissions), "
                    "then reinstall the app."
                )
        print(f"[{datetime.now():%H:%M}] Forwarded message from <@{TEAM_MEMBER_USER_ID}> to admin.")
        return

    # Admin (you) messaging the bot directly → forward straight to the teammate
    # (the /start trigger itself is handled separately below as a real slash command,
    # since Slack intercepts any message starting with "/" before it reaches here)
    if channel_id == admin_dm_channel_id["id"] and user_id == ADMIN_USER_ID:
        forward_to_teammate(message)
        if files:
            channel = target_dm_channel_id["id"] or get_dm_channel(TEAM_MEMBER_USER_ID)
            failed = forward_files(files, channel)
            if failed:
                forward_to_admin(
                    f"⚠️ Couldn't forward the actual file(s) ({', '.join(failed)}) to "
                    f"<@{TEAM_MEMBER_USER_ID}> — the bot probably needs the 'files:read' bot "
                    "scope added (OAuth & Permissions), then reinstall the app."
                )
        print(f"[{datetime.now():%H:%M}] Forwarded message from admin to <@{TEAM_MEMBER_USER_ID}>.")
        return


@app.command("/start")
def handle_start_command(ack, body, respond):
    """
    Manual trigger for the setup questionnaire, registered as a real Slack
    slash command (Features → Slash Commands → /start, needs the "commands"
    bot scope). Type /start in your DM with the bot whenever you're ready.
    """
    ack()
    invoking_user = body.get("user_id")
    if invoking_user != ADMIN_USER_ID:
        respond("Only the admin can trigger this.")
        return

    send_setup_questions(force=True)
    respond("🍵 Sent the setup questionnaire to Nouf!")
    print(f"[{datetime.now():%H:%M}] Admin triggered /start — setup questionnaire (re)sent.")


def _get_message_text(channel_id: str, ts: str) -> str:
    """Look up the text of the specific message a reaction was added to."""
    try:
        result = app.client.conversations_history(
            channel=channel_id, latest=ts, oldest=ts, inclusive=True, limit=1
        )
        messages = result.get("messages", [])
        if messages:
            return messages[0].get("text", "").strip()
    except Exception as e:
        print(f"Could not look up reacted-to message: {e}")
    return ""


@app.event("reaction_added")
def handle_reaction(event):
    """Relay every reaction the teammate adds (to any of the bot's DM messages) to the admin."""
    user_id = event.get("user")
    item    = event.get("item", {})
    emoji   = event.get("reaction")

    if user_id != TEAM_MEMBER_USER_ID:
        return
    if item.get("type") != "message":
        return
    if item.get("channel") != target_dm_channel_id["id"]:
        return

    detail       = f":{emoji}:"
    reacted_text = _get_message_text(item.get("channel"), item.get("ts"))

    log_exchange("reaction", f"{detail} on: {reacted_text}" if reacted_text else detail)

    if reacted_text:
        forward_to_admin(f"🍵 <@{TEAM_MEMBER_USER_ID}> reacted with {detail} to: \"{reacted_text}\"")
    else:
        forward_to_admin(f"🍵 <@{TEAM_MEMBER_USER_ID}> reacted with {detail} (couldn't find the original message)")

    print(f"[{datetime.now():%H:%M}] Forwarded reaction {detail} from <@{TEAM_MEMBER_USER_ID}> to admin.")


# ── Scheduler ─────────────────────────────────────────────────────────────────

def run_scheduler():
    """Run the blocking schedule loop in a background thread."""
    schedule.every().day.at(SEND_TIME).do(send_matcha_recommendation)
    print(f"Scheduler started — matcha recommendations will be sent daily at {SEND_TIME}")
    while True:
        schedule.run_pending()
        time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Open (and remember) the admin's own DM channel, so messages you send the
    # bot directly can be matched and relayed to the teammate.
    open_admin_dm()

    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    print("Matcha Bot is running 🍵")
    print(f"  Admin        : {ADMIN_USER_ID}")
    print(f"  Teammate     : {TEAM_MEMBER_USER_ID}")
    print(f"  Group channel: {GROUP_CHANNEL_ID or '(not set yet)'}")
    print(f"  Daily time   : {SEND_TIME}")
    print("  Run the /start slash command (registered in your Slack app) whenever "
          "you're ready to send the setup questionnaire.")
    print()

    # Start the Socket Mode handler (keeps the bot connected to Slack)
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
