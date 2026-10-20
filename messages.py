"""All Matcha Bot–facing text lives here, separate from bot.py's logic, so
wording can be tweaked without touching any of the actual behavior.
"""

# ── Setup / onboarding ────────────────────────────────────────────────────────

# Sent to the teammate (Nouf) in her DM with the bot, the first time the
# setup questionnaire goes out. Triggered by send_setup_questions(), which
# runs on /start.
SETUP_QUESTIONS = (
    "Good morning Nouf! 🍵 Your matcha bot is cooking, list all of your "
    "requirements here! Reply however you'd like (text, emoji reactions, "
    "whatever), it all gets passed along, no fixed format needed."
)

# Sent to the admin right after the setup questionnaire above goes out to the
# teammate, confirming it was sent. Used in send_setup_questions().
SETUP_SENT_CONFIRMATION = (
    "Sent the Matcha Bot setup questionnaire to <@{team_member_id}>. "
    "I'll forward their replies and reactions here as they come in. "
    "Anything you DM me, I'll pass straight on to them too."
)

# Sent to the admin when a file the teammate uploaded couldn't be passed on
# (after a few upload attempts). Used in handle_message(), formatted with the
# file names. FILE_FORWARD_SCOPE_HINT is added when the cause was permissions.
FILE_FORWARD_FAILED_TO_ADMIN = "⚠️ Couldn't forward the file(s) from Nouf ({names}). Ask her to send it again."

# Sent to the admin when a file they uploaded couldn't be passed on to the
# teammate (after a few upload attempts). Used in handle_message(), formatted
# with the file names and the teammate's ID.
FILE_FORWARD_FAILED_TO_TEAMMATE = "⚠️ Couldn't forward the file(s) ({names}) to <@{team_member_id}>. Please try sending it again."

# Added to the two messages above only when Slack refused the download for
# missing permissions.
FILE_FORWARD_SCOPE_HINT = (
    "The bot seems to be missing the 'files:read' scope (OAuth & Permissions), "
    "so add it and reinstall the app first."
)

# ── Matcha Party: starting ────────────────────────────────────────────────────
# Anyone can run /matcha-party now. Whoever runs it is that party's "host" , 
# every message below marked "to the host" goes to that person specifically,
# not to a fixed admin. Many parties can run at once; see "active_users" in
# bot.py for how a person can only be tied up in one at a time.


# Sent to the host (via `respond`) if they run /matcha-party while they're
# already hosting one. Used in handle_matcha_party_command().
PARTY_ALREADY_IN_PROGRESS = (
    "A Matcha Party is already in progress. Tap below if you want to scrap "
    "it and start over."
)

# Sent (via `respond`) if someone runs /matcha-party while they're already
# tied up in someone else's party (invited and not yet declined). Used in
# handle_matcha_party_command().
BUSY_IN_ANOTHER_PARTY = (
    "You're already part of someone else's Matcha Party right now. Finish "
    "up or decline there before starting your own."
)

# Sent (via `respond`) if /matcha-party is run from a channel instead of the
# host's own DM with the bot. Used in handle_matcha_party_command().
PARTY_DM_ONLY = "Run /matcha-party from your DM with me, not a channel."

# Replied (only visible to them) when someone not in MATCHA_ALLOWED_HOSTS runs
# /matcha-party, or DMs the bot, while starting parties is limited to a few
# people. Used in handle_matcha_party_command() and handle_message().
PARTY_NOT_OPEN_YET = "Matcha Party isn't open to everyone yet. Check back soon!"

# DMed to anyone (other than the admin and teammate, whose DMs are relayed)
# who messages the bot outside a party. Used in handle_message().
DM_HELLO = "Hi! Run /matcha-party here to start a group matcha order."

# DMed to the host right after start_party_flow() kicks off, asking them to
# @-mention the invitees. Used in start_party_flow().
ASK_INVITEES = (
    "Matcha Party started :matcha-salute:\n"
    "Who wants to order matcha? Pick people below, then tap Send invites"
)


# DMed to the host if nobody they mentioned can get an invite at all (bots,
# deactivated accounts, failed DMs), followed by INVITE_UNREACHABLE. People
# busy in another party never trigger this, they're shown as invited and
# auto-declined instead. Used in handle_invitee_reply().
COULDNT_INVITE_ANYONE = "Couldn't invite anyone from that. Try again with some different people."

