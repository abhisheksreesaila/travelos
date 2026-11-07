import sys, asyncio
from playwright.async_api import async_playwright
BASE = 'file:///home/abhisheksreesaila/Projects/travelos-autopilot/docs/design/cover-v2/d.html'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/abhisheksreesaila/Projects/travelos-autopilot/docs/design/cover-v2/png'
JOBS = [(n, 'wide', 'light') for n in range(1, 8)] + [(1, 'phone', 'light'), (4, 'phone', 'light'), (7, 'phone', 'light'), (7, 'wide', 'dark')]
if len(sys.argv) > 2: JOBS = [j for j in JOBS if f'{j[0]}-{j[1]}-{j[2]}' in sys.argv[2].split(',')]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for n, form, scheme in JOBS:
            vp = {'width': 1440, 'height': 900} if form == 'wide' else {'width': 390, 'height': 844}
            ctx = await b.new_context(viewport=vp, color_scheme=scheme, device_scale_factor=1 if form == 'wide' else 2, has_touch=form == 'phone')
            pg = await ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            await pg.goto(f'{BASE}?scene={n}')
            await pg.wait_for_timeout(4800)
            name = f'd-{n}-{form}' + ('-dark' if scheme == 'dark' else '') + '.png'
            await pg.screenshot(path=f'{OUT}/{name}')
            print(name, errs or 'ok')
            await ctx.close()
        await b.close()
asyncio.run(main())
