
(function(){
'use strict';
var root=document.getElementById('journey'),sections=Array.from(document.querySelectorAll('.chapter')),calmButton=document.getElementById('calm');
var prefers=matchMedia('(prefers-reduced-motion: reduce)'),userCalm=false,quiet=prefers.matches,active=0,frame=0,lastWidth=0,view=0;
var state={slower:false,shared:false,planTouched:false,shareTouched:false},worlds=[];
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function smooth(a,b,v){var x=clamp((v-a)/(b-a),0,1);return x*x*(3-2*x)}
function navHeight(){return document.querySelector('.topbar').offsetHeight}
function fitViewport(){
 var embed=document.documentElement.dataset.embed;
 var next=embed?Number(embed):window.innerHeight;
 if(!view||lastWidth!==innerWidth||Math.abs(view-next)>120){view=next;document.documentElement.style.setProperty('--view',view+'px');lastWidth=innerWidth}
}
sections.forEach(function(s){s.style.setProperty('--depth',s.dataset.depth||'1.3')});
function bounds(s){return {start:s.offsetTop-navHeight(),range:Math.max(1,s.offsetHeight-(view-navHeight()))}}
function request(){if(!frame)frame=requestAnimationFrame(update)}
function update(){
 frame=0;var y=root.scrollTop,nav=navHeight(),threshold=y+nav+(view-nav)*.32;
 sections.forEach(function(s,i){
  var b=bounds(s),p=clamp((y-b.start)/b.range,0,1);
  s.style.setProperty('--p',p.toFixed(4));
  if(s.id==='plan'&&!state.planTouched&&state.slower!==(p>=.48))setPlan(p>=.48);
  if(s.id==='share'&&!state.shareTouched&&state.shared!==(p>=.42))setShared(p>=.42);
  s.style.setProperty('--tab-opacity',(1-smooth(.5,1,p)*.5).toFixed(4));
  s.querySelectorAll('[data-reveal]').forEach(function(e){e.style.setProperty('--reveal',quiet?1:(.22+.78*smooth(Number(e.dataset.reveal)-.14,Number(e.dataset.reveal)+.08,p)).toFixed(4))});
  if(s.offsetTop<=threshold)active=i;
  if(s.classList.contains('immersive')){
   // A postcard opens into the place, then returns to the page before we leave.
   // The camera below follows the same scroll in both directions, with no timer.
   var enter=smooth(0,.14,p),leave=smooth(.9,1,p);
   s.style.setProperty('--world-scale',quiet?'1':(.84+.16*enter-.16*leave).toFixed(4));
   s.style.setProperty('--world-corners',quiet?'0':String(32*(1-enter)+32*leave));
   s.style.setProperty('--world-copy',quiet?'1':(1-smooth(.06,.16,p)).toFixed(4));
   s.style.setProperty('--world-ui',quiet?'0':(smooth(.07,.17,p)*(1-smooth(.92,1,p))).toFixed(4));
   s.style.setProperty('--world-progress',String(p));
   var moment=p<(s.classList.contains('summer')?.36:.30)?0:p<(s.classList.contains('summer')?.67:.63)?1:2;
   s.querySelectorAll('[data-world-stop]').forEach(function(button,n){button.setAttribute('aria-current',n===moment?'step':'false')});
   var whisper=s.querySelector('.world-whisper'),words=s.classList.contains('summer')?
    ['Follow the shoreline.','Stay by the water a while.','Their kind of summer.']:
    ['Let the pines pass by.','A whole lake. Nothing urgent.','Somewhere to come back to.'];
   if(whisper&&whisper.textContent!==words[moment])whisper.textContent=words[moment];
   var world=worlds.find(function(w){return w.section===s});
   if(world&&!quiet&&s.offsetTop<y+view*1.7&&s.offsetTop+s.offsetHeight>y-view*.4){world.ensure();world.draw(p)}
  }
 });
 document.getElementById('chapter-count').textContent=String(active+1).padStart(2,'0')+' / '+String(sections.length);
 document.getElementById('chapter-name').textContent=sections[active].dataset.phase;
 document.getElementById('rail-progress').style.width=(100*y/Math.max(1,root.scrollHeight-root.clientHeight))+'%';
 var next=document.getElementById('next-chapter');
 next.href='#'+sections[(active+1)%sections.length].id;
 next.setAttribute('aria-label',active===sections.length-1?'Back to the beginning':'Next: '+sections[active+1].dataset.title);
}
function goTo(s,progress){var b=bounds(s);root.scrollTo({top:b.start+(progress||0)*b.range,behavior:'auto'});request()}
document.addEventListener('click',function(e){
 var a=e.target.closest('a[href^="#"]');if(!a)return;
 var target=document.getElementById(a.getAttribute('href').slice(1));if(!target)return;
 e.preventDefault();goTo(target,0);
 if(a.classList.contains('skip')){target.setAttribute('tabindex','-1');target.focus({preventScroll:true})}
});
function setQuiet(){
 var s=sections[active],b=bounds(s),p=clamp((root.scrollTop-b.start)/b.range,0,1);
 quiet=userCalm||prefers.matches;
 document.documentElement.classList.toggle('no-motion',quiet);
 calmButton.setAttribute('aria-pressed',String(quiet));
 calmButton.setAttribute('aria-label',quiet?'Calm view is on':'Use calm view');
 goTo(s,p);
}
calmButton.addEventListener('click',function(){userCalm=!userCalm;setQuiet()});
prefers.addEventListener('change',setQuiet);
function setPlan(value){
 state.slower=value;
 document.getElementById('morning-time').textContent=state.slower?'10:00':'9:00';
 document.getElementById('walk-time').textContent=state.slower?'11:30':'10:30';
 document.getElementById('slower').setAttribute('aria-pressed',String(state.slower));
 document.getElementById('plan-status').textContent=state.slower?'A slower start. The shared plan is updated.':'A shared plan. Easy to change.';
}
document.getElementById('slower').addEventListener('click',function(){state.planTouched=true;setPlan(!state.slower)});
var photo=document.querySelector('.trail-card>img'),privatePhoto=photo.src,privateAlt=photo.alt;
function setShared(value){
 state.shared=value;document.getElementById('share-preview').setAttribute('aria-pressed',String(state.shared));
 document.getElementById('trail-card').classList.toggle('shared',state.shared);
 var label=document.getElementById('trail-audience'),icon=label.querySelector('svg');
 label.textContent=state.shared?'Anonymous trail · shared preview':'Your private trip';if(icon)label.prepend(icon);
 photo.src=state.shared?document.querySelector('.winter .world-poster').src:privatePhoto;
 photo.alt=state.shared?'The lake and winter landscape. No traveller names or faces.':privateAlt;
 document.getElementById('share-status').textContent=state.shared?'A reusable plan, with names, faces and family notes left out.':'This preview doesn’t publish anything.';
}
document.getElementById('share-preview').addEventListener('click',function(){state.shareTouched=true;setShared(!state.shared)});
document.querySelectorAll('[data-world-stop]').forEach(function(button){button.addEventListener('click',function(){goTo(button.closest('.chapter'),Number(button.dataset.worldStop))})});
/*WORLDS*/
document.querySelectorAll('[data-world]').forEach(function(c){worlds.push(new World(c))});
root.addEventListener('scroll',request,{passive:true});
window.addEventListener('resize',function(){fitViewport();worlds.forEach(function(w){w.last=-1});request()},{passive:true});
document.addEventListener('visibilitychange',function(){if(!document.hidden)request()});
document.querySelectorAll('img').forEach(function(img){img.addEventListener('load',request,{once:true})});
function startReview(){var id=document.documentElement.dataset.start;if(id){var s=document.getElementById(id);if(s)goTo(s,.02)}request()}
if(document.fonts)document.fonts.ready.then(startReview);else requestAnimationFrame(startReview);
fitViewport();document.documentElement.classList.add('enhanced');document.documentElement.classList.toggle('no-motion',quiet);calmButton.setAttribute('aria-pressed',String(quiet));calmButton.setAttribute('aria-label',quiet?'Calm view is on':'Use calm view');update();
window.GitAwayScroll={sampleState:state,worlds:worlds,goTo:function(id,p){var s=document.getElementById(id);if(s)goTo(s,p||0)},get active(){return sections[active].id},get quiet(){return quiet}};
})();

