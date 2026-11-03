import asyncio, sys, json, statistics
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv)>1 else 'http://localhost:18431/index.html?seed=7'
async def metrics(cdp):
    m = await cdp.send('Performance.getMetrics'); return {x['name']:x['value'] for x in m['metrics']}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page(); errs=[]
        page.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(page); await cdp.send('Performance.enable')
        await page.goto(URL); await page.wait_for_function('window.__game'); await page.wait_for_timeout(1500)
        await page.click('#title'); await page.wait_for_timeout(1500)
        await page.evaluate('__game.freezeSpawns(true); __game.clear()')
        # two chains of 2s and 3s, plus ones near, to exercise sink/pop/burst/popup/toast
        await page.evaluate('''(()=>{ for(let x=0;x<6;x++) __game.place(x,0,2); for(let x=0;x<6;x++) __game.place(x,2,3); __game.evaluate(); })()''')
        await page.wait_for_timeout(500)
        st = await page.evaluate('__game.dice.map(d=>d.state).join()'); print('states', st)
        await page.evaluate('__game.resetPerf()')
        m0 = await metrics(cdp); prog0 = await page.evaluate('__game.perf.programs')
        pre = await page.evaluate('({calls:__game.perf.calls, tris:__game.perf.tris, programs:__game.perf.programs, geoms:__game.perf.geoms, texs:__game.perf.texs})')
        await page.wait_for_timeout(9000)   # sink (6s) + pop + particles + popups
        m1 = await metrics(cdp)
        post = await page.evaluate('({cpu:Array.from(__game.perf.cpu).slice(0,Math.min(300,__game.perf.n)), max:__game.perf.maxCpu, programs:__game.perf.programs, geoms:__game.perf.geoms})')
        cpu=sorted(post['cpu']); 
        d = lambda k: m1[k]-m0[k]
        print(json.dumps({'drawCallsWith12dice':pre['calls'],'tris':pre['tris'],'programsBefore':prog0,'programsAfter':post['programs'],'geoms':post['geoms'],
          'frameCPU_ms_avg':round(statistics.mean(cpu),2),'p95':round(cpu[int(len(cpu)*.95)],2),'max':round(post['max'],1),
          'LayoutCount':d('LayoutCount'),'RecalcStyleCount':d('RecalcStyleCount'),'LayoutDur_ms':round(d('LayoutDuration')*1000,1),'StyleDur_ms':round(d('RecalcStyleDuration')*1000,1),
          'ScriptDur_ms':round(d('ScriptDuration')*1000,1),'JSHeapUsed_delta_KB':round(d('JSHeapUsedSize')/1024),'errors':errs}, indent=1))
        await b.close()
asyncio.run(main())
