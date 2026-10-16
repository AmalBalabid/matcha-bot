from __future__ import annotations

import functools
import json
import os
import random
import re
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import messages as msg

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

SLACK_BOT_TOKEN     = os.environ["SLACK_BOT_TOKEN"]   # xoxb-...
SLACK_APP_TOKEN     = os.environ["SLACK_APP_TOKEN"]    # xapp-...
ADMIN_USER_ID       = os.environ["ADMIN_USER_ID"]      # You, receives everything the teammate sends
TEAM_MEMBER_USER_ID = os.environ["TEAM_MEMBER_USER_ID"]  # Teammate the bot interviews about "bot details"

# Where the bot keeps its data files. On a host with a persistent volume
# (e.g. Northflank), set MATCHA_STATE_DIR to the volume's mount path so parties
# survive restarts and redeploys. Defaults to the folder bot.py is in.
STATE_DIR   = Path(os.getenv("MATCHA_STATE_DIR") or Path(__file__).parent)
STATE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = STATE_DIR / "matcha_config.json"
STATE_PATH  = STATE_DIR / "party_state.json"

# ── App setup ────────────────────────────────────────────────────────────────
app = App(token=SLACK_BOT_TOKEN)

# The DM channels between the bot and each person, once opened.
target_dm_channel_id = {"id": None}  # bot ↔ teammate (Nouf), for the onboarding interview
admin_dm_channel_id  = {"id": None}  # bot ↔ admin (you)

_user_info_cache: dict = {}

# Order deadlines are shown in Riyadh time (fixed UTC+3, no daylight saving),
# whatever time zone the server runs in.
RIYADH_TZ = timezone(timedelta(hours=3), "Asia/Riyadh")

# Caps on free text people type. Spot names end up on vote buttons, which
# Slack limits to 75 characters.
SPOT_MAX_LEN        = 60
ORDER_FIELD_MAX_LEN = 100
ETA_MAX_LEN         = 100
# After the host gives an ETA, how long the "The order arrived" button stays
# live before the party is closed quietly.
ARRIVAL_WAIT_HOURS = 3

# How long the bot waits on the host at a step with no other deadline
# (picking invitees, picking the spot, confirming the order, the ETA) before
# closing the party, so nobody stays locked in it forever.
HOST_IDLE_MINUTES = 60

# Test mode (MATCHA_TEST_MODE=1 in .env or the environment): lets a host
# invite themselves, so one person can play host and invitee, and shortens
# the windows so a full run takes a few minutes, and switches off the
# onboarding relay (no /start, no forwarding to or from the teammate).
# Messages still say "5 minutes"/"3 minutes". Leave it off for real use.
TEST_MODE = os.getenv("MATCHA_TEST_MODE") == "1"

# Who can start a party: comma-separated Slack user IDs in MATCHA_ALLOWED_HOSTS
# (e.g. for a trial run). Unset or empty means everyone can. Anyone can still
# be invited either way.
ALLOWED_HOSTS = {u.strip() for u in os.getenv("MATCHA_ALLOWED_HOSTS", "").split(",") if u.strip()}
RSVP_SECONDS       = 60 if TEST_MODE else 5 * 60
SUGGESTION_SECONDS = 60 if TEST_MODE else 5 * 60
VOTE_SECONDS       = 30 if TEST_MODE else 3 * 60
ORDER_SECONDS      = 60 if TEST_MODE else 5 * 60

# Slack handlers and the timer thread all read-modify-write party_state.json,
# so every one of them runs under this lock (see @locked). Re-entrant because
# handlers call each other (e.g. a button handler that closes a window early).
state_lock = threading.RLock()


def locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with state_lock:
            return fn(*args, **kwargs)
    return wrapper


# ── Config / log helpers (onboarding interview) ──────────────────────────────

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


# ── Party state helpers ──────────────────────────────────────────────────────
#
# Anyone can start a Matcha Party now, and many can run at once. State is a
# single JSON blob with two parts:
#   "parties"     , party_id -> party dict. A party's id is just its host's
#                     user_id, which works because of the rule below.
#   "active_users", user_id -> party_id, tracking who is currently tied up
#                     in which party (as host, or as someone invited who
#                     hasn't declined yet). Anyone in here can't be the host
#                     or an invitee of a second party until they're released.
#                     This is what lets us turn a plain DM reply (a spot
#                     suggestion, a spot name, an ETA, "cancel") into "which
#                     party is this for", with no extra bookkeeping on the
#                     user's part. Invitees are freed once the order summary
#                     goes out, since they have nothing left to do.

def default_state() -> dict:
    return {"parties": {}, "active_users": {}}


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text())
            if "parties" in data and "active_users" in data:
                return data
        except Exception:
            pass
    return default_state()


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def default_party(host_id: str) -> dict:
    return {
        "host_id": host_id,
        "phase": "awaiting_invitees",
        "invited": {},          # user_id -> display name, everyone ever invited
        "pending_rsvps": {},    # user_id -> display name, still to accept/decline
        "accepted": {},         # user_id -> display name, confirmed joiners
        "declined": {},         # user_id -> display name
        "spot_name": None,
        "suggestions": [],       # [{"id", "user", "spot"}], in the order they came in
        "suggestion_order": [],  # unique spots from `suggestions`, first-seen order (what gets voted on)
        "votes": {},             # voter user_id -> suggestion text
        "orders": {},            # user_id -> {"drink":..., "milk":..., "cream":...}
        "order_deadline": None,
        "order_round": 0,        # bumped on every spot announcement, so stale timers/buttons are ignored
        "dropped_out": {},       # user_id -> display name, tapped "Can't make it" after the spot was announced
        "uid": uuid.uuid4().hex,  # unique per party, carried on buttons so old ones can't touch a newer party
        "timer": None,           # {"kind", "due" (epoch secs), ...}, see set_timer / run_due_timers
        "ghosts": {},            # user_id -> epoch secs: busy invitees shown as invited, auto-declined then (never DMed)
    }


def get_party_for_user(state: dict, user_id: str):
    """Look up the party a user is currently tied up in (as host or invitee).
    Returns (party_id, party) or (None, None)."""
    party_id = state["active_users"].get(user_id)
    if not party_id:
        return None, None
    return party_id, state["parties"].get(party_id)


def lock_user(state: dict, user_id: str, party_id: str) -> None:
    state["active_users"][user_id] = party_id


def unlock_user(state: dict, user_id: str) -> None:
    state["active_users"].pop(user_id, None)


def unlock_many(state: dict, user_ids) -> None:
    for uid in list(user_ids):
        unlock_user(state, uid)


def unlock_if_in(state: dict, user_id: str, party_id: str) -> None:
    """Unlock a user only if they're tied to this party, a ghost invitee is
    tied to a different one, and must stay there."""
    if state["active_users"].get(user_id) == party_id:
        unlock_user(state, user_id)


def unlock_guest(state: dict, party: dict, party_id: str, user_id: str) -> None:
    """Free an invitee from this party (never the host, who can be their own
    invitee in test mode, and never someone tied to a different party)."""
    if user_id != party["host_id"]:
        unlock_if_in(state, user_id, party_id)


def real_guests(party: dict) -> list:
    """Everyone invited or joined who actually got a message from this party
    (so not ghosts), the people to tell if it's scrapped."""
    ghosts = party.get("ghosts", {})
    return [u for u in list(party.get("accepted", {})) + list(party.get("pending_rsvps", {})) if u not in ghosts]


def release_party(state: dict, party_id: str) -> None:
    """Tear a party down: free the host and everyone ever invited to it who's
    still tied to it (someone who declined may already be in another party)."""
    party = state["parties"].pop(party_id, None)
    if not party:
        return
    close_all_live(party, msg.LINE_PARTY_CLOSED)
    for uid in list(party.get("invited", {}).keys()) + [party["host_id"]]:
        if state["active_users"].get(uid) == party_id:
            unlock_user(state, uid)


def party_ref(party_id: str, party: dict, **extra) -> str:
    """JSON stamped on a button or modal, pointing at exactly this party."""
    return json.dumps({"pid": party_id, "uid": party.get("uid"), **extra})


def resolve_party(state: dict, ref: dict):
    """The party a party_ref points at, or None if it has ended since."""
    party = state["parties"].get(ref.get("pid"))
    if not party or party.get("uid") != ref.get("uid"):
        return None
    return party


def set_timer(party: dict, kind: str, seconds: float, **extra) -> None:
    """Arm the party's single timer (each phase has at most one deadline).
    It's saved with the party, so it still fires after a restart."""
    party["timer"] = {"kind": kind, "due": time.time() + seconds, **extra}


def set_host_idle_timer(party: dict) -> None:
    set_timer(party, "host_idle", HOST_IDLE_MINUTES * 60, phase=party["phase"])


def _btn(text: str, action_id: str, value: str = "", style: str | None = None) -> dict:
    b = {"type": "button", "text": {"type": "plain_text", "text": text}, "action_id": action_id}
    if value:
        b["value"] = value
    if style:
        b["style"] = style
    return b


def _blocks(text: str, buttons: list) -> list:
    """A message: the text, then its buttons (Slack allows 25 per row)."""
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    for i in range(0, len(buttons), 25):
        blocks.append({"type": "actions", "elements": buttons[i:i + 25]})
    return blocks


