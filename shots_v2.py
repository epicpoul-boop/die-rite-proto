import asyncio, sys
from playwright.async_api import async_playwright
URL = 'http://localhost:18431/index.html?seed=7'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        ctx = await b.new_context(viewport={'width':360,'height':780}, device_scale_factor=3, is_mobile=True, has_touch=True)
        page = await ctx.new_page(); errs=[]
        page.on('console', lambda m: errs.append(m.text) if m.type in ('error','warning') else None); page.on('pageerror', lambda e: errs.append(str(e)))
        await page.goto(URL); await page.wait_for_function('window.__game'); await page.wait_for_timeout(2000)
        await page.click('#title'); await page.wait_for_timeout(500)
        G = lambda e: page.evaluate(e)
        await G('__game.freezeSpawns(true); __game.clear()'); await G('__game.setStage(2,true)')
        for x,y,t,k in [(1,1,5,'slime'),(3,2,2,'normal'),(4,4,6,'chained'),(2,4,3,'normal'),(0,3,4,'normal'),(5,0,1,'normal')]: await G(f'__game.place({x},{y},{t},"{k}")')
        await page.wait_for_timeout(1500); await page.screenshot(path='help_button2.png')
        await page.click('#helpBtn'); await page.wait_for_timeout(400); await page.screenshot(path='help_panel2.png'); await page.click('#helpOk')
        await page.click('#view'); await page.wait_for_timeout(1800)
        for x,y,t,k in [(0,0,6,'normal'),(5,5,2,'normal'),(5,0,3,'chained'),(0,5,4,'normal')]: await G(f'__game.place({x},{y},{t},"{k}")')
        await page.wait_for_timeout(700); await page.screenshot(path='iso_zoom2.png')
        print(await G('({t:__game.tileExtents(), b:__game.boardExtents()})'), errs)
        await b.close()
asyncio.run(main())
