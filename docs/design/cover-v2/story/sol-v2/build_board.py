"""Build the review board and its web-sized assets. Run through pixi."""
import html
import json
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
shots = json.loads((HERE / "shots.json").read_text())
elapsed = 0
for s in shots:
    s["start"] = elapsed
    elapsed += s["duration"]
    s["end"] = elapsed
    source = HERE / s["image"]
    if s["id"] == "18":
        source = HERE / "frames/17.png"
    if not source.exists():
        raise SystemExit(f"Missing artwork: {source}")
    preview = HERE / f"frames/{s['id']}-preview.webp"
    with Image.open(source) as image:
        image.thumbnail((1200, 675))
        image.convert("RGB").save(preview, quality=85, method=6)
    s["preview"] = f"frames/{s['id']}-preview.webp"
    if s["id"] == "18":
        s["image"] = "frames/17.png"

def esc(s):
    return html.escape(str(s), quote=True)

cards = []
articles = []
for s in shots:
    marked = " immersive" if "3D" in s["medium"] else ""
    stamp = f"{s['start']//60:02}:{s['start']%60:02}–{s['end']//60:02}:{s['end']%60:02}"
    cards.append(f"""<button class="thumb{marked}" type="button" data-scene="{s['id']}" aria-label="Scene {s['id']}: {esc(s['title'])}">
      <img src="{s['preview']}" alt="" loading="lazy" width="1200" height="675">
      <span><b>{s['id']}</b> {esc(s['title'])}</span><small>{stamp} · {s['duration']}s</small></button>""")
    dialogue = "".join(f"<p>{esc(line)}</p>" for line in s["dialogue"].split(" | ") if line)
    articles.append(f"""<article class="shot{marked}" id="scene-{s['id']}">
      <header><span class="eyebrow">SCENE {s['id']} · {stamp}</span><span class="tag">{esc(s['medium'])}</span></header>
      <h3>{esc(s['title'])}</h3><img src="{s['preview']}" alt="{esc(s['title'])}" loading="lazy" width="1200" height="675">
      <p class="line">{esc(s['narration'])}</p><div class="dialogue">{dialogue or '<p>Let the image and sound breathe.</p>'}</div>
      <p class="camera"><b>Camera & transition</b>{esc(s['camera'])}</p>
      <a href="{s['image']}">Open original PNG</a></article>""")