def _cancel_btn(party_id: str, party: dict) -> dict:
    return _btn(msg.BUTTON_CANCEL_PARTY, "party_cancel", party_ref(party_id, party), style="danger")


# ── Shared helpers ───────────────────────────────────────────────────────────

def get_dm_channel(user_id: str) -> str:
    """Open (or retrieve) a DM channel with a user and return its channel ID."""
    result = app.client.conversations_open(users=user_id)
    return result["channel"]["id"]


def get_user_info(user_id: str) -> dict | None:
    """Slack's users_info record for a user (cached), or None if the lookup fails."""
    if user_id not in _user_info_cache:
        try:
            _user_info_cache[user_id] = app.client.users_info(user=user_id)["user"]
        except Exception as e:
            print(f"Could not look up user {user_id}: {e}")
            return None
    return _user_info_cache[user_id]


def get_display_name(user_id: str) -> str:
    """Resolve a Slack user ID to a human-readable display name (cached)."""
    info = get_user_info(user_id)
    if not info:
        return user_id
    return info.get("profile", {}).get("display_name") or info.get("real_name") or user_id


def is_invitable(user_id: str) -> bool:
    """Bots and deactivated accounts can't be DMed an invite."""
    info = get_user_info(user_id)
    return bool(info) and not info.get("is_bot") and not info.get("deleted")


def post(channel: str, text: str, blocks: list | None = None) -> str:
    """Send a message, logging (not raising) on failure, so one bad recipient
    doesn't stop a loop over everyone else. Returns the message's ts, or ""
    if it wasn't sent."""
    try:
        if blocks is None:
            result = app.client.chat_postMessage(channel=channel, text=text)
        else:
            result = app.client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        return result.get("ts") or "sent"
    except Exception as e:
        print(f"Could not post to {channel}: {e}")
        return ""


def dm(user_id: str, text: str, blocks: list | None = None) -> str:
    """DM a user; same failure handling and return value as post()."""
    try:
        channel = get_dm_channel(user_id)
    except Exception as e:
        print(f"Could not open a DM with {user_id}: {e}")
        return ""
    return post(channel, text, blocks)


# ── Live button messages ─────────────────────────────────────────────────────
#
# Messages with buttons that only work during one window (invites, suggestion
# prompts, votes, order messages) are remembered on the party under
# party["live_msgs"][kind]. When that window closes, their buttons are removed
# and a short line says why, so nobody can tap a dead button and get a
# confusing "closed" reply at the bottom of the chat.

def dm_live(party: dict, kind: str, user_id: str, text: str, blocks: list) -> str:
    ts = dm(user_id, text, blocks)
    if ts:
        party.setdefault("live_msgs", {}).setdefault(kind, []).append([get_dm_channel(user_id), ts, text, user_id])
    return ts


def close_live(party: dict, kind: str, line) -> None:
    """Remove the buttons from every live message of this kind. `line` is the
    closing line, or a function of the recipient's user ID that returns one
    (so it can show that person's answer)."""
    for item in party.get("live_msgs", {}).pop(kind, []):
        channel, ts, text = item[:3]
        user_id = item[3] if len(item) > 3 else None
        closing = line(user_id) if callable(line) else line
        _close_message(app.client, channel, ts, text, closing)


# Closing lines that show what each person answered.

def rsvp_line(party: dict, user_id: str) -> str:
    if user_id in party.get("accepted", {}) or user_id in party.get("dropped_out", {}):
        return msg.LINE_INVITE_CLOSED_IN
    if user_id in party.get("declined", {}):
        return msg.LINE_INVITE_CLOSED_OUT
    return msg.LINE_INVITE_CLOSED


def vote_line(party: dict, user_id: str) -> str:
    spot = party.get("votes", {}).get(user_id)
    return msg.LINE_VOTING_CLOSED_VOTED.format(spot=spot) if spot else msg.LINE_VOTING_CLOSED_NO_VOTE


def suggest_prompt_line(party: dict, user_id: str) -> str:
    entries = party["suggestions"] if isinstance(party.get("suggestions"), list) else []
    spots = [e["spot"] for e in entries if e["user"] == user_id]
    return msg.LINE_SUGGESTIONS_CLOSED_SUGGESTED.format(spots=", ".join(spots)) if spots else msg.LINE_SUGGESTIONS_CLOSED_NONE


def order_line(party: dict, user_id: str) -> str:
    order = party.get("orders", {}).get(user_id)
    if not order:
        return msg.LINE_ORDERING_CLOSED_NONE
    details = f"{order['drink']}, {order['milk']}, {order['sweetness']}, {order['cream']}"
    return msg.LINE_ORDERING_CLOSED_ORDERED.format(order=details)


def close_all_live(party: dict, line: str) -> None:
    for kind in list(party.get("live_msgs", {})):
        close_live(party, kind, line)


def retext_live(party: dict, ts: str, text: str | None) -> None:
    """A live message was edited (new text), or no longer has buttons (None)."""
    for kind, items in party.get("live_msgs", {}).items():
        for item in list(items):
            if item[1] == ts:
                if text is None:
                    items.remove(item)
                else:
                    item[2] = text


def _close_in_place(body: dict, line: str, party: dict | None = None) -> None:
    """Remove the buttons from the message that was just tapped and show
    `line` under it: the answer to a tap whose window already closed (rather
    than a new message at the bottom), or the host's choice. Pass the party
    to stop tracking that message, so it isn't closed again later."""
    message = body.get("message") or {}
    if party is not None and message:
        retext_live(party, message["ts"], None)
    if message:
        # The message's own text, without any closing line it may already have.
        blocks = message.get("blocks") or []
        text = blocks[0].get("text", {}).get("text") if blocks and blocks[0].get("type") == "section" else message.get("text", "")
        _close_message(app.client, body["channel"]["id"], message["ts"], text, line)


def _close_message(client, channel: str, ts: str, text: str, line: str) -> None:
    """Replace a message's buttons with a small grey status line under it."""
    try:
        client.chat_update(channel=channel, ts=ts, text=f"{text}\n{line}", blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": line}]},
        ])
    except Exception as e:
        print(f"Could not close a message: {e}")


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
        print(f"File {file_info.get('name')} has no url_private, can't download it.")
        return None
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            # A missing/insufficient "files:read" scope makes Slack return an HTML
            # login page instead of the file, so guard against silently "succeeding".
            if data[:15].lstrip().lower().startswith(b"<!doctype html") or data[:5] == b"<html":
                print(f"Download of {file_info.get('name')} returned an HTML page, not the "
                      "file, this usually means the bot is missing the 'files:read' scope.")
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
            app.client.files_upload_v2(channel=channel, content=data, filename=name)
        except Exception as e:
            print(f"Could not upload file {name} to {channel}: {e}")
            failed.append(name)
    return failed


# ── Onboarding interview ─────────────────────────────────────────────────────

def send_setup_questions(force: bool = False):
    """DM the teammate the 'bot details' interview, only once, even across restarts.

    Pass force=True (or delete "setup_sent" in matcha_config.json) to resend.
    """
    config = load_config()
    channel_id = get_dm_channel(TEAM_MEMBER_USER_ID)
    target_dm_channel_id["id"] = channel_id

    if config.get("setup_sent") and not force:
        print(f"[{datetime.now():%H:%M}] Setup questionnaire already sent to "
              f"<@{TEAM_MEMBER_USER_ID}>, skipping (pass force=True to resend).")
        return

    app.client.chat_postMessage(channel=channel_id, text=msg.SETUP_QUESTIONS)
    print(f"[{datetime.now():%H:%M}] Sent setup questionnaire to <@{TEAM_MEMBER_USER_ID}>.")

    config["setup_sent"] = True
    save_config(config)

    forward_to_admin(msg.SETUP_SENT_CONFIRMATION.format(team_member_id=TEAM_MEMBER_USER_ID))


def open_admin_dm():
    """Open (and remember) the DM channel with the admin, so incoming DMs can be matched."""
    admin_dm_channel_id["id"] = get_dm_channel(ADMIN_USER_ID)


# ── Matcha Party: starting + invitees ────────────────────────────────────────

def start_party_flow(host_id: str, state: dict) -> None:
    party = default_party(host_id)
    state["parties"][host_id] = party
    lock_user(state, host_id, host_id)
    set_host_idle_timer(party)
    dm_live(party, "host", host_id, msg.ASK_INVITEES, _blocks(msg.ASK_INVITEES, [
        _btn(msg.BUTTON_PICK_PEOPLE, "party_pick_people", party_ref(host_id, party), style="primary"),
        _cancel_btn(host_id, party),
    ]))
    save_state(state)


@app.action("party_pick_people")
@locked
def handle_pick_people(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_invitees" or party["host_id"] != body["user"]["id"]:
        return
    client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal",
        "callback_id": "party_invite_modal",
        "private_metadata": party_ref(ref["pid"], party, msg_channel=body["channel"]["id"], msg_ts=body["message"]["ts"]),
        "title": {"type": "plain_text", "text": msg.INVITE_MODAL_TITLE},
        "submit": {"type": "plain_text", "text": msg.INVITE_MODAL_SUBMIT},
        "blocks": [{
            "type": "input",
            "block_id": "invitees_block",
            "label": {"type": "plain_text", "text": msg.INVITE_MODAL_LABEL},
            "element": {"type": "multi_users_select", "action_id": "invitees_input"},
        }],
    })


