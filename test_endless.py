import asyncio, sys
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:18431/index.html?seed=7'
VW = int(sys.argv[2]) if len(sys.argv) > 2 else 390
VH = int(sys.argv[3]) if len(sys.argv) > 3 else 844
SHOTS = len(sys.argv) > 4 and sys.argv[4] == 'shots'
errors = []; results = []
def check(name, ok, extra=''):
    results.append((name, bool(ok), extra)); print(('PASS' if ok else 'FAIL'), name, extra)

async def swipe(page, a, b):
    pa = await page.evaluate(f'__game.tileToScreen({a[0]},{a[1]})'); pb = await page.evaluate(f'__game.tileToScreen({b[0]},{b[1]})')
    await page.mouse.move(pa['x'], pa['y']); await page.mouse.down()
    for i in range(1, 7): await page.mouse.move(pa['x']+(pb['x']-pa['x'])*i/6, pa['y']+(pb['y']-pa['y'])*i/6)
    await page.mouse.up(); await page.wait_for_timeout(900)

async def fresh(page, url_extra=''):
    await page.goto(BASE + url_extra); await page.wait_for_function('window.__game', timeout=30000); await page.wait_for_timeout(1800)
    await page.click('#title'); await page.wait_for_timeout(600)
    await page.evaluate('__game.freezeSpawns(true); __game.clear()'); await page.wait_for_timeout(200)

