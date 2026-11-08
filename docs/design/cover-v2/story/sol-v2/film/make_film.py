"""Render the approved artwork with depth-projected 3D camera scenes, narration and an original score."""
import argparse,json,mimetypes,subprocess,wave
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
REPO=HERE.parents[5]
FPS=24
TOTAL=87
ORIGIN="https://gitaway-film.invalid"
SHOTS=json.loads((BOARD/"shots.json").read_text())
start=0
for s in SHOTS:
    s["start"]=start;start+=s["duration"];s["end"]=start
    if s["id"]=="18":s["image"]="frames/17.png"
VOICE=[
(1,1.0,"Maya and Sam wanted Lake Tahoe. All they had was a guidebook."),
(2,13.5,"So they turned it into a trip. Weather, drives, every booking, one screen."),
(3,30.0,"Then they went. And it was everything."),
(4,49.0,"Back home, they left a trail."),
(5,57.1,"Half a world away, Rosa and Tomás found it. And said thank you."),
(6,62.0,"They made it theirs. A slower morning, a little more soak."),
(7,73.0,"They went. And they left a trail too."),
(8,81.0,"Every trip here grew from another. Take a trip. Leave a trail.")]
def audio():
    rate=48000;mix=np.zeros((TOTAL*rate,2),np.float32);cues=[]
    for n,at,line in VOICE:
        r=subprocess.run(["ffmpeg","-v","error","-i",str(REPO/f"docs/design/cover-v2/e-assets/vo-{n}.ogg"),"-ar",str(rate),"-ac","1","-f","f32le","-"],capture_output=True,check=True)
        a=np.frombuffer(r.stdout,dtype=np.float32).copy()*.82
        f=min(700,len(a)//2);a[:f]*=np.linspace(0,1,f);a[-f:]*=np.linspace(1,0,f)
        i=round(at*rate);mix[i:i+len(a)]+=a[:,None];cues.append({"start":at,"end":at+len(a)/rate,"text":line})
    def note(at,midi,duration=3,gain=.02,pan=0):
        freq=440*2**((midi-69)/12);t=np.arange(int(duration*rate),dtype=np.float32)/rate;a=np.zeros_like(t)
        for k in range(1,7):a+=np.sin(2*np.pi*freq*k*t+.006*np.sin(2*np.pi*.7*t))/(k*k)*np.exp(-t*(1.1+k*.24))
        a*=np.minimum(t/.024,1)*(1-np.maximum((t-duration+.3)/.3,0))*gain
        at=int(at*rate);n=min(len(a),len(mix)-at)
        if n<=0:return
        stereo=np.column_stack((a[:n]*(1-pan*.45),a[:n]*(1+pan*.45)));mix[at:at+n]+=stereo
        for delay,g in ((.17,.15),(.29,.10),(.43,.07)):
            d=int(delay*rate);k=min(n,len(mix)-at-d)
            if k>0:mix[at+d:at+d+k]+=stereo[:k,::-1]*g
    chords=[(50,57,62,66),(47,54,59,62),(43,50,55,59),(45,52,57,61)]
    for bar,at in enumerate(np.arange(0,TOTAL-2,6.0)):
        chord=chords[bar%4]
        for j,midi in enumerate(chord):note(at+j*.32,midi,4,.018,-.4+j*.26)
        for j in range(4):note(at+1.6+j*.95,chord[(j+bar)%4]+12,2.5,.013,(-1)**j*.3)
    rng=np.random.default_rng(8719)
    for a,b,gain in ((24,39,.008),(72,78,.013)):
        n=int((b-a)*rate);noise=rng.normal(0,1,n).astype(np.float32)
        z=np.convolve(noise,np.ones(100,dtype=np.float32)/100,mode="same");t=np.arange(n,dtype=np.float32)/rate
        z*=np.minimum(t,1)*np.minimum((b-a)-t,1)*(.45+.55*np.sin(t*1.7)**2)*gain*10
        i=int(a*rate);mix[i:i+n,0]+=z;mix[i:i+n,1]+=np.roll(z,101)
    for at in (24,53,67):
        n=int(.65*rate);t=np.arange(n)/rate;a=rng.normal(0,1,n).astype(np.float32)*np.sin(np.pi*t/.65)**2*.006
        i=int(at*rate);mix[i:i+n]+=a[:,None]
    f=int(1.6*rate);mix[:f]*=np.linspace(0,1,f)[:,None];mix[-f:]*=np.linspace(1,0,f)[:,None]
    mix=np.tanh(mix*1.2)*.85
    with wave.open(str(HERE/"soundtrack.wav"),"wb") as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes((mix*32767).astype("<i2").tobytes())
    (HERE/"voice-cues.json").write_text(json.dumps(cues,indent=2),encoding="utf-8")
    def stamp(v):
        ms=round(v*1000);return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    (HERE/"gitaway-story.srt").write_text("\n\n".join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(cues))+"\n",encoding="utf-8")
    print("Soundtrack and narrator cues ready",flush=True)