@app.view("party_invite_modal")
@locked
def handle_invite_submission(ack, body, view, client):
    meta = json.loads(view["private_metadata"])
    host_id = meta["pid"]
    people = view["state"]["values"]["invitees_block"]["invitees_input"].get("selected_users") or []
    people = [u for u in people if u != host_id or TEST_MODE]
    if not people:
        ack(response_action="errors", errors={"invitees_block": msg.INVITE_PICK_SOMEONE})
        return
    ack()
    state = load_state()
    party = resolve_party(state, meta)
    if not party or party["phase"] != "awaiting_invitees":
        return
    names = invite_people(party, state, people)
    if names:
        retext_live(party, meta["msg_ts"], None)
        save_state(state)
        _close_message(client, meta["msg_channel"], meta["msg_ts"], msg.ASK_INVITEES, msg.LINE_HOST_INVITED.format(names=names))


def invite_people(party: dict, state: dict, people: list) -> str:
    """Invite the people the host picked. Returns their names ("" if nobody
    could be invited)."""
    host_id = party["host_id"]
    # Bots and deactivated accounts can never get an invite, so the host is
    # told about those by name. Anyone busy in another party becomes a
    # "ghost": listed as invited like everyone else, but never messaged, and
    # auto-declined about 2 minutes later, so to the host it looks like an
    # ordinary "Can't make it" and nothing reveals they're in another party.
    unreachable = [u for u in people if not is_invitable(u)]
    busy = [u for u in people if u not in unreachable and u != host_id and state["active_users"].get(u)]
    available = [u for u in people if u not in unreachable and u not in busy]

    rsvp_text = msg.RSVP_PROMPT.format(host=f"<@{host_id}>")
    rsvp_blocks = _blocks(rsvp_text, [
        _btn(msg.BUTTON_RSVP_ACCEPT, "party_rsvp_accept", party_ref(host_id, party), style="primary"),
        _btn(msg.BUTTON_RSVP_DECLINE, "party_rsvp_decline", party_ref(host_id, party)),
    ])
    invited_names = {}
    for uid in available:
        if dm_live(party, "rsvp", uid, rsvp_text, rsvp_blocks):
            invited_names[uid] = get_display_name(uid)
        else:
            unreachable.append(uid)

    for uid in busy:
        invited_names[uid] = get_display_name(uid)
        party.setdefault("ghosts", {})[uid] = time.time() + random.uniform(90, 150)

    if not invited_names:
        dm(host_id, msg.COULDNT_INVITE_ANYONE)
        if unreachable:
            dm(host_id, msg.INVITE_UNREACHABLE.format(names=", ".join(get_display_name(u) for u in unreachable)))
        set_host_idle_timer(party)
        save_state(state)
        return ""

    for uid in invited_names:
        if uid not in busy:
            lock_user(state, uid, host_id)
    # Keep the host's list in the order they picked people, so ghosts don't
    # stand out at the end.
    invited_names = {u: invited_names[u] for u in people if u in invited_names}
    party["invited"] = invited_names
    party["pending_rsvps"] = dict(invited_names)
    party["phase"] = "awaiting_rsvps"
    set_timer(party, "rsvp", RSVP_SECONDS)
    save_state(state)

    text = msg.RSVP_SENT_TO_HOST.format(names=", ".join(invited_names.values()))
    dm_live(party, "host", host_id, text, _blocks(text, [_cancel_btn(host_id, party)]))
    save_state(state)
    if unreachable:
        dm(host_id, msg.INVITE_UNREACHABLE.format(names=", ".join(get_display_name(u) for u in unreachable)))
    print(f"[{datetime.now():%H:%M}] Matcha Party invites sent: {', '.join(invited_names.values())}")
    return ", ".join(invited_names.values())


def cancel_party(party_id: str, party: dict, state: dict) -> None:
    """Host cancelled: tear down and tell everyone invited or joined."""
    guests = real_guests(party)
    release_party(state, party_id)
    save_state(state)
    dm(party["host_id"], msg.PARTY_CANCELLED)
    for uid in guests:
        dm(uid, msg.PARTY_CANCELLED_NOTICE.format(host=f"<@{party['host_id']}>"))
    print(f"[{datetime.now():%H:%M}] <@{party['host_id']}> cancelled their Matcha Party.")


@app.action("party_cancel")
@locked
def handle_cancel_button(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if party and party["host_id"] == body["user"]["id"] and state["active_users"].get(party["host_id"]) == ref["pid"]:
        _close_in_place(body, msg.LINE_HOST_CANCELLED, party)
        cancel_party(ref["pid"], party, state)
    else:
        _close_in_place(body, msg.LINE_PARTY_CLOSED)


def on_host_idle(party_id: str, phase: str) -> None:
    """The host left a step unanswered for HOST_IDLE_MINUTES, close the party
    so the host and invitees aren't locked in it forever."""
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != phase:
        return
    guests = real_guests(party)
    release_party(state, party_id)
    save_state(state)
    dm(party["host_id"], msg.PARTY_TIMED_OUT.format(minutes=HOST_IDLE_MINUTES))
    # Once the order's been sent, there's nothing for invitees to hear, the
    # host just never gave an ETA.
    if phase != "awaiting_eta":
        for uid in guests:
            dm(uid, msg.PARTY_TIMED_OUT_NOTICE.format(host=f"<@{party['host_id']}>"))
    print(f"[{datetime.now():%H:%M}] Matcha Party closed, host idle at '{phase}'.")


# ── Matcha Party: RSVPs ───────────────────────────────────────────────────────

def _rsvp_target(state: dict, body: dict, action: dict):
    """(party_id, party, uid) for an RSVP tap that still counts, else tells
    the invitee the invite closed and returns (None, None, uid)."""
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    party = resolve_party(state, ref)
    if party and party["phase"] == "awaiting_rsvps" and uid in party["pending_rsvps"]:
        return ref["pid"], party, uid
    # A second tap after already answering needs no reply.
    if not (party and (uid in party["accepted"] or uid in party["declined"])):
        _close_in_place(body, rsvp_line(party, uid) if party else msg.LINE_INVITE_CLOSED)
    return None, None, uid


@app.action("party_rsvp_accept")
@locked
def handle_rsvp_accept(ack, body, action):
    ack()
    state = load_state()
    party_id, party, uid = _rsvp_target(state, body, action)
    if not party:
        return
    name = party["pending_rsvps"].pop(uid)
    party["accepted"][uid] = name
    save_state(state)
    dm(uid, msg.RSVP_ACCEPTED_CONFIRMATION)
    if not party["pending_rsvps"]:
        on_rsvp_window_end(party_id)


@app.action("party_rsvp_decline")
@locked
def handle_rsvp_decline(ack, body, action):
    ack()
    state = load_state()
    party_id, party, uid = _rsvp_target(state, body, action)
    if not party:
        return
    name = party["pending_rsvps"].pop(uid)
    party["declined"][uid] = name
    unlock_guest(state, party, party_id, uid)
    save_state(state)
    dm(uid, msg.RSVP_DECLINED_CONFIRMATION)
    if not party["pending_rsvps"]:
        on_rsvp_window_end(party_id)


def on_rsvp_window_end(party_id: str) -> None:
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != "awaiting_rsvps":
        return
    close_live(party, "rsvp", lambda u: rsvp_line(party, u))

    no_response = dict(party["pending_rsvps"])
    if no_response:
        for uid in no_response:
            unlock_guest(state, party, party_id, uid)
        party["pending_rsvps"] = {}
    # Ghosts still pending (only possible if the bot was down) count as declined.
    for uid in party.get("ghosts", {}):
        if uid in no_response:
            party["declined"][uid] = no_response.pop(uid)
    party["ghosts"] = {}

    accepted = party["accepted"]
    not_joining = {**party["declined"], **no_response}

    if not accepted:
        release_party(state, party_id)
        save_state(state)
        dm(party["host_id"], msg.NOBODY_ACCEPTED)
        print(f"[{datetime.now():%H:%M}] Matcha Party scrapped, nobody accepted.")
        return

    party["phase"] = "awaiting_spot_method"
    set_host_idle_timer(party)
    save_state(state)

    names = ", ".join(accepted.values())
    if len(accepted) == 1:
        text = msg.ASK_SPOT_METHOD_ONE.format(name=names)
    else:
        text = msg.ASK_SPOT_METHOD.format(names=names)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_DECIDED}, "action_id": "party_spot_decided", "value": party_ref(party_id, party)},
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_SUGGEST}, "action_id": "party_spot_suggest", "value": party_ref(party_id, party)},
            _cancel_btn(party_id, party),
        ]},
    ]
    dm_live(party, "host", party["host_id"], text, blocks)
    save_state(state)
    if not_joining:
        dm(party["host_id"], msg.RSVP_NOT_JOINING.format(names=", ".join(not_joining.values())))
    print(f"[{datetime.now():%H:%M}] Matcha Party RSVPs in, joining: {names}")


# ── Matcha Party: deciding the spot ──────────────────────────────────────────

