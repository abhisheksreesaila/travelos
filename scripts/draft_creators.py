"""Draft every A-priority creator's example post from docs/research/creators.csv (F-188): `pixi run draft-creators [--limit N]`.

Needs ANTHROPIC_API_KEY in the environment (never printed); without it, says so and exits 1. Each post is read the way the app reads it (safe fetch, Claude Haiku 5.5, validation) into a
private draft owned by no one, with the creator's name from the CSV. A post that already has a draft is skipped, and the site-wide daily AI ceiling (GITAWAY_CREATOR_IMPORT_SITE_LIMIT) stops the run
when it is used up. The claim links are printed (this is the captain's own terminal) and written to claim-links.csv in the data folder (GITAWAY_DATA_DIR, never committed); each link works once,
for 30 days, and is stored only as a hash, so the file is the only place they are kept. GitAway sends nothing: the captain copies each message from /admin.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = "claim-links.csv"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Draft every A-priority creator's example post and print the claim links.")
    ap.add_argument("--limit", type=int, default=0, help="draft at most this many posts (0: all)")
    args = ap.parse_args(argv)
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("ANTHROPIC_API_KEY must be set (it is never printed): drafting a post is a call to Claude Haiku 5.5.\n"
              "Without a key, run the app locally (pixi run dev): the admin page drafts made-up sample drafts so you can try the flow.")
        return 1
    from gitaway import ai, auth, creatorclaim as cc, creatordraft as cd, importsource
    from gitaway.hub import HubError
    folder = auth.configure_storage()
    todo = [c for c in cc.candidates() if (c.get("priority") or "").strip() == "A" and not c["drafted"]]
    skipped = sum(1 for c in cc.candidates() if (c.get("priority") or "").strip() == "A" and c["drafted"])
    if args.limit > 0:
        todo = todo[:args.limit]
    rows, failed = [], []
    for c in todo:
        url = c["example_post_url"].strip()
        try:
            d, link = cc.draft("script", url, c["person"])
        except (importsource.SourceError, ai.AIError, HubError) as e:
            failed.append((c["person"], str(e)))
            if str(e) == cd.SITE_LIMIT_HIT:
                break
            continue
        rows.append((c["person"], d["title"], url, link))
    path = folder / OUT
    if rows:
        new = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["creator", "title", "post_url", "claim_link"])
            w.writerows(rows)
        os.chmod(path, 0o600)
    print(f"{'creator':28} {'draft':44} claim link")
    for who, title, _url, link in rows:
        print(f"{who[:28]:28} {title[:44]:44} {link}")
    for who, why in failed:
        print(f"{who[:28]:28} FAILED: {why}")
    print(f"\n{len(rows)} drafted, {skipped} already had a draft, {len(failed)} failed." + (f" Links saved to {path} (never commit it)." if rows else ""))
    return 0 if not failed else 3


if __name__ == "__main__":
    sys.exit(main())
