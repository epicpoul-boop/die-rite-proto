import asyncio, json, sys
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:18431/index.html?seed=7'
errors = []; results = []
def check(name, ok, extra=''):
    results.append((name, bool(ok), extra)); print(('PASS' if ok else 'FAIL'), name, extra)

async def swipe(page, a, b, steps=6, hold=0.0):
    pa = await page.evaluate(f'__game.tileToScreen({a[0]},{a[1]})'); pb = await page.evaluate(f'__game.tileToScreen({b[0]},{b[1]})')
    await page.mouse.move(pa['x'], pa['y']); await page.mouse.down()
    for i in range(1, steps+1):
        await page.mouse.move(pa['x']+(pb['x']-pa['x'])*i/steps, pa['y']+(pb['y']-pa['y'])*i/steps)
    if hold: await page.wait_for_timeout(int(hold*1000))
    return pa, pb

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--enable-webgl'])
        ctx = await b.new_context(viewport={'width':390,'height':844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text}') if m.type in ('error','warning') else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        await page.goto(URL); await page.wait_for_function('window.__game', timeout=30000)
        await page.wait_for_timeout(2500)
        await page.screenshot(path='screenshot_start.png')
        n = await page.evaluate('__game.dice.length'); check('initial dice spawned', n == 7, str(n))
        # clean scenario
        await page.evaluate('__game.freezeSpawns(true); __game.clear()')
        # 1) roll east x1, top changes; 4 rolls returns
        t0 = await page.evaluate('__game.place(1,2,3)')
        # wait rising irrelevant (place -> idle)
        tops=[t0]
        for i in range(4):
            gx = 1+i
            await swipe(page,(gx,2),(gx+1,2)); 
            await page.mouse.up(); await page.wait_for_timeout(450)
            tops.append(await page.evaluate(f'__game.topAt({gx+1},2)'))
        check('die rolls 1 tile east per swipe', tops[-1] is not None, str(tops))
        check('top face changes each roll', all(tops[i]!=tops[i+1] for i in range(4)), str(tops))
        # 2) ghost preview while finger down
        await page.evaluate('__game.clear()'); await page.evaluate('__game.place(2,2,4)')
        await swipe(page,(2,2),(2,1),hold=0.1)
        await page.screenshot(path='screenshot_ghost.png')
        pred = await page.evaluate('(()=>{const g=__game; return 1})()')
        await page.mouse.up(); await page.wait_for_timeout(450)
        check('swipe up rolls north', await page.evaluate('__game.topAt(2,1)') is not None and await page.evaluate('__game.topAt(2,2)') is None)
        # 3) blocked: edge and die
        await page.evaluate('__game.clear(); __game.place(0,0,5); __game.place(1,0,2)')
        await swipe(page,(0,0),(1,0)); await page.mouse.up(); await page.wait_for_timeout(400)
        check('cannot roll into another die', await page.evaluate('__game.topAt(0,0)') == 5 and await page.evaluate('__game.stateAt(0,0)')=='idle')
        await swipe(page,(0,0),(-1,0)) if False else None
        # edge: swipe left from (0,0) -> screen left of tile
        pa = await page.evaluate('__game.tileToScreen(0,0)')
        await page.mouse.move(pa['x'],pa['y']); await page.mouse.down(); await page.mouse.move(pa['x']-40,pa['y'],steps=5); await page.mouse.up(); await page.wait_for_timeout(400)
        check('cannot roll off board', await page.evaluate('__game.topAt(0,0)') == 5)
        # 4) matching: two 2s -> sinking
        await page.evaluate('__game.clear()')
        await page.evaluate('__game.place(1,1,2)'); await page.evaluate('__game.placeFor(3,1,"W",2)')
        await swipe(page,(3,1),(2,1)); await page.mouse.up(); await page.wait_for_timeout(500)
        st = await page.evaluate('[__game.stateAt(1,1), __game.stateAt(2,1)]')
        check('pair of 2s starts sinking', st == ['sinking','sinking'], str(st))
        await page.screenshot(path='screenshot_sinking.png')
        # 5) chain join: another die with top 2 rolled adjacent joins (single die, would not match alone)
        await page.evaluate('__game.placeFor(2,3,"N",2)')
        await swipe(page,(2,3),(2,2)); await page.mouse.up(); await page.wait_for_timeout(500)
        st = await page.evaluate('__game.stateAt(2,2)')
        check('third 2 joins sinking chain', st == 'sinking', str(st))
        # 6) ones wipe: place 1s elsewhere then roll a 1 next to chain
        await page.evaluate('__game.place(5,5,1); __game.place(0,5,1)')
        await page.evaluate('__game.placeFor(3,2,"W",1)')   # rolls to (2,2)? occupied -> use (3,2)->(2,2) blocked; use different spot
        await page.evaluate('__game.clear()')
        await page.evaluate('__game.place(1,1,2)'); await page.evaluate('__game.placeFor(3,1,"W",2)')
        await swipe(page,(3,1),(2,1)); await page.mouse.up(); await page.wait_for_timeout(450)
        await page.evaluate('__game.place(5,5,1); __game.place(0,5,1); __game.placeFor(2,3,"N",1)')
        await swipe(page,(2,3),(2,2)); await page.mouse.up(); await page.wait_for_timeout(350)
        await page.screenshot(path='screenshot_wipe.png')
        await page.wait_for_timeout(1200)
        ones = await page.evaluate('__game.dice.filter(d=>d.top===1).length')
        check('1 touching sinking chain wipes all 1s', ones == 0, f'ones left={ones}')
        # let chain finish -> score
        await page.wait_for_timeout(3200)
        sc = await page.evaluate('__game.score'); check('score awarded', sc > 0, str(sc))
        check('sunk dice removed', await page.evaluate('__game.dice.length') == 0, str(await page.evaluate('__game.dice')))
        # 7) spawning
        await page.evaluate('__game.clear(); __game.freezeSpawns(false)')
        await page.wait_for_timeout(4200)
        n = await page.evaluate('__game.dice.length'); check('dice spawn periodically', n >= 1, str(n))
        # 8) touch swipe via CDP
        await page.evaluate('__game.freezeSpawns(true); __game.clear(); __game.place(2,3,6)')
        cdp = await ctx.new_cdp_session(page)
        pa = await page.evaluate('__game.tileToScreen(2,3)')
        await cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':pa['x'],'y':pa['y']}]})
        for i in range(1,7):
            await cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':pa['x']+i*8,'y':pa['y']}]})
        await cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        await page.wait_for_timeout(450)
        check('touch swipe rolls die east', await page.evaluate('__game.topAt(3,3)') is not None and await page.evaluate('__game.topAt(2,3)') is None)
        # 9) game over: fill board
        await page.evaluate('__game.clear()')
        await page.evaluate('''(()=>{ let k=0; for(let y=0;y<6;y++)for(let x=0;x<6;x++){ __game.place(x,y,((x+2*y)%2)? ((x+y)%3===0?3:5):((y%2)?4:6)); } })()''')
        await page.wait_for_timeout(1200)
        over = await page.evaluate('__game.over'); st = await page.evaluate('__game.dice.map(d=>d.state+d.top).join()')
        check('game over when board full', over, st[:80])
        await page.screenshot(path='screenshot_over.png')
        await page.click('#again'); await page.wait_for_timeout(500)
        check('restart works', (await page.evaluate('!__game.over && __game.dice.length')) == 7)
        # final nice screenshot: mid game
        await page.evaluate('__game.freezeSpawns(false)'); await page.wait_for_timeout(2600)
        await page.screenshot(path='screenshot.png')
        sc = await page.evaluate('[document.documentElement.scrollWidth, document.documentElement.scrollHeight, window.innerWidth, window.innerHeight]')
        check('no page scroll overflow', sc[0]<=sc[2] and sc[1]<=sc[3], str(sc))
        await b.close()
    check('no console errors/warnings', not errors, '; '.join(errors)[:600])
    print('FAILED' if any(not r[1] for r in results) else 'ALL OK')
asyncio.run(main())
