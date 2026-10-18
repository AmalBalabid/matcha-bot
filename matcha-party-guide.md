# Matcha Party: A Quick Guide

Hi Nouf! Matcha Bot is ready to try. This guide covers what it does and how to use it, plus a checklist of your requirements and what was built for each one.

For the exact wording of every message, see `matcha-bot-messages.md`. If you'd like any wording changed, tell Amal which message and how.

---

## For the trial

For now, **only you and Amal can start a party**. Anyone else who tries is told it isn't open yet. You can still invite anyone. Once we're happy with it, it'll be opened to everyone.

---

## Starting a party (you're the host)

1. Open your DM with **Matcha Bot** and type `/matcha-party`. It only works from your DM with the bot, not from a channel.
2. Tap **Pick people**, choose who to invite, and tap **Send invites**.
3. Wait for people to answer. They have 5 minutes. You'll see who's in, who can't make it, and who didn't answer.
4. When at least one person is in, choose how to pick the spot:
   - **I've already decided**: type the spot name in the form.
   - **Let them suggest**: everyone who's in gets up to 5 minutes to suggest spots, then up to 3 minutes to vote. Each step moves on early once everyone has suggested (at least one spot) or voted.
5. Everyone who's in gets the order form and has 5 minutes to order.
6. You get a summary of all the orders. Place the order with the restaurant, then tap **I placed the order ✅**. If something goes wrong (for example the restaurant can't take the order), tap **There's a problem** and write what happened. Everyone in the party gets your message, and the party carries on.
7. Add an ETA if you have one (**Add ETA**), or tap **No ETA**.
8. When the matcha arrives, tap **The order arrived** and everyone gets told. That closes the party.

You can tap **Cancel party** (the red button) on most of your messages at any point. Running `/matcha-party` again while your party is going also offers a Cancel button.

---

## If you're invited

1. You get an invite with **I'm in!** and **Can't make it**.
2. If the group is suggesting spots, tap **Suggest a spot**. You can suggest as many as you like, and remove any of them until voting starts. Voting starts once everyone has suggested at least one.
3. If there's a vote, tap the spot you want.
4. When the spot is decided, tap **Place your order** and fill in the form:
   - Drink name
   - Milk type
   - With or without cream
   - Sweetness: Sweet, Less Sweet or No Sweet
5. Changed your mind? Tap **Change my order**. The form opens with your last order filled in, and you can change it until ordering closes.
6. You'll get a message when the order has been placed, the ETA (if there is one), and when it arrives.

On the order message you'll also find:
- **Can't make it**: drops you out of the party, and the host is told.
- **Suggest somewhere else**: only shown when the host picked the spot. The host can keep the spot or switch to yours.

---

## Good to know

- **No typing needed.** Everything is buttons and small pop-up forms. If you type in the chat during a party, the bot just reminds you to use the buttons.
- **Buttons clean up after themselves.** Once you've answered, or the time is up, the buttons disappear and a small grey line shows what you chose. For example: *Voting has closed · You voted for **Kultura***.
- **Similar suggestions get merged.** Capital letters and extra spaces never matter. If someone types "Kultra" after "Kultura", they're asked whether it's the same place. Numbers always count as different spots, so "Cafe 1" and "Cafe 2" stay separate.
- **Ties go to the host.** If two spots tie, the host picks one, or chooses another spot.
- **Steps move on early.** Suggestions, voting and ordering each close as soon as everyone has answered, without waiting for the time to run out.
- **The deadline is shown in Riyadh time.**
- **One party at a time per person.** Several parties can run at once, but nobody can be in two.
- **Privacy:** if someone you invite is already in another party, they still show as invited. About 2 minutes later they count as "Can't make it", so nobody can tell they're busy.
- **Quiet parties close.** If the host doesn't respond for 60 minutes at a step that's waiting on them, the party closes and everyone is told.
- **Your onboarding chat with Amal still works.** Outside a party, messages between you and Amal in your DMs with the bot are passed along as before. During a party you're in, what you type isn't passed along.

---

## Your requirements, and what was built

| Your requirement | Status |
|---|---|
| Ask the host who to invite | ✅ A people picker opens from the **Pick people** button |
| Two options: host already knows the spot, or invitees suggest | ✅ **I've already decided** / **Let them suggest** |
| Collect suggestions for 5 minutes | ✅ As many suggestions per person as they like, with a Remove button |
| Share the suggestions and give 3 minutes to vote | ✅ One button per spot |
| Send the host the results | ✅ The vote count for each spot, and the winner |
| Announce the spot and collect orders (drink, milk, cream), with 5 minutes and the deadline shown | ✅ Order form, deadline in Riyadh time |
| Sweetness option: Sweet, Less Sweet, No Sweet | ✅ In the order form |
| Send the host an order summary | ✅ Also lists who didn't order and who couldn't make it |
| Ask the host to confirm the order was sent | ✅ **I placed the order ✅** |
| Tell invitees the order was sent, and ask the host for an ETA | ✅ ETA is optional |
| Anyone can start a party, several at once | ✅ After the trial (for now only you and Amal) |
| Invitees accept or decline | ✅ **I'm in!** / **Can't make it** |
| One active party per person | ✅ |
| Don't reveal that someone is in another party | ✅ They show as invited, then decline automatically |

**Also added along the way:**
- **Change my order** before ordering closes
- **Can't make it** and **Suggest somewhere else** on the order message
- Similar suggestions are merged, after asking the person who suggested it
- The host breaks ties
- **The order arrived** notification
- **There's a problem** button for the host after the orders are in
- Steps move on as soon as everyone has answered
- The host sees who declined and who didn't answer, separately
- Buttons replaced by a grey line showing each person's answer
- The bot keeps working through restarts, and quiet parties close on their own

Enjoy, and let Amal know what you think after the trial!
