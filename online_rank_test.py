"""Online N-1 ranking with the REAL server + 3 real browser clients (tokens pre-positioned near home through a test-only harness port)."""
import os,sys,json,subprocess,time,socket,urllib.request
from playwright.sync_api import sync_playwright
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)))
    if not ok: fails.append(n)
s=socket.socket();s.bind(('127.0.0.1',0));PORT=s.getsockname()[1];s.close()
srv=subprocess.Popen(['node','tests/online_rank_harness.js'],cwd=ROOT,env=dict(os.environ,PORT=str(PORT)),stdout=subprocess.PIPE);time.sleep(1.2)
BASE=f'http://127.0.0.1:{PORT}/'
def new(b,name):
    ctx=b.new_context(viewport={'width':390,'height':844});pg=ctx.new_page();pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)));pg.goto(BASE);pg.wait_for_timeout(400)
    pg.evaluate(f"()=>{{PRF.d[0].name='{name}';go('home')}}");return pg
DRIVE="""()=>{if(!M||!M.cfg.online||M.done)return;const p=M.players[M.turn];if(!p||!p.mine)return;if(M.canRoll&&!M.busy&&!gate)document.getElementById('dice').click()}"""
with sync_playwright() as p:
    b=p.chromium.launch();h=new(b,'Hosty');h.evaluate("()=>$('#m-friends').click()");h.click('[data-a=mkroom]');h.click('[data-a=cn][data-v=\"3\"]');h.click('[data-a=docreate]');h.wait_for_function("()=>NET.room&&NET.room.code");code=h.evaluate("()=>NET.room.code")
    gs=[new(b,'Gee'),new(b,'Why')]
    for g in gs:
        g.evaluate("()=>$('#m-friends').click()");g.click('[data-a=joinroom]');g.fill('#rc',code);g.click('[data-a=dojoin]');g.wait_for_function("()=>NET.room&&NET.room.players.length>=2");g.click('[data-a=ready]')
    h.wait_for_function("()=>NET.room.players.length==3&&NET.room.players.every(p=>p.ready)");h.click('[data-a=startroom]')
    pages=[h]+gs
    for pg in pages: pg.wait_for_function("()=>M&&M.cfg.online&&document.getElementById('game').classList.contains('on')",timeout=10000)
    urllib.request.urlopen(f'http://127.0.0.1:{PORT+1}/preset?code={code}').read()
    for pg in pages: pg.reload()
    for pg in pages: pg.wait_for_function("()=>M&&M.cfg.online&&document.getElementById('game').classList.contains('on')&&S.length==12",timeout=15000)
    check('3 real clients resynced to the pre-positioned state (tokens near home)',all(pg.evaluate("()=>S.filter(t=>t.s==HOME).length")==9 for pg in pages))
    t0=time.time();midshot=False;reloaded=False
    while time.time()-t0<120:
        for pg in pages:
            try:pg.evaluate(DRIVE)
            except Exception:pass
        st=[pg.evaluate("()=>({done:M.done,fin:M.rank.length})") for pg in pages]
        if st[0]['fin']==1 and not reloaded and not st[0]['done']:
            reloaded=True;time.sleep(.5);gs[0].reload();gs[0].wait_for_function("()=>M&&M.cfg.online&&S.length>=9",timeout=15000)
            check('after 1st finisher: match NOT over, no celebration yet, Gold badge on finisher card (all clients)',all(not pg.evaluate("()=>M.done")and pg.evaluate("()=>document.getElementById('res').hidden")and pg.evaluate("()=>[...document.querySelectorAll('.pp.fin .rk')].map(e=>e.textContent).join()")=='1st' for pg in pages),[pg.evaluate("()=>[...document.querySelectorAll('.pp.fin .rk')].map(e=>e.textContent).join()") for pg in pages])
            check('a client reconnecting mid-match recovers the finished player\'s rank badge',gs[0].evaluate("()=>M.rank.length")==1)
        if all(x['done'] for x in st):break
        time.sleep(.15)
    time.sleep(3)
    data=[pg.evaluate("""()=>[...document.querySelectorAll('#rank li')].map(li=>li.className.split(' ')[1]+':'+li.querySelector('b').textContent+':'+li.querySelector('small').textContent)""") for pg in pages]
    check('match finished on all 3 clients with 3 ranking rows',all(len(d)==3 for d in data),data)
    check('all clients show the SAME ranking (positions/labels; names differ only because reload resets the in-memory test names)',len({json.dumps([x.split(':')[0]+x.split(':')[2] for x in d]) for d in data})==1,data)
    d=data[0];check('1st Gold, 2nd Silver, last = Eliminated (exactly one loser)','Gold' in d[0] and 'Silver' in d[1] and d[2].startswith('lose') and 'Eliminated' in d[2] and sum(x.startswith('lose') for x in d)==1,d)
    check('no page errors',not any(pg.errs for pg in pages),[pg.errs for pg in pages])
    pages[0].screenshot(path=os.environ.get('SHOT_DIR','/tmp')+'/online_rank.png')
    b.close()
srv.terminate()
print(f"\n{sum(res)}/{len(res)} passed");sys.exit(1 if fails else 0)
