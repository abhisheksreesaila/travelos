"""Offline Three.js capture: Playwright serves repository files in memory; no HTTP server."""
import argparse
import json
import mimetypes
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
ORIGIN = "https://gitaway-film.invalid"
FPS = 24
SHELL = """<!doctype html><html><head><style>*{box-sizing:border-box}html,body{margin:0;overflow:hidden}.cv-stage{width:100vw;height:100vh}canvas{width:100%;height:100%;display:block}.cv-anchors{display:none}</style>
<script type="importmap">{"imports":{"three":"/assets/vendor/three-0.187.0/three.cover.min.js"}}</script></head>
<body><div class="cv-stage"><canvas></canvas></div><div class="cv-anchors"></div>
<script>
window.STATE={chapter:1,local:.6,travel:0,cam:1,N:7};
window.GA_COVER={assets:'/assets/cover/',tier:'mid',Q:new URLSearchParams('capture'),debug:true,REDUCE:true,layout:'wide',mode:'light',visible:true,still:false,on:()=>{},tick:()=>window.STATE,weak:()=>{window.FILM_ERROR='WebGL failed'},ready:()=>{window.FILM_READY=true}};
</script><script type="module" src="/cover3d/src/main.js"></script></body></html>"""

HOOK = """
const summerU = { ...FU, uSnowCol: { value: new Color(0xb8afa0) } };
const summerT = { ...T, places: { ...P, cabin: P.sand, nextCabin: [P.sand[0]+180,P.sand[1]+100] } };
const sandForest = buildForest(summerT, {...q, heroR:210, craftR:90, heroCell:14, midCell:100, rocks:220,
 forestBox:[P.sand[0]-1500,P.sand[1]-1500,P.sand[0]+1500,P.sand[1]+1500]},summerU,[]);
sandForest.traverse(o=>{if(o.material && o.material.userData && 'snowScale' in o.material.userData)o.material.userData.snowScale=0;});
sandForest.visible=false; scene.add(sandForest);
window.__film = {
 T, S,
 frame(shot,u) {
  const summer=shot===16;
  window.STATE = shot===6 ? {chapter:0,local:1,travel:0.12+u*.88,cam:0.12+u*.88,N:7} :
    {chapter:shot===8?2:1,local:shot===8?0:.8,travel:0,cam:shot===8?2:1,N:7};
  update(window.STATE,1/24);
  if(shot!==6) {
   book.visible=false; trail.visible=fork.visible=route.visible=pins.visible=tree.visible=treePins.visible=false;
   family.visible=car.visible=cards.visible=false;
   netTrails.forEach(o=>o.visible=false);
   camera.clearViewOffset(); camera.up.set(0,1,0); camera.fov=48;
   if(shot===7) {
    const A=P.emerald, B=P.island;
    camera.position.set(A[0]+1750-u*1050,900-u*470,A[1]+1900-u*1050);
    camera.position.y=Math.max(camera.position.y,T.landH(camera.position.x,camera.position.z)+70);
    camera.lookAt(B[0],35,B[1]-100);
    cabin.visible=next.visible=pier.visible=false;
   }
   if(shot===8) {
    camera.position.copy(C).addScaledVector(DH,46-u*17).addScaledVector(SD,15-u*7);
    camera.position.y=C.y+8-u*2.2;
    camera.lookAt(C.x,C.y+5,C.z);
    cabin.visible=true;
    forest.children.forEach(m=>{if(m.userData.hero)m.visible=Math.hypot(camera.position.x-m.userData.center[0],camera.position.z-m.userData.center[1])<m.userData.R+1400;});
    midForest.visible=true;
    S.sun.castShadow=true;
    S.sun.position.copy(C).addScaledVector(TU.uLightDir.value,700);S.sun.target.position.copy(C);S.sun.target.updateMatrixWorld();
    renderer.shadowMap.needsUpdate=true;
   }
   if(summer) {
    const A=P.sand;
    // Approach the eastern shore from the water, then ease sideways beside its granite.
    camera.position.set(A[0]-150+u*55,18-u*9,A[1]+130-u*95);
    camera.position.y=Math.max(camera.position.y,(T.waterY(camera.position.x,camera.position.z)??T.landH(camera.position.x,camera.position.z))+5);
    camera.lookAt(A[0]+30,14,A[1]-30);
    camera.fov=52;
    TU.uSnow.value.set(0xc1b992);TU.uRock.value.set(0xb2a99a);TU.uCanopy.value.set(0x304b32);TU.uSparkle.value=0;
    TU.uHero.value[0].set(A[0],A[1],210);
    forest.visible=false;towns.visible=false;cabin.visible=next.visible=pier.visible=false;
    summerU.uTime.value=time;sandForest.visible=true;
    SKYU.uZen.value.set(0x4c8ebe);SKYU.uMid.value.set(0x8dc3d6);SKYU.uHor.value.set(0xe9dfc4);
    SKYU.uHaze.value.set(0xe6dfcb);SKYU.uHazeDensity.value=1/90000;
    SKYU.uSunDir.value.set(...sunDir(145,58));
    TU.uLightDir.value.copy(SKYU.uSunDir.value);
    S.sun.position.copy(camera.position).addScaledVector(TU.uLightDir.value,700);S.sun.target.position.set(A[0],0,A[1]);S.sun.target.updateMatrixWorld();
    S.sun.castShadow=false;
   } else {forest.visible=true;sandForest.visible=false;towns.visible=true;}
   camera.updateProjectionMatrix();camera.updateMatrixWorld();
   sky.position.copy(camera.position);stars.position.copy(camera.position);
   snow.userData.U.uAmt.value=shot===8?.20:0;
   snow.userData.U.uCam.value.copy(camera.position);
   lake.userData.U.uReflAmt.value=0;
  }
  render();
  return {camera:camera.position.toArray(),tiles:terrain.geometry.instanceCount};
 }
};
"""

