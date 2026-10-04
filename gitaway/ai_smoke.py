"""One real call to the model, by hand (not part of the test suite): `pixi run python -m gitaway.ai_smoke [file]`.

Converts the captain's Universal Studios and California Adventure messages (tests/fixtures/universal_dca.txt, or the file given) with the real Azure
deployment from the environment (.env) and prints only counts and the time taken: days, areas, steps, set aside, lists, tokens. It prints no text from the
messages or from the answer, and never the key. The call is logged to a throwaway database in a temporary folder, not to the app's own.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    os.environ.setdefault("DB_TYPE", "SQLITE")
    os.environ["DB_NAME"] = "smoke_host"
    folder = tempfile.mkdtemp(prefix="gitaway-smoke-")
    os.chdir(folder)
    try:
        from gitaway import ai, canvas
        if not ai.configured("convert"):
            print("The assistant is not configured (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT).")
            return 1
        path = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "universal_dca.txt"
        text = path.read_text()
        start = time.monotonic()
        try:
            draft = canvas.convert({"tenant_id": "smoke"}, text)
        except (ai.AIError, canvas.CanvasError) as e:
            print(f"Convert failed after {time.monotonic() - start:.1f} s: {e}")
            return 2
        took = time.monotonic() - start
        s = canvas.summary(draft)
        row = (ai.usage_rows() or [{}])[-1]
        print(f"deployment={ai.deployment('convert')} took={took:.1f}s days={s['days']} parts(areas)={s['areas']} steps={s['steps']} set_aside={s['set_aside']} "
              f"lists={s['lists']} list_items={s['list_items']} merged_repeats={draft['merged_repeats']} tokens_in={row.get('tokens_in', '?')} tokens_out={row.get('tokens_out', '?')}")
        return 0
    finally:
        os.chdir(Path(__file__).resolve().parent)
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
