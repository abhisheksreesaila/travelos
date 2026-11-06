# Feature brief: "Plan it for me", the first thing a family pays GitAway for

Status: draft, built in agent time (autopilot, 2026-11-06). The captain approves the price, the promise and the delivery before anything is deployed. Nothing here is live.

## Why
- Booking commissions settle only after travel, so they cannot be the first money. A direct sale can: a family pays once and an agent builds their whole trip in their own GitAway account in minutes.
- It also fills GitAway with real trips (the thing creators and families come for) and shows what the app does better than a blank calendar.

## Who and when
- A family that has picked a place (or been inspired by a creator's trip) and does not want to plan the days themselves. Phone first: this is bought on an iPhone in a couple of minutes.

## The offer, in plain words
- **Price: $29, one time** (`PLAN_FOR_ME_PRICE_CENTS=2900`; the number lives in one setting, never on the client).
- **Promise: "Not useful? Reply within 7 days for a full refund."** The captain refunds by hand in Stripe. The page says it before the button and again on the order page.
- **What they get:** a trip in their family's GitAway calendar: day by day, with times, real named places where the agent is sure and a plain "pick a place" where it is not, kid-friendly pacing for the ages given, a note with a few tips, and links to book flights (Aviasales) and stays and things to do (Klook) carrying the order id as the SubID.
- **What they never get:** an invented price or exact opening hours. A place the agent is unsure of shows without a name.

## The flow
1. **Entry points.** A card on every public creator trip page ("Want this trip built around your family?", the place and trip name carried over), a card on the signed-out landing, and a line in the signed-in trip menu. Nothing else.
2. **Intake, one short phone screen:** where (free text; suggestions are the catalog's places plus "Disneyland, California"), dates, home airport, adults, kids with ages, budget band (Easy on the wallet, Comfortable, Treat ourselves), must-dos (free text), pace (Relaxed, Balanced, Packed).
3. **Sign in before paying**, so the trip lands in the family's account. A signed-out visitor fills the form, the browser keeps their answers while they sign in, and the form comes back filled in.
4. **Pay** on Stripe Checkout (one line item, mode payment). The price is read on the server when the order is made; the form has no price field.
5. **Order page** `/plan-for-me/<order>`, for the buyer only: paid -> building -> ready (with the link to the trip) -> failed ("we'll refund you"; the captain sees it on /admin). It survives a restart: orders and their state live in the database, and a paid order that was building when the process stopped is picked up again at boot.
6. **Local only:** with no `STRIPE_SECRET_KEY`, a local copy shows a stand-in checkout (like /sandbox) that completes the order, and with no AI key a sample trip stands in for the real one, so the whole flow is clickable. In production without `STRIPE_SECRET_KEY` the offer is hidden (404, no cards).

## How it is built (short)
- Orders: one table in the community database (`plan_orders`), a small state machine (awaiting_payment, paid, building, ready, failed) moved only by guarded UPDATEs, plus a table of Stripe event ids so a repeated webhook does nothing.
- Money: the webhook `checkout.session.completed` is verified with `STRIPE_WEBHOOK_SECRET`, must name the session the order was created with, and must carry the amount the order holds. Idempotent by event id.
- The agent: a new `ai.py` job `plan-for-me` (Claude Sonnet 5.5 by default, `GITAWAY_AI_MODEL_PLAN_FOR_ME` to change it, structured output). Its answer is never trusted: `planforme.validate()` rebuilds it field by field, drops prices and opening hours, and turns an unsure place into a generic stop. AI cost (tokens and dollars) is stored on the order.
- The write: the existing trip and plan functions (`importer.save` for the trip, `tripcal.apply_plans` for the days), as the buyer, in their family's database. A worker thread like `draftjobs` does it, so no request waits for the model.

## Not now
- Taking a refund from inside GitAway (the captain uses Stripe), emailing anyone (nothing is sent by GitAway), changing a plan after delivery (they use the Ask box on their own trip), a second payment, subscriptions, tax handling beyond Stripe's own.
- Anything for a viewer: only a family editor or admin can buy, because the trip lands where a viewer cannot write.

## Checks that say it is done
See F-193 in docs/plan.md.

## What the captain must decide before deploy
- The price and the 7-day promise in these words.
- Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in Railway (service web), point the Stripe webhook at `https://gitaway.me/stripe/webhook` for `checkout.session.completed`, and make one test-mode purchase end to end before going live (nothing here could call the real Stripe).
- Add `GITAWAY_ADMIN_EMAILS` (already needed for /admin) so failed orders reach someone.