css = """
:root{--paper:#f5efe3;--paper-bright:#fffbf2;--ink:#302b26;--quiet:#74685b;--rule:#d9cdb8;--ochre:#a9682f;--lake:#266b80;--radius:14px}
*{box-sizing:border-box}body{margin:0;font-family:Georgia,"Iowan Old Style",serif;line-height:1.5;color:var(--ink);background:var(--paper)}
main{max-width:1100px;margin:auto;padding:36px 28px 64px}header.intro{margin-bottom:24px}.eyebrow{font:11px/1.4 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--quiet)}
h1{font-size:clamp(30px,5vw,52px);font-weight:400;letter-spacing:-.04em;line-height:1.12;margin:10px 0 12px}h2{font-size:27px;font-weight:400;margin:0 0 14px}h3{font-size:22px;font-weight:400;margin:8px 0 14px}
p{margin:8px 0}.intro p{max-width:720px;color:var(--quiet);font-size:16px}
.chapters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:22px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.chapters div{padding:12px 10px;min-width:0;font-size:14px}.chapters div+div{border-left:1px solid var(--rule)}.chapters span{display:block;font-size:12px;color:var(--quiet)}
.stage{border:1px solid var(--rule);border-radius:var(--radius);overflow:hidden;background:var(--paper-bright)}
.stagehead{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:12px 16px;flex-wrap:wrap}
.tag{font:11px/1.4 system-ui,sans-serif;border:1px solid var(--rule);border-radius:99px;padding:4px 9px;color:var(--quiet)}
.viewport{position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--paper);min-width:0}.viewport img{width:100%;height:100%;object-fit:contain;display:none}.viewport img.active{display:block}
.endcopy{position:absolute;inset:0;display:none;place-content:center;text-align:center;background:rgb(245 239 227 / .84);padding:20px}.endcopy.active{display:grid}
.endcopy strong{font-size:clamp(25px,5vw,52px);font-weight:400;line-height:1.1}.endcopy span{color:var(--quiet);margin-top:16px}
.caption{padding:16px 18px;border-top:1px solid var(--rule)}.caption h2{font-size:23px;margin:0 0 6px}.caption .narration{font-size:20px;font-style:italic}.caption .spoken{color:var(--quiet);font-size:14px}
.caption .camera{color:var(--quiet);font-size:13px;margin-top:12px}.camera b{display:block;font:10px/1.7 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ochre)}
.controls{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:14px 0 20px}button{font:13px/1.4 system-ui,sans-serif;cursor:pointer;border:1px solid var(--rule);color:var(--ink);background:var(--paper-bright);border-radius:8px;min-height:44px;padding:9px 14px}button:hover{border-color:var(--ochre)}button:focus-visible,a:focus-visible{outline:2px solid var(--lake);outline-offset:3px}button:disabled{opacity:.45;cursor:default}.controls .primary{background:var(--ink);color:var(--paper-bright);border-color:var(--ink)}
.counter{margin-left:auto;font:12px/1.4 ui-monospace,monospace;color:var(--quiet)}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.thumb{padding:0 0 10px;text-align:left;overflow:hidden;min-width:0;border-radius:8px}.thumb img{display:block;aspect-ratio:16/9;width:100%;height:auto;object-fit:cover}.thumb span{display:block;font-size:12px;margin:8px 9px 2px}.thumb b{font:11px ui-monospace,monospace;color:var(--ochre);margin-right:5px}.thumb small{font:10px ui-monospace,monospace;color:var(--quiet);margin:0 9px}
.thumb[aria-current=true]{outline:2px solid var(--ochre);outline-offset:2px}.thumb.immersive span:after{content:" · 3D";color:var(--lake)}
details{margin-top:24px;border-top:1px solid var(--rule);padding-top:16px}summary{cursor:pointer;font-size:19px;padding:4px 0;min-height:44px}
.fullgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin-top:18px}.shot{min-width:0;padding-bottom:20px;border-bottom:1px solid var(--rule)}.shot header{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.shot img{width:100%;height:auto;display:block;border-radius:8px}.shot .line{font-size:19px;font-style:italic;margin-top:14px}.shot .dialogue{color:var(--quiet);font-size:14px}.shot .camera{font-size:13px;margin-top:14px}.shot a{font:12px system-ui;color:var(--lake)}
.proof{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.proof figure{margin:0;min-width:0}.proof img{width:100%;height:auto;border-radius:8px}.proof figcaption{font-size:12px;color:var(--quiet)}
.note{font-size:13px;color:var(--quiet);padding:14px 16px;border-left:2px solid var(--lake);background:var(--paper-bright);margin-top:18px}
footer{border-top:1px solid var(--rule);margin-top:32px;padding-top:16px;color:var(--quiet);font-size:13px}
@media(max-width:560px){main{padding:24px 14px 40px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.fullgrid{grid-template-columns:minmax(0,1fr)}.chapters div{font-size:12px;padding:10px 6px}.chapters span{font-size:11px}.counter{width:100%;margin-left:0}.proof{grid-template-columns:minmax(0,1fr)}.caption .narration{font-size:18px}.stagehead{padding:10px 12px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
@media print{.controls,.grid,.stage{display:none}.fullgrid{display:grid}details>summary{display:none}.shot{break-inside:avoid}}
"""
stage_images = "\n".join(f'<img data-frame="{s["id"]}" src="{s["preview"]}" alt="{esc(s["title"])}" width="1200" height="675" class="{"active" if s["id"]=="01" else ""}">' for s in shots)
script = """
const shots = SHOTS;
let index=0,playing=false,timer=null;
const el=id=>document.getElementById(id);
function stop(){playing=false;clearTimeout(timer);el('play').textContent='Play timing preview';el('play').setAttribute('aria-pressed','false')}
function show(n,manual=true){
 if(manual)stop();
 index=Math.max(0,Math.min(shots.length-1,n));
 const s=shots[index];
 document.querySelectorAll('[data-frame]').forEach(img=>img.classList.toggle('active',img.dataset.frame===s.id));
 document.querySelectorAll('[data-scene]').forEach(btn=>btn.setAttribute('aria-current',btn.dataset.scene===s.id?'true':'false'));
 el('scene-label').textContent='SCENE '+s.id+' / 18';
 el('medium').textContent=s.medium;
 el('scene-title').textContent=s.title;
 el('narration').textContent=s.narration;
 el('dialogue').textContent=s.dialogue.split(' | ').join('  /  ');
 el('camera').textContent=s.camera;
 el('counter').textContent=String(s.start).padStart(2,'0')+'–'+s.end+'s · '+s.duration+' seconds';
 el('endcopy').classList.toggle('active',s.id==='18');
 el('prev').disabled=index===0;el('next').disabled=index===shots.length-1;
 if(playing){clearTimeout(timer);timer=setTimeout(()=>{if(index===shots.length-1){stop();return}show(index+1,false)},s.duration*1000)}
}
el('prev').onclick=()=>show(index-1);el('next').onclick=()=>show(index+1);
el('play').onclick=()=>{if(playing){stop();return}playing=true;el('play').textContent='Pause preview';el('play').setAttribute('aria-pressed','true');if(index===shots.length-1)index=0;show(index,false)};
document.querySelectorAll('[data-scene]').forEach(b=>b.onclick=()=>show(shots.findIndex(s=>s.id===b.dataset.scene)));
document.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,select,button,a'))return;if(e.key==='ArrowRight'){e.preventDefault();show(index+1)}if(e.key==='ArrowLeft'){e.preventDefault();show(index-1)}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
show(0);
""".replace("SHOTS", json.dumps(shots, ensure_ascii=False).replace("</","<\\/"))