# DMed to the host when they type "cancel" while hosting an active party.
# Used in handle_message(), in the host-DM branch's cancel check.
PARTY_CANCELLED = "Party scrapped. Run /matcha-party whenever you want to start another."

# DMed to every guest (anyone invited and not yet declined, accepted or
# still awaiting RSVP) when the host cancels. Used in handle_message(), same
# cancel branch as PARTY_CANCELLED above.
PARTY_CANCELLED_NOTICE = "{host} scrapped the Matcha Party."

# ── Matcha Party: RSVPs ───────────────────────────────────────────────────────
# New stage: being @-mentioned no longer auto-includes someone. Each invitee
# is asked to accept or decline before they count as "in".

# DMed to each invitee once the host picks them, with BUTTON_RSVP_ACCEPT /
# BUTTON_RSVP_DECLINE buttons attached. Used in handle_invitee_reply(),
# formatted with the host's mention.
RSVP_PROMPT = "{host} wants to order matcha with you! Want to join? :cute-matcha:"

# Label for the button (action_id "party_rsvp_accept") on the RSVP_PROMPT
# message. Used in handle_invitee_reply().
BUTTON_RSVP_ACCEPT = "I'm in!"

# Label for the button (action_id "party_rsvp_decline") on the RSVP_PROMPT
# message. Used in handle_invitee_reply().
BUTTON_RSVP_DECLINE = "Can't make it"

# DMed to an invitee right after they tap BUTTON_RSVP_ACCEPT, confirming it
# landed. Used in handle_rsvp_accept().
RSVP_ACCEPTED_CONFIRMATION = "You're in! I'll let you know once the spot's decided."

# DMed to an invitee right after they tap BUTTON_RSVP_DECLINE, confirming it
# landed. Used in handle_rsvp_decline().
RSVP_DECLINED_CONFIRMATION = "No worries, maybe next time!"

# DMed to the host right after invites go out, confirming who was invited.
# Used in invite_people(), formatted with the invited names and how long
# invites stay open.
RSVP_SENT_TO_HOST = "Invited: {names}. I'll let you know as they respond (give it up to {minutes})."

# DMed to the host if nobody accepted by the time RSVPs closed (all declined,
# or the invite window ran out), the party is auto-scrapped at this point. Used in on_rsvp_window_end().
NOBODY_ACCEPTED = "Nobody accepted your invite, so I've scrapped this Matcha Party."

# DMed to the host once RSVPs close (only the lines that apply), listing who
# said they can't make it and who never answered, separately. Used in
# on_rsvp_window_end(), formatted with their names.
RSVP_DECLINED_LIST = "Can't make it: {names}"
RSVP_NO_ANSWER_LIST = "Didn't answer: {names}"

# ── Matcha Party: deciding the spot ───────────────────────────────────────────

# DMed to the host (as the text of a message with BUTTON_DECIDED /
# BUTTON_SUGGEST buttons attached) once RSVPs close with at least one
# acceptance, asking how the spot will be chosen. Used in
# on_rsvp_window_end(), formatted with the accepted invitees' display names.
ASK_SPOT_METHOD = "{names} are in! Do you already know the spot, or want the group to suggest one?"

# Same as ASK_SPOT_METHOD, for when exactly one person accepted. Used in
# on_rsvp_window_end(), formatted with that invitee's display name.
ASK_SPOT_METHOD_ONE = "{name} is in! Do you already know the spot, or want the group to suggest one?"

# Label for the button (action_id "party_spot_decided") on the ASK_SPOT_METHOD
# message, for when the host already knows the spot. Used in
# on_rsvp_window_end().
BUTTON_DECIDED = "I've already decided"

# Label for the button (action_id "party_spot_suggest") on the ASK_SPOT_METHOD
# message, for letting invitees suggest spots. Used in on_rsvp_window_end().
BUTTON_SUGGEST = "Let them suggest"


# DMed to every accepted invitee after the host taps BUTTON_SUGGEST, opening
# the suggestion window. Used in handle_spot_suggest(), formatted
# with the host's mention.
SUGGESTION_PROMPT = (
    "Matcha Party time! {host} invited you to the party. Suggest a spot to "
    "order from within {minutes}. You can suggest as many as you like. Voting "
    "starts once everyone has suggested at least one :matcha-kitty:"
)

# DMed to the host if nobody suggested a spot within the suggestion window,
# asking what to do next (pause-and-ask fallback). Used in
# on_suggestion_window_end().
NO_SUGGESTIONS_FALLBACK = (
    "Nobody suggested a spot within {minutes}. Pick a spot yourself, or "
    "cancel this party."
)

