// Original travel choreography inspired by ThreeUI's public cinematic chapters.
// Painted depth meshes and particles share one camera. No timer, CDN or scroll trap.
function travelPose(summer,p){
 var keys=summer?[
  [0,0,0,0,.72],[.14,-.15,.18,.8,.52],[.32,.10,-.18,1.55,.29],
  [.50,.22,-.65,2.05,.38],[.64,.12,-.30,1.7,.48],
  [.78,.05,.42,.50,.72],[.90,0,.15,.20,.68],[1,0,0,0,.72]
 ]:[
  [0,0,0,0,.50],[.12,-.42,.12,.8,.24],[.28,-.25,.04,1.9,.38],
  [.47,.30,-.10,2.3,.52],[.61,.65,-.12,1.65,.60],
  [.74,.20,.22,1.1,.56],[.86,-.20,.05,.8,.48],[1,0,0,0,.50]
 ];
 var i=0;while(i<keys.length-2&&p>keys[i+1][0])i++;
 var a=keys[i],b=keys[i+1],t=smooth(a[0],b[0],p),values=[];
 for(var n=1;n<5;n++)values.push(a[n]+(b[n]-a[n])*t);
 return {camera:[values[0],values[1],-values[2]],focus:values[3],
  cabin:summer?0:smooth(.59,.69,p)*(1-smooth(.84,.95,p)),
  cabinFocus:.39+.30*smooth(.74,.84,p)};
}
function World(container){
 this.container=container;this.section=container.closest('.chapter');this.canvas=container.querySelector('canvas');
 this.poster=container.querySelector('.world-poster');this.cabinPoster=container.querySelector('.world-source');
 this.summer=container.dataset.world==='summer';this.gl=null;this.ready=false;this.failed=false;this.pending=false;
 this.last=-1;this.renderCount=0;this.uniforms={};this.pointer=[0,0];this.lastPointer='';
 var w=this;
 container.addEventListener('pointermove',function(e){
  if(e.pointerType!=='mouse'||quiet)return;
  var r=container.getBoundingClientRect();w.pointer=[(e.clientX-r.left)/r.width-.5,(e.clientY-r.top)/r.height-.5];request();
 },{passive:true});
 container.addEventListener('pointerleave',function(){w.pointer=[0,0];request()},{passive:true});
}
World.prototype.texture=function(image){
 var gl=this.gl,texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
 gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
 gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
 return texture;
};
World.prototype.fail=function(error){
 this.failed=true;this.ready=false;this.error=error?String(error):undefined;this.container.classList.remove('live');
 var visible=this.section.offsetTop<root.scrollTop+view&&this.section.offsetTop+this.section.offsetHeight>root.scrollTop+navHeight();
 this.section.classList.add('world-still');if(visible)goTo(this.section,0);request();
};
World.prototype.ensure=function(){
 var w=this;if(w.gl||w.failed||w.pending||quiet)return;
 if(!w.poster.complete){
  w.pending=true;
  w.poster.addEventListener('load',function(){w.pending=false;w.ensure();request()},{once:true});
  w.poster.addEventListener('error',function(){w.pending=false;w.fail()},{once:true});return;
 }
 if(!w.poster.naturalWidth){w.fail();return}
 try{
  var gl=w.canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});
  if(!gl){w.fail();return}w.gl=gl;
  function shader(kind,source){
   var s=gl.createShader(kind);gl.shaderSource(s,source);gl.compileShader(s);
   if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;
  }
  function program(vs,fs,attribute){
   var pr=gl.createProgram();gl.attachShader(pr,shader(gl.VERTEX_SHADER,vs));gl.attachShader(pr,shader(gl.FRAGMENT_SHADER,fs));
   gl.bindAttribLocation(pr,0,attribute);gl.linkProgram(pr);
   if(!gl.getProgramParameter(pr,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(pr));return pr;
  }
  w.program=program([
   'precision highp float;attribute vec2 aUv;uniform vec4 uRect;uniform vec3 uCam;uniform float uAspect,uSummer,uCabin;varying vec2 vUv;',
   'float sm(float a,float b,float x){float t=clamp((x-a)/(b-a),0.,1.);return t*t*(3.-2.*t);}',
   'void main(){vUv=uRect.xy+aUv*uRect.zw;float y=1.-vUv.y;float d=10.5-5.5*sm(.17,.95,y);',
   'd-=2.7*(1.-sm(.10,.32,vUv.x))*sm(.05,.80,y);d-=uSummer*1.1*sm(.76,.96,vUv.x);',
   'd=mix(max(3.5,d),9.-1.3*sm(.2,.95,y),uCabin);',
   'float tf=.41421356;vec3 p=vec3((aUv.x-.5)*2.*tf*uAspect*d*1.11,(aUv.y-.5)*2.*tf*d*1.11,-d)-uCam;',
   'float near=.1,far=30.;gl_Position=vec4(p.x/(tf*uAspect),p.y/tf,((far+near)/(near-far))*p.z+2.*far*near/(near-far),-p.z);}'
  ].join('\n'),[
   'precision highp float;uniform sampler2D uImage;uniform float uScroll,uSummer,uCabin,uOpacity;varying vec2 vUv;',
   'void main(){vec2 uv=vUv;float lake=(1.-smoothstep(.53,.63,uv.y))*smoothstep(.08,.22,uv.y);',
   'lake*=mix(smoothstep(.12,.28,uv.x)*(1.-smoothstep(.89,.98,uv.x)),(1.-smoothstep(.49,.64,uv.x)),uSummer)*(1.-uCabin);',
   'uv.x+=sin(uv.y*170.+uScroll*32.)*.0012*lake;uv.y+=sin(uv.x*125.-uScroll*23.)*.0006*lake;',
   'vec3 color=texture2D(uImage,clamp(uv,vec2(.001),vec2(.999))).rgb;',
   'float light=pow(max(0.,sin(uv.x*112.+uv.y*91.+uScroll*30.)),12.)*lake*.025;',
   'gl_FragColor=vec4(color+light,uOpacity);}'
  ].join('\n'),'aUv');
  gl.useProgram(w.program);
  var points=[],indices=[],cols=128,rows=80;
  for(var yy=0;yy<=rows;yy++)for(var xx=0;xx<=cols;xx++)points.push(xx/cols,yy/rows);
  for(var y=0;y<rows;y++)for(var x=0;x<cols;x++){var n=y*(cols+1)+x;indices.push(n,n+1,n+cols+1,n+1,n+cols+2,n+cols+1)}
  w.meshBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,w.meshBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(points),gl.STATIC_DRAW);
  w.indexBuffer=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,w.indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);w.count=indices.length;
  w.lakeTexture=w.texture(w.poster);
  ['uRect','uCam','uAspect','uSummer','uScroll','uImage','uCabin','uOpacity'].forEach(function(k){w.uniforms[k]=gl.getUniformLocation(w.program,k)});
  w.particleProgram=program([
   'precision highp float;attribute vec3 aSeed;uniform vec3 uCam;uniform float uAspect,uScroll,uDpr,uSummer;varying float vAlpha;',
   'void main(){float tf=.41421356;float d=3.8+aSeed.z*9.;float speed=mix(.9,.22,uSummer);',
   'float y=fract(aSeed.y-uScroll*speed);float x=aSeed.x+sin(aSeed.y*25.+uScroll*6.)*.025;',
   'vec3 p=vec3((x-.5)*2.*tf*uAspect*d*1.45,(y-.5)*2.*tf*d*1.45,-d)-uCam;',
   'gl_Position=vec4(p.x/(tf*uAspect),p.y/tf,-1.00669*p.z-.20067,-p.z);',
   'gl_PointSize=(1.4+(1.-aSeed.z)*4.)*uDpr;vAlpha=.16+(1.-aSeed.z)*.42;}'
  ].join('\n'),[
   'precision highp float;uniform float uSummer,uStrength;varying float vAlpha;',
   'void main(){float r=length(gl_PointCoord-vec2(.5));float a=(1.-smoothstep(.18,.5,r))*vAlpha*uStrength;',
   'gl_FragColor=vec4(mix(vec3(1.,.99,.96),vec3(1.,.94,.72),uSummer),a);}'
  ].join('\n'),'aSeed');
  w.particleUniforms={};['uCam','uAspect','uScroll','uDpr','uSummer','uStrength'].forEach(function(k){w.particleUniforms[k]=gl.getUniformLocation(w.particleProgram,k)});
  var seed=731,seeds=[];function random(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
  w.particleCount=w.summer?45:(w.container.clientWidth<640?100:180);
  for(var j=0;j<w.particleCount*3;j++)seeds.push(random());
  w.particleBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,w.particleBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(seeds),gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);gl.clearColor(.96,.94,.89,1);w.ready=true;w.last=-1;w.container.classList.add('live');
  w.canvas.addEventListener('webglcontextlost',function(e){e.preventDefault();w.fail()});
 }catch(e){w.fail(e)}
};
World.prototype.draw=function(p){
 if(!this.ready||quiet)return;
 var w=this,gl=w.gl,dpr=Math.min(devicePixelRatio||1,1.5);
 var width=Math.max(1,Math.round(w.container.clientWidth*dpr)),height=Math.max(1,Math.round(w.container.clientHeight*dpr));
 var pointerKey=w.pointer.join(',');
 if(Math.abs(w.last-p)<.00005&&width===w.canvas.width&&height===w.canvas.height&&pointerKey===w.lastPointer)return;
 if(w.canvas.width!==width||w.canvas.height!==height){w.canvas.width=width;w.canvas.height=height}
 gl.viewport(0,0,width,height);gl.disable(gl.BLEND);gl.clear(gl.COLOR_BUFFER_BIT);
 var pose=travelPose(w.summer,p),aspect=width/height,inside=smooth(.07,.2,p)*(1-smooth(.89,1,p));
 var camera=pose.camera.slice();camera[0]*=Math.min(1,aspect/1.1);camera[0]+=w.pointer[0]*.12*inside;camera[1]-=w.pointer[1]*.08*inside;w.camera=camera;
 gl.useProgram(w.program);gl.bindBuffer(gl.ARRAY_BUFFER,w.meshBuffer);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,w.indexBuffer);
 gl.uniform1i(w.uniforms.uImage,0);gl.uniform1f(w.uniforms.uSummer,w.summer?1:0);gl.uniform1f(w.uniforms.uAspect,aspect);gl.uniform1f(w.uniforms.uScroll,p);
 function layer(image,texture,cam,focus,isCabin,opacity){
  var imageAspect=image.naturalWidth/image.naturalHeight,dx=1,dy=1,x0=0,y0=0;
  if(aspect<imageAspect){dx=aspect/imageAspect;x0=clamp(focus-dx/2,0,1-dx)}else{dy=imageAspect/aspect;y0=(1-dy)/2}
  gl.uniform4f(w.uniforms.uRect,x0,y0,dx,dy);gl.uniform3f(w.uniforms.uCam,cam[0],cam[1],cam[2]);
  gl.uniform1f(w.uniforms.uCabin,isCabin);gl.uniform1f(w.uniforms.uOpacity,opacity);gl.bindTexture(gl.TEXTURE_2D,texture);gl.drawElements(gl.TRIANGLES,w.count,gl.UNSIGNED_SHORT,0);
 }
 layer(w.poster,w.lakeTexture,camera,pose.focus,0,1);
 if(pose.cabin>0&&w.cabinPoster&&w.cabinPoster.complete&&w.cabinPoster.naturalWidth){
  if(!w.cabinTexture)w.cabinTexture=w.texture(w.cabinPoster);
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
  layer(w.cabinPoster,w.cabinTexture,[w.pointer[0]*.08,.18,-.35-.3*smooth(.64,.84,p)],pose.cabinFocus,1,pose.cabin);
 }
 w.cabinBlend=pose.cabin;
 gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.useProgram(w.particleProgram);
 gl.bindBuffer(gl.ARRAY_BUFFER,w.particleBuffer);gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
 var pu=w.particleUniforms;gl.uniform3f(pu.uCam,camera[0],camera[1],camera[2]);gl.uniform1f(pu.uAspect,aspect);
 gl.uniform1f(pu.uScroll,p);gl.uniform1f(pu.uDpr,dpr);gl.uniform1f(pu.uSummer,w.summer?1:0);gl.uniform1f(pu.uStrength,inside*(w.summer?.55:1));
 gl.drawArrays(gl.POINTS,0,w.particleCount);gl.disable(gl.BLEND);
 w.last=p;w.lastPointer=pointerKey;w.renderCount++;
};