document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitAway — Take a trip. Leave a trail. Storyboard v2</title><style>{css}</style></head><body><main>
<header class="intro"><div class="eyebrow">GitAway · watercolor story · Sol v2</div><h1>Take a trip.<br>Leave a trail.</h1>
<p>18 scenes. Two couples. One trail, in two seasons. The sketchbook becomes a world you can step into.</p></header>
<div class="chapters"><div>01–05 · Find the way<span>Decide together · 24 seconds</span></div><div>06–10 · Step inside<span>Tahoe in winter · 24 seconds</span></div><div>11–18 · Pass it on<span>Lisbon to summer · 39 seconds</span></div></div>
<section class="stage" aria-label="Scene viewer"><div class="stagehead"><span class="eyebrow" id="scene-label">SCENE 01 / 18</span><span class="tag" id="medium">Watercolor</span></div>
<div class="viewport">{stage_images}<div class="endcopy" id="endcopy"><strong>Take a trip.<br>Leave a trail.</strong><span>GitAway · Start a trip</span></div></div>
<div class="caption" aria-live="polite"><h2 id="scene-title">Fourteen tabs</h2><p class="narration" id="narration"></p><p class="spoken" id="dialogue"></p><p class="camera"><b>Camera & transition</b><span id="camera"></span></p></div></section>
<div class="controls"><button id="prev" type="button">Previous scene</button><button id="play" class="primary" type="button" aria-pressed="false">Play timing preview</button><button id="next" type="button">Next scene</button><span class="counter" id="counter"></span></div>
<div class="grid" aria-label="Choose a scene">{''.join(cards)}</div>
<p class="note">Scenes 06–08 and 16 are visual targets for immersive 3D camera shots. This review shows generated still keyframes; its timing preview changes frames and is silent. It does not yet render the 3D flythrough or a finished video.</p>
<details><summary>All 18 scenes, with dialogue and camera direction</summary><div class="fullgrid">{''.join(articles)}</div></details>
<details><summary>The existing 3D Tahoe foundation</summary><p>These are existing renders from the project’s Three.js world, not the newly generated artwork above. Terrain, water, trees, a cabin, the pier and a moving camera already exist. Matching the watercolor direction and adding the summer look remain video-production work.</p>
<div class="proof"><figure><img src="existing-3d-lake.webp" alt="Existing 3D Tahoe basin" loading="lazy"><figcaption>Lake basin · existing 3D</figcaption></figure><figure><img src="existing-3d-cabin.webp" alt="Existing 3D cabin" loading="lazy"><figcaption>Cabin arrival · existing 3D</figcaption></figure><figure><img src="existing-3d-pier.webp" alt="Existing 3D sunset pier" loading="lazy"><figcaption>Pier at sunset · existing 3D</figcaption></figure></div></details>
<details><summary>Video edit and sound direction</summary><p>87-second landscape master, with a separate portrait reframe. Narration and character dialogue are alternative copy tracks at this stage: choose the character-led or narrator-led cut before recording, rather than trying to fit both into every short shot.</p><p>Sound starts with paper, tabs and a room tone. At scene 06 the page rustle opens into wind, water and distant birds; leave scene 07 almost wordless. Cabin snow and the sled lead to warm room tone. The paper plane carries us to Lisbon. At scene 16, water returns in summer; a restrained musical lift carries the final globe and invitation.</p><p>Use the existing 3D terrain and camera for continuous spatial movement. Image generation supplied the art targets; it did not generate moving video. No generative-video tool is connected in this session. A rendered MP4 combining the artwork, compositing and 3D camera work is the available production route.</p></details>
<footer>Review the scenes in order, or jump straight to the lake shots: 06, 07, 08 and 16. Scene 15 keeps the watercolor image you approved. The original 13-panel board is preserved. Reply with scene numbers and any line or camera changes before the video edit.</footer>
</main><script>{script}</script></body></html>"""
(HERE/"index.html").write_text(document,encoding="utf-8")
with (HERE/"storyboard.md").open("w",encoding="utf-8") as f:
    f.write("# GitAway storyboard v2 — Take a trip. Leave a trail.\n\n18 shots · 87 seconds · storyboard review before video\n\n")
    for s in shots:
        f.write(f"## {s['id']}. {s['title']} ({s['start']}–{s['end']}s)\n\n![{s['title']}]({s['image']})\n\n**Medium:** {s['medium']}\n\n**Caption / optional narration:** {s['narration']}\n\n**Dialogue:** {s['dialogue'] or 'None — environmental sound.'}\n\n**Camera:** {s['camera']}\n\n")
    f.write("## Production status\n\nGenerated artwork and camera targets, not a finished animated film. The existing Three.js Tahoe world provides a 3D foundation; the watercolor treatment and summer scene still need production work. Keep narrator and character dialogue as alternative cuts until the script is locked.\n")
print(f"Built {HERE/'index.html'} — {len(shots)} scenes, {elapsed} seconds")