@app.action("party_spot_decided")
@locked
def handle_spot_decided(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    # Tapping again after closing the form just reopens it.
    if not party or party["phase"] not in ("awaiting_spot_method", "awaiting_spot_name"):
        return
    party["phase"] = "awaiting_spot_name"
    set_host_idle_timer(party)
    save_state(state)
    open_text_modal(client, body, ref["pid"], party, "spot")


@app.action("party_spot_suggest")
@locked
def handle_spot_suggest(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_spot_method":
        return
    party["phase"] = "collecting_suggestions"
    set_timer(party, "suggestion", SUGGESTION_SECONDS)
    _close_in_place(body, msg.LINE_HOST_LET_THEM_SUGGEST, party)
    save_state(state)
    prompt_text = msg.SUGGESTION_PROMPT.format(host=f"<@{party['host_id']}>")
    prompt_blocks = _blocks(prompt_text, [_btn(msg.BUTTON_SUGGEST_SPOT, "party_suggest_spot", party_ref(ref["pid"], party), style="primary")])
    for uid in party["accepted"]:
        dm_live(party, "suggest_prompt", uid, prompt_text, prompt_blocks)
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Suggestion window opened for a Matcha Party (5 min).")


@app.action("party_suggest_spot")
@locked
def handle_suggest_spot_button(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "collecting_suggestions" or uid not in party["accepted"]:
        _close_in_place(body, msg.LINE_SUGGESTIONS_CLOSED)
        return
    open_text_modal(client, body, ref["pid"], party, "suggestion")


def handle_suggestion_reply(user_id: str, message: str, party: dict, state: dict) -> None:
    suggestion = message.strip()
    if len(suggestion) > SPOT_MAX_LEN:
        dm(user_id, msg.SPOT_TOO_LONG.format(max=SPOT_MAX_LEN))
        return
    entries = party["suggestions"] if isinstance(party.get("suggestions"), list) else []
    # One typo away from a spot already in? Count them together, but ask the
    # suggester in case it's really a different place.
    # (An exact match, ignoring case and spaces, just joins it, no question.)
    spots = _unique_spots(entries)
    exact = any(_normalize_spot(s) == _normalize_spot(suggestion) for s in spots)
    near = None if exact else next((s for s in spots if _one_typo_apart(s, suggestion)), None)
    entry = {"id": uuid.uuid4().hex[:8], "user": user_id, "spot": suggestion, "separate": False}
    if near:
        entry["asked_match"] = near
    entries.append(entry)
    party["suggestions"] = entries
    party["suggestion_order"] = _unique_spots(entries)
    save_state(state)
    if near:
        text = msg.SUGGESTION_MERGE_ASK.format(spot=suggestion, match=near)
    else:
        text = msg.SUGGESTION_RECEIVED_CONFIRMATION.format(spot=suggestion)
    dm_live(party, "suggest", user_id, text, _suggestion_blocks(text, party, entry, ask_merge=bool(near)))
    save_state(state)


def _suggestion_blocks(text: str, party: dict, entry: dict, ask_merge: bool) -> list:
    """A suggestion confirmation: the text, Yes/No merge buttons if we're
    asking, and always a Remove button."""
    ref = party_ref(party["host_id"], party, entry=entry["id"])
    buttons = []
    if ask_merge:
        buttons += [
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_MERGE_YES}, "action_id": "party_merge_yes", "value": ref},
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_MERGE_NO}, "action_id": "party_merge_no", "value": ref},
        ]
    buttons.append({"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_REMOVE_SUGGESTION}, "action_id": "party_remove_suggestion", "value": ref})
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": buttons},
    ]


def _normalize_spot(name: str) -> str:
    return " ".join(name.lower().split())


def _one_typo_apart(a: str, b: str) -> bool:
    """Whether two names differ by exactly one character (added, missing, or
    different), ignoring case and extra spaces. Doesn't count when either name
    is under 4 characters ("Joe" vs "Moe") or the differing character is a
    digit ("Cafe 1" vs "Cafe 2"), those are usually genuinely different places."""
    a, b = _normalize_spot(a), _normalize_spot(b)
    if a == b or min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    # Strip the common prefix and suffix; what's left is the difference.
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    diff_a, diff_b = a[i:len(a) - j], b[i:len(b) - j]
    if len(diff_a) > 1 or len(diff_b) > 1:
        return False
    return not any(ch.isdigit() for ch in diff_a + diff_b)


def _unique_spots(entries: list) -> list:
    """Spots to vote on, in first-seen order, each shown with the spelling of
    whoever suggested it first. Suggestions that match ignoring case and
    spaces are always one spot; ones a typo apart are too, unless the
    suggester said it's a different place."""
    spots = []
    for e in entries:
        same = any(_normalize_spot(e["spot"]) == _normalize_spot(s) for s in spots)
        if not same and not e.get("separate"):
            same = any(_one_typo_apart(e["spot"], s) for s in spots)
        if not same:
            spots.append(e["spot"])
    return spots


def _own_suggestion(state: dict, body: dict, action: dict):
    """(party, entry) for a tap on one of the invitee's own suggestion
    buttons while suggestions are still open. If voting has started, tells
    them it's too late and returns (None, None)."""
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    party = resolve_party(state, ref)
    if not party or party["phase"] != "collecting_suggestions":
        _close_in_place(body, msg.LINE_SUGGESTIONS_CLOSED)
        return None, None
    entry = next((e for e in party["suggestions"] if e["id"] == ref["entry"] and e["user"] == uid), None)
    return (party, entry) if entry else (None, None)


@app.action("party_remove_suggestion")
@locked
def handle_remove_suggestion(ack, body, action, client):
    ack()
    state = load_state()
    party, entry = _own_suggestion(state, body, action)
    if not entry:
        return
    party["suggestions"].remove(entry)
    # Another person may have suggested the same spot, so it only drops off
    # the ballot if nobody else still has it.
    party["suggestion_order"] = _unique_spots(party["suggestions"])
    _close_in_place(body, msg.LINE_SUGGESTION_REMOVED, party)
    save_state(state)


@app.action("party_merge_yes")
@locked
def handle_merge_yes(ack, body, action, client):
    ack()
    state = load_state()
    party, entry = _own_suggestion(state, body, action)
    if not entry:
        return
    entry["separate"] = False
    party["suggestion_order"] = _unique_spots(party["suggestions"])
    text = msg.SUGGESTION_MERGE_CONFIRMED.format(spot=entry["spot"], match=entry.get("asked_match", entry["spot"]))
    retext_live(party, body["message"]["ts"], text)
    save_state(state)
    _update_suggestion_message(client, body, text, party, entry)


@app.action("party_merge_no")
@locked
def handle_merge_no(ack, body, action, client):
    ack()
    state = load_state()
    party, entry = _own_suggestion(state, body, action)
    if not entry:
        return
    entry["separate"] = True
    party["suggestion_order"] = _unique_spots(party["suggestions"])
    text = msg.SUGGESTION_KEPT_SEPARATE.format(spot=entry["spot"])
    retext_live(party, body["message"]["ts"], text)
    save_state(state)
    _update_suggestion_message(client, body, text, party, entry)


def _update_suggestion_message(client, body, text: str, party: dict, entry: dict) -> None:
    """Swap the merge question for the answer, keeping the Remove button."""
    try:
        client.chat_update(
            channel=body["channel"]["id"], ts=body["message"]["ts"], text=text,
            blocks=_suggestion_blocks(text, party, entry, ask_merge=False),
        )
    except Exception as e:
        print(f"Could not update a suggestion message: {e}")


def on_suggestion_window_end(party_id: str) -> None:
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != "collecting_suggestions":
        return
    close_live(party, "suggest_prompt", lambda u: suggest_prompt_line(party, u))
    close_live(party, "suggest", msg.LINE_SUGGESTIONS_CLOSED)

    if not party.get("suggestion_order"):
        party["phase"] = "awaiting_host_fallback_spot"
        set_host_idle_timer(party)
        save_state(state)
        dm_live(party, "host", party["host_id"], msg.NO_SUGGESTIONS_FALLBACK, _blocks(msg.NO_SUGGESTIONS_FALLBACK, [
            _btn(msg.BUTTON_PICK_SPOT, "party_pick_spot", party_ref(party_id, party), style="primary"),
            _cancel_btn(party_id, party),
        ]))
        save_state(state)
        print(f"[{datetime.now():%H:%M}] No suggestions came in, asked the host what to do.")
        return

    party["phase"] = "collecting_votes"
    set_timer(party, "vote", VOTE_SECONDS)
    save_state(state)

    suggestions = party["suggestion_order"]
    buttons = [
        {"type": "button", "text": {"type": "plain_text", "text": s}, "action_id": f"party_vote_{i}", "value": party_ref(party_id, party, spot=s)}
        for i, s in enumerate(suggestions)
    ]
    # Slack allows at most 25 buttons per actions block.
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": msg.VOTE_PROMPT_HEADER}}] + [
        {"type": "actions", "elements": buttons[i:i + 25]} for i in range(0, len(buttons), 25)
    ]
    for uid in party["accepted"]:
        dm_live(party, "vote", uid, msg.VOTE_PROMPT_HEADER, blocks)
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Voting window opened for a Matcha Party (3 min): {suggestions}")


@app.action(re.compile(r"^party_vote_\d+$"))
@locked
def handle_vote(ack, body, action):
    ack()
    ref = json.loads(action["value"])
    voter_id = body["user"]["id"]
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "collecting_votes" or voter_id not in party["accepted"]:
        _close_in_place(body, vote_line(party, voter_id) if party else msg.LINE_VOTING_CLOSED)
        return
    party["votes"][voter_id] = ref["spot"]
    save_state(state)
    dm(voter_id, msg.VOTE_RECEIVED_CONFIRMATION)


