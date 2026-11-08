"""Generate one storyboard image with Gemini.

Usage:  GEMINI_KEY_FILE=/path/to/keyfile pixi run python tools/gen.py <job-id> [--model M]
The key is read from the file named by GEMINI_KEY_FILE and sent only as the
x-goog-api-key header. It is never printed or written. Prompts live in jobs.py.
"""
import base64, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORY = HERE.parent
sys.path.insert(0, str(HERE))
import jobs  # noqa: E402

MODELS = ["gemini-3-pro-image", "gemini-3.1-flash-image"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def mime(p):
    return "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"


def call(model, prompt, refs, aspect):
    parts = [{"text": prompt}]
    for r in refs:
        parts.append({"inlineData": {"mimeType": mime(r), "data": base64.b64encode(r.read_bytes()).decode()}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
    }
    key = Path(os.environ["GEMINI_KEY_FILE"]).read_text().strip()
    req = urllib.request.Request(URL.format(model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


def main():
    job_id = sys.argv[1]
    models = MODELS
    if "--model" in sys.argv:
        models = [sys.argv[sys.argv.index("--model") + 1]]
    job = jobs.JOBS[job_id]
    out = STORY / job["out"]
    refs = [STORY / r for r in job["refs"]]
    prompt = jobs.full_prompt(job_id)
    for model in models:
        t = time.time()
        with open(STORY / "tools" / "calls.log", "a") as log:
            log.write(f"{time.strftime('%H:%M:%S')} {job_id} {model}\n")
        try:
            data = call(model, prompt, refs, job.get("aspect", "16:9"))
        except urllib.error.HTTPError as e:
            print(f"{model} HTTP {e.code}: {e.read()[:400].decode(errors='replace')}")
            continue
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    if out.exists():  # keep the previous take
                        n = 1
                        while (out.parent / "takes" / f"{out.stem}-{n}{out.suffix}").exists():
                            n += 1
                        (out.parent / "takes").mkdir(exist_ok=True)
                        out.rename(out.parent / "takes" / f"{out.stem}-{n}{out.suffix}")
                    raw = base64.b64decode(part["inlineData"]["data"])
                    out.write_bytes(raw)
                    print(f"ok {job_id} -> {out.relative_to(STORY)} via {model} "
                          f"({part['inlineData'].get('mimeType')}, {len(raw)//1024} KB, {time.time()-t:.0f}s)")
                    return
        print(f"{model}: no image. finish={[c.get('finishReason') for c in data.get('candidates', [])]} "
              f"feedback={data.get('promptFeedback')}")
    sys.exit(1)


if __name__ == "__main__":
    main()
