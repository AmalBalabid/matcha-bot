# Matcha Bot

A Slack bot (slack-bolt, Socket Mode) that does two things:

1. **Onboarding relay**: DMs a teammate a setup questionnaire and relays everything they send (messages, files, emoji reactions) straight to an admin, and relays the admin's replies back.
2. **Matcha Party**: lets anyone in the workspace run `/matcha-party` to organize a group matcha order: invite people, collect RSVPs, decide on a spot, collect orders, and send a summary.

This file is developer-facing: setup, environment variables, Slack app configuration, and how the code is put together. For the exact wording the bot sends during a Matcha Party, see `matcha-bot-messages.md`.

---

## 1. Setup

```bash
pip install -r requirements.txt
cp example.env .env   # then fill in the values below
python3 bot.py
```

The bot runs in Socket Mode, so no public URL or Request URL is needed: just a valid app-level token and the scopes/toggles below.

To limit who can start a party (e.g. for a trial run), set `MATCHA_ALLOWED_HOSTS` to a comma-separated list of Slack user IDs; anyone else running `/matcha-party` is told it isn't open yet. Remove it to open parties to everyone.

To try a Matcha Party on your own, start it with `MATCHA_TEST_MODE=1 python3 bot.py`: you can pick yourself as the invitee, and the onboarding relay is switched off so nothing reaches the teammate. For a quick run, set every step to 1 minute on the invite form. Leave it off for real use.

### Environment variables (`.env`)

| Variable | Where to get it | Purpose |
|---|---|---|
| `SLACK_BOT_TOKEN` | OAuth & Permissions → Bot User OAuth Token (`xoxb-...`) | Authenticates all bot API calls |
| `SLACK_APP_TOKEN` | Basic Information → App-Level Tokens, scope `connections:write` (`xapp-...`) | Opens the Socket Mode connection |
| `ADMIN_USER_ID` | Your Slack user ID | Receives everything the teammate sends during onboarding |
| `TEAM_MEMBER_USER_ID` | The teammate's Slack user ID | Who gets DMed the onboarding questionnaire |

`example.env` has the same table with more detail inline, plus the full list of required Slack app scopes/toggles: see below.

### Required Slack app configuration

- **Bot scopes** (OAuth & Permissions):
  - `chat:write`: sends every bot message.
  - `im:write`: opens DMs with hosts and invitees (`conversations_open`).
  - `im:history` + a subscription to the `message.im` event: receives DM replies (`conversations_history` is also used on DMs).
  - `reactions:read` + a subscription to the `reaction_added` event: relays teammate reactions to the admin.
  - `files:read` + `files:write`: re-uploads forwarded photos/videos/files so they're viewable, not just described as text.
  - `users:read`: looks up invitees' display names for Matcha Party (`users_info`).
  - `commands`: required for both slash commands below.
- **Slash commands** (Features → Slash Commands): create `/start` and `/matcha-party`. Both are real Slack slash commands, not plain-text triggers: Slack intercepts anything starting with `/` before it reaches the bot's message handler.
- **Interactivity & Shortcuts**: turn this ON. Since the bot runs in Socket Mode, no Request URL is needed: just the toggle. This is what makes the RSVP buttons, spot-decision buttons, vote buttons, and the order modal work.
- Reinstall the app to the workspace after changing scopes.

### Deployment

`Procfile` declares a single worker process (`python3 bot.py`), suitable for Northflank/Heroku-style platforms. State is persisted to JSON files in `MATCHA_STATE_DIR` (default: next to `bot.py`; see below). On Northflank, attach a volume, e.g. at `/data`, and set `MATCHA_STATE_DIR=/data`. The deploy target needs that persistent disk/volume if parties should survive a restart: otherwise in-flight parties are lost on redeploy (restarts do not resend or reopen anything).

---

## 2. Architecture

Two files hold all the logic:

- **`bot.py`**: event/action/command handlers, state management, all control flow.
- **`messages.py`**: every user-facing string the bot sends, as named constants (`import messages as msg`). Keeping wording out of `bot.py` means message copy can be edited without touching logic, and `matcha-bot-messages.md` can be kept in sync by reading this file alone.

### Persistence

Two JSON files on disk, next to `bot.py`:

- `matcha_config.json`: onboarding interview state (`exchanges` log, `setup_sent` flag so the questionnaire is only auto-sent once, even across restarts).
- `party_state.json`: all Matcha Party state (see below). Written on every state change via `save_state`, so a restart picks up exactly where things left off (subject to the persistent-disk caveat above).

### Matcha Party state model

```python
state = {
    "parties": {},        # party_id -> party dict
    "active_users": {},    # user_id -> party_id
}
```

A party's `party_id` is simply its host's user ID: this works because a host is also subject to the one-active-party-per-person rule, so a host can never collide with their own earlier party.

`active_users` is the single mechanism that does two jobs at once:
- **Routing**: a DM typed during a party is matched to "which party is this for" via `get_party_for_user(state, user_id)`, so it gets the right nudge (and never reaches the onboarding relay).
- **Locking**: anyone present in `active_users`: host or invitee: cannot be invited into, or start, a second party until they're released. This is enforced once, centrally, rather than re-checked per code path. Invitees are released as soon as the order summary goes out (they have nothing left to do); the host stays locked until the ETA step closes the party.

Buttons and modals don't rely on `active_users`: they carry a `party_ref` (`{"pid", "uid", ...}`), and `resolve_party` only accepts it if that exact party (matched by its unique `uid`) is still running. So a button from a finished party can never act on a newer one, even for the same host.

Each party dict (`default_party`):

| Field | Meaning |
|---|---|
| `host_id` | Who started it |
| `phase` | Current step: see state machine below |
| `invited` | Everyone ever invited (`user_id -> display name`), used at teardown to know who to unlock |
| `pending_rsvps` | Invitees who haven't accepted/declined yet |
| `accepted` / `declined` | Invitees who have responded |
| `spot_name`, `votes` | Spot-decision data |
| `suggestions` | Every suggestion as `{"id", "user", "spot", "separate"}`; invitees can remove their own (Remove button) until voting starts |
| `suggestion_order` | Distinct spots from `suggestions`, first-seen order: what gets voted on. Suggestions matching ignoring case/extra spaces are always one spot. One a typo apart (`_one_typo_apart`: one character different, except a digit or names under 4 characters) is merged by default, and the suggester is asked (Yes/No buttons); "No" sets the entry's `separate` flag so it gets its own button |
| `orders`, `order_deadline` | Order data |
| `order_round` | Bumped on every spot announcement. The order timer, order modal, and Keep/Switch buttons carry the round they were created in, and are ignored if the host has switched spots since |
| `dropped_out` | Invitees who tapped "Can't make it" after the spot was announced (listed in the order summary) |
| `uid` | Unique ID for this party, stamped on every button/modal via `party_ref` |
| `timer` | The party's one pending deadline, `{"kind", "due", ...}`: see Timers |
| `minutes` | How long each timed step lasts (`rsvp`, `suggestion`, `vote`, `order`), set by the host on the invite form (defaults in `DEFAULT_MINUTES`) |

### Phase state machine