def on_vote_window_end(party_id: str) -> None:
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != "collecting_votes":
        return
    close_live(party, "vote", lambda u: vote_line(party, u))

    votes = party.get("votes", {})
    if not votes:
        party["phase"] = "awaiting_host_fallback_spot"
        set_host_idle_timer(party)
        save_state(state)
        _ask_host_to_pick(party_id, party, msg.NO_VOTES_FALLBACK, party.get("suggestion_order", []))
        save_state(state)
        print(f"[{datetime.now():%H:%M}] No votes came in, asked the host what to do.")
        return

    tally: dict = {}
    for suggestion in votes.values():
        tally[suggestion] = tally.get(suggestion, 0) + 1

    order = party.get("suggestion_order", [])
    breakdown = "\n".join(f"• {s}: {tally.get(s, 0)} vote(s)" for s in order)
    top = max(tally.values())
    tied = [s for s in order if tally.get(s, 0) == top]

    if len(tied) > 1:
        # A tie is the host's call: they pick one of the tied spots, or another spot.
        party["phase"] = "awaiting_tiebreak"
        set_host_idle_timer(party)
        save_state(state)
        text = msg.VOTE_RESULTS_TIE.format(breakdown=breakdown, tied=" and ".join(f"*{s}*" for s in tied))
        _ask_host_to_pick(party_id, party, text, tied)
        save_state(state)
        print(f"[{datetime.now():%H:%M}] Matcha Party vote tied: {tied}, asked the host to pick.")
        return

    winner = tied[0]
    dm(party["host_id"], msg.VOTE_RESULTS_TO_HOST.format(breakdown=breakdown, winner=winner))
    print(f"[{datetime.now():%H:%M}] Matcha Party voting results: {tally}, winner: {winner}")
    announce_spot(party_id, winner, party, state)


def _ask_host_to_pick(party_id: str, party: dict, text: str, spots: list) -> None:
    """Host message with a button per spot, plus "Another spot" and Cancel."""
    buttons = [_btn(s, f"party_pick_listed_{i}", party_ref(party_id, party, spot=s)) for i, s in enumerate(spots)]
    buttons += [_btn(msg.BUTTON_ANOTHER_SPOT, "party_pick_spot", party_ref(party_id, party)), _cancel_btn(party_id, party)]
    dm_live(party, "host", party["host_id"], text, _blocks(text, buttons))


