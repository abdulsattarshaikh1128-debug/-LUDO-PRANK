import os
import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch();pg=b.new_page(viewport={'width':390,'height':844});errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ludo-prank-v2.html')));pg.evaluate("()=>startMatch({n:2,h:2})")
    log=[];ok=True
    for step in range(14):
        # wait until human can roll
        pg.wait_for_function("()=>M&&M.canRoll&&!M.busy",timeout=15000)
        before=pg.evaluate("()=>({t:M.turn,k:M.players[M.turn].k,par:document.getElementById('dice').parentElement.id,s:S.map(t=>t.s)})")
        pg.click('#dice',force=True)
        pg.wait_for_function("()=>M.dice.state=='settled'",timeout=8000)
        r=pg.evaluate("()=>({v:M.dice.value,pips:document.querySelectorAll('#dice s.p').length,par:document.getElementById('dice').parentElement.id,elig:M.elig.length})")
        pg.wait_for_function("()=>M.busy===false||M.canRoll",timeout=8000)
        moved=None
        if r['elig']:
            pg.evaluate("()=>pick(M,M.elig[0])")
            pg.wait_for_function("()=>!M.busy",timeout=15000);time.sleep(.2)
        after=pg.evaluate("()=>({t:M.turn,par:document.getElementById('dice').parentElement.id,s:S.map(t=>t.s),again:M.canRoll,cnt:document.querySelectorAll('#dice').length})")
        diff=[(a,c) for a,c in zip(before['s'],after['s']) if a!=c]
        log.append((before['k'],r['v'],r['pips']==r['v'],r['par']==before['par'],diff,after['par'],after['t']))
        if r['pips']!=r['v'] or after['cnt']!=1 or r['par']!='ds-'+before['k']: ok=False
        if after['par']!='ds-'+pg.evaluate("()=>M.players[M.turn].k"): ok=False
    for l in log: print(l)
    print('ALL OK' if ok else 'FAIL',errs)
    b.close()