def connected(t):
    pits = {(x, y) for x, y in t['pits']}; walls = {(x, y, k) for x, y, k in t['walls']}
    tiles = [(x, y) for x in range(6) for y in range(6) if (x, y) not in pits]
    seen = {tiles[0]}; st = [tiles[0]]
    while st:
        x, y = st.pop()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            a, b = x+dx, y+dy
            if not (0 <= a < 6 and 0 <= b < 6) or (a, b) in pits or (a, b) in seen: continue
            w = (x, y, 'e') in walls if dx == 1 else (a, b, 'e') in walls if dx == -1 else (x, y, 's') in walls if dy == 1 else (a, b, 's') in walls
            if w: continue
            seen.add((a, b)); st.append((a, b))
    return len(seen) == len(tiles)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--enable-webgl'])
        ctx = await b.new_context(viewport={'width':VW,'height':VH}, device_scale_factor=2, has_touch=True, is_mobile=True)
        page = await ctx.new_page()
        page.on('console', lambda m: errors.append(f'console.{m.type}: {m.text}') if m.type in ('error','warning') else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        G = lambda e: page.evaluate(e)

        # ---- stage 0 is today's game
        await fresh(page)
        si = await G('__game.stageInfo'); check('starts at RITE I, no twists', si['stage'] == 0 and si['label'] == 'RITE I' and not (si['chained'] or si['slime'] or si['pits'] or si['walls']), str(si))
        check('stage 0 spawn interval unchanged (<=4.3s at start)', abs(si['interval'] - 5.1*0.83) < 0.01, str(si['interval']))
        kinds = []
        for i in range(25):
            await G('__game.forceSpawn()'); 
            await G('__game.clear()') if i % 12 == 11 else None
        kinds = await G('(()=>{const k=[];for(let x=0;x<6;x++)for(let y=0;y<6;y++){const v=__game.kindAt(x,y);if(v)k.push(v)}return k})()')
        check('stage 0 only spawns normal dice', len(kinds) > 0 and all(k == 'normal' for k in kinds), str(len(kinds)))
        check('bone dice default + stone hall A', await G('__game.hall') == 'a')
        pf0 = await G('__game.perf.programs')

        # ---- chained
        await fresh(page); await G('__game.setStage(1,false)')
        await G('__game.place(2,2,3,"chained")'); await G('__game.place(4,4,5,"normal")')
        await swipe(page, (2,2), (3,2))
        check('chained die cannot roll', await G('__game.stateAt(2,2)') == 'idle' and await G('__game.topAt(2,2)') == 3 and await G('__game.topAt(3,2)') is None)
        await swipe(page, (4,4), (4,3))  # normal still rolls
        check('normal die still rolls at RITE II', await G('__game.topAt(4,3)') is not None)
        await G('__game.clear()'); await G('__game.place(1,1,2,"chained")'); await G('__game.place(2,1,2,"normal")'); await G('__game.evaluate()'); await page.wait_for_timeout(250)
        check('chained die matches and sinks with its group', await G('__game.stateAt(1,1)') == 'sinking' and await G('__game.stateAt(2,1)') == 'sinking')
        check('sinking frees the chains', await G('__game.kindAt(1,1)') == 'normal')
        await page.wait_for_timeout(7500)
        check('chained match fully removed', await G('__game.topAt(1,1)') is None)
        # spawn mix at stage 1
        # direct distribution through placing/spawning cycle
        ks = await G('(()=>{const out={chained:0,normal:0,slime:0};for(let i=0;i<150;i++){__game.clear();__game.forceSpawn(null);for(let x=0;x<6;x++)for(let y=0;y<6;y++){const k=__game.kindAt(x,y);if(k)out[k]++}}__game.clear();return out})()')
        check('RITE II spawns chained dice (but not slime)', ks['chained'] > 0 and ks['slime'] == 0 and ks['normal'] > ks['chained'], str(ks))
        if SHOTS:
            await G('__game.clear()'); await G('__game.setStage(1,true)')
            for x, y, t, k in [(0,0,6,'normal'),(1,0,6,'chained'),(3,1,4,'chained'),(2,2,3,'normal'),(5,3,1,'chained'),(1,4,5,'normal'),(4,4,2,'chained'),(3,5,6,'normal')]: await G(f'__game.place({x},{y},{t},"{k}")')
            await page.wait_for_timeout(1200); await page.screenshot(path='endless_chained.png')

        # ---- chained look: real chains to floor anchors, cheap, break away
        await fresh(page); await G('__game.setStage(1,false)'); pgm = await G('__game.perf.programs')
        for x, y, t_, k in [(2,2,4,"chained"),(3,2,4,"normal"),(1,4,3,"chained"),(5,5,1,"chained"),(0,0,2,"chained")]: await G(f'__game.place({x},{y},{t_},"{k}")')
        await page.wait_for_timeout(600)
        check('every chained die has its chain mesh (corner dice too)', await G('__game.chainMeshes') == 4, str(await G('__game.chainMeshes')))
        pf = await G('({c:__game.perf.calls, p:__game.perf.programs})')
        check('chains: one extra call per chained die, no new shader programs', pf['c'] <= 20 and pf['p'] == pgm, str(pf) + f' prog0={pgm}')
        await G('__game.place(2,3,4,"normal")'); await G('__game.place(2,1,4,"normal")'); await G('__game.evaluate()'); await page.wait_for_timeout(250)
        check('chains break away (debris) when the die sinks', await G('__game.chainDebris') >= 1 and await G('__game.chainMeshes') == 3, str(await G('({d:__game.chainDebris,m:__game.chainMeshes})')))
        await page.wait_for_timeout(1200)
        check('broken chains are recycled', await G('__game.chainDebris') == 0)
        await G('__game.clear()'); check('clearing the board frees all chains', await G('__game.chainMeshes') == 0)
        if SHOTS:
            await G('__game.setStage(1,true)')
            for x, y, t_, k in [(1,1,6,'chained'),(3,1,4,'normal'),(2,3,3,'chained'),(4,3,5,'normal'),(0,4,2,'chained'),(5,5,1,'chained'),(3,4,6,'normal')]: await G(f'__game.place({x},{y},{t_},"{k}")')
            await page.wait_for_timeout(1500); await page.screenshot(path='chained_new.png')

        # ---- help buttons
        await fresh(page); await G('__game.freezeSpawns(false)'); await G('__game.setStage(2,true)'); await page.wait_for_timeout(500)
        bb = await G('(()=>{const r=document.getElementById("helpBtn").getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,t:document.getElementById("helpBtn").textContent,d:getComputedStyle(document.getElementById("helpBtn")).display,hud:document.getElementById("spawnbar").getBoundingClientRect().bottom,hint:document.getElementById("hint").getBoundingClientRect().top}})()')
        ext = await G('__game.boardExtents()'); st_ = await G('__game.stripTop')
        check('help button shows "SLIME ?" when slime arrives', bb['d'] != 'none' and bb['t'] == 'SLIME ?', str(bb))
        check('help button clear of HUD, board and hint; tappable size', bb['y'] > st_ + 4 and bb['y'] > bb['hud'] and bb['y'] + bb['h'] < bb['hint'] and bb['h'] >= 40 and bb['x'] >= 0 and bb['x'] + bb['w'] <= VW, f"btn y={bb['y']:.0f}-{bb['y']+bb['h']:.0f} strip top={st_:.0f} hint={bb['hint']:.0f}")
        if SHOTS:
            for x, y, t_, k in [(1,1,5,'slime'),(3,2,2,'normal'),(4,4,6,'chained'),(2,4,3,'normal'),(0,3,4,'normal')]: await G(f'__game.place({x},{y},{t_},"{k}")')
            await page.wait_for_timeout(500); await page.screenshot(path='help_button.png')
        n0 = await G('__game.dice.length'); st0 = (await G('__game.stageInfo'))['stageT']
        await page.click('#helpBtn'); await page.wait_for_timeout(300)
        ht_ = await page.inner_text('#helpText')
        check('tap opens the help sheet with what/how/tip', await G('__game.helpOpen') and await page.is_visible('#helpPanel') and all(k in ht_ for k in ['IS ', 'HOW ', 'TIP ']) and 'SLIME' in await page.inner_text('#helpName'))
        pb_ = await G('(()=>{const r=document.getElementById("helpBox").getBoundingClientRect();return {y:r.top,b:r.bottom,x:r.left,r:r.right}})()'); ext = await G('__game.boardExtents()'); st_ = await G('__game.stripTop')
        check('help sheet does not cover the board (above or below it), clear of the HUD, on-screen', (pb_['b'] <= ext['minY'] - 2 or pb_['y'] >= st_) and pb_['y'] >= ext['hudBottom'] and pb_['b'] <= VH and pb_['x'] >= 0 and pb_['r'] <= VW, f"sheet y={pb_['y']:.0f}-{pb_['b']:.0f} board {ext['minY']:.0f}..{st_:.0f} hud {ext['hudBottom']:.0f}")
        if SHOTS: await page.screenshot(path='help_panel.png')
        await page.wait_for_timeout(6000)
        n1 = await G('__game.dice.length'); st1 = (await G('__game.stageInfo'))['stageT']
        check('game is paused while the panel is open (no spawns, clock stopped)', n1 == n0 and abs(st1 - st0) < 0.5, f'{n0}->{n1} stageT {st0:.1f}->{st1:.1f}')
        await page.click('#helpOk'); await page.wait_for_timeout(300)
        check('closing resumes the game and removes the button', not await G('__game.helpOpen') and not await page.is_visible('#helpPanel') and not await page.is_visible('#helpBtn') and await G('__game.helpFor') == 0)
        await page.click('#view'); await page.wait_for_timeout(1500); await G('__game.setStage(4,true)'); await page.wait_for_timeout(300)
        bb = await G('(()=>{const r=document.getElementById("helpBtn").getBoundingClientRect();return {y:r.y,h:r.height}})()'); st_ = await G('__game.stripTop')
        check('[iso] help button clear of the board', bb['y'] > st_ + 4, f"btn y={bb['y']:.0f} strip {st_:.0f}")
        await page.click('#helpBtn'); await page.wait_for_timeout(300)
        pb_ = await G('(()=>{const r=document.getElementById("helpBox").getBoundingClientRect();return {y:r.top,b:r.bottom}})()'); ext = await G('__game.boardExtents()'); st_ = await G('__game.stripTop')
        check('[iso] help sheet does not cover the board', pb_['b'] <= ext['minY'] - 2 or pb_['y'] >= st_, f"sheet {pb_['y']:.0f}-{pb_['b']:.0f} board {ext['minY']:.0f}..{st_:.0f}")
        await page.click('#helpOk'); await page.click('#view'); await page.wait_for_timeout(1500)
        await G('__game.setStage(3,true)'); await page.wait_for_timeout(300); check('PITS button appears for the next twist', await page.inner_text('#helpBtn') == 'PITS ?')
        await G('__game.skipHelpTime(10)'); await page.wait_for_timeout(200); check('button still there after ~10s', await page.is_visible('#helpBtn'))
        await G('__game.skipHelpTime(15)'); await page.wait_for_timeout(300); check('button disappears by itself after ~23s', not await page.is_visible('#helpBtn'))
        await G('__game.setStage(4,true)'); await G('__game.setStage(5,true)'); await page.wait_for_timeout(300)
        check('a newer twist replaces the old button', await page.inner_text('#helpBtn') == 'THE MIX ?')
        await G('__game.freezeSpawns(true)')

        # ---- slime
        await fresh(page); await G('__game.setStage(2,false)')
        await G('__game.place(0,3,3,"slime")'); await swipe(page, (0,3), (1,3))
        check('slime slides to the far wall of the board, never rotates', await G('__game.topAt(5,3)') == 3 and await G('__game.topAt(0,3)') is None, str(await G('__game.dice')))
        await G('__game.clear()'); await G('__game.place(0,2,4,"slime")'); await G('__game.place(4,2,5,"normal")'); await swipe(page, (0,2), (1,2))
        check('slime stops against a die', await G('__game.topAt(3,2)') == 4 and await G('__game.topAt(4,2)') == 5)
        await G('__game.clear()'); await G('__game.place(2,2,4,"slime")'); await G('__game.place(2,3,5,"normal")'); await swipe(page, (2,2), (2,3))
        check('slime cannot move when blocked right away', await G('__game.topAt(2,2)') == 4)
        await G('__game.clear()'); await G('__game.place(0,0,6,"slime")'); await swipe(page, (0,0), (0,1))
        check('slime slides vertically too', await G('__game.topAt(0,5)') == 6)
        # slime stops and matches at the end
        await G('__game.clear()'); await G('__game.place(0,1,2,"slime")'); await G('__game.place(5,1,2,"normal")'); await swipe(page, (0,1), (1,1)); await page.wait_for_timeout(300)
        check('slime slide ends next to a die and evaluates a match', await G('__game.stateAt(4,1)') == 'sinking' and await G('__game.stateAt(5,1)') == 'sinking')
        if SHOTS:
            await G('__game.clear()'); await G('__game.setStage(2,true)')
            for x, y, t, k in [(0,0,2,'slime'),(2,0,5,'normal'),(5,1,6,'slime'),(1,2,3,'normal'),(3,3,1,'slime'),(4,4,4,'normal'),(0,4,6,'slime'),(2,5,3,'chained'),(5,5,5,'chained')]: await G(f'__game.place({x},{y},{t},"{k}")')
            await page.wait_for_timeout(1200); await page.screenshot(path='endless_slime.png')

        # ---- pits
        await fresh(page); await G('__game.setStage(3,false)')
        tr = await G('__game.terrain'); check('RITE IV has pits, still connected', 2 <= len(tr['pits']) <= 5 and connected(tr), str(tr))
        await G('__game.setTerrain([[3,3]], [])'); await G('__game.place(2,3,4)'); await swipe(page, (2,3), (3,3))
        check('die cannot roll into a pit', await G('__game.topAt(2,3)') == 4 and await G('__game.topAt(3,3)') is None)
        await G('__game.clear()'); await G('__game.place(0,3,4,"slime")'); await swipe(page, (0,3), (1,3))
        check('slime stops before a pit', await G('__game.topAt(2,3)') == 4)
        await G('__game.clear()'); await G('__game.setTerrain([[1,1],[4,2],[2,4]], [])')
        okp = True
        for i in range(30):
            await G('__game.clear()'); await G('__game.forceSpawn()')
            for [x, y] in [[1,1],[4,2],[2,4]]:
                if await G(f'__game.topAt({x},{y})') is not None: okp = False
        check('spawns avoid pits', okp)
        await G('__game.clear()'); pl = await G('__game.playable'); check('board full = all non-pit tiles (33 playable)', pl == 33, str(pl))
        for x in range(6):
            for y in range(6):
                if [x, y] not in [[1,1],[4,2],[2,4]]: await G(f'__game.place({x},{y},1)')
        await page.wait_for_timeout(1500)
        check('game over triggers when every non-pit tile is full', await G('__game.over'))
        await G('__game.freezeSpawns(true)')

        # ---- walls
        await fresh(page); await G('__game.setStage(4,false)')
        tr = await G('__game.terrain'); check('RITE V has walls and pits, still connected', len(tr['walls']) >= 3 and len(tr['pits']) >= 2 and connected(tr), str(tr))
        await G('__game.clear()'); await G('__game.setTerrain([], [[2,3,"e"],[4,1,"s"]])')
        await G('__game.place(2,3,4)'); await swipe(page, (2,3), (3,3))
        check('wall blocks a roll across its edge', await G('__game.topAt(2,3)') == 4 and await G('__game.topAt(3,3)') is None)
        await swipe(page, (2,3), (1,3)); check('same die rolls away from the wall', await G('__game.topAt(1,3)') is not None)
        await G('__game.clear()'); await G('__game.place(4,1,4)'); await swipe(page, (4,1), (4,2))
        check('horizontal wall blocks vertical roll', await G('__game.topAt(4,1)') == 4)
        await G('__game.clear()'); await G('__game.place(0,3,3,"slime")'); await swipe(page, (0,3), (1,3))
        check('slime stops at a wall', await G('__game.topAt(2,3)') == 3)
        # walls do not block matching adjacency
        await G('__game.clear()'); await G('__game.place(2,3,2)'); await G('__game.place(3,3,2)'); await G('__game.evaluate()'); await page.wait_for_timeout(250)
        check('walls do not stop matches', await G('__game.stateAt(2,3)') == 'sinking')
        if SHOTS:
            await G('__game.clear()'); await G('__game.setStage(4,true)'); await page.wait_for_timeout(800)
            t = await G('__game.terrain'); pits = {tuple(q) for q in t['pits']}; i = 0
            for x, y in [(0,0),(2,0),(4,1),(1,2),(3,2),(5,3),(0,4),(2,4),(4,5),(3,5),(1,5),(5,0)]:
                if (x, y) in pits: continue
                await G(f'__game.place({x},{y},{[6,3,5,2,4,1][i%6]},"{["normal","normal","chained","slime"][i%4]}")'); i += 1
            await page.wait_for_timeout(1500); await page.screenshot(path='endless_pits_walls.png')

        # ---- board rotation (bottom strip) + screen-relative controls, flat and iso
        for vw in ['flat', 'iso']:
            await fresh(page)
            if vw == 'iso': await page.click('#view'); await page.wait_for_timeout(1500)
            st = await G('__game.stripTop'); ext = await G('__game.boardExtents()')
            check(f'[{vw}] rotate strip starts below the board and above the screen bottom', st >= ext['maxY'] - 80 and st < VH - 60, f"strip from y={st:.0f}, board bottom {ext['maxY']:.0f}")
            ys = st + 22
            async def strip_swipe(x0, x1):
                await page.mouse.move(x0, ys); await page.mouse.down()
                for i in range(1, 7): await page.mouse.move(x0 + (x1 - x0) * i / 6, ys + 2)
                await page.mouse.up()
            # board-area swipe never rotates; strip swipe never rolls dice
            await G('__game.place(2,5,3)')
            pa = await G('__game.tileToScreen(0,0)'); await page.mouse.move(pa['x'] - 10, pa['y']); await page.mouse.down(); await page.mouse.move(pa['x'] + 150, pa['y'], steps=6); await page.mouse.up(); await page.wait_for_timeout(500)
            check(f'[{vw}] horizontal swipe on the board does not rotate', await G('__game.rotQ') == 0 and await G('__game.camRot') == 0)
            await strip_swipe(60, 330); await page.wait_for_timeout(120)
            mid = await G('({r:__game.rotating,c:__game.camRot})'); await page.wait_for_timeout(450)
            fin = await G('({r:__game.rotating,c:__game.camRot,q:__game.rotQ})')
            check(f'[{vw}] strip swipe right turns the camera +90deg, smoothly (~250ms)', mid['r'] and 0 < mid['c'] < 1.5707 and not fin['r'] and abs(fin['c'] - 1.5708) < 0.01 and fin['q'] == 1, f'{mid} {fin}')
            check(f'[{vw}] strip swipe does not move a die above it', await G('__game.topAt(2,5)') == 3 and await G('__game.stateAt(2,5)') == 'idle')
            await strip_swipe(330, 60); await page.wait_for_timeout(500)
            check(f'[{vw}] strip swipe left turns back (-90deg)', await G('__game.rotQ') == 0 and abs(await G('__game.camRot')) < 0.01)
            await G('__game.clear()')
            # screen-relative controls after every rotation
            for q in [1, 2, 3, 4]:
                await strip_swipe(60, 330); await page.wait_for_timeout(500)
                await G('__game.clear()'); await G('__game.place(2,2,3)')
                if vw == 'flat':
                    pdie = await G('__game.tileToScreen(2,2)')
                    away = {1: (-1, 0), 2: (0, 1), 3: (1, 0), 0: (0, -1)}[q % 4]       # camera at +x/-z/-x/+z: "up" = away from the viewer
                    await page.mouse.move(pdie['x'], pdie['y']); await page.mouse.down(); await page.mouse.move(pdie['x'], pdie['y'] - 70, steps=6)
                    gi = await G('__game.ghostInfo'); lab = await G('__game.labelInfo')
                    await page.mouse.up(); await page.wait_for_timeout(700)
                    tgt = (2 + away[0], 2 + away[1])
                    check(f'[flat] after {q*90}deg: swipe UP moves the die away from the viewer', await G(f'__game.topAt({tgt[0]},{tgt[1]})') is not None and await G('__game.topAt(2,2)') is None, f'expected {tgt}')
                    check(f'[flat] after {q*90}deg: ghost preview + direction label on the same neighbour', gi['v'] and abs(gi['x'] - (tgt[0] - 2.5)) < 0.01 and abs(gi['z'] - (tgt[1] - 2.5)) < 0.01 and lab and any(v and abs(v[0] - (tgt[0] - 2.5)) < 0.01 and abs(v[1] - (tgt[1] - 2.5)) < 0.01 for v in lab.values()), f'{gi}')
                else:
                    for nb in [(1,0), (-1,0), (0,1), (0,-1)]:
                        await G('__game.clear()'); await G('__game.place(2,2,3)')
                        pa = await G('__game.tileToScreen(2,2)'); pb = await G(f'__game.tileToScreen({2+nb[0]},{2+nb[1]})')
                        await page.mouse.move(pa['x'], pa['y']); await page.mouse.down()
                        for i in range(1, 7): await page.mouse.move(pa['x'] + (pb['x'] - pa['x']) * i / 6, pa['y'] + (pb['y'] - pa['y']) * i / 6)
                        await page.mouse.up(); await page.wait_for_timeout(600)
                        if await G(f'__game.topAt({2+nb[0]},{2+nb[1]})') is None: check(f'[iso] after {q*90}deg: swipe toward {nb} follows the view', False); break
                    else: check(f'[iso] after {q*90}deg: swipes toward each neighbour follow the view', True)
            if SHOTS and vw == 'flat':
                await G('__game.clear()')
                for x, y, t_, k in [(0,0,6,'normal'),(2,1,3,'chained'),(4,2,4,'normal'),(1,3,5,'slime'),(3,4,2,'normal'),(5,5,1,'normal')]: await G(f'__game.place({x},{y},{t_},"{k}")')
                await strip_swipe(60, 330); await page.wait_for_timeout(110); await page.screenshot(path='rotated_mid.png'); await page.wait_for_timeout(500); await page.screenshot(path='rotated.png')
            if SHOTS and vw == 'iso':
                await G('__game.clear()')
                for x, y, t_, k in [(0,0,6,'normal'),(2,1,3,'chained'),(4,2,4,'normal'),(1,3,5,'slime'),(3,4,2,'normal'),(5,5,1,'normal')]: await G(f'__game.place({x},{y},{t_},"{k}")')
                await page.wait_for_timeout(600); await page.screenshot(path='iso_zoom.png')

        # ---- in-place morph A -> C (dice, pits and walls preserved), then C -> B
        await fresh(page); await G('__game.setStage(4,false)')
        await G('__game.setTerrain([[1,1],[4,4]], [[2,2,"e"],[3,3,"s"]])')
        for x, y, t_, k in [(0,0,6,'normal'),(2,0,3,'chained'),(5,0,5,'normal'),(0,2,2,'slime'),(3,2,4,'normal'),(5,2,1,'normal'),(1,4,6,'normal'),(3,5,2,'chained'),(5,5,3,'normal')]: await G(f'__game.place({x},{y},{t_},"{k}")')
        before = {'dice': await G('JSON.stringify(__game.dice)'), 'terrain': await G('JSON.stringify(__game.terrain)')}
        await G('__game.setStage(5,true)'); await page.wait_for_timeout(1000)
        mid = await G('({hall:__game.hall, dice:JSON.stringify(__game.dice), terrain:JSON.stringify(__game.terrain), calls:__game.perf.calls, morph:__game.morphing})')
        check('morph is a wave in progress (hall switches only at the end)', mid['morph'] and mid['hall'] == 'a', str(mid['hall']))
        check('dice and terrain untouched mid-morph', mid['dice'] == before['dice'] and mid['terrain'] == before['terrain'])
        check('draw calls stay low mid-morph', mid['calls'] <= 45, str(mid['calls']))
        if SHOTS: await page.screenshot(path='endless_transform.png')
        check('transform: just the THE MIX ? button, no toast or panel', await G('document.getElementById("toast").textContent') == '' and await page.inner_text('#helpBtn') == 'THE MIX ?' and not await G('__game.helpOpen'))
        await page.wait_for_timeout(2400)
        after = {'hall': await G('__game.hall'), 'dice': await G('JSON.stringify(__game.dice)'), 'terrain': await G('JSON.stringify(__game.terrain)'), 'morph': await G('__game.morphing')}
        check('morph finished into mossy temple C, nothing cleared or reset', after['hall'] == 'c' and not after['morph'] and after['dice'] == before['dice'] and after['terrain'] == before['terrain'], after['hall'])
        check('morphed board is whole again (tris like a fresh build)', (await G('__game.boardInfo'))['tris'] > 500)
        await G('__game.addStageTime(0)'); await G('__game.setStage(8,true)'); await page.wait_for_timeout(3500)
        check('second transform C -> B (basalt)', await G('__game.hall') == 'b' and await G('JSON.stringify(__game.dice)') == before['dice'] and await G('JSON.stringify(__game.terrain)') == before['terrain'])

        # ---- progression
        await fresh(page, '&stage=0')
        await G('__game.addStageTime(140)'); await page.wait_for_timeout(300)
        check('no twist before 150s', await G('__game.stage') == 0)
        await G('__game.addStageTime(12)'); await page.wait_for_timeout(500)
        si = await G('__game.stageInfo'); check('twist arrives at 150s: RITE II + breather', si['stage'] == 1 and si['chained'] and si['breather'] > 10 and si['interval'] > 5.1*0.83*1.6, str(si))
        callout = await G('({toast:document.getElementById("toast").textContent, call:!!document.getElementById("callout"), hud:document.getElementById("stage").textContent, btn:document.getElementById("helpBtn").textContent, panel:document.getElementById("helpPanel").classList.contains("show")})')
        check('twist arrival: ONLY the blinking help button (no toast, no callout, no auto panel)', callout['toast'] == '' and not callout['call'] and callout['btn'] == 'CHAINED ?' and not callout['panel'] and callout['hud'] == 'RITE II', str(callout))
        await G('__game.addStageTime(-10)'); 
        await G('__game.setStage(1,false)')
        # score milestone
        await G('__game.addStageTime(0)')
        halls = []
        for n in range(1, 12):
            await G(f'__game.setStage({n},false)'); si = await G('__game.stageInfo'); halls.append(si['hall'])
        check('hall: A through the four twists, C once they mix (RITE VI), B at the second escalation (RITE IX)', halls[:4] == ['a']*4 and halls[4:7] == ['c']*3 and halls[7:] == ['b']*4, str(halls))
        pf = await G('({calls:__game.perf.calls, programs:__game.perf.programs})')
        check('no new shader programs from stage changes', pf['programs'] == pf0, f"{pf} vs {pf0}")

        # ---- late game
        await fresh(page, '&stage=12')
        si = await G('__game.stageInfo'); tr = await G('__game.terrain')
        check('?stage=12 jumps to late game with all twists', si['stage'] == 12 and si['chained'] and si['slime'] and si['pits'] and si['walls'] and si['L'] == 6, str(si))
        check('late game caps: pits<=5, walls<=8, connected', len(tr['pits']) <= 5 and len(tr['walls']) <= 8 and len(tr['pits']) >= 3 and connected(tr), str(tr))
        await G('__game.addStageTime(-1000)'); await G('__game.freezeSpawns(false)')
        await G('__game.clear()'); await G('__game.setStage(12,false)')
        iv = (await G('__game.stageInfo'))['interval']; check('late spawn interval ramps but stays sane (>=1.7s, faster than early)', 1.7 <= iv <= 3.2, str(iv))
        # caps over a filled board
        await G('__game.clear()')
        await G('(()=>{window.__mx={c:0,s:0};})()')
        for i in range(60):
            await G('__game.forceSpawn()')
            m = await G('(()=>{let c=0,s=0;for(let x=0;x<6;x++)for(let y=0;y<6;y++){const k=__game.kindAt(x,y);if(k==="chained")c++;if(k==="slime")s++}return [c,s]})()')
            if m[0] > 6 or m[1] > 5: check('late caps hold', False, str(m)); break
        else: check('late caps hold: chained<=6, slime<=5 across 60 spawns', True)
        if SHOTS:
            await G('__game.clear()'); await G('__game.freezeSpawns(true)'); await G('__game.setStage(12,true)'); await page.wait_for_timeout(700)
            t = await G('__game.terrain'); pits = {tuple(q) for q in t['pits']}; i = 0
            for x, y in [(0,0),(1,0),(3,0),(5,0),(2,1),(4,1),(0,2),(3,2),(5,2),(1,3),(2,3),(4,3),(0,4),(3,4),(5,4),(1,5),(2,5),(4,5)]:
                if (x, y) in pits: continue
                await G(f'__game.place({x},{y},{[6,3,5,2,4,1][i%6]},"{["normal","chained","slime","normal","normal"][i%5]}")'); i += 1
            await page.wait_for_timeout(1500); await page.screenshot(path='endless_late.png')

        # ---- perf
        pf = await G('({calls:__game.perf.calls, programs:__game.perf.programs})')
        check('draw calls stay low with a full late board', pf['calls'] <= 45, str(pf))
        ext = await G('__game.tileExtents()'); check('playable tiles stay on screen', ext['minX'] >= 0 and ext['maxX'] <= ext['W'], str(ext))
        check('no console errors/warnings', not errors, '; '.join(errors)[:300])
        await b.close()
    bad = [r for r in results if not r[1]]; print(f'\n{len(results)-len(bad)}/{len(results)} passed'); sys.exit(1 if bad else 0)
asyncio.run(main())
