# Matcha Bot: All the Things It Says

Hi Nouf! Below is every message the bot sends, in the order they'd actually show up. This matches exactly what's in the bot's code. Feel free to suggest different wording for any of them, just reply with the section name and what you'd change.

Anything in `{curly braces}` gets swapped out automatically (a name, a spot, a time, etc.); leave those as is, just tweak the wording around them.

Anyone in the workspace can run this, not just one fixed person. Whoever starts one becomes the host for that one, and more than one can be running at once, as long as nobody's tied up in two at a time.

Nobody ever has to type in the chat: everything happens through buttons and small pop-up forms.

Once a button has been used (or its time is up), the buttons disappear and a small grey line appears under that message showing what was chosen. For you as the host, that looks like the lines marked *(grey line)* below.

---

## 1. Getting Started

You get things going by typing `/matcha-party` in your DM with the bot (it only works from there, not from a channel).


**If starting parties is limited to a few people for now, and someone else runs it:**
> Matcha Party isn't open to everyone yet. Check back soon!

**If you run it from a channel instead:**
> Run /matcha-party from your DM with me, not a channel.

**If you try to start a new one while yours is still running, with a "Cancel party" button:**
> A Matcha Party is already in progress. Tap below if you want to scrap it and start over.

**If you try to start one while you're already in someone else's:**
> You're already part of someone else's Matcha Party right now. Finish up or decline there before starting your own.

**You run it from your DM, and the bot asks who to invite:**
> Matcha Party started :matcha-salute:
> Who wants to order matcha? Tap below to pick people

* Button: **Pick people**
* Button: **Cancel party** *(this red button is on most of your messages, so you can scrap the party at any step)*

**"Pick people" opens a form:**
* Title: **Invite to Matcha Party**
* Field: **Who's invited?** (search and pick teammates)
* Submit button: **Send invites**

**After you send it:** *(grey line under the question)*
> Invites sent to *{names}*

**If you only picked yourself, the form shows:**
> Pick at least one person other than you.

**If some people can't get an invite at all (bots, deactivated accounts, or a message that failed to send):**
> Couldn't send an invite to: {names}

**If that was everyone you picked, this comes first:**
> Couldn't invite anyone from that. Try again with some different people.

**If you tap "Cancel party", that message gets the grey line "You cancelled this party" (your other messages get "This party has closed"), and you get:**
> Party scrapped. Run /matcha-party whenever you want to start another.

**Anyone who was invited or had already joined then gets told:**
> {host} scrapped the Matcha Party.

*(Whenever a party ends early like this, any buttons still showing on their messages disappear, with this line added: "This party has closed".)*

---

## 2. Accepting or declining

**Each invitee gets this, with two buttons:**
> {host} wants to order matcha with you! Want to join? :cute-matcha:

* Button: **I'm in!**
* Button: **Can't make it**

