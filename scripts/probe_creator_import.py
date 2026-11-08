"""One real creator-import call (F-183): `pixi run probe-import <url>` (or `--text "..."` for pasted text).

Needs ANTHROPIC_API_KEY in the environment (never printed). Reads the page the way the app does (gitaway.importsource, with the safe fetcher), asks Claude Haiku 5.5 for the draft through
gitaway/ai.py (job "creator-import", production's own settings: GITAWAY_AI_MODEL_CREATOR_IMPORT and GITAWAY_AI_EFFORT_CREATOR_IMPORT apply), and prints the validated draft as JSON, then the tokens
in and out, the seconds and the cost estimate. Everything it logs goes to a throwaway data folder that is deleted at the end, never to a real one. Exit 1 without a key, 2 when the post cannot be
read, 3 when the model fails (the sentence is the app's own, never the service's).
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Draft one trip from a post with the real model and print it.")
    ap.add_argument("url", nargs="?", default="", help="the post's address (a blog post, a YouTube video, an Instagram post)")
    ap.add_argument("--text", default="", help="pasted text: the post itself, a caption or a transcript (needed for Instagram)")
    args = ap.parse_args(argv)
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("ANTHROPIC_API_KEY must be set (it is never printed).")
        return 1
    data = tempfile.mkdtemp(prefix="gitaway-probe-import-")
    os.environ.update({"GITAWAY_DATA_DIR": os.path.realpath(data), "DB_TYPE": "SQLITE", "DB_NAME": "app_host"})
    try:
        from gitaway import ai, auth, creatordraft, importsource
        from gitaway.hub import HubError
        auth.configure_storage()
        try:
            material = importsource.gather(args.url, args.text)
        except importsource.SourceError as e:
            print(f"Could not read the post: {e}")
            return 2
        print(f"Read a {material.kind} post: {len(material.text):,} characters, {len(material.images)} pictures offered", *[f"\n  note: {n}" for n in material.notices])
        try:
            draft = creatordraft.ask("probe", "probe", material)
        except (ai.AIError, HubError) as e:
            row = next(iter(reversed([r for r in ai.usage_rows() if r["job"] == creatordraft.JOB])), {})
            print(f"The model did not give a draft: {e} (logged as {row.get('error') or 'n/a'}, {row.get('tokens_in', 0)} tokens in, {row.get('tokens_out', 0)} out)")
            return 3
        row = [r for r in ai.usage_rows() if r["job"] == creatordraft.JOB][-1]
        print(json.dumps(draft, indent=2, ensure_ascii=False))
        print(f"\nmodel {row['deployment']} · {row['tokens_in']:,} tokens in · {row['tokens_out']:,} tokens out · {row['ms'] / 1000:.1f} s · "
              f"about ${ai.cost_usd(row['deployment'], row['tokens_in'], row['tokens_out']):.5f} for this draft")
        return 0
    finally:
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