```
awaiting_invitees
  -> awaiting_rsvps          (host picks people in the invite form)
       -> [released, NOBODY_ACCEPTED]        (nobody accepted in time)
       -> awaiting_spot_method               (at least one accept)
            -> awaiting_spot_name             ("I've already decided" -> spot form)
            -> collecting_suggestions         ("Let them suggest")
                 -> awaiting_host_fallback_spot  (no suggestions in time -> "Pick a spot" form)
                 -> collecting_votes             (suggestions came in)
                      -> awaiting_host_fallback_spot  (no votes in time -> tap a suggestion, or "Another spot" form)
                      -> awaiting_spot_approval     (clear winner -> host taps "Go with <spot>", "Another spot" form, or Cancel)
                           -> awaiting_orders
                      -> awaiting_tiebreak          (top spots tied -> host taps one, or "Another spot" form)
                           -> awaiting_orders
            -> awaiting_orders   (host entered or picked a spot, from any path above)
                 -> awaiting_orders         (host switched to an invitee's "Suggest somewhere else" spot:
                                             orders cleared, order_round bumped, fresh order window)
                 -> [released, ALL_DROPPED_OUT]  (every invitee tapped "Can't make it")
                 -> awaiting_confirmation   (everyone ordered, or the order window elapsed)
                      -> awaiting_bills      (host taps "I placed the order"; skipped if nobody ordered)
                           -> awaiting_eta   (host sends the bills form, or taps "Skip")
                           -> awaiting_arrival  (host sends an ETA in the form, or taps "No ETA"; host is unlocked)
                                -> [released]   (host taps "The order arrived", or ARRIVAL_WAIT_HOURS (3) pass)

Any phase that waits on the host (awaiting_invitees, awaiting_spot_method,
awaiting_spot_name, awaiting_host_fallback_spot, awaiting_tiebreak,
awaiting_spot_approval, awaiting_confirmation, awaiting_bills, awaiting_eta)
-> [released, PARTY_TIMED_OUT] after HOST_IDLE_MINUTES (60) with no reply.

From awaiting_confirmation onwards, "There's a problem" opens a form where the host
writes what happened and must choose: cancel (-> [released], everyone told) or carry on.
```

The host can cancel at any point: the red "Cancel party" button on their step messages, or `/matcha-party` while a party is running (which replies with a Cancel button). Typing "cancel" in the DM also still works. All of these go to `cancel_party`, which tears down (`release_party`) and notifies anyone who was invited or had already joined.

**No typed input.** Every step is a button or a form (Slack modal): the invite list is a people picker (`multi_users_select`) in the start message itself, since inside a form Slack only shows two names before it has to be expanded (picks are also saved on the party by `handle_invitee_select`; Send invites opens a step-times form), and spot names, suggestions and the ETA use one-field forms (`open_text_modal` → `handle_text_modal`, keyed by `purpose`). Once a step's form is sent, the buttons on the message that opened it are removed (`_strip_buttons`). Anything typed in the DM during a party just gets a "use the buttons" nudge.

**Changing an order.** After submitting, the invitee gets a "Change my order" button that reopens the order form filled in with their last order. It works until ordering closes, which happens at the deadline or as soon as every accepted invitee has ordered.

`release_party` only unlocks users whose `active_users` entry still points at this party, so someone who declined and has since joined another party isn't freed from that one by mistake.

### Timers

Each party has at most one pending deadline, stored on the party as `timer` (`set_timer`) and saved to `party_state.json`. A background thread (`timer_loop`) calls `run_due_timers` every 5 seconds, which disarms and fires anything due. Because deadlines live on disk, a restart picks them back up, and anything that came due while the bot was down fires as soon as it's back. Each handler checks the party is still in the expected `phase` before acting, so a stale timer is a no-op.

- RSVPs, suggestions, votes and orders last as long as the host set on the invite form (1 to 60 minutes each, starting at 5, 5, 3 and 5; `step_seconds`)
- RSVPs: `on_rsvp_window_end`
- Suggestions: `on_suggestion_window_end`
- Votes: `on_vote_window_end`
- Orders: from spot announcement (`on_order_window_end`), restarted if the host switches spots
- Host idle: 60 minutes at any step waiting on the host (`on_host_idle`), closes the party
- Arrival: 3 hours after the ETA step (`on_arrival_wait_end`), closes the party quietly if nobody tapped "The order arrived"

