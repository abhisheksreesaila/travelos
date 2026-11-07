"""Screenshots and a silent-autoplay video of cover E. pixi run python docs/design/cover-v2/shoot-e.py [only=1-wide,5-phone] [video]"""
import sys, asyncio, pathlib
from playwright.async_api import async_playwright
HERE = pathlib.Path(__file__).resolve().parent
BASE = (HERE / 'e.html').as_uri()
OUT = HERE / 'png'
JOBS = [(n, 'wide', 'light') for n in range(1, 9)] + [(1, 'phone', 'light'), (5, 'phone', 'light'), (8, 'phone', 'light'), (8, 'wide', 'dark')]
args = sys.argv[1:]
only = next((a[5:].split(',') for a in args if a.startswith('only=')), None)
T = next((a[2:] for a in args if a.startswith('t=')), '0.6')
if only: JOBS = [j for j in JOBS if f'{j[0]}-{j[1]}' + ('-dark' if j[2] == 'dark' else '') in only]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for n, form, scheme in ([] if 'videoonly' in args else JOBS):
            vp = {'width': 1440, 'height': 900} if form == 'wide' else {'width': 390, 'height': 844}
            ctx = await b.new_context(viewport=vp, color_scheme=scheme, device_scale_factor=1 if form == 'wide' else 2, has_touch=form == 'phone')
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            await pg.goto(f'{BASE}?beat={n}&t={T}')
            await pg.wait_for_timeout(1500)
            name = f'e-{n}-{form}' + ('-dark' if scheme == 'dark' else '') + '.png'
            await pg.screenshot(path=str(OUT / name)); print(name, errs or 'ok')
            await ctx.close()
        if 'video' in args or 'videoonly' in args:
            ctx = await b.new_context(viewport={'width': 1280, 'height': 720}, record_video_dir=str(OUT / 'vid'), record_video_size={'width': 1280, 'height': 720})
            pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            await pg.goto(BASE); await pg.wait_for_timeout(25500)
            v = pg.video; await ctx.close(); src = await v.path()
            pathlib.Path(src).rename(OUT / 'e-autoplay.webm'); (OUT / 'vid').rmdir(); print('e-autoplay.webm', errs or 'ok')
        if 'audio' in args:
            ctx = await b.new_context(); pg = await ctx.new_page(); await pg.goto(BASE)
            res = await pg.evaluate("""() => Promise.all([1,2,3,4,5,6,7,8].map(i => new Promise(r => { const a = new Audio(`e-assets/vo-${i}.ogg`);
              a.onloadedmetadata = () => r(`vo-${i}.ogg ${a.duration.toFixed(2)}s`); a.onerror = () => r(`vo-${i}.ogg FAILED`); })))""")
            print('\n'.join(res)); await ctx.close()
        if 'sound' in args:
            ctx = await b.new_context(viewport={'width': 1440, 'height': 900}); pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            await pg.add_init_script("""window.__plays = []; const P = HTMLMediaElement.prototype.play;
              HTMLMediaElement.prototype.play = function () { window.__plays.push(this.src.split('/').pop() + '@' + performance.now().toFixed(0)); return P.call(this); };""")
            await pg.goto(f'{BASE}'); await pg.wait_for_timeout(1500)
            await pg.click('#sound'); await pg.wait_for_timeout(5600)
            label = await pg.inner_text('#sound'); plays = await pg.evaluate('window.__plays')
            cap = await pg.inner_text('#cap')
            await pg.click('#sound'); muted = await pg.evaluate("document.body.classList.contains('muted')")
            await pg.click('.seg:nth-child(5)'); await pg.wait_for_timeout(300); cap5 = await pg.inner_text('#cap')
            print('sound:', label, '| plays:', plays, '| caption:', cap, '| muted after 2nd tap:', muted, '| step 5 caption:', cap5, '|', errs or 'ok'); await ctx.close()
        if 'rm' in args:
            ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce'); pg = await ctx.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            await pg.goto(BASE); await pg.wait_for_timeout(1200); await pg.screenshot(path='/tmp/e-tools/rm-1.png')
            await pg.click('.seg:nth-child(8)'); await pg.wait_for_timeout(1200); await pg.screenshot(path='/tmp/e-tools/rm-8.png')
            print('reduced motion', errs or 'ok'); await ctx.close()
        await b.close()
asyncio.run(main())