*(If someone you picked is already in someone else's party, they're still listed as invited, but they never get a message. About 2 minutes later they're counted as "Can't make it", so it looks like a normal decline and nobody can tell they're in another party.)*

**Meanwhile, you get this confirming who was invited:**
> Invited: {names}. I'll let you know as they respond (give it up to 5 minutes).

**Confirmation shown to someone right after they tap "I'm in!":**
> You're in! I'll let you know once the spot's decided.

**Confirmation shown to someone right after they tap "Can't make it":**
> No worries, maybe next time!

**When the invite closes (5 minutes, or once everyone answered), its buttons disappear and a small grey line showing their answer appears under the invite:**
> This invite has closed · You said *you're in*
> This invite has closed · You said *you can't make it*
> This invite has closed *(if they didn't answer)*

**If nobody accepts (everyone declined, or 5 minutes passed):**
> Nobody accepted your invite, so I've scrapped this Matcha Party.

**Once at least one person's in, if anyone declined or never answered, you also get (only the lines that apply):**
> Can't make it: {names}
> Didn't answer: {names}

---

## 3. Deciding where to order from

**Once you know who's actually in, you see this with buttons:**
> {names} are in! Do you already know the spot, or want the group to suggest one?

*(If only one person is in, it says "{name} is in!" instead.)*

* Button: **I've already decided**
* Button: **Let them suggest**
* Button: **Cancel party**

**After you choose:** *(grey line)*
> You chose *Let them suggest* / You chose *{spot}*

**"I've already decided" opens a form:**
* Title: **Where are we ordering?**
* Field: **Spot name**
* Submit button: **Send**

**If you tap "Let them suggest", everyone who's in gets this:**
> Matcha Party time! {host} invited you to the party. Suggest a spot to order from within 5 minutes. You can suggest as many as you like. Voting starts once everyone has suggested at least one :matcha-kitty:

* Button: **Suggest a spot** *(opens a form with a "Spot name" field; it can be used as many times as they like)*

**Confirmation shown to someone right after they suggest a spot:**
> Got your suggestion: *{spot}*. Thanks!

* Button: **Remove** *(works until voting starts)*

**After they tap "Remove", the suggestion stays visible with a grey line under it:**
> You removed this suggestion · You can suggest another anytime before voting starts

*(If someone else suggested the same spot, it stays on the vote.)*

**If someone's suggestion is one typo away from one already in (e.g. "Kultra" after "Kultura"), they're asked instead:**
> Got your suggestion: *{spot}*. Is that the same place as *{match}*, which someone already suggested? I'll count them together unless you say otherwise.

* Button: **Yes, same place**
* Button: **No, different place**
* Button: **Remove**

*(If they don't answer before voting starts, the two are counted as one spot. Capital letters and extra spaces never matter: an exact match just joins, no question. A one-character difference doesn't trigger the question when it's a number, like "Cafe 1" and "Cafe 2", or when the name is under 4 letters, like "Joe" and "Moe".)*

**After "Yes, same place", that message changes to (Remove stays):**
> Got it, *{spot}* counts as *{match}*.

**After "No, different place", it changes to (Remove stays), and their spot gets its own button on the vote:**
> Got it, *{spot}* will be its own option on the vote.

**When suggestions close, the buttons disappear. The "Suggest a spot" prompt gets a small grey line showing what they suggested:**
> Suggestions have closed · You suggested *{spots}*
> Suggestions have closed · You didn't suggest a spot

**And each of their suggestion messages gets:**
> Suggestions have closed

**If someone sends the suggestion form just after suggestions closed (they had it open):**
> Suggestions are closed for this one, sorry!

**If nobody suggests anything in 5 minutes, you get:**
> Nobody suggested a spot within 5 minutes. Pick a spot yourself, or cancel this party.

* Button: **Pick a spot** *(opens the "Where are we ordering?" form)*
* Button: **Cancel party**

*(Suggestions close as soon as everyone who's in has suggested at least one spot, or after 5 minutes.)*

**If suggestions do come in, everyone gets a vote, with a button for each spot:**
> Suggestions are in! Vote for your favorite, you've got 3 minutes:

*(Voting closes as soon as everyone who's in has voted, or after 3 minutes.)*

**Confirmation shown to someone right after they vote:**
> Got your vote, thanks!

**When voting closes, the vote buttons disappear and a small grey line showing their vote appears:**
> Voting has closed · You voted for *{spot}*
> Voting has closed · You didn't vote

**If nobody votes in 3 minutes, you get a button for each suggestion, plus:**
> Nobody voted within 3 minutes. Pick one of the suggestions, choose another spot, or cancel this party.

* Button: **Another spot** *(opens the "Where are we ordering?" form)*
* Button: **Cancel party**

**Once voting closes with a clear winner, you see the results:**
> Voting results:
> {breakdown of votes per suggestion}
> Winner: *{winner}*

**If two or more spots tie, you get this instead, with a button for each tied spot, plus "Another spot" and "Cancel party":**
> Voting results:
> {breakdown of votes per suggestion}
> It's a tie between {tied spots}! Tap the one you want to go with, or choose another spot.

**After you pick one from a list, or enter a spot in the form:** *(grey line)*
> You chose *{spot}*

**If a spot name is over 60 characters (the forms don't allow it, so this is just a safety net):**
> That's a bit long. Keep the spot name under 60 characters and send it again.

---

## 4. Placing the order

**Once a spot is settled, everyone who's in gets this with buttons:**
> {host} invited you to the *{spot}* party! Tap below to send your order, you've got until {deadline} :meow_matcha:

* Button: **Place your order**
* Button: **Can't make it**
* Button: **Suggest somewhere else** *(only when you picked the spot yourself, not when the group voted for it)*

*(The deadline is always shown in Riyadh time.)*

**"Place your order" opens a form:**
* Title: **Your matcha order**
* Field: **Drink name** (up to 100 characters)
* Field: **Milk type** (up to 100 characters)
* Field: **With or without cream?** (choices: **With cream** / **Without cream**)
* Field: **Sweetness level** (choices: **Sweet** / **Less Sweet** / **No Sweet**)
* Submit button: **Submit**

**Confirmation shown right after they submit their order:**
> Got your order, thanks! You can change it until ordering closes.

* Button: **Change my order** *(opens the same form, already filled in with their last order)*

**After they change it:**
> Updated your order! You can still change it until ordering closes.

*(Ordering closes when the time is up, or as soon as everyone who's in has ordered. After that, changes aren't possible.)*

**When ordering closes, the buttons disappear. The order message gets a small grey line showing their order:**
> Ordering has closed · Your order: *{drink}, {milk}, {sweetness}, {cream}*
> Ordering has closed · You didn't order

**And their "Got your order" message gets:**
> Ordering has closed

**If someone submits the order form just after ordering closed (they had it open):**
> Ordering's closed for this party, sorry!

**If you switch spots, the buttons on the old order message disappear and this line is added:**
> The spot changed, see the newer message below

**If someone submits an order after you switched spots (from the old spot's form):**
> The spot changed before your order went through. Please order again from the latest message.

**If someone taps "Can't make it", the buttons on that message disappear with this line added:**
> You're out of this one

**And they get:**
> No worries, I've taken you off this one. Maybe next time!

**And you get:**
> {name} can't make it to *{spot}*, so they're out of this party.

**If that was the last person in, you also get (and it's scrapped):**
> Everyone dropped out, so I've scrapped this Matcha Party.

**If someone taps "Suggest somewhere else", a small form opens:**
* Title: **Suggest another spot**
* Field: **Where would you rather order from?**
* Submit button: **Send**

**They then get:**
> Sent your suggestion to {host}. I'll let you know what they decide.

**And you get this, with two buttons:**
> {name} would rather order from *{suggestion}* instead of *{spot}*.

* Button: **Keep current spot**
* Button: **Switch to this one**

**If you tap "Keep current spot":** *(grey line)*
> You kept *{spot}*

**And the person who suggested it gets:**
> {host} is sticking with *{spot}*. You can still place your order, or tap Can't make it.

**If you tap "Switch to this one":** *(grey line)*
> You switched to *{spot}* · Orders were reset and everyone has 5 more minutes

**Everyone who's in gets this, followed by a fresh order message for the new spot:**
> Change of plans: {host} switched the party to *{spot}*. If you already ordered, please order again below.

**Any other "would rather order from" messages, once you switch spots or ordering closes:** *(grey line)*
> This suggestion isn't active anymore

**If someone sends the "Suggest somewhere else" form after ordering closed:**
> Too late to suggest another spot, ordering's already closed.

**If someone sends that form after you already switched to a different spot:**
> The spot changed to *{spot}* before your suggestion went through, so I didn't send it. Suggest again from the latest message if you'd like.

---

## 5. Wrapping up

**Once ordering closes, you get a summary. First line:**
> Order summary for *{spot}*:

**Then one line per person who ordered:**
> • *{name}*: {drink}, {milk}, {sweetness}, {cream}

**If anyone never ordered, this gets added:**
> Didn't order: {names}

**If anyone tapped "Can't make it", this gets added:**
> Can't make it: {names}

**Below the summary, buttons for you:**
* Button: **I placed the order ✅**
* Button: **There's a problem** *(also on the ETA question and on "Tap below when the order arrives")*

**"There's a problem" opens a form:**
* Title: **What happened?**
* Field: **Tell everyone what happened** (up to 300 characters)
* Submit button: **Send**

**Everyone who's in then gets:**
> Update from {host} about the *{spot}* order: {what you wrote}

**And you get (the party carries on, so the buttons stay):**
> Sent to everyone in the party. The party carries on, so you can still use the buttons above.

**After you tap it:** *(grey line)*
> You placed the order

**After you tap that, you get:**
> Noted! Letting everyone know the order's in.

**Meanwhile, everyone who's in gets:**
> Heads up, {host} just sent off the Matcha Party order!

**Then you're asked:**
> Got an ETA for when it'll arrive?

* Button: **Add ETA** *(opens a form: "When will it arrive?", field "ETA (e.g. 20 minutes or 3:30 PM)", up to 100 characters)*
* Button: **No ETA**

**After you answer:** *(grey line)*
> ETA sent: *{eta}* / You chose *No ETA*

**If you add an ETA, everyone who's in gets:**
> ETA on the matcha: {eta}

**Either way, you then get:**
> Noted! Tap below when the order arrives and I'll let everyone know.

* Button: **The order arrived**

*(You're free to start another party while you wait for this.)*

**When you tap "The order arrived", everyone who's in gets:**
> The matcha has arrived! Come grab yours :matcha-lahloob:

**And under your message:** *(grey line)*
> You told everyone the order arrived · Party closed

*(If nobody taps it, the party closes on its own 3 hours after the ETA step, and the button is replaced by "This party has closed".)*

---

## 6. If things go quiet or someone types in the chat

**If you don't respond for 60 minutes at a step that's waiting on you (picking people, picking the spot, confirming the order, or the ETA), the party closes and you get:**
> No reply for 60 minutes, so I've closed this Matcha Party. Run /matcha-party to start another.

**Everyone invited or in gets (unless the order was already sent):**
> {host}'s Matcha Party went quiet, so I've closed it.

**If anyone types in the chat during a party:**
> No need to type anything here. Just use the buttons in my messages above.

**If anyone (other than you and Nouf, whose messages are passed between you) messages the bot outside a party:**
> Hi! Run /matcha-party here to start a group matcha order.

*(While starting parties is limited to a few people, they get "Matcha Party isn't open to everyone yet. Check back soon!" instead.)*
