"""v8 tests: Google sign-in (server-verified), guest preserved, fresh-device isolation, AdMob reward rules, banner/interstitial placement.
Real server process (tests/test-server-launch.js: fake Google verifier + test SSV key) + real Chromium. The native AdMob/Google SDKs cannot run here,
so the Android bridge (window.LudoAndroid) is simulated in the page - the SERVER-side verification is real."""
import os, sys, json, subprocess, time, socket, tempfile
from playwright.sync_api import sync_playwright
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..')
res=[];fails=[]
def check(n,ok,i=''):
    res.append(bool(ok));print(('PASS ' if ok else 'FAIL ')+n+('' if ok else ' | '+str(i)))
    if not ok: fails.append(n)
def free():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
procs=[]
def server(**kw):
    port=free();env=dict(os.environ,PORT=str(port),TEST_DATA_DIR=kw.pop('data',tempfile.mkdtemp()),**{k:v for k,v in kw.items()})
    procs.append(subprocess.Popen(['node','tests/test-server-launch.js'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT));time.sleep(1.0);return port
DATA=tempfile.mkdtemp()
P_DEV=server(TEST_ADS_MODE='dev',data=DATA)
P_SSV=server(TEST_ADS_MODE='ssv')
P_NOG=server(TEST_CLIENT_ID='')
GOOD={'alice':'good-alice-token-000000000000','bob':'good-bob-token-00000000000000'}
BRIDGE="""(opts)=>{window.__log={rew:0,inter:0,ban:[],google:0};window.LUDO_AD_POLLS=2;const o=opts||{};
window.LudoAndroid={showRewarded(n,u,k){window.__log.rew++;window.__nonce=n;setTimeout(async()=>{const b=o.rewarded||'complete';
 if(b==='complete'||b==='fake'){if(o.ssv&&b==='complete')await fetch('/__test/ssv?nonce='+n+'&tx=tx'+Math.random().toString(36).slice(2));window.onAdResult(n,'completed')}
 else window.onAdResult(n,b)},30)},showInterstitial(){window.__log.inter++},showBanner(v){window.__log.ban.push(!!v)},
 googleSignIn(c){window.__log.google++;setTimeout(()=>window.onGoogleResult(o.google||{idToken:'x'}),30)}}}"""
def ctx(b,port,w=390,h=844):
    c=b.new_context(viewport={'width':w,'height':h});pg=c.new_page();pg.errs=[];pg.on('pageerror',lambda e:pg.errs.append(str(e)));pg.c=c
    pg.goto(f'http://127.0.0.1:{port}/');pg.wait_for_timeout(500);return pg
def on(pg):return pg.evaluate("()=>document.querySelector('.screen.on').id")
with sync_playwright() as p:
    b=p.chromium.launch()
    # ---------- fresh device ----------
    f=ctx(b,P_DEV)
    r=f.evaluate("()=>({c:W.coins,g:W.gems,t:W.tickets,inv:W.inv.length,dl:W.daily.last,sp:W.sp.free+W.sp.ad+W.sp.tk,tx:W.tx.length,st:PRF.d.map(x=>x.st.g+x.st.w+x.xp).reduce((a,b)=>a+b,0),ls:Object.keys(localStorage).filter(k=>/wallet|prof|acct/.test(k))})")
    check('fresh device: default coins/gems, no rewards, no spins, no stats',r['c']==1250 and r['g']==30 and r['t']==0 and r['inv']==0 and r['dl']=='' and r['sp']==0 and r['tx']==0 and r['st']==0,r)
    check('fresh device: no pre-existing account/progress keys',r['ls']==[],r)
    check('fresh device starts on login screen',on(f)=='login')
    f.c.close()
    # ---------- existing device data unchanged + guest ----------
    ex=b.new_context(viewport={'width':390,'height':844});pg=ex.new_page();pg.errs=[]
    pg.goto(f'http://127.0.0.1:{P_DEV}/');pg.evaluate("""()=>{localStorage.setItem('lp-wallet',JSON.stringify({coins:5555,gems:77,inv:['dice:Golden Dice'],daily:{cycle:0,day:2,last:'2026-11-20'}}));const p=JSON.parse(JSON.stringify(PRF.d));p[0].name='OldMe';p[0].xp=321;localStorage.setItem('lp-prof',JSON.stringify(p))}""")
    pg.reload();pg.wait_for_timeout(500)
    a=pg.evaluate("()=>({c:W.coins,g:W.gems,n:PRF.d[0].name,xp:PRF.d[0].xp,s:on0()})".replace('on0()',"document.querySelector('.screen.on').id"))
    check('existing device: wallet+profile loaded unchanged',a['c']==5555 and a['g']==77 and a['n']=='OldMe' and a['xp']==321,a)
    pg.click('#guest');pg.wait_for_timeout(300)
    check('guest login still opens Home',on(pg)=='home')
    pg.evaluate("()=>saveW()");w=pg.evaluate("()=>JSON.parse(localStorage.getItem('lp-wallet'))")
    check('guest data stays in the original keys and unchanged',w['coins']==5555 and w['gems']==77 and pg.evaluate("()=>localStorage.getItem('lp-acct')")is None,w)
    check('guest: settings say guest, no sign-out button',pg.evaluate("()=>/Guest/.test($('#accttxt').textContent)&&$('#signout').hidden"))
    pg.reload();pg.wait_for_timeout(400);check('guest relaunch shows login again (not forced into account)',on(pg)=='login')
    # ---------- google: not configured ----------
    n=ctx(b,P_NOG);n.click('#google');n.wait_for_timeout(800)
    t=n.evaluate("()=>$('#gerr').textContent");check('google not configured -> clear error, stays on login (no auto-success)',on(n)=='login' and 'not set up' in t and n.evaluate("()=>!localStorage.getItem('lp-acct')"),t)
    n.click('#guest');check('guest works even when Google is not configured',on(n)=='home');n.c.close()
    # ---------- google: no server reachable ----------
    nv=b.new_context();q=nv.new_page();q.goto('file://'+os.path.abspath(os.path.join(ROOT,'ludo-prank-v2.html')));q.wait_for_timeout(400);q.click('#google');q.wait_for_timeout(500)
    check('google with no server -> error, no login',on(q)=='login' and 'server' in q.evaluate("()=>$('#gerr').textContent").lower(),q.evaluate("()=>$('#gerr').textContent"));nv.close()
    # ---------- google: web (GIS) cannot load offline ----------
    g=ctx(b,P_DEV);g.click('#google');g.wait_for_timeout(2500)
    check('google web: GIS blocked/offline -> error shown, still login, no coins/home',on(g)=='login' and g.evaluate("()=>$('#gerr').textContent.length>5") and g.evaluate("()=>!localStorage.getItem('lp-acct')"),g.evaluate("()=>$('#gerr').textContent"))
    # ---------- google: bridge cases ----------
    for name,opt,ok_msg in [('forged token',{'google':{'idToken':'forged-token-forged-token-0000'}},'could not be verified'),('user cancelled',{'google':{'error':'cancelled'}},'cancelled'),('sdk failure',{'google':{'error':'boom'}},'failed')]:
        g.evaluate(BRIDGE,opt);g.click('#google');g.wait_for_timeout(700)
        t=g.evaluate("()=>$('#gerr').textContent");check('google '+name+' -> message, no login',on(g)=='login' and ok_msg in t and g.evaluate("()=>!localStorage.getItem('lp-acct')"),t)
    g.c.close()
    # ---------- google: success, sync, restore, isolation ----------
    A=ctx(b,P_DEV);A.evaluate(BRIDGE,{'google':{'idToken':GOOD['alice']}});A.evaluate("()=>{window.__noReload=1}")
    A.click('#guest');A.evaluate("()=>{W.coins=4321;saveW()}");guest_before=A.evaluate("()=>localStorage.getItem('lp-wallet')")
    A.evaluate("()=>go('login')");A.click('#google');A.wait_for_timeout(1500)
    acct=A.evaluate("()=>JSON.parse(localStorage.getItem('lp-acct')||'null')")
    check('google success: session stored (after server verification)',acct and acct['sub']=='g-alice' and acct['token'] and acct['name']=='Alice',acct)
    check('google success: guest data untouched',A.evaluate("()=>localStorage.getItem('lp-wallet')")==guest_before)
    A.evaluate("()=>location.reload()");A.wait_for_timeout(800)
    r=A.evaluate("()=>({s:document.querySelector('.screen.on').id,c:W.coins,t:$('#accttxt').textContent,so:!$('#signout').hidden})")
    check('signed-in relaunch -> Home, account progress is FRESH (not guest data)',r['s']=='home' and r['c']==1250 and 'Alice' in r['t'] and r['so'],r)
    A.evaluate("()=>{W.coins=9999;W.gems=123;saveW();PRF.d[0].name='AliceTop';PRF.save()}");A.wait_for_timeout(3500)
    srv=json.loads(A.evaluate("""async()=>JSON.stringify(await (await fetch('/api/progress',{headers:{authorization:'Bearer '+JSON.parse(localStorage.getItem('lp-acct')).token}})).json())"""))
    check('progress saved to the server account',srv['ok'] and srv['data']['wallet']['coins']==9999 and srv['data']['prof'][0]['name']=='AliceTop',str(srv)[:200])
    check('account data kept under its own keys; guest key still the guest data',A.evaluate("()=>JSON.parse(localStorage.getItem('lp-wallet')).coins")==4321 and A.evaluate("()=>JSON.parse(localStorage.getItem('lp-wallet:g-alice')).coins")==9999)
    # new device, same account
    D2=ctx(b,P_DEV);check('second device: fresh before login',D2.evaluate("()=>W.coins")==1250)
    D2.evaluate(BRIDGE,{'google':{'idToken':GOOD['alice']}});D2.evaluate("()=>{window.__noReload=1}");D2.click('#google');D2.wait_for_timeout(1500);D2.evaluate("()=>location.reload()");D2.wait_for_timeout(800)
    r=D2.evaluate("()=>({c:W.coins,g:W.gems,n:PRF.d[0].name,l:Object.keys(localStorage).filter(k=>k=='lp-wallet')})")
    check("second device + same Google account: progress restored from server",r['c']==9999 and r['g']==123 and r['n']=='AliceTop',r)
    check('second device: no guest wallet key created by sign-in',r['l']==[],r)
    # other account on a third device
    D3=ctx(b,P_DEV);D3.evaluate(BRIDGE,{'google':{'idToken':GOOD['bob']}});D3.evaluate("()=>{window.__noReload=1}");D3.click('#google');D3.wait_for_timeout(1500);D3.evaluate("()=>location.reload()");D3.wait_for_timeout(800)
    check("different Google account never receives Alice's progress",D3.evaluate("()=>W.coins")==1250 and D3.evaluate("()=>PRF.d[0].name")!='AliceTop')
    # sign out -> guest
    D3.evaluate("()=>{W.coins=1500;saveW()}");D3.wait_for_timeout(3200);D3.evaluate("()=>$('#signout').click()");D3.wait_for_timeout(1200)
    r=D3.evaluate("()=>({s:document.querySelector('.screen.on').id,c:W.coins,a:localStorage.getItem('lp-acct'),k:Object.keys(localStorage).filter(k=>/:g-bob/.test(k))})")
    check('sign out -> login screen, guest-fresh data, account keys removed from device',r['s']=='login' and r['c']==1250 and r['a'] is None and r['k']==[],r)
    D3.evaluate(BRIDGE,{'google':{'idToken':GOOD['bob']}});D3.evaluate("()=>{window.__noReload=1}");D3.click('#google');D3.wait_for_timeout(1500);D3.evaluate("()=>location.reload()");D3.wait_for_timeout(800)
    check("sign back in -> Bob's saved progress restored",D3.evaluate("()=>W.coins")==1500)
    for x in (A,D2,D3): x.c.close()
    # ---------- ads ----------
    def adpage(port,**o):
        pg=ctx(b,port);pg.click('#guest');pg.wait_for_timeout(200);pg.evaluate(BRIDGE,o);return pg
    pg=ctx(b,P_DEV);pg.click('#guest');pg.wait_for_timeout(200)
    pg.evaluate("()=>{window.LUDO_AD_POLLS=2}");c0=pg.evaluate("()=>W.coins")
    pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(600)
    check('daily: web without Android ad bridge -> NO reward',pg.evaluate("()=>W.coins")==c0 and pg.evaluate("()=>W.daily.last")=='' and 'Android' in pg.evaluate("()=>document.querySelector('.toast,#toast')?document.querySelector('.toast,#toast').textContent:'Android'"))
    pg.evaluate(BRIDGE,{'rewarded':'closed'});pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(900)
    check('daily: ad closed early -> NO reward',pg.evaluate("()=>W.coins")==c0 and pg.evaluate("()=>W.daily.last")=='' and pg.evaluate("()=>__log.rew")==1)
    pg.evaluate(BRIDGE,{'rewarded':'failed'});pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(900);check('daily: ad failed -> NO reward',pg.evaluate("()=>W.coins")==c0)
    pg.evaluate(BRIDGE,{'rewarded':'unavailable'});pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(900);check('daily: no ad available -> NO reward',pg.evaluate("()=>W.coins")==c0)
    pg.evaluate(BRIDGE,{});pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(1500)
    check('daily: reward credited only after completed + server-verified ad',pg.evaluate("()=>W.coins")==c0+150 and pg.evaluate("()=>W.daily.last")!='')
    pg.evaluate("()=>doClaimDaily()");pg.wait_for_timeout(700)
    check('daily: claimed day does not show another ad or pay again',pg.evaluate("()=>__log.rew")==1 and pg.evaluate("()=>W.coins")==c0+150)
    # nonce is single use
    r=pg.evaluate("""async()=>{const j=async(p,b)=>(await fetch(p,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)})).json();return await j('/api/ads/redeem',{nonce:__nonce,kind:'daily'})}""")
    check('ad proof cannot be redeemed twice (duplicate reward blocked)',r['ok']is False and r['reason']=='already_used',r)
    # weekly
    pg.evaluate("()=>{W.week.prog.days=3;saveW()}");cw=pg.evaluate("()=>W.coins+W.gems+W.tickets");pg.evaluate(BRIDGE,{'rewarded':'closed'});pg.evaluate("()=>doClaimWeekly(0)");pg.wait_for_timeout(900)
    check('weekly: closed ad -> NO reward',pg.evaluate("()=>W.coins+W.gems+W.tickets")==cw and pg.evaluate("()=>!W.week.claimed[0]") and pg.evaluate("()=>__log.rew")==1)
    pg.evaluate(BRIDGE,{});pg.evaluate("()=>doClaimWeekly(0)");pg.wait_for_timeout(1500);check('weekly: credited after verified ad',pg.evaluate("()=>W.coins+W.gems+W.tickets")>cw and pg.evaluate("()=>!!W.week.claimed[0]"))
    pg.evaluate("()=>doClaimWeekly(0)");pg.wait_for_timeout(500);check('weekly: second claim blocked without an ad',pg.evaluate("()=>__log.rew")==1)
    pg.evaluate("()=>doClaimWeekly(4)");pg.wait_for_timeout(500);check('weekly: locked tier shows no ad / no reward',pg.evaluate("()=>__log.rew")==1)
    # spin
    h0=pg.evaluate("()=>W.hist.length");pg.evaluate(BRIDGE,{'rewarded':'closed'});pg.evaluate("()=>{$('#wadb').click()}");pg.wait_for_timeout(900)
    check('spin: closed ad -> no spin granted',pg.evaluate("()=>W.hist.length")==h0 and pg.evaluate("()=>W.sp.ad")==0)
    pg.evaluate("()=>{window.LudoAndroid=undefined}");pg.evaluate("()=>$('#wadb').click()");pg.wait_for_timeout(500);check('spin: no ad bridge -> no spin',pg.evaluate("()=>W.hist.length")==h0)
    pg.evaluate(BRIDGE,{});pg.evaluate("()=>$('#wadb').click()");pg.wait_for_timeout(6500)
    check('spin: bonus spin only after verified ad',pg.evaluate("()=>W.hist.length")==h0+1 and pg.evaluate("()=>W.sp.ad")==1 and pg.evaluate("()=>W.hist[W.hist.length-1].src")=='ad')
    for i in range(4):
        pg.evaluate("()=>{$('#wadb').click()}");pg.wait_for_timeout(5800)
    check('spin: ad-spin daily cap (3) enforced',pg.evaluate("()=>W.sp.ad")==3,pg.evaluate("()=>W.sp.ad"))
    pg.c.close()
    # ---------- ssv production mode ----------
    s=ctx(b,P_SSV);s.click('#guest');s.evaluate(BRIDGE,{'rewarded':'fake'});c0=s.evaluate("()=>W.coins")
    s.evaluate("()=>doClaimDaily()");s.wait_for_timeout(3500)
    check('production mode: app-reported "completed" WITHOUT Google SSV -> NO reward (fake completion blocked)',s.evaluate("()=>W.coins")==c0 and s.evaluate("()=>W.daily.last")=='')
    r=s.evaluate("""async()=>(await (await fetch('/api/ads/complete',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({nonce:__nonce})})).json())""")
    check('production mode: client cannot self-complete an ad',r.get('error')=='ssv_required',r)
    s.evaluate(BRIDGE,{'rewarded':'complete','ssv':1});s.evaluate("()=>doClaimDaily()");s.wait_for_timeout(2500)
    check('production mode: signed SSV callback + completion -> reward',s.evaluate("()=>W.coins")==c0+150)
    s.c.close()
    # ---------- banners / interstitial ----------
    m=ctx(b,P_DEV);m.click('#guest');m.evaluate(BRIDGE,{});m.evaluate("()=>{go('store');go('rw');go('home');startMatch({n:2,h:2});}");m.wait_for_timeout(400)
    ban=m.evaluate("()=>__log.ban");check('banner shown on Store/Home, hidden on rewards and in gameplay',ban==[True,False,True,False],ban)
    c1=m.evaluate("()=>[W.coins,W.gems]");m.evaluate("()=>{go('home');go('store');go('inv')}");check('banner views grant nothing',m.evaluate("()=>[W.coins,W.gems]")==c1 and m.evaluate("()=>__log.rew")==0)
    m.evaluate("()=>startMatch({n:2,h:2})");m.wait_for_timeout(1500);check('no interstitial during active gameplay',m.evaluate("()=>__log.inter")==0)
    for i in range(2):
        m.evaluate("()=>{startMatch({n:2,h:2})}");m.wait_for_timeout(300);m.evaluate("()=>endMatch(M)");m.wait_for_timeout(600)
        check(f'no interstitial while result screen {i+1} is showing',m.evaluate("()=>__log.inter")==0)
        m.evaluate("()=>{$('#rhome').click()}");m.wait_for_timeout(300)
    check('interstitial shown once, at the natural transition after the 2nd finished match',m.evaluate("()=>__log.inter")==1 and on(m)=='home',m.evaluate("()=>__log.inter"))
    m.evaluate("()=>{startMatch({n:2,h:2})}");m.wait_for_timeout(200);m.evaluate("()=>endMatch(M)");m.wait_for_timeout(400);m.evaluate("()=>{$('#rhome').click()}");m.evaluate("()=>{startMatch({n:2,h:2})}");m.wait_for_timeout(200);m.evaluate("()=>endMatch(M)");m.wait_for_timeout(400);m.evaluate("()=>{$('#rhome').click()}")
    check('interstitial frequency cap (3 min) respected',m.evaluate("()=>__log.inter")==1)
    errs=[]
    b.close()
for p_ in procs:p_.terminate()
print(f'{sum(res)}/{len(res)} passed');sys.exit(1 if fails else 0)