# Header text on the vote message (with one button per suggestion) sent to
# every accepted invitee once suggestions are in. Used in
# on_suggestion_window_end().
VOTE_PROMPT_HEADER = "Suggestions are in! Vote for your favorite, you've got {minutes}:"

# DMed to the host if nobody voted within the voting window, asking what to
# do next (pause-and-ask fallback), listing the suggestions that came in.
# Used in on_vote_window_end().
NO_VOTES_FALLBACK = (
    "Nobody voted within {minutes}. Pick one of the suggestions, choose "
    "another spot, or cancel this party."
)

# DMed to the host once voting closes with a clear winner, showing the tally
# and the winning spot, with BUTTON_GO_WITH, BUTTON_ANOTHER_SPOT and Cancel.
# Nobody orders until the host answers. Used in on_vote_window_end().
VOTE_RESULTS_TO_HOST = (
    "Voting results:\n{breakdown}\nWinner: *{winner}*\nGo with it, choose "
    "another spot, or cancel the party?"
)

# Button on VOTE_RESULTS_TO_HOST that approves the winning spot. Used in
# _ask_host_to_pick(), formatted with the spot.
BUTTON_GO_WITH = "Go with {spot}"

# DMed to the host instead of VOTE_RESULTS_TO_HOST when two or more spots tie
# for the most votes, with a button per tied spot. Used in
# on_vote_window_end(), formatted with the vote breakdown and the tied spots.
VOTE_RESULTS_TIE = (
    "Voting results:\n{breakdown}\nIt's a tie between {tied}! Tap the one you"
    " want to go with, or choose another spot."
)



# DMed to an invitee right after they tap a vote button, confirming it landed.
# Used in handle_vote().
VOTE_RECEIVED_CONFIRMATION = "Got your vote, thanks!"

# DMed to an invitee right after they reply with a spot suggestion, confirming
# it landed, with a BUTTON_REMOVE_SUGGESTION button. Used in
# handle_suggestion_reply(), formatted with the spot.
SUGGESTION_RECEIVED_CONFIRMATION = "Got your suggestion: *{spot}*. Thanks!"

# Sent instead of SUGGESTION_RECEIVED_CONFIRMATION when the suggestion is one
# typo away from a spot already in. They're counted as the same spot unless
# the suggester taps BUTTON_MERGE_NO. Comes with BUTTON_MERGE_YES /
# BUTTON_MERGE_NO / BUTTON_REMOVE_SUGGESTION. Used in
# handle_suggestion_reply(), formatted with what they typed and the match.
SUGGESTION_MERGE_ASK = (
    "Got your suggestion: *{spot}*. Is that the same place as *{match}*, "
    "which someone already suggested? I'll count them together unless you "
    "say otherwise."
)

# Button labels on SUGGESTION_MERGE_ASK. Used in _suggestion_blocks().
BUTTON_MERGE_YES = "Yes, same place"
BUTTON_MERGE_NO = "No, different place"

# Replaces SUGGESTION_MERGE_ASK after BUTTON_MERGE_YES (Remove button stays).
# Used in handle_merge_yes(), formatted with what they typed and the match.
SUGGESTION_MERGE_CONFIRMED = "Got it, *{spot}* counts as *{match}*."

# Replaces SUGGESTION_MERGE_ASK after BUTTON_MERGE_NO (Remove button stays).
# Used in handle_merge_no(), formatted with what they typed.
SUGGESTION_KEPT_SEPARATE = "Got it, *{spot}* will be its own option on the vote."

# Label for the button (action_id "party_remove_suggestion") on
# SUGGESTION_RECEIVED_CONFIRMATION. Works until voting starts. Used in
# handle_suggestion_reply().
BUTTON_REMOVE_SUGGESTION = "Remove"



# DMed to whoever types a spot name (a suggestion, or the host's own pick)
# longer than SPOT_MAX_LEN in bot.py. Spot names end up on vote buttons, which
# Slack caps at 75 characters. Used in handle_suggestion_reply() and
# handle_host_spot_name(), formatted with the limit.
SPOT_TOO_LONG = "That's a bit long. Keep the spot name under {max} characters and send it again."

# DMed to an invitee who replies with a suggestion after the
# suggestion window closed. Used in handle_message().
SUGGESTION_WINDOW_CLOSED = "Suggestions are closed for this one, sorry!"


