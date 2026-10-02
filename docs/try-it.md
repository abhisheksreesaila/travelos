# Try GitAway with your real LA trip (local)

About 15 minutes. Everything runs on your machine; nothing is deployed.

## 1. Start it

```
pixi install
GITAWAY_DEV_LOGIN=1 pixi run dev        # http://localhost:5002
```

Data goes to `./data/db` (gitignored). To start over, stop the server and delete that folder.

To use real Google sign-in instead of the dev sign-in, follow `docs/setup.md` → "Google sign-in" (create the OAuth client, add `http://localhost:5002/auth/callback`, put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`, and add your family's Gmail addresses as **Test users**).

## 2. Sign in and import your trip

1. Open <http://localhost:5002/signin> and use **Dev sign-in (local only)** with your Gmail address.
2. Fill in `docs/trip-template.md` from your Expedia confirmation:
   - Quote confirmation numbers if you like, though they're kept exactly as typed either way.
   - Use `hotels:` for two hotels.
   - Delete `car:` if you'll use rides.
3. Open **Import a trip** (`/trips/import`), paste the block, press **Preview**, check it, then press **Save**. The calendar opens on your trip. Your bookings are marked "Booked elsewhere · Expedia".
4. Made a mistake? Fix the template and import it again. The preview offers **Replace the existing trip**, and your plans, notes and rides are kept.

## 3. Invite your family

1. Click your avatar (or open `/family`), enter a family member's Gmail address, choose **Editor** (can plan) or **Viewer** (can look), then **Invite**.
2. **Copy link** and send it to them yourself; GitAway doesn't send email yet.
3. They open the link and sign in with that same Gmail address, and they're in your family with your trips.
   - **Locally:** each person signs in with the dev sign-in in another browser or a private window.
   - **With Google keys:** they use **Continue with Google**.

## 4. Plan together

- **Calendar:** opens on the whole-trip view. **Day by day** shows the hour grid, where you can add, move and resize plans. Everyone sees everyone's changes.
- **Talk to plan:** a scripted voice demo fills free slots, using the same preview and apply steps as forks.
- **Your forks:** fork or save any trip from **Browse trips people loved**, then apply it into your empty slots.
- **Rides:** with no car, the calendar and rides card offer **Schedule an Uber** for landing and the flight home. It's simulated, follows Uber's real steps, and appears on the calendar.
- **Share:** publishes a snapshot of the trip to the hub (no notes, confirmations or prices). **Update shared page** refreshes it, and **Unpublish** takes it down.

## 5. On your iPhone

The phone has to reach your computer:
- On the same Wi-Fi, open `http://<your-computer-ip>:5002` (the dev server already listens on all interfaces). The dev sign-in is refused from other devices on purpose, so use Google sign-in there; Google only allows `localhost` or HTTPS redirect addresses, so this works best after deploying.
- Or deploy later.

In Safari, **Share → Add to Home Screen** opens GitAway full screen with its icon. Note that "Add to Home Screen" install and offline need HTTPS on a real phone (localhost is the exception), so the phone test is best done after deploying.

## What's still simulated

- The booking workspace's flights, hotels and cars (sample LA data; no real inventory or payment).
- Uber rides.
- Voice planning.
- Creator transcripts.
- The 3D area map (an illustration).