SHELL=r"""<!doctype html><html><head><style>html,body{margin:0;overflow:hidden;background:#f5efe3}canvas#film{display:block;width:100vw;height:100vh}</style><script type="importmap">{"imports":{"three":"/assets/vendor/three-0.187.0/three.cover.min.js"}}</script></head><body><canvas id="film" width="1920" height="1080"></canvas><script type="module">
import {WebGLRenderer,Scene,PerspectiveCamera,PlaneGeometry,Mesh,ShaderMaterial,CanvasTexture,SRGBColorSpace,DoubleSide,Vector3} from 'three';
const shots=SHOTS,cues=CUES,W=1920,H=1080,canvas=document.querySelector('#film'),ctx=canvas.getContext('2d',{alpha:false});
const A=document.createElement('canvas'),B=document.createElement('canvas');A.width=B.width=W;A.height=B.height=H;
const a=A.getContext('2d',{alpha:false}),b=B.getContext('2d',{alpha:false});
const gl=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true,alpha:false});gl.setSize(W,H);gl.setPixelRatio(1);gl.outputColorSpace=SRGBColorSpace;gl.setClearColor(0xf5efe3,1);
const scene=new Scene(),camera=new PerspectiveCamera(45,W/H,.1,30),meshes=new Map();
const pictures=await Promise.all(shots.map(s=>new Promise((res,rej)=>{const i=new Image;i.onload=()=>res(i);i.onerror=rej;i.src='/board/'+s.image})));
function smooth(a,b,v){v=Math.max(0,Math.min(1,(v-a)/(b-a)));return v*v*(3-2*v)}
function depth(id,x,y){let d=8;
if(id===6)d=4.5+5.5*(1-smooth(.2,.92,y));
if(id===7){d=11-6*smooth(.22,.88,y);d-=3.1*(1-smooth(.12,.35,x))*smooth(.03,.6,y);d-=.9*smooth(.72,.98,y)}
if(id===8){d=10-5*smooth(.20,.85,y);d-=2*(1-smooth(.13,.34,x));d-=1.5*smooth(.58,.95,x)}
if(id===16){d=11-6.5*smooth(.25,.97,y);d-=2.7*(1-smooth(.06,.3,x))*smooth(.5,.9,y);d-=1.2*smooth(.76,.98,x)}
return Math.max(3.2,d)}
function meshFor(s){const n=+s.id;if(meshes.has(n))return meshes.get(n);
const tex=new CanvasTexture(pictures[n-1]);tex.colorSpace=SRGBColorSpace;
const geo=new PlaneGeometry(2,2,240,135),p=geo.attributes.position,uv=geo.attributes.uv,tan=Math.tan(45*Math.PI/360);
for(let i=0;i<p.count;i++){let x=uv.getX(i),y=uv.getY(i),d=depth(n,x,1-y);p.setXYZ(i,(x-.5)*2*tan*(W/H)*d*1.075,(y-.5)*2*tan*d*1.075,-d)}p.needsUpdate=true;
const mat=new ShaderMaterial({uniforms:{picture:{value:tex},time:{value:0},water:{value:n===7||n===16?1:0}},side:DoubleSide,
vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
fragmentShader:`uniform sampler2D picture;uniform float time,water;varying vec2 vUv;
void main(){vec2 uv=vUv;float mask=smoothstep(.12,.25,uv.y)*(1.-smoothstep(.55,.65,uv.y));
uv.x+=sin(uv.y*160.+time*1.3)*.00065*mask*water;uv.y+=sin(uv.x*120.-time*.9)*.00035*mask*water;
gl_FragColor=texture2D(picture,uv);
#include <tonemapping_fragment>
#include <colorspace_fragment>
}`});
const m=new Mesh(geo,mat);m.frustumCulled=false;scene.add(m);meshes.set(n,m);return m}
const deep=new Set([6,7,8,16]);
function plane(target,s,u,t){const n=+s.id,im=pictures[n-1];target.fillStyle='#f5efe3';target.fillRect(0,0,W,H);
if(deep.has(n)){const m=meshFor(s);meshes.forEach(mm=>mm.visible=mm===m);const k=u*u*(3-2*u);
camera.position.set((k-.5)*(n===7?.24:n===16?.18:.13),.025*Math.sin(u*Math.PI),-.07-.18*k);camera.lookAt(new Vector3(0,0,-8));camera.updateMatrixWorld();m.material.uniforms.time.value=t;gl.render(scene,camera);target.drawImage(gl.domElement,0,0,W,H);
if(n===8||n===7){target.fillStyle='rgba(255,253,245,.65)';for(let i=0;i<42;i++){const z=(i*.618)%1,x=((i*317.31+t*(14+z*12))%(W+80))-40,y=((i*193.73+t*(40+z*25))%(H+50))-25;target.beginPath();target.arc(x,y,1.2+z*1.8,0,Math.PI*2);target.fill()}}return}
const e=u*u*(3-2*u),z=1.025+(n%2?.025:-.018)*e,dw=W*z,dh=H*z;target.drawImage(im,(W-dw)/2+(n%3-1)*e*12,(H-dh)/2+Math.sin(u*Math.PI)*5,dw,dh);
if(n===12||n===17){target.save();target.globalAlpha=.33;target.strokeStyle=n===12?'#b47d3b':'#2b7f90';target.lineWidth=3;
const ps=n===12?[[.47,.43,.67,.13,.83,.43]]:[[.34,.44,.45,.12,.60,.46],[.46,.59,.61,.48,.64,.68],[.35,.45,.35,.72,.46,.77]];
for(const p of ps){target.beginPath();target.moveTo(p[0]*W,p[1]*H);target.quadraticCurveTo(p[2]*W,p[3]*H,p[4]*W,p[5]*H);target.setLineDash([8,15]);target.lineDashOffset=-t*13;target.stroke()}target.restore()}}
function round(c,x,y,w,h,r){c.beginPath();c.roundRect(x,y,w,h,r)}
function speech(s,u){const n=+s.id;if(!s.dialogue||[1,7,8,11,13,16,17,18].includes(n)||u<.17||u>.95)return;
const all=s.dialogue.split(' | '),f=all[Math.min(all.length-1,Math.floor(u*all.length))],colon=f.indexOf(':'),name=f.slice(0,colon),text=f.slice(colon+1).trim();
ctx.save();ctx.globalAlpha=smooth(.17,.27,u)*(1-smooth(.87,.96,u));ctx.font='italic 36px Georgia';const w=Math.min(1120,ctx.measureText(text).width+80),x=(W-w)/2,y=58;
ctx.fillStyle='rgba(255,251,240,.93)';round(ctx,x,y,w,106,18);ctx.fill();ctx.strokeStyle='rgba(88,71,50,.25)';ctx.lineWidth=1.2;ctx.stroke();ctx.textAlign='center';ctx.fillStyle='#81705d';ctx.font='17px sans-serif';ctx.fillText(name.toUpperCase(),W/2,y+28);ctx.fillStyle='#302b26';ctx.font='italic 36px Georgia';ctx.fillText(text,W/2,y+76);ctx.restore()}
function subtitle(t){const cue=cues.find(c=>t>=c.start&&t<c.end);if(!cue)return;const words=cue.text.split(' '),num=Math.ceil(words.length/10),group=Math.min(num-1,Math.floor((t-cue.start)/(cue.end-cue.start)*num)),text=words.slice(group*10,(group+1)*10).join(' ');
ctx.save();ctx.font='32px Georgia';const w=ctx.measureText(text).width+68,x=(W-w)/2,y=H-100;ctx.fillStyle='rgba(255,251,240,.94)';round(ctx,x,y,w,62,14);ctx.fill();ctx.fillStyle='#302b26';ctx.textAlign='center';ctx.fillText(text,W/2,y+41);ctx.restore()}
window.filmFrame=t=>{let i=shots.findIndex(s=>t<s.end);if(i<0)i=shots.length-1;const s=shots[i],u=Math.min(1,(t-s.start)/s.duration);plane(a,s,u,t);
if(i>0&&t<s.start+.65){plane(b,shots[i-1],1,t);ctx.globalAlpha=1;ctx.drawImage(B,0,0);ctx.globalAlpha=smooth(0,.65,t-s.start);ctx.drawImage(A,0,0);ctx.globalAlpha=1}else ctx.drawImage(A,0,0);
speech(s,u);
if(s.id==='18'){ctx.fillStyle='rgba(245,239,227,'+(.88*smooth(0,.28,u))+')';ctx.fillRect(0,0,W,H);ctx.globalAlpha=smooth(.1,.35,u);ctx.textAlign='center';ctx.fillStyle='#302b26';ctx.font='72px Georgia';ctx.fillText('Take a trip.',W/2,440);ctx.fillText('Leave a trail.',W/2,525);ctx.font='27px Georgia';ctx.fillStyle='#85705d';ctx.fillText('GitAway',W/2,615);ctx.font='23px sans-serif';ctx.fillStyle='#302b26';ctx.fillText('Start a trip',W/2,697);ctx.globalAlpha=1}
subtitle(t);
if(t<.6){ctx.fillStyle='rgba(245,239,227,'+(1-smooth(0,.6,t))+')';ctx.fillRect(0,0,W,H)}
if(t>86.5){ctx.fillStyle='rgba(245,239,227,'+smooth(86.5,87,t)+')';ctx.fillRect(0,0,W,H)}
return {scene:s.id,frame:Math.round(t*24)}};
window.FILM_READY=true;window.filmFrame(0);
</script></body></html>"""
def shell():
    return SHELL.replace("SHOTS",json.dumps(SHOTS,ensure_ascii=False)).replace("CUES",json.dumps(json.loads((HERE/"voice-cues.json").read_text()),ensure_ascii=False))