# ── Matcha Party: ordering ────────────────────────────────────────────────────

# DMed to every accepted invitee once the spot is decided (whichever path got
# there), along with a "Place your order" button. Used in announce_spot(),
# formatted with the host's mention, the spot name, and the order deadline.
SPOT_ANNOUNCEMENT = (
    "{host} invited you to the *{spot}* party! Tap below to send your "
    "order, you've got until {deadline} :meow_matcha:"
)

# Label for the button (action_id "party_place_order") on the SPOT_ANNOUNCEMENT
# message, which opens the order modal. Used in announce_spot().
PLACE_ORDER_BUTTON = "Place your order"

# Label for the button (action_id "party_order_decline") on the
# SPOT_ANNOUNCEMENT message, letting an invitee drop out once they see the
# spot. Used in announce_spot().
ORDER_DECLINE_BUTTON = "Can't make it"

# Label for the button (action_id "party_suggest_other") on the
# SPOT_ANNOUNCEMENT message. Only shown when the host picked the spot
# themselves (not when it won a vote). Used in announce_spot().
SUGGEST_OTHER_BUTTON = "Suggest somewhere else"

# DMed to every accepted invitee when the host switches to an invitee's
# alternative spot, right before the fresh SPOT_ANNOUNCEMENT. Used in
# handle_switch_spot(), formatted with the host's mention and the new spot.
SPOT_CHANGED_NOTICE = (
    "Change of plans: {host} switched the party to *{spot}*. If you already"
    " ordered, please order again below."
)

# Title of the order modal opened when an invitee taps PLACE_ORDER_BUTTON.
# Used in handle_place_order().
ORDER_MODAL_TITLE = "Your matcha order"

# Submit-button label on the order modal. Used in handle_place_order().
ORDER_MODAL_SUBMIT = "Submit"

# Field label for the drink-name input on the order modal. Used in
# handle_place_order().
DRINK_LABEL = "Drink name"

# Field label for the optional size input on the order modal. Used in
# _order_modal_view().
SIZE_LABEL = "Size (optional)"

# Field label for the optional comments box at the bottom of the order modal.
# Used in _order_modal_view().
COMMENTS_LABEL = "Comments (optional)"

# Added after an order's details in the summary and the grey line when the
# invitee wrote comments. Used in order_details(), formatted with them.
ORDER_COMMENTS = " · Comments: {comments}"

# Field label for the milk-type input on the order modal. Used in
# handle_place_order().
MILK_LABEL = "Milk type"

# Field label for the with/without-cream input on the order modal. Used in
# handle_place_order().
CREAM_LABEL = "With or without cream?"

# Radio-button option label for "with cream" on the order modal, and also
# used as the stored/displayed value for that choice. Used in
# handle_place_order() (modal option) and handle_order_submission() (stored
# order value).
CREAM_WITH = "With cream"

# Radio-button option label for "without cream" on the order modal, and also
# used as the stored/displayed value for that choice. Used in
# handle_place_order() (modal option) and handle_order_submission() (stored
# order value).
CREAM_WITHOUT = "Without cream"

# Field label for the sweetness-level input on the order modal. Used in
# handle_place_order().
SWEETNESS_LABEL = "Sweetness level"

# Radio-button option for "Default" on the order modal (the restaurant's
# usual sweetness), and what's stored and shown in the summary for it. Used
# in _order_modal_view() and _SWEETNESS.
SWEETNESS_DEFAULT = "Default"
SWEETNESS_DEFAULT_VALUE = "Default sweetness"

# Radio-button option label for "Sweet" on the order modal, and also used as
# the stored/displayed value for that choice. Used in handle_place_order()
# (modal option) and handle_order_submission() (stored order value).
SWEETNESS_SWEET = "Sweet"

# Radio-button option label for "Less Sweet" on the order modal, and also
# used as the stored/displayed value for that choice. Used in
# handle_place_order() (modal option) and handle_order_submission() (stored
# order value).
SWEETNESS_LESS_SWEET = "Less Sweet"

# Radio-button option label for "No Sweet" on the order modal, and also used
# as the stored/displayed value for that choice. Used in handle_place_order()
# (modal option) and handle_order_submission() (stored order value).
SWEETNESS_NO_SWEET = "No Sweet"

# DMed to an invitee right after they submit the order modal, confirming it
# landed. Used in handle_order_submission().
ORDER_RECEIVED_CONFIRMATION = "Got your order, thanks! You can change it until ordering closes."

