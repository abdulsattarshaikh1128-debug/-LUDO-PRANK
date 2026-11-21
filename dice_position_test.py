import os
import sys, json, time
from playwright.sync_api import sync_playwright
URL='file://'+os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ludo-prank-v2.html'))
JS_SAMPLE="""()=>{const d=document.getElementById('dice');if(!M)return null;const pl=M.players[M.turn];const par=d.parentElement;
const r=d.getBoundingClientRect(),bw=document.querySelector('#game .bw').getBoundingClientRect();
const rects=[...document.querySelectorAll('#game .pp')].filter(e=>e.style.visibility!='hidden').map(e=>e.getBoundingClientRect());
const ov=(a,b)=>!(a.right<=b.left+0.5||a.left>=b.right-0.5||a.bottom<=b.top+0.5||a.top>=b.bottom-0.5);
const pips=d.querySelectorAll('s.p').length;
return {turn:M.turn,k:pl.k,parent:par.id,n:M.cfg.n,cnt:document.querySelectorAll('#dice').length,state:M.dice.state,val:M.dice.value,pips,
 overlapBoard:ov(r,bw),overlapPanel:rects.some(p=>ov(r,p)),inView:r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,
 cx:Math.round(r.left+r.width/2),bcx:Math.round(bw.left+bw.width/2),below:r.top>=bw.bottom-1,anim:d.getAnimations().length}}"""
def run(n,w,h,secs,label,human=0):
    out={'label':label,'n':n,'size':f'{w}x{h}'}
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={'width':w,'height':h})
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.evaluate("()=>{try{localStorage.clear()}catch(e){}}")
        pg.evaluate(f"()=>startMatch({{n:{n},h:{human},diff:'medium'}})")
        seq=[];bad=[];t0=time.time();last=None
        while time.time()-t0<secs:
            s=pg.evaluate(JS_SAMPLE)
            if s:
                if s['state']=='settled' and s['pips']!=s['val'] : bad.append(('face!=result',s))
                if s['cnt']!=1: bad.append(('dupe',s))
                settled = s['anim']==0
                if settled:
                    if not s['inView']: bad.append(('offscreen',s))
                    if s['n']<4:
                        if s['parent']!='ds-'+s['k']: bad.append(('wrong side',s))
                        if s['overlapBoard'] or s['overlapPanel']: bad.append(('overlap',s))
                    else:
                        if s['parent']!='dock': bad.append(('not dock',s))
                        if abs(s['cx']-s['bcx'])>2 or not s['below']: bad.append(('not centred below board',s))
                if last!=(s['turn'],s['parent']): seq.append((s['turn'],s['k'],s['parent'])); last=(s['turn'],s['parent'])
            time.sleep(.04)
        from collections import Counter
        out.update(seq=' '.join(x[1] for x in seq[:16]),parents=sorted(set(x[2] for x in seq)),transitions=len(seq),bad=dict(Counter(x[0] for x in bad)),first_bad=bad[:1],errors=errs)
        if w==390: pg.screenshot(path=os.path.join(os.environ.get('TMPDIR','/tmp'),f'shot_{label}.png'))
        b.close()
    return out
if __name__=='__main__':
    cases=json.loads(sys.argv[1]); res=[run(**c) for c in cases]; print(json.dumps(res,indent=1))