def render(test=False):
    def serve(route):
        path=urlparse(route.request.url).path
        if path=="/index.html":route.fulfill(body=shell(),content_type="text/html");return
        source=((BOARD/path.removeprefix("/board/")) if path.startswith("/board/") else (REPO/path.lstrip("/"))).resolve()
        if not source.is_relative_to(REPO) or not source.is_file():route.abort();return
        route.fulfill(path=source,content_type=mimetypes.guess_type(source)[0] or "application/octet-stream")
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chromium",args=["--use-angle=vulkan","--enable-features=Vulkan","--ignore-gpu-blocklist","--enable-unsafe-swiftshader"])
        page=browser.new_page(viewport={"width":1920,"height":1080},device_scale_factor=1);errors=[];page.on("pageerror",lambda e:errors.append(str(e)));page.route(ORIGIN+"/**",serve)
        page.goto(ORIGIN+"/index.html");page.wait_for_function("window.FILM_READY",timeout=60000)
        if test:
            for t in (2,14,26,31,36,54,64,69,75,84):print(page.evaluate("t=>window.filmFrame(t)",t),flush=True);page.screenshot(path=HERE/f"film-test-{t:02}.jpg",type="jpeg",quality=92)
            print("Page errors:",errors,flush=True);browser.close();return
        cmd=["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-c:v","mjpeg","-i","-","-an","-c:v","libx264","-threads","4","-preset","fast","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(HERE/"picture-master.mp4")]
        with (HERE/"encode.log").open("w") as err:
            encoder=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=err)
            try:
                for i in range(TOTAL*FPS):
                    page.evaluate("t=>window.filmFrame(t)",i/FPS);encoder.stdin.write(page.screenshot(type="jpeg",quality=94))
                    if i%120==0:print(f"Film: {i/FPS:.0f}/{TOTAL}s ({i}/{TOTAL*FPS} frames)",flush=True)
            finally:encoder.stdin.close()
            if encoder.wait()!=0:raise RuntimeError((HERE/"encode.log").read_text())
        assert not errors,errors;browser.close();print("Picture master complete",flush=True)