# DMed to an invitee who submits an order modal that was opened before the
# host switched spots, so the order is for the old spot and isn't saved.
# Used in handle_order_submission().
# DMed to an invitee who taps a button (or submits a form) after the order
# window closed, or after the party ended. Used in _order_target() and
# handle_order_submission().
ORDER_CLOSED = "Ordering's closed for this party, sorry!"


ORDER_STALE = (
    "The spot changed before your order went through. Please order again "
    "from the latest message."
)

# ── Matcha Party: dropping out or suggesting another spot ────────────────────

# DMed to an invitee right after they tap ORDER_DECLINE_BUTTON. Used in
# handle_order_decline().
ORDER_DECLINED_CONFIRMATION = "No worries, I've taken you off this one. Maybe next time!"

# DMed to the host when an invitee taps ORDER_DECLINE_BUTTON. Used in
# handle_order_decline(), formatted with the invitee's name and the spot.
ORDER_DECLINED_TO_HOST = "{name} can't make it to *{spot}*, so they're out of this party."

# DMed to the host when the last remaining invitee drops out, scrapping the
# party. Used in handle_order_decline().
ALL_DROPPED_OUT = "Everyone dropped out, so I've scrapped this Matcha Party."

# Title of the modal opened by SUGGEST_OTHER_BUTTON (Slack caps modal titles
# at 24 characters). Used in handle_suggest_other().
ALT_SPOT_MODAL_TITLE = "Suggest another spot"

# Submit-button label on the alternative-spot modal. Used in
# handle_suggest_other().
ALT_SPOT_MODAL_SUBMIT = "Send"

# Field label on the alternative-spot modal. Used in handle_suggest_other().
ALT_SPOT_LABEL = "Where would you rather order from?"

# DMed to an invitee right after they submit the alternative-spot modal.
# Used in handle_alt_spot_submission(), formatted with the host's mention.
ALT_SPOT_SENT_CONFIRMATION = "Sent your suggestion to {host}. I'll let you know what they decide."

# DMed to the host when an invitee suggests another spot, along with
# BUTTON_KEEP_SPOT / BUTTON_SWITCH_SPOT. Used in handle_alt_spot_submission().
ALT_SPOT_SUGGESTED_TO_HOST = "{name} would rather order from *{suggestion}* instead of *{spot}*."

# Button labels on ALT_SPOT_SUGGESTED_TO_HOST. Used in
# handle_alt_spot_submission().
BUTTON_KEEP_SPOT = "Keep current spot"
BUTTON_SWITCH_SPOT = "Switch to this one"


# DMed to the invitee who suggested another spot when the host keeps the
# current one. Used in handle_keep_spot().
ALT_SPOT_KEPT = (
    "{host} is sticking with *{spot}*. You can still place your order, or "
    "tap Can't make it."
)



# DMed to an invitee who taps "Suggest somewhere else", or submits that form,
# after ordering closed. Used in handle_suggest_other() and
# handle_alt_spot_submission().
ALT_SPOT_TOO_LATE_CLOSED = "Too late to suggest another spot, ordering's already closed."

# DMed to an invitee whose "Suggest somewhere else" form is submitted after
# the host already switched spots, so it isn't sent. Used in
# handle_alt_spot_submission(), formatted with the current spot.
ALT_SPOT_TOO_LATE_CHANGED = (
    "The spot changed to *{spot}* before your suggestion went through, so I "
    "didn't send it. Suggest again from the latest message if you'd like."
)

# ── Matcha Party: wrap-up ─────────────────────────────────────────────────────

# First line of the order summary DMed to the host once ordering closes.
# Used in send_order_summary(), formatted with the spot name.
ORDER_SUMMARY_HEADER = "Order summary for *{spot}*:"

# One line per accepted invitee who ordered, appended to the order summary.
# Used in send_order_summary(), formatted with each invitee's name and order
# details (see order_details()).
ORDER_SUMMARY_LINE = "• *{name}*: {order}"

# Line listing accepted invitees who never ordered, appended to the order
# summary (only if there are any). Used in send_order_summary().
ORDER_SUMMARY_MISSING = "Didn't order: {names}"

# Line listing invitees who tapped ORDER_DECLINE_BUTTON, appended to the order
# summary (only if there are any). Used in send_order_summary().
ORDER_SUMMARY_DROPPED_OUT = "Can't make it: {names}"

