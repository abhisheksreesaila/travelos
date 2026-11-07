# Where to pick up (stopped 2026-11-07 to save tokens)

Run every subagent and delegated task at **medium effort** from now on; the founder asked.

Nothing is deployed and nothing is pushed. Each ticket lives on its own branch and work folder.

| Ticket | Branch · folder | State | Next step |
|---|---|---|---|
| F-207 stop unpinned CDN scripts (LIVE site) | `f-207-no-cdn-scripts` · `travelos-f207` (from master) | Built, tests green (stale-date tests fixed by cherry-picking 617fe16, cf2a383, 40fc4db) | Reviewer, then **ask the founder** to deploy it on its own: merge to master, `railway status` (gitaway / web), `railway up --service web`, check pages with `?q=<random>` |
| F-206 cover page 3D world | `f-206-cover-world` · `travelos-f206` | Review fixes done (262eade, 07afe58); security already PASS | Re-review the delta, then merge |
| F-203 real weather + F-208 blog fetch deadline | `f-203-real-weather` · `travelos-f203` | Reviewed and passed; a last small round was **in progress (uncommitted edits)** | Finish that round: deadline.get tests, safefetch TLS tests, handshake window, DNS in the deadline, IPv6 2000::/3, Unicode redirects, https-to-http refusal, alias recall. Commit, then merge |
| F-198 booking anywhere + F-199 free Plan it for me | `f-198-booking-anywhere` · `travelos-f198` | Review fixes committed (408f987); it may be partial because it was cancelled mid-run | Check what's done against the review list in this thread, finish, then re-review |
| F-201 Ticket line cockpit | `f-201-ticket-line` · `travelos-f201` | Review fix round **in progress (uncommitted edits)** | Finish: Overpass timeout remark, router steps (OSRM steps=true), no invented weather on real trips, 16px phone type, one-at-a-time pack builds with caps and budgets, the should-fixes. Then re-review |
| F-200 Direction A everywhere | `f-200-direction-a` · `travelos-f200` | Built (last commit adds the Early preview label); not reviewed | Reviewer and security check, then merge **first**, since everything else picks up its tokens |
| F-202 book of tickets, F-205 shared-trip story | — | Not started | After the merges |

**Merge order:** F-200, then F-203, then F-206, then F-198, then F-201, each into `autopilot/booking-creators`.
- **Before each merge commit:** renumber clashing D- numbers and check for unmerged files.
- **After each merge:** run both test suites.
- **Then:** merge master, which has F-207, into the branch.

**Waiting on the founder:**
1. Routes: openrouteservice; the founder will set `ORS_API_KEY` later.
2. Done (founder, 2026-11-07): Railway variables are set.
3. Accept MET Norway's terms, then set `MET_NORWAY_TERMS_ACCEPTED=1`.
4. Approve deleting the test temp folders under `~/.cache/*-tmp` (several GB).
5. Say "ship" for the whole release once it's merged and green.

**Dev server for the founder:** `cd ~/Projects/travelos-autopilot && GITAWAY_DATA_DIR=$HOME/.cache/gitaway-dev-data/db GITAWAY_DEV_LOGIN=1 pixi run dev`, then open http://localhost:6001. Each work folder needs `ln -s ../travelos/.env .env` first.