@app.action(re.compile(r"^party_pick_listed_\d+$"))
@locked
def handle_pick_listed(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if (not party or party["phase"] not in ("awaiting_tiebreak", "awaiting_host_fallback_spot")
            or party["host_id"] != body["user"]["id"]):
        _close_in_place(body, msg.LINE_HOST_ALREADY_SETTLED)
        return
    _close_in_place(body, msg.LINE_HOST_PICKED.format(spot=ref["spot"]), party)
    print(f"[{datetime.now():%H:%M}] Host picked '{ref['spot']}' from the list.")
    announce_spot(ref["pid"], ref["spot"], party, state)


@app.action("party_pick_spot")
@locked
def handle_pick_spot_button(ack, body, action, client):
    """"Pick a spot" / "Another spot": the host types a spot in a form."""
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if (not party or party["phase"] not in ("awaiting_tiebreak", "awaiting_host_fallback_spot")
            or party["host_id"] != body["user"]["id"]):
        _close_in_place(body, msg.LINE_HOST_ALREADY_SETTLED)
        return
    open_text_modal(client, body, ref["pid"], party, "spot")


# ── Matcha Party: one-line forms (spot name, suggestion, ETA) ────────────────

_TEXT_MODALS = {
    # purpose: (title, field label, max length)
    "spot":       (msg.SPOT_MODAL_TITLE, msg.SPOT_MODAL_LABEL, SPOT_MAX_LEN),
    "suggestion": (msg.SUGGEST_MODAL_TITLE, msg.SPOT_MODAL_LABEL, SPOT_MAX_LEN),
    "eta":        (msg.ETA_MODAL_TITLE, msg.ETA_MODAL_LABEL, ETA_MAX_LEN),
}


def open_text_modal(client, body, party_id: str, party: dict, purpose: str) -> None:
    """Open a one-field form. The button message it came from is remembered,
    so its buttons can be removed once the form is sent."""
    title, label, max_len = _TEXT_MODALS[purpose]
    client.views_open(trigger_id=body["trigger_id"], view={
        "type": "modal",
        "callback_id": "party_text_modal",
        "private_metadata": party_ref(party_id, party, purpose=purpose, user=body["user"]["id"],
                                      msg_channel=body["channel"]["id"], msg_ts=body["message"]["ts"],
                                      msg_text=body["message"].get("text", "")[:500]),
        "title": {"type": "plain_text", "text": title},
        "submit": {"type": "plain_text", "text": msg.MODAL_SUBMIT_SEND},
        "blocks": [{
            "type": "input",
            "block_id": "text_block",
            "label": {"type": "plain_text", "text": label},
            "element": {"type": "plain_text_input", "action_id": "text_input", "max_length": max_len},
        }],
    })


@app.view("party_text_modal")
@locked
def handle_text_modal(ack, body, view, client):
    ack()
    meta = json.loads(view["private_metadata"])
    uid, purpose = meta["user"], meta["purpose"]
    text = view["state"]["values"]["text_block"]["text_input"]["value"].strip()
    state = load_state()
    party = resolve_party(state, meta)
    phase = party["phase"] if party else None
    is_host = bool(party) and party["host_id"] == uid

    if purpose == "suggestion":
        if phase != "collecting_suggestions" or uid not in party["accepted"]:
            dm(uid, msg.SUGGESTION_WINDOW_CLOSED)
            return
        handle_suggestion_reply(uid, text, party, state)
        return  # the prompt keeps its button, for more suggestions

    if purpose == "spot":
        if not is_host or phase not in ("awaiting_spot_name", "awaiting_host_fallback_spot", "awaiting_tiebreak"):
            return
        retext_live(party, meta["msg_ts"], None)
        _close_message(client, meta["msg_channel"], meta["msg_ts"], meta["msg_text"], msg.LINE_HOST_SPOT.format(spot=text))
        handle_host_spot_name(uid, text, party, state)
    elif purpose == "eta":
        if not is_host or phase != "awaiting_eta":
            return
        retext_live(party, meta["msg_ts"], None)
        _close_message(client, meta["msg_channel"], meta["msg_ts"], meta["msg_text"], msg.LINE_HOST_ETA.format(eta=text))
        handle_host_eta_reply(uid, text, party, state)


def _strip_buttons(client, channel: str, ts: str, text: str) -> None:
    """Remove the buttons from a message once its step is done, keeping its text."""
    try:
        client.chat_update(channel=channel, ts=ts, text=text,
                           blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": text}}])
    except Exception as e:
        print(f"Could not remove buttons from a message: {e}")


def handle_host_spot_name(user_id: str, message: str, party: dict, state: dict) -> None:
    """Host entered a spot name in a form: from "I've already decided", or as
    a fallback when nobody suggested/voted in time, or instead of a tied spot."""
    spot = message.strip()
    if len(spot) > SPOT_MAX_LEN:
        dm(user_id, msg.SPOT_TOO_LONG.format(max=SPOT_MAX_LEN))
        return
    announce_spot(party["host_id"], spot, party, state, host_picked=True)


# ── Matcha Party: ordering ────────────────────────────────────────────────────

def announce_spot(party_id: str, spot_name: str, party: dict, state: dict, host_picked: bool = False) -> None:
    """Announce the spot and open a 5-minute order window. host_picked adds a
    "Suggest somewhere else" button, since nobody else got a say in the spot."""
    party["spot_name"] = spot_name
    party["phase"] = "awaiting_orders"
    party["order_round"] = party.get("order_round", 0) + 1
    order_round = party["order_round"]
    deadline_dt = datetime.now(RIYADH_TZ) + timedelta(seconds=ORDER_SECONDS)
    deadline_str = deadline_dt.strftime("%H:%M")
    party["order_deadline"] = deadline_dt.isoformat()
    set_timer(party, "order", ORDER_SECONDS, round=order_round)
    save_state(state)

    text = msg.SPOT_ANNOUNCEMENT.format(host=f"<@{party['host_id']}>", spot=spot_name, deadline=deadline_str)
    ref = party_ref(party_id, party, round=order_round)
    buttons = [
        {"type": "button", "text": {"type": "plain_text", "text": msg.PLACE_ORDER_BUTTON}, "action_id": "party_place_order", "value": ref, "style": "primary"},
        {"type": "button", "text": {"type": "plain_text", "text": msg.ORDER_DECLINE_BUTTON}, "action_id": "party_order_decline", "value": ref},
    ]
    if host_picked:
        buttons.append({"type": "button", "text": {"type": "plain_text", "text": msg.SUGGEST_OTHER_BUTTON}, "action_id": "party_suggest_other", "value": ref})
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": buttons},
    ]
    for uid in party["accepted"]:
        dm_live(party, "order", uid, text, blocks)
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Announced matcha spot '{spot_name}', orders due by {deadline_str} (Riyadh).")


def _order_target(state: dict, body: dict, ref: dict, uid: str, check_round: bool = True):
    """(party_id, party) if this invitee can still act on the order message
    that `ref` came from. Otherwise says why on that message, and returns
    (None, None)."""
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_orders" or uid not in party["accepted"]:
        _close_in_place(body, order_line(party, uid) if party else msg.LINE_ORDERING_CLOSED)
        return None, None
    if check_round and ref.get("round") != party.get("order_round", 0):
        _close_in_place(body, msg.LINE_SPOT_CHANGED)
        return None, None
    return ref["pid"], party


@app.action(re.compile(r"^party_(place|change)_order$"))
@locked
def handle_place_order(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    state = load_state()
    party_id, party = _order_target(state, body, ref, uid)
    if not party:
        return
    # Changing an order: open the form filled in with what they sent before.
    existing = party["orders"].get(uid) or {}
    cream_value = "with" if existing.get("cream") == msg.CREAM_WITH else "without"
    sweet_value = {msg.SWEETNESS_SWEET: "sweet", msg.SWEETNESS_LESS_SWEET: "less_sweet",
                   msg.SWEETNESS_NO_SWEET: "no_sweet"}.get(existing.get("sweetness"))
    view = _order_modal_view(party_ref(party_id, party, round=party["order_round"], user=uid))
    if existing:
        for block in view["blocks"]:
            el = block["element"]
            if block["block_id"] == "drink_block":
                el["initial_value"] = existing["drink"]
            elif block["block_id"] == "milk_block":
                el["initial_value"] = existing["milk"]
            elif block["block_id"] == "cream_block":
                el["initial_option"] = next(o for o in el["options"] if o["value"] == cream_value)
            elif block["block_id"] == "sweetness_block" and sweet_value:
                el["initial_option"] = next(o for o in el["options"] if o["value"] == sweet_value)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def _order_modal_view(metadata: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "party_order_modal",
        "private_metadata": metadata,
        "title": {"type": "plain_text", "text": msg.ORDER_MODAL_TITLE},
        "submit": {"type": "plain_text", "text": msg.ORDER_MODAL_SUBMIT},
        "blocks": [
            {
                "type": "input",
                "block_id": "drink_block",
                "label": {"type": "plain_text", "text": msg.DRINK_LABEL},
                "element": {"type": "plain_text_input", "action_id": "drink_input", "max_length": ORDER_FIELD_MAX_LEN},
            },
            {
                "type": "input",
                "block_id": "milk_block",
                "label": {"type": "plain_text", "text": msg.MILK_LABEL},
                "element": {"type": "plain_text_input", "action_id": "milk_input", "max_length": ORDER_FIELD_MAX_LEN},
            },
            {
                "type": "input",
                "block_id": "cream_block",
                "label": {"type": "plain_text", "text": msg.CREAM_LABEL},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "cream_input",
                    "options": [
                        {"text": {"type": "plain_text", "text": msg.CREAM_WITH}, "value": "with"},
                        {"text": {"type": "plain_text", "text": msg.CREAM_WITHOUT}, "value": "without"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "sweetness_block",
                "label": {"type": "plain_text", "text": msg.SWEETNESS_LABEL},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "sweetness_input",
                    "options": [
                        {"text": {"type": "plain_text", "text": msg.SWEETNESS_SWEET}, "value": "sweet"},
                        {"text": {"type": "plain_text", "text": msg.SWEETNESS_LESS_SWEET}, "value": "less_sweet"},
                        {"text": {"type": "plain_text", "text": msg.SWEETNESS_NO_SWEET}, "value": "no_sweet"},
                    ],
                },
            },
        ],
    }


@app.view("party_order_modal")
@locked
def handle_order_submission(ack, body, view, client):
    ack()
    meta = json.loads(view["private_metadata"])
    user_id = meta["user"]
    state = load_state()
    party = resolve_party(state, meta)
    if not party or party["phase"] != "awaiting_orders" or user_id not in party["accepted"]:
        dm(user_id, msg.ORDER_CLOSED)
        return
    if meta["round"] != party.get("order_round", 0):
        dm(user_id, msg.ORDER_STALE)
        return
    party_id = meta["pid"]

    values = view["state"]["values"]
    drink = values["drink_block"]["drink_input"]["value"]
    milk = values["milk_block"]["milk_input"]["value"]
    cream_option = values["cream_block"]["cream_input"].get("selected_option")
    cream = msg.CREAM_WITH if cream_option and cream_option["value"] == "with" else msg.CREAM_WITHOUT
    sweetness_option = values["sweetness_block"]["sweetness_input"].get("selected_option")
    sweetness_value = sweetness_option["value"] if sweetness_option else None
    sweetness = {
        "sweet": msg.SWEETNESS_SWEET,
        "less_sweet": msg.SWEETNESS_LESS_SWEET,
        "no_sweet": msg.SWEETNESS_NO_SWEET,
    }.get(sweetness_value, msg.SWEETNESS_SWEET)

    changed = user_id in party["orders"]
    party["orders"][user_id] = {"drink": drink, "milk": milk, "cream": cream, "sweetness": sweetness}
    save_state(state)
    text = msg.ORDER_UPDATED_CONFIRMATION if changed else msg.ORDER_RECEIVED_CONFIRMATION
    dm_live(party, "order_confirm", user_id, text, _blocks(text, [
        _btn(msg.BUTTON_CHANGE_ORDER, "party_change_order", party_ref(party_id, party, round=party["order_round"])),
    ]))
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Got order from {get_display_name(user_id)}: {drink}, {milk}, {sweetness}, {cream}")

    # Everyone's in, no need to wait out the rest of the window.
    if set(party["orders"].keys()) >= set(party["accepted"].keys()):
        send_order_summary(party_id, party, state)


# ── Matcha Party: dropping out or suggesting another spot ────────────────────

@app.action("party_order_decline")
@locked
def handle_order_decline(ack, body, action):
    ack()
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    state = load_state()
    # Dropping out doesn't depend on which spot, so an older announcement's
    # button still works.
    party_id, party = _order_target(state, body, ref, uid, check_round=False)
    if not party:
        return
    _close_in_place(body, msg.LINE_DROPPED_OUT)
    retext_live(party, body["message"]["ts"], None)

    name = party["accepted"].pop(uid)
    party.setdefault("dropped_out", {})[uid] = name
    party["orders"].pop(uid, None)
    unlock_guest(state, party, party_id, uid)
    save_state(state)

    dm(uid, msg.ORDER_DECLINED_CONFIRMATION)
    dm(party["host_id"], msg.ORDER_DECLINED_TO_HOST.format(name=name, spot=party["spot_name"]))
    print(f"[{datetime.now():%H:%M}] {name} dropped out of a Matcha Party.")

    if not party["accepted"]:
        release_party(state, party_id)
        save_state(state)
        dm(party["host_id"], msg.ALL_DROPPED_OUT)
        print(f"[{datetime.now():%H:%M}] Matcha Party scrapped, everyone dropped out.")
        return

    # Everyone still in has already ordered, no need to wait out the window.
    if set(party["orders"].keys()) >= set(party["accepted"].keys()):
        send_order_summary(party_id, party, state)


@app.action("party_suggest_other")
@locked
def handle_suggest_other(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    uid = body["user"]["id"]
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_orders" or uid not in party["accepted"]:
        _close_in_place(body, msg.LINE_ORDERING_CLOSED)
        return
    if ref.get("round") != party.get("order_round", 0):
        _close_in_place(body, msg.LINE_SPOT_CHANGED)
        return
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "party_alt_spot_modal",
            "private_metadata": party_ref(ref["pid"], party, round=party["order_round"], user=uid),
            "title": {"type": "plain_text", "text": msg.ALT_SPOT_MODAL_TITLE},
            "submit": {"type": "plain_text", "text": msg.ALT_SPOT_MODAL_SUBMIT},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "alt_spot_block",
                    "label": {"type": "plain_text", "text": msg.ALT_SPOT_LABEL},
                    "element": {"type": "plain_text_input", "action_id": "alt_spot_input", "max_length": SPOT_MAX_LEN},
                },
            ],
        },
    )


@app.view("party_alt_spot_modal")
@locked
def handle_alt_spot_submission(ack, body, view, client):
    ack()
    meta = json.loads(view["private_metadata"])
    uid = meta["user"]
    state = load_state()
    party = resolve_party(state, meta)
    if not party or party["phase"] != "awaiting_orders" or uid not in party["accepted"]:
        dm(uid, msg.ALT_SPOT_TOO_LATE_CLOSED)
        return
    if meta["round"] != party.get("order_round", 0):
        dm(uid, msg.ALT_SPOT_TOO_LATE_CHANGED.format(spot=party["spot_name"]))
        return

    suggestion = view["state"]["values"]["alt_spot_block"]["alt_spot_input"]["value"].strip()
    name = party["accepted"][uid]
    text = msg.ALT_SPOT_SUGGESTED_TO_HOST.format(name=name, suggestion=suggestion, spot=party["spot_name"])
    value = party_ref(meta["pid"], party, round=meta["round"], user=uid, spot=suggestion)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_KEEP_SPOT}, "action_id": "party_keep_spot", "value": value},
            {"type": "button", "text": {"type": "plain_text", "text": msg.BUTTON_SWITCH_SPOT}, "action_id": "party_switch_spot", "value": value},
        ]},
    ]
    dm_live(party, "host_alt", party["host_id"], text, blocks)
    save_state(state)
    dm(uid, msg.ALT_SPOT_SENT_CONFIRMATION.format(host=f"<@{party['host_id']}>"))
    print(f"[{datetime.now():%H:%M}] {name} suggested '{suggestion}' instead of '{party['spot_name']}'.")