# Label for the button (action_id "party_confirm_sent") on the order summary
# message, for the host to confirm they placed the order. Used in
# send_order_summary().
CONFIRM_ORDER_BUTTON = "I placed the order ✅"

# DMed to the host right after they tap CONFIRM_ORDER_BUTTON, acknowledging
# it while the invitee confirmations go out. Used in handle_confirm_sent().
ORDER_SENT_ACK = "Noted! Letting everyone know the order's in."

# DMed to every accepted invitee right after the host taps CONFIRM_ORDER_BUTTON,
# letting them know the order was actually sent in. Used in handle_confirm_sent().
ORDER_SENT_TO_INVITEES = "Heads up, {host} just sent off the Matcha Party order!"

# DMed to the host right after ORDER_SENT_ACK, asking for an ETA to pass
# along to invitees, optional, since the host may not have one yet. Used in
# handle_confirm_sent().
ASK_ETA = "Got an ETA for when it'll arrive?"

# DMed to every accepted invitee if the host replies to ASK_ETA with an
# actual ETA (anything other than "skip"/"no"/"none"/"n/a"). Used in
# handle_host_eta_reply(), formatted with the host's ETA text.
ETA_ANNOUNCEMENT = "ETA on the matcha: {eta}"

# DMed to the host if their ETA reply is longer than ETA_MAX_LEN in bot.py.
# Used in handle_host_eta_reply(), formatted with the limit.
ETA_TOO_LONG = "That's a bit long. Keep the ETA under {max} characters and send it again."


# ── Matcha Party: edge cases ──────────────────────────────────────────────────

# DMed to the host when some people they @-mentioned can't get an invite at
# all (bots, deactivated accounts, or a DM that failed to send). Not used for
# people busy in another party, those are dropped silently. Used in
# handle_invitee_reply(), formatted with their names.
INVITE_UNREACHABLE = "Couldn't send an invite to: {names}"


# DMed to the host when a step waiting on them (picking invitees, the spot,
# confirming the order, or the ETA) goes unanswered for HOST_IDLE_MINUTES in
# bot.py, closing the party. Used in on_host_idle(), formatted with the
# minutes.
PARTY_TIMED_OUT = (
    "No reply for {minutes} minutes, so I've closed this Matcha Party. Run "
    "/matcha-party to start another."
)

# DMed to everyone invited or joined when the party closes for inactivity
# (unless the order was already sent). Used in on_host_idle(), formatted with
# the host's mention.
PARTY_TIMED_OUT_NOTICE = "{host}'s Matcha Party went quiet, so I've closed it."

# DMed to the host if they type something when no reply is expected (e.g.
# while RSVPs or votes are still coming in). Used in handle_message().
HOST_NOTHING_TO_REPLY = "No need to type anything here. Just use the buttons in my messages above."

# DMed to an invitee if they type something when no reply is expected. Used
# in handle_message().
INVITEE_NOTHING_TO_REPLY = "No need to type anything here. Just use the buttons in my messages above."

# ── Matcha Party: buttons and forms ───────────────────────────────────────────

# The people picker and button on ASK_INVITEES. Send invites opens a small
# form for the step times. Used in start_party_flow().
INVITE_PICKER_PLACEHOLDER = "Pick people"
BUTTON_SEND_INVITES = "Send invites"

# The step-times form opened by BUTTON_SEND_INVITES, listing who's being
# invited (Slack caps form titles at 24 characters). Used in
# handle_send_invites().
INVITE_MODAL_TITLE = "Invite to Matcha Party"
INVITE_MODAL_SUBMIT = "Send invites"
INVITE_MODAL_PEOPLE = "Inviting: *{names}*"

# The step times on that form, in minutes (1 to 60). Used in
# handle_send_invites().
STEP_TIMES_HEADER = "*How long each step lasts* (in minutes)"
STEP_TIMES_RSVP = "Answering the invite"
STEP_TIMES_SUGGESTION = "Suggesting spots"
STEP_TIMES_VOTE = "Voting"
STEP_TIMES_ORDER = "Ordering"
STEP_TIMES_SUGGEST_HINT = "Only used if you let the group suggest"

# Shown only to the host (under ASK_INVITEES) if they tap Send invites with
# nobody picked, or only themselves. Used in handle_send_invites().
INVITE_PICK_SOMEONE = "Pick at least one person other than you."

