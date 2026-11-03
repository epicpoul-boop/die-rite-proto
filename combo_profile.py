import asyncio, sys, json, statistics
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv)>1 else 'http://localhost:18431/index.html?seed=7'
RATE = float(sys.argv[2]) if len(sys.argv)>2 else 6
async def metrics(cdp):
    m = await cdp.send('Performance.getMetrics'); return {x['name']:x['value'] for x in m['metrics']}
def stats(a):
    if not a: return {}
    a=sorted(a); return {'n':len(a),'avg':round(statistics.mean(a),1),'p95':round(a[int(len(a)*.95)],1),'max':round(a[-1],1),'over33ms':sum(1 for x in a if x>33),'over50ms':sum(1 for x in a if x>50)}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page(); errs=[]
        page.on('pageerror', lambda e: errs.append(str(e)))
        cdp = await ctx.new_cdp_session(page); await cdp.send('Performance.enable')
        await page.goto(URL); await page.wait_for_function('window.__game'); await page.wait_for_timeout(1500)
        await page.click('#title'); await page.wait_for_timeout(1200)
        await page.evaluate('''window.__ft=[]; window.__lt=[]; (function f(t){__ft.push(t); requestAnimationFrame(f)})(0);
          try{ new PerformanceObserver(l=>l.getEntries().forEach(e=>__lt.push([performance.now(),e.duration]))).observe({entryTypes:['longtask']}) }catch(e){}''')
        await page.evaluate('__game.freezeSpawns(true); __game.clear(); for(let x=0;x<5;x++) __game.place(x,1,6); __game.placeFor(5,2,"N",6)')
        await page.wait_for_timeout(600)
        await cdp.send('Emulation.setCPUThrottlingRate', {'rate': RATE})
        await page.wait_for_timeout(300)
        res = {}
        pa = await page.evaluate('__game.tileToScreen(5,2)'); pb = await page.evaluate('__game.tileToScreen(5,1)')
        async def window(name, ms):
            m0 = await metrics(cdp); t0 = await page.evaluate('performance.now()')
            await page.wait_for_timeout(ms)
            m1 = await metrics(cdp); t1 = await page.evaluate('performance.now()')
            fr = await page.evaluate(f'(()=>{{const a=__ft.filter(t=>t>={t0}&&t<={t1});const d=[];for(let i=1;i<a.length;i++)d.push(a[i]-a[i-1]);return d}})()')
            lt = await page.evaluate(f'__lt.filter(x=>x[0]>={t0}&&x[0]<={t1}).map(x=>x[1])')
            busy = (m1['TaskDuration']-m0['TaskDuration'])*1000
            res[name] = {'frame_intervals_ms': stats(fr), 'main_thread_busy_%': round(busy/(t1-t0)*100,1), 'script_ms': round((m1['ScriptDuration']-m0['ScriptDuration'])*1000), 'layout_n': int(m1['LayoutCount']-m0['LayoutCount']), 'style_n': int(m1['RecalcStyleCount']-m0['RecalcStyleCount']), 'longtasks': len(lt), 'longest_task_ms': round(max(lt),0) if lt else 0}
        # trigger the combo with a real swipe
        await page.mouse.move(pa['x'], pa['y']); await page.mouse.down()
        for i in range(1,7): await page.mouse.move(pa['x']+(pb['x']-pa['x'])*i/6, pa['y']+(pb['y']-pa['y'])*i/6)
        await page.mouse.up()
        await window('A_trigger_0-0.8s', 800)
        await window('B_sinking_0.8-5.8s', 5000)
        st = await page.evaluate('__game.dice.map(d=>d.state).join()'); res['states_at_B_end']=st
        await window('C_pop_5.8-8.3s', 2500)
        res['errors']=errs
        print(json.dumps(res, indent=1))
        await b.close()
asyncio.run(main())