def _active_alt_suggestion(state: dict, body: dict, action: dict):
    """Return (party_id, party, suggestion) if a Keep/Switch tap is still for
    the current spot, otherwise (None, None, None)."""
    suggestion = json.loads(action["value"])
    party = resolve_party(state, suggestion)
    if (not party or party["host_id"] != body["user"]["id"] or party["phase"] != "awaiting_orders"
            or suggestion["round"] != party.get("order_round", 0)):
        return None, None, None
    return suggestion["pid"], party, suggestion


@app.action("party_keep_spot")
@locked
def handle_keep_spot(ack, body, action, client):
    ack()
    state = load_state()
    _, party, suggestion = _active_alt_suggestion(state, body, action)
    if not party:
        _close_in_place(body, msg.LINE_HOST_SUGGESTION_INACTIVE)
        return
    _close_in_place(body, msg.LINE_HOST_KEPT.format(spot=party["spot_name"]), party)
    save_state(state)
    if suggestion["user"] in party["accepted"]:
        dm(suggestion["user"], msg.ALT_SPOT_KEPT.format(host=f"<@{party['host_id']}>", spot=party["spot_name"]))


@app.action("party_switch_spot")
@locked
def handle_switch_spot(ack, body, action, client):
    ack()
    state = load_state()
    party_id, party, suggestion = _active_alt_suggestion(state, body, action)
    if not party:
        _close_in_place(body, msg.LINE_HOST_SUGGESTION_INACTIVE)
        return
    new_spot = suggestion["spot"]
    party["orders"] = {}
    close_live(party, "order", msg.LINE_SPOT_CHANGED)
    close_live(party, "order_confirm", msg.LINE_SPOT_CHANGED)
    _close_in_place(body, msg.LINE_HOST_SWITCHED.format(spot=new_spot), party)
    # Any other "suggested somewhere else" messages are about the old spot now.
    close_live(party, "host_alt", msg.LINE_HOST_SUGGESTION_INACTIVE)
    notice = msg.SPOT_CHANGED_NOTICE.format(host=f"<@{party['host_id']}>", spot=new_spot)
    for uid in party["accepted"]:
        dm(uid, notice)
    print(f"[{datetime.now():%H:%M}] Host switched the Matcha Party spot to '{new_spot}'.")
    announce_spot(party_id, new_spot, party, state, host_picked=True)


def on_order_window_end(party_id: str, order_round: int) -> None:
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != "awaiting_orders":
        return
    # The host switched spots since this timer started, the newer timer owns it.
    if order_round != party.get("order_round", 0):
        return
    send_order_summary(party_id, party, state)


# ── Matcha Party: wrap-up ─────────────────────────────────────────────────────

def send_order_summary(party_id: str, party: dict, state: dict) -> None:
    close_live(party, "order", lambda u: order_line(party, u))
    close_live(party, "order_confirm", msg.LINE_ORDERING_CLOSED)
    close_live(party, "host_alt", msg.LINE_HOST_SUGGESTION_INACTIVE)
    party["phase"] = "awaiting_confirmation"
    set_host_idle_timer(party)
    # Invitees have nothing left to do, so free them to join other parties
    # now rather than waiting on the host's confirmation and ETA. They stay in
    # `accepted`, so they still get the "order sent" and ETA messages.
    for uid in party["accepted"]:
        unlock_guest(state, party, party_id, uid)
    save_state(state)

    lines = [msg.ORDER_SUMMARY_HEADER.format(spot=party.get("spot_name", "?"))]
    for uid, name in party["accepted"].items():
        order = party["orders"].get(uid)
        if order:
            lines.append(msg.ORDER_SUMMARY_LINE.format(
                name=name, drink=order["drink"], milk=order["milk"],
                sweetness=order["sweetness"], cream=order["cream"],
            ))
    missing = [name for uid, name in party["accepted"].items() if uid not in party["orders"]]
    if missing:
        lines.append(msg.ORDER_SUMMARY_MISSING.format(names=", ".join(missing)))
    if party.get("dropped_out"):
        lines.append(msg.ORDER_SUMMARY_DROPPED_OUT.format(names=", ".join(party["dropped_out"].values())))
    summary_text = "\n".join(lines)

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": msg.CONFIRM_ORDER_BUTTON}, "action_id": "party_confirm_sent", "value": party_ref(party_id, party)},
        ]},
    ]
    dm_live(party, "host", party["host_id"], summary_text, blocks)
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Sent Matcha Party order summary to the host.")


@app.action("party_confirm_sent")
@locked
def handle_confirm_sent(ack, body, action, client):
    ack()
    state = load_state()
    party = resolve_party(state, json.loads(action["value"]))
    party_id = party["host_id"] if party else None
    if not party or party["phase"] != "awaiting_confirmation":
        return
    _close_in_place(body, msg.LINE_HOST_PLACED, party)
    dm(party["host_id"], msg.ORDER_SENT_ACK)

    sent_text = msg.ORDER_SENT_TO_INVITEES.format(host=f"<@{party['host_id']}>")
    for uid in party["accepted"]:
        dm(uid, sent_text)

    party["phase"] = "awaiting_eta"
    set_host_idle_timer(party)
    dm_live(party, "host", party["host_id"], msg.ASK_ETA, _blocks(msg.ASK_ETA, [
        _btn(msg.BUTTON_ADD_ETA, "party_add_eta", party_ref(party_id, party), style="primary"),
        _btn(msg.BUTTON_NO_ETA, "party_no_eta", party_ref(party_id, party)),
    ]))
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Order confirmed sent, notified invitees, asked host for an ETA.")