# Red button on the host's messages (and on PARTY_ALREADY_IN_PROGRESS) that
# scraps the party. Used in _cancel_btn().
BUTTON_CANCEL_PARTY = "Cancel party"

# Button on SUGGESTION_PROMPT that opens the suggestion form. Stays usable,
# so people can suggest more than one spot. Used in handle_spot_suggest().
BUTTON_SUGGEST_SPOT = "Suggest a spot"

# Button on NO_SUGGESTIONS_FALLBACK that opens the spot form for the host.
BUTTON_PICK_SPOT = "Pick a spot"

# Button next to the listed spots on NO_VOTES_FALLBACK and VOTE_RESULTS_TIE,
# for the host to enter a different spot. Used in _ask_host_to_pick().
BUTTON_ANOTHER_SPOT = "Another spot"

# One-field forms. Used in open_text_modal().
SPOT_MODAL_TITLE = "Where are we ordering?"
SUGGEST_MODAL_TITLE = "Suggest a spot"
SPOT_MODAL_LABEL = "Spot name"
ETA_MODAL_TITLE = "When will it arrive?"
ETA_MODAL_LABEL = "ETA (e.g. 20 minutes or 3:30 PM)"
MODAL_SUBMIT_SEND = "Send"

# Button on the "Got your order" message, reopening the order form filled in
# with their last order. Works until ordering closes. Used in
# handle_order_submission().
BUTTON_CHANGE_ORDER = "Change my order"

# Sent instead of ORDER_RECEIVED_CONFIRMATION when someone changes an order
# they already sent. Used in handle_order_submission().
ORDER_UPDATED_CONFIRMATION = "Updated your order! You can still change it until ordering closes."

# Buttons on ASK_ETA. Used in handle_confirm_sent().
BUTTON_ADD_ETA = "Add ETA"
BUTTON_NO_ETA = "No ETA"

# DMed to the host after the ETA step, with BUTTON_ORDER_ARRIVED. Used in
# handle_host_eta_reply().
WAITING_FOR_ARRIVAL = "Noted! Tap below when the order arrives and I'll let everyone know."
BUTTON_ORDER_ARRIVED = "The order arrived"

# DMed to everyone in the party when the host taps BUTTON_ORDER_ARRIVED.
# Used in handle_order_arrived().
ORDER_ARRIVED_NOTICE = "The matcha has arrived! Come grab yours :matcha-lahloob:"



# ── Matcha Party: closed buttons ──────────────────────────────────────────────

# When a window closes, the buttons on its messages are removed and one of
# these is shown under the message as a small grey line, saying why (and,
# where it applies, what that person answered, in bold). Also shown on the
# message itself (not as a new message) if someone taps a button just as it
# closes. Used via close_live() and _close_in_place().
LINE_INVITE_CLOSED = "This invite has closed"
LINE_SUGGESTIONS_CLOSED = "Suggestions have closed"
LINE_VOTING_CLOSED = "Voting has closed"
LINE_ORDERING_CLOSED = "Ordering has closed"
LINE_SPOT_CHANGED = "The spot changed, see the newer message below"
LINE_DROPPED_OUT = "You're out of this one"
LINE_PARTY_CLOSED = "This party has closed"

# Versions that also show the person's own answer. Used in rsvp_line(),
# vote_line(), suggest_prompt_line() and order_line().
LINE_INVITE_CLOSED_IN = "This invite has closed · You said *you're in*"
LINE_INVITE_CLOSED_OUT = "This invite has closed · You said *you can't make it*"
LINE_VOTING_CLOSED_VOTED = "Voting has closed · You voted for *{spot}*"
LINE_VOTING_CLOSED_NO_VOTE = "Voting has closed · You didn't vote"
LINE_SUGGESTIONS_CLOSED_SUGGESTED = "Suggestions have closed · You suggested *{spots}*"
LINE_SUGGESTIONS_CLOSED_NONE = "Suggestions have closed · You didn't suggest a spot"
LINE_ORDERING_CLOSED_ORDERED = "Ordering has closed · Your order: *{order}*"
LINE_ORDERING_CLOSED_NONE = "Ordering has closed · You didn't order"