The order deadline shown to invitees is in Riyadh time (`RIYADH_TZ`, fixed UTC+3), regardless of the server's time zone.

The RSVP and order windows also close early once everyone relevant has responded: `on_rsvp_window_end` runs immediately once `pending_rsvps` empties out, suggestions close once every accepted invitee has suggested at least one spot, voting closes once all of them have voted, and `send_order_summary` runs as soon as every accepted invitee has ordered.

### Concurrency

Slack handlers run on multiple threads, and the timer thread runs alongside them, all doing load → change → save on `party_state.json`. Every handler and the timer loop run under one re-entrant lock (`state_lock`, via the `@locked` decorator), so two simultaneous taps can't overwrite each other.

### Failure handling and limits

- All party messages go through `dm()` / `post()`, which log a failed send instead of raising, so one undeliverable person doesn't stop a loop over everyone else.
- Bots, deactivated accounts, and anyone whose invite DM fails are reported to the host by name (`INVITE_UNREACHABLE`) and never locked.
- Free text is capped: spot names `SPOT_MAX_LEN` (60, since they become vote buttons and Slack caps button labels at 75), order fields `ORDER_FIELD_MAX_LEN` (100), ETA `ETA_MAX_LEN` (100). Vote buttons are split into blocks of 25 (Slack's per-block limit).
- Buttons that only work during one window (invites, suggestion prompts and suggestion messages, votes, order messages) are tracked per party in `party["live_msgs"]` (`dm_live`). When the window closes, `close_live` removes their buttons and adds a short italic line saying why (`LINE_*` in `messages.py`); `release_party` does the same for anything still live. A tap that slips in just as a window closes is answered on that same message (`_close_in_place`), never as a new message at the bottom of the chat. Only forms submitted late (they had one open) get a DM.

### Privacy: busy invitees look like ordinary declines

If someone the host @-mentions is already tied up in another party (as host or invitee), they become a **ghost**: they're listed in "Invited: …" like everyone else (in the host's original mention order), but they're never messaged, never locked to this party, and are auto-declined 90–150 seconds later (`party["ghosts"]`, fired by `run_due_timers` → `on_ghost_decline`). To the host it looks exactly like that person tapped "Can't make it". The randomized delay keeps a fixed timing from becoming a tell, and the RSVP window waits for ghosts like any pending invitee, so closing early can't give them away either.

Ghosts are excluded from every message a party sends to its guests (`real_guests`), so they never learn the party existed, and `unlock_if_in` makes sure tearing this party down never frees them from the party they're actually in.

### Onboarding relay (unchanged legacy feature)

Separate from Matcha Party: `/start` (admin-only) sends `TEAM_MEMBER_USER_ID` a one-time setup questionnaire. Anything that teammate sends back in that DM (text, files, emoji reactions) is relayed to `ADMIN_USER_ID`, and anything the admin DMs the bot is relayed back to the teammate. This logic lives in `handle_message` and `handle_reaction`. Only the admin and the teammate use it, and only while the sender isn't in a Matcha Party: once someone is in a party, every DM they send is handled by the party (with a "nothing to reply to right now" nudge if the current step doesn't expect text), so nothing typed mid-party gets relayed.

---

## 3. Extending the bot

- **Changing message wording**: edit the relevant constant in `messages.py`. Keep `matcha-bot-messages.md` in sync if the change is user-facing (that file is written for a non-technical reader reviewing copy, not developers).
- **Adding a new order field**: follow the pattern used for sweetness: add a block to the modal in `handle_place_order`, extract it in `handle_order_submission`, store it on `party["orders"][user_id]`, and include it in `ORDER_SUMMARY_LINE` in `send_order_summary`.
- **Adding a new phase**: remember every phase transition must (a) `save_state`, (b) message whoever needs to act next, and (c) if it's a terminal/scrap path, call `release_party` to unlock the host and all invitees: otherwise those users stay locked out of starting or joining anything else.