@app.action("party_add_eta")
@locked
def handle_add_eta(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_eta" or party["host_id"] != body["user"]["id"]:
        return
    open_text_modal(client, body, ref["pid"], party, "eta")


@app.action("party_no_eta")
@locked
def handle_no_eta(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_eta" or party["host_id"] != body["user"]["id"]:
        return
    _close_in_place(body, msg.LINE_HOST_NO_ETA, party)
    handle_host_eta_reply(party["host_id"], "", party, state)


def handle_host_eta_reply(user_id: str, message: str, party: dict, state: dict) -> None:
    """Host sent an ETA (or tapped "No ETA", message empty). Passes it on, then
    waits for the host to say the order arrived."""
    party_id = party["host_id"]
    eta_text = message.strip()
    if len(eta_text) > ETA_MAX_LEN:
        dm(user_id, msg.ETA_TOO_LONG.format(max=ETA_MAX_LEN))
        return
    if eta_text:
        announcement = msg.ETA_ANNOUNCEMENT.format(eta=eta_text)
        for uid in party["accepted"]:
            dm(uid, announcement)

    # The host has nothing left to do but tap "arrived", so free them to start
    # another party meanwhile. The button finds this party by its party_ref.
    party["phase"] = "awaiting_arrival"
    set_timer(party, "arrival_wait", ARRIVAL_WAIT_HOURS * 3600)
    unlock_if_in(state, party_id, party_id)
    dm_live(party, "host", party_id, msg.WAITING_FOR_ARRIVAL, _blocks(msg.WAITING_FOR_ARRIVAL, [
        _btn(msg.BUTTON_ORDER_ARRIVED, "party_order_arrived", party_ref(party_id, party), style="primary"),
    ]))
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Matcha Party order sent, waiting for it to arrive.")


@app.action("party_order_arrived")
@locked
def handle_order_arrived(ack, body, action, client):
    ack()
    ref = json.loads(action["value"])
    state = load_state()
    party = resolve_party(state, ref)
    if not party or party["phase"] != "awaiting_arrival" or party["host_id"] != body["user"]["id"]:
        _close_in_place(body, msg.LINE_PARTY_CLOSED)
        return
    for uid in party["accepted"]:
        dm(uid, msg.ORDER_ARRIVED_NOTICE)
    _close_in_place(body, msg.LINE_HOST_ARRIVED, party)
    release_party(state, ref["pid"])
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Matcha Party order arrived, party closed.")


def on_arrival_wait_end(party_id: str) -> None:
    """Nobody tapped "The order arrived" in time: close the party quietly."""
    state = load_state()
    party = state["parties"].get(party_id)
    if not party or party["phase"] != "awaiting_arrival":
        return
    release_party(state, party_id)
    save_state(state)
    print(f"[{datetime.now():%H:%M}] Matcha Party closed, arrival never confirmed.")


# ── Matcha Party: timers ──────────────────────────────────────────────────────
#
# Every deadline is stored on its party (set_timer), and a background thread
# checks for due ones every few seconds. Because they're saved to disk, a
# restart picks them back up, anything that came due while the bot was down
# fires as soon as it's back.

_TIMER_HANDLERS = {
    "rsvp":       lambda pid, t: on_rsvp_window_end(pid),
    "suggestion": lambda pid, t: on_suggestion_window_end(pid),
    "vote":       lambda pid, t: on_vote_window_end(pid),
    "order":      lambda pid, t: on_order_window_end(pid, t["round"]),
    "host_idle":  lambda pid, t: on_host_idle(pid, t["phase"]),
    "arrival_wait": lambda pid, t: on_arrival_wait_end(pid),
}


def on_ghost_decline(party_id: str, user_id: str) -> None:
    """A busy invitee's auto-decline comes due, record it exactly like a
    real "Can't make it" tap (minus any message to them)."""
    state = load_state()
    party = state["parties"].get(party_id)
    if not party:
        return
    party.get("ghosts", {}).pop(user_id, None)
    if party["phase"] != "awaiting_rsvps" or user_id not in party["pending_rsvps"]:
        save_state(state)
        return
    party["declined"][user_id] = party["pending_rsvps"].pop(user_id)
    save_state(state)
    if not party["pending_rsvps"]:
        on_rsvp_window_end(party_id)


def run_due_timers() -> None:
    with state_lock:
        state = load_state()
        now = time.time()
        due_ghosts = [(pid, uid) for pid, p in state["parties"].items()
                      for uid, due in p.get("ghosts", {}).items() if due <= now]
        for pid, uid in due_ghosts:
            try:
                on_ghost_decline(pid, uid)
            except Exception as e:
                print(f"Ghost decline for {uid} in party {pid} failed: {e}")
        state = load_state()
        due = [(pid, p["timer"]) for pid, p in state["parties"].items()
               if p.get("timer") and p["timer"]["due"] <= now]
        if not due:
            return
        # Disarm first, so a handler that doesn't set a new timer can't fire twice.
        for pid, _ in due:
            state["parties"][pid]["timer"] = None
        save_state(state)
        for pid, timer in due:
            try:
                _TIMER_HANDLERS[timer["kind"]](pid, timer)
            except Exception as e:
                print(f"Timer '{timer['kind']}' for party {pid} failed: {e}")


def timer_loop() -> None:
    while True:
        try:
            run_due_timers()
        except Exception as e:
            print(f"Timer loop error: {e}")
        time.sleep(5)


@app.command("/matcha-party")
@locked
def handle_matcha_party_command(ack, body, respond):
    """
    Kicks off a Matcha Party, anyone can run this, but only from their own DM
    with the bot (not from a channel). The person who runs it becomes that
    party's host, and gets the fallback prompts, order summary, and
    confirm-sent button for it. Multiple parties can run at once, as long as
    nobody is tied up in more than one at a time. Registered as a real Slack
    slash command (Features → Slash Commands → /matcha-party). Also needs
    "Interactivity & Shortcuts" turned on in the Slack app config, since this
    flow uses buttons and a modal.
    """
    ack()
    if body.get("channel_name") != "directmessage":
        respond(msg.PARTY_DM_ONLY)
        return

    host_id = body["user_id"]
    if ALLOWED_HOSTS and host_id not in ALLOWED_HOSTS:
        respond(msg.PARTY_NOT_OPEN_YET)
        return
    state = load_state()
    existing_party_id = state["active_users"].get(host_id)
    if existing_party_id:
        if existing_party_id == host_id:
            party = state["parties"][host_id]
            respond(text=msg.PARTY_ALREADY_IN_PROGRESS,
                    blocks=_blocks(msg.PARTY_ALREADY_IN_PROGRESS, [_cancel_btn(host_id, party)]))
        else:
            respond(msg.BUSY_IN_ANOTHER_PARTY)
        return

    # No separate confirmation: ASK_INVITEES itself says the party started.
    start_party_flow(host_id, state)
    print(f"[{datetime.now():%H:%M}] <@{host_id}> started a new Matcha Party.")


# ── Event listeners ───────────────────────────────────────────────────────────

def _extract_message_text(event: dict) -> str:
    """Build a readable message from whatever was sent, text, photo, video, or file."""
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
@locked
def handle_message(event, say):
    """Relay onboarding DMs both ways, and route hosts/invitees through
    whatever step of their Matcha Party is currently active."""
    if event.get("bot_id"):
        return
    if event.get("channel_type") != "im":
        return
    # Only new messages (with or without files), not edits or deletions.
    if event.get("subtype") not in (None, "file_share"):
        return

    channel_id = event.get("channel")
    user_id    = event.get("user")
    if not user_id:
        return
    files      = event.get("files", [])
    message    = _extract_message_text(event)
    if not message:
        return

    state = load_state()
    party_id, party = get_party_for_user(state, user_id)

    # Anyone in a party has all their DMs handled here, even ones the current
    # step doesn't expect, so nothing typed mid-party ever falls through to
    # the onboarding relay below.
    if party:
        if user_id == party["host_id"] and message.strip().lower() == "cancel":
            cancel_party(party_id, party, state)  # still works, though the buttons are the main way
        elif user_id == party["host_id"]:
            dm(user_id, msg.HOST_NOTHING_TO_REPLY)
        else:
            dm(user_id, msg.INVITEE_NOTHING_TO_REPLY)
        return

    # Test mode never relays anything between the admin and the teammate.
    if TEST_MODE:
        dm(user_id, msg.DM_HELLO)
        return

    # Admin DM, fall back to the original "whatever you DM me goes straight
    # to the teammate" relay. (/start itself is handled separately as a real
    # slash command, since Slack intercepts anything starting with "/" before
    # it reaches here.)
    # (Matched by who sent it: each person has exactly one DM with the bot, so
    # this works even before the bot has seen that DM since it last started.)
    if user_id == ADMIN_USER_ID:
        admin_dm_channel_id["id"] = channel_id
        forward_to_teammate(message)
        if files:
            channel = target_dm_channel_id["id"] or get_dm_channel(TEAM_MEMBER_USER_ID)
            failed = forward_files(files, channel)
            if failed:
                forward_to_admin(msg.FILE_FORWARD_FAILED_TO_TEAMMATE.format(
                    names=", ".join(failed), team_member_id=TEAM_MEMBER_USER_ID
                ))
        print(f"[{datetime.now():%H:%M}] Forwarded message from admin to <@{TEAM_MEMBER_USER_ID}>.")
        return

    # Teammate (Nouf) replying in her onboarding DM with the bot → forward to admin
    if user_id == TEAM_MEMBER_USER_ID:
        target_dm_channel_id["id"] = channel_id
        log_exchange("message", message)
        forward_to_admin(f"🍵 <@{TEAM_MEMBER_USER_ID}> said: {message}")
        if files:
            failed = forward_files(files, get_dm_channel(ADMIN_USER_ID))
            if failed:
                forward_to_admin(msg.FILE_FORWARD_FAILED_TO_ADMIN.format(names=", ".join(failed)))
        print(f"[{datetime.now():%H:%M}] Forwarded message from <@{TEAM_MEMBER_USER_ID}> to admin.")
        return

    # Anyone else, outside a party: point them at /matcha-party rather than
    # leaving them with silence.
    if ALLOWED_HOSTS and user_id not in ALLOWED_HOSTS:
        dm(user_id, msg.PARTY_NOT_OPEN_YET)
    else:
        dm(user_id, msg.DM_HELLO)


@app.command("/start")
def handle_start_command(ack, body, respond):
    """
    Manual trigger for the setup questionnaire, registered as a real Slack
    slash command (Features → Slash Commands → /start, needs the "commands"
    bot scope). Type /start in your DM with the bot whenever you're ready.
    """
    ack()
    if TEST_MODE:
        respond("Test mode is on, so the onboarding questionnaire is disabled.")
        return
    invoking_user = body.get("user_id")
    if invoking_user != ADMIN_USER_ID:
        respond("Only the admin can trigger this.")
        return

    send_setup_questions(force=True)
    respond("🍵 Sent the setup questionnaire to Nouf!")
    print(f"[{datetime.now():%H:%M}] Admin triggered /start, setup questionnaire (re)sent.")


def _get_message_text(channel_id: str, ts: str) -> str:
    """Look up the text of the specific message a reaction was added to."""
    try:
        result = app.client.conversations_history(
            channel=channel_id, latest=ts, oldest=ts, inclusive=True, limit=1
        )
        found = result.get("messages", [])
        if found:
            return found[0].get("text", "").strip()
    except Exception as e:
        print(f"Could not look up reacted-to message: {e}")
    return ""


@app.event("reaction_added")
def handle_reaction(event):
    """Relay every reaction the teammate adds (to any of the bot's onboarding DM
    messages) to the admin."""
    if TEST_MODE:
        return
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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Open (and remember) the admin's own DM channel, so messages you send the
    # bot directly can be matched and relayed to the teammate (or routed into
    # an active Matcha Party flow).
    open_admin_dm()

    print("Matcha Bot is running 🍵" + ("  [TEST MODE: self-invite on, short timers, onboarding relay off]" if TEST_MODE else ""))
    print(f"  Admin    : {ADMIN_USER_ID}")
    print(f"  Teammate : {TEAM_MEMBER_USER_ID}")
    print(f"  Can start a party: {', '.join(sorted(ALLOWED_HOSTS)) if ALLOWED_HOSTS else 'everyone'}")
    print("  Run the /start slash command whenever you're ready to send Nouf's "
          "setup questionnaire.")
    print("  Run the /matcha-party slash command whenever you want to organize "
          "a matcha order, anyone can run it, from their own DM with the bot.")
    print()

    # Fire party deadlines (RSVPs, suggestions, votes, orders, host idle),
    # including any that came due while the bot was down.
    threading.Thread(target=timer_loop, daemon=True).start()

    # Start the Socket Mode handler (keeps the bot connected to Slack)
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