def route_file(route):
    path = urlparse(route.request.url).path
    if path == "/index.html":
        route.fulfill(body=SHELL, content_type="text/html")
        return
    source = (REPO / path.lstrip("/")).resolve()
    if not source.is_relative_to(REPO) or not source.is_file():
        route.abort()
        return
    if source.suffix == ".js":
        code = source.read_text()
        if path == "/cover3d/src/data.js":
            code = code.replace("const DATA_V = __COVER_DATA__;", "const DATA_V = {};")
        if path == "/cover3d/src/main.js":
            code = code.replace("  function render() {", HOOK + "\n  function render() {")
        route.fulfill(body=code, content_type="text/javascript")
    else:
        route.fulfill(path=source, content_type="application/octet-stream" if source.suffix==".gz" else mimetypes.guess_type(source)[0] or "application/octet-stream")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--test",action="store_true")
    ap.add_argument("--shots",default="6,7,8,16")
    args=ap.parse_args()
    HERE.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chromium",args=["--use-angle=vulkan","--enable-features=Vulkan","--ignore-gpu-blocklist","--enable-unsafe-swiftshader"])
        page=browser.new_page(viewport={"width":1280,"height":720},device_scale_factor=1)
        page.route(ORIGIN+"/**",route_file)
        logs=[]
        page.on("pageerror",lambda e:logs.append(str(e)))
        page.on("console",lambda m:logs.append(m.text) if m.type in ("error","warning") else None)
        page.goto(ORIGIN+"/index.html")
        try:
            page.wait_for_function("window.FILM_READY || window.FILM_ERROR",timeout=120000)
        except Exception:
            print("\n".join(logs[-15:]),flush=True)
            raise
        assert not page.evaluate("window.FILM_ERROR"),logs
        for shot in map(int,args.shots.split(",")):
            if args.test:
                print(shot,page.evaluate("([s,u])=>window.__film.frame(s,u)",[shot,.55]),flush=True)
                page.screenshot(path=HERE/f"world-{shot:02}-test.jpg",type="jpeg",quality=92)
                continue
            duration={6:4,7:6,8:5,16:6}[shot]
            out=HERE/f"world-{shot:02}"
            out.mkdir(exist_ok=True)
            for i in range(duration*FPS):
                page.evaluate("([s,u])=>window.__film.frame(s,u)",[shot,i/(duration*FPS-1)])
                page.screenshot(path=out/f"{i:05}.jpg",type="jpeg",quality=93)
                if i%48==0: print(f"3D shot {shot}: {i}/{duration*FPS}",flush=True)
            subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate",str(FPS),"-i",str(out/"%05d.jpg"),"-c:v","libx264","-crf","17","-preset","fast","-pix_fmt","yuv420p",str(HERE/f"world-{shot:02}.mp4")],check=True)
            print(f"3D shot {shot} complete",flush=True)
        print("Browser messages:",logs[-10:],flush=True)
        browser.close()

if __name__=="__main__":main()