# Small grey lines under the host's own messages once they've acted on them,
# showing what they chose (the buttons are removed at the same time).
LINE_HOST_INVITED = "Invites sent to *{names}*"
LINE_HOST_LET_THEM_SUGGEST = "You chose *Let them suggest*"
LINE_HOST_SPOT = "You chose *{spot}*"
LINE_HOST_PICKED = "You chose *{spot}*"
LINE_HOST_ALREADY_SETTLED = "This is already settled"
LINE_HOST_KEPT = "You kept *{spot}*"
LINE_HOST_SWITCHED = "You switched to *{spot}* · Orders were reset and everyone has {minutes} more"
LINE_HOST_SUGGESTION_INACTIVE = "This suggestion isn't active anymore"
LINE_HOST_PLACED = "You placed the order"
LINE_HOST_ETA = "ETA sent: *{eta}*"
LINE_HOST_NO_ETA = "You chose *No ETA*"
LINE_HOST_ARRIVED = "You told everyone the order arrived · Party closed"
LINE_HOST_CANCELLED = "You cancelled this party"

# Small grey line under an invitee's suggestion message after they tap Remove.
LINE_SUGGESTION_REMOVED = "You removed this suggestion · You can suggest another anytime before voting starts"

# ── Matcha Party: reporting a problem ─────────────────────────────────────────

# Button on the order summary, the bills question, the ETA question and "Tap
# below when the order arrives", for the host to tell everyone something went
# wrong (e.g. the restaurant rejected the order). Used in _problem_btn().
BUTTON_PROBLEM = "There's a problem"

# The form opened by BUTTON_PROBLEM (Slack caps form titles at 24 characters):
# what happened, then a required choice between cancelling the party and
# carrying on. Used in handle_problem_button().
PROBLEM_MODAL_TITLE = "What happened?"
PROBLEM_MODAL_LABEL = "Tell everyone what happened"
PROBLEM_NEXT_LABEL = "What should happen to the party?"
PROBLEM_NEXT_CANCEL = "Cancel the party"
PROBLEM_NEXT_CARRY_ON = "Carry on"

# DMed to everyone in the party when the host sends the problem form and
# chooses to carry on. Used in handle_problem_submission(), formatted with the
# host's mention, the spot and what the host wrote.
PROBLEM_NOTICE = "Update from {host} about the *{spot}* order: {problem}"

# DMed to the host once PROBLEM_NOTICE has gone out. Used in
# handle_problem_submission().
PROBLEM_SENT = "Sent to everyone in the party. The party carries on, so you can still use the buttons above."

# DMed to everyone in the party when the host sends the problem form and
# chooses to cancel. Used in handle_problem_submission().
PROBLEM_NOTICE_CANCELLED = "Update from {host} about the *{spot}* order: {problem}\nThe party has been cancelled."

# DMed to the host once PROBLEM_NOTICE_CANCELLED has gone out. Used in
# handle_problem_submission().
PROBLEM_CANCELLED = "Sent to everyone and cancelled the party. Run /matcha-party whenever you want to start another."

# ── Matcha Party: bills ───────────────────────────────────────────────────────

# DMed to the host right after they tap CONFIRM_ORDER_BUTTON (skipped if
# nobody ordered), with BUTTON_SEND_BILLS / BUTTON_SKIP_BILLS. Used in
# handle_confirm_sent().
ASK_BILLS = "Want to send everyone their bill? I'll message each person privately."
BUTTON_SEND_BILLS = "Send bills"
BUTTON_SKIP_BILLS = "Skip"

# The bills form: one amount per person who ordered. Used in
# handle_send_bills_button(), the label formatted with the person's name.
BILLS_MODAL_TITLE = "Send bills"
BILLS_MODAL_LABEL = "{name} (SAR)"
BILLS_MODAL_HINT = "Enter 0 if it's on you"

# DMed privately to each person with an amount above 0. Used in
# handle_bills_submission(), formatted with the host's mention, the amount
# and the spot.
BILL_NOTICE = "You owe {host} {amount} SAR for your order from *{spot}*"

# DMed privately instead of BILL_NOTICE when the host enters 0. Used in
# handle_bills_submission(), formatted with the host's mention and the spot.
BILL_FREE_NOTICE = "Your matcha from *{spot}* is on {host} :matcha-kitty:"

# Grey line under ASK_BILLS once the host sends the form (BILL_SENT_ITEM per
# person, or BILL_FREE_ITEM for 0, joined with commas) or taps Skip. Used in handle_bills_submission()
# and handle_skip_bills().
BILL_SENT_ITEM = "{name} {amount} SAR"
BILL_FREE_ITEM = "{name} on you"
LINE_HOST_BILLS_SENT = "Bills sent: *{bills}*"
LINE_HOST_NO_BILLS = "No bills sent"