def finish():
    chapters=[";FFMETADATA1","title=GitAway — Take a trip. Leave a trail.","artist=GitAway","comment=Watercolor film with depth-projected 3D camera scenes. Kokoro af_heart narration and original procedural score."]
    for s in SHOTS:chapters.extend(["[CHAPTER]","TIMEBASE=1/1000",f"START={s['start']*1000}",f"END={s['end']*1000}",f"title={s['id']}. {s['title']}"])
    (HERE/"chapters.txt").write_text("\n".join(chapters)+"\n",encoding="utf-8")
    master=HERE/"gitaway-take-a-trip-1080p.mp4"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(HERE/"picture-master.mp4"),"-i",str(HERE/"soundtrack.wav"),"-i",str(HERE/"gitaway-story.srt"),"-f","ffmetadata","-i",str(HERE/"chapters.txt"),"-map","0:v","-map","1:a","-map","2","-map_metadata","3","-map_chapters","3","-c:v","copy","-c:a","aac","-b:a","192k","-af","loudnorm=I=-16:TP=-1.5:LRA=9","-ar","48000","-c:s","mov_text","-disposition:s:0","0","-metadata:s:s:0","language=eng","-metadata:s:s:0","title=English narration","-t",str(TOTAL),"-movflags","+faststart",str(master)],check=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(master),"-map","0:v","-map","0:a","-vf","scale=1280:720","-c:v","libx264","-threads","4","-crf","26","-maxrate","1600k","-bufsize","3200k","-preset","fast","-c:a","aac","-b:a","128k","-ar","48000","-movflags","+faststart",str(HERE/"gitaway-take-a-trip-720p.mp4")],check=True)
    print("Finished",master,flush=True)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("mode",choices=["audio","test","render","finish","all"]);a=ap.parse_args();HERE.mkdir(exist_ok=True)
    if a.mode in ("audio","all"):audio()
    if a.mode=="test":render(True)
    if a.mode in ("render","all"):render()
    if a.mode in ("finish","all"):finish()

