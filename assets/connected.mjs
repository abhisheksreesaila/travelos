import {createStore,defaults,search,fixtures,role,shiftDate,minutes,clock,warnings} from './connected-state.mjs';
import {publicPayload,contributionFrom} from './connected-public.mjs';
import {esc,icon,btn,field,select,check,empty,tag,shell,searchPage,tripHeader,calendar,tripsPage,communityPage,publicPage,publicEditor,creatorPage,itinerary} from './connected-views.mjs';
let storage;try{storage=window.sessionStorage;}catch{storage={getItem(){throw Error();}};}
const store=createStore(storage), app=document.querySelector('#app'), dialog=document.querySelector('#context-drawer');
let opener='',lastPage='',workingDraft=null,preview=null,snapshot=null,dirty=false,drag=null;
const $=(s,root=document)=>s?root.querySelector(s):null;
const route=()=>{const [path,query='']=(location.hash.slice(1)||'/search').split('?');return {path,parts:path.split('/').filter(Boolean),params:new URLSearchParams(query)};};
const currentTrip=()=>store.state.trips[route().parts[1]];
const currentQuery=()=>{const t=currentTrip(),scope=t?.id||'search';return store.state.research[`${store.state.persona}:${scope}`]||{draft:t?{...defaults(),destination:t.destination,start:t.start,end:t.end,airport:t.destination==='Lisbon'?'LIS':'GRX'}:defaults(),committed:null};};
function notify(message) {$('#announcer').textContent='';requestAnimationFrame(()=>{$('#announcer').textContent=message;const e=$('#saved-state');if(e)e.textContent=store.warning||message+' · saved in this tab';});}
function go(path) {if(dialog.open)dialog.close();dirty=false;location.hash=path;}
function open(type,params={}) {
  const focused=document.activeElement;
  if(!dialog.open && focused instanceof HTMLElement) opener=focused.id?`#${CSS.escape(focused.id)}`:focused.dataset.action?`[data-action="${focused.dataset.action}"]${focused.dataset.id?`[data-id="${focused.dataset.id}"]`:''}`:'';
  const r=route(),q=new URLSearchParams();q.set('drawer',type);for(const [k,v] of Object.entries(params))q.set(k,v);
  if(dialog.open){history.replaceState(null,'',`#${r.path}?${q}`);renderDrawer();}else location.hash=`${r.path}?${q}`;
}
function close() {
  if(dirty&&!confirm('Discard unsaved activity edits? Notes drafts remain saved.'))return;
  dirty=false;const r=route();dialog.close();history.replaceState(null,'',`#${r.path}`);render();requestAnimationFrame(()=>($(opener)||$('#main')).focus());
}
function mutate(type,p={},message='Updated locally') {const result=store.act(type,p);notify(message);return result;}
function readSearch(form) {
  const d=new FormData(form),q={};for(const [k,v]of d)q[k]=v;
  for(const k of ['flights','hotels','family','pet'])q[k]=d.has(k);
  for(const k of ['adults','children','rooms','maxPrice'])q[k]=Number(q[k]);return q;
}
function saveResearch(committed=false) {const value=currentQuery(),draft=readSearch($('#search-form'));store.act('research',{scope:currentTrip()?.id||'search',value:{draft,committed:committed?draft:value.committed}});return draft;}
function readPublic() {
  const form=$('#public-form'),d=new FormData(form),base=workingDraft;
  return {...base,title:d.get('title'),destination:d.get('destination'),backlink:route().path==='/creator'?(d.has('backlink')?store.state.creator.source:''):d.get('backlink'),blocks:base.blocks.map((b,i)=>({...b,title:d.get(`title-${i}`),day:Number(d.get(`day-${i}`)),start:d.get(`start-${i}`),end:d.get(`end-${i}`)}))};
}
function render() {
  const r=route(),s=store.state;let content,active='search',t;
  const scroll=$('.calendar-scroll')?.scrollTop;
  if(r.parts[0]==='trip') {
    active='trips';t=s.trips[r.parts[1]];
    if(!t||!role(t,s.persona))content=empty('This plan is not available.','Unknown trip or this simulated persona has no access.',btn('Switch demo persona','account'));
    else if(!['research','calendar'].includes(r.parts[2]))content=empty('That trip view does not exist.','Choose Research or Calendar.',`<a class="btn" href="#/trip/${t.id}/research">Research</a>`);
    else {
      if(lastPage!==r.path){store.act('visit',{trip:t.id,tab:r.parts[2]});t=store.state.trips[t.id];}
      const q=currentQuery();let results=null;try{if(q.committed)results=search(q.committed);}catch{}
      content=tripHeader(t,s.persona,r.parts[2])+(r.parts[2]==='calendar'?calendar(t,s.persona):searchPage(q.draft,results,t));
    }
  } else if(r.path==='/search') {
    const q=currentQuery();let results=null;try{if(q.committed)results=search(q.committed);}catch{}content=searchPage(q.draft,results);
  } else if(r.path==='/trips'){active='trips';content=tripsPage(s);}
  else if(r.path==='/community'){active='community';content=communityPage(s);}
  else if(r.parts[0]==='community') {
    active='community';const c=s.publications[r.parts[1]],v=r.parts[2]==='v'?c?.versions.find(x=>String(x.version)===r.parts[3]):c?.versions.at(-1);
    content=v?publicPage(c,v,s.persona):empty('That published edition is unavailable.','Nothing else was substituted.','<a class="btn" href="#/community">Back to Community</a>');
  } else if(r.parts[0]==='contribute') {
    active='community';const c=s.publications[r.parts[1]];
    if(c?.owner===s.persona){workingDraft=structuredClone(c.draft);content=`<section class="page-heading"><h1>Separate public contribution</h1><p>Your private plan stays private. This is its own editable itinerary.</p></section>${publicEditor(workingDraft)}`;}
    else content=empty('Contribution unavailable.','Only its local contributor may edit it.');
  } else if(r.path==='/creator') {active='community';workingDraft=s.creator?.draft?structuredClone(s.creator.draft):null;content=creatorPage(s.creator);}
  else if(r.path==='/signin') {
    content=`<section class="signin panel"><span class="stamp">${icon('plane')}</span><span class="eyebrow">WELCOME TO YOUR NEXT CHAPTER</span><h1>Good to see you.</h1><p>Same trip. Same good maybes.<br>This is a local identity simulation, not authentication.</p><form id="demo-signin">${select('Demo persona','persona',['Ari','Mina','Jo','Lee'],s.persona)}<button class="btn primary" type="submit">Continue as demo persona →</button></form>${btn('Continue browsing','return')}<p class="meta">No passwords, provider requests, real invitations or identity checks.</p></section>`;
  } else if(r.parts[0]==='shared') {
    active='trips';const shared=store.shared(r.parts[1],r.parts[2]);
    content=shared?`<section class="page-heading"><h1>${esc(shared.title)}</h1><p>Live local shared view · ${esc(shared.link.role)} link · same tab only</p><p class="notice">Account-free preview. This read-only surface does not expose notes or payer details. To exercise named roles, use People & access → Preview recipient.</p>${btn('Refresh local view','refresh')}</section>${itinerary(contributionFrom(shared))}`:empty('Link unavailable.','It may be revoked, expired or from a different tab. No private content is shown.');
  } else content=empty('A small detour.','This address is not part of the sample. Your plans are still here.','<a class="btn primary" href="#/search">Back to Search</a>');
  app.innerHTML=shell(s,content,active,store.warning);
  if($('.calendar-scroll'))$('.calendar-scroll').scrollTop=lastPage===r.path&&scroll!==undefined?scroll:7*45;
  if(lastPage!==r.path){window.scrollTo(0,0);lastPage=r.path;}
  if(r.params.has('drawer'))renderDrawer();else if(dialog.open){dialog.close();requestAnimationFrame(()=>($(opener)||$('#main')).focus());}
}
function drawerFrame(title,content) {
  dialog.innerHTML=`<div class="drawer-head"><h2 id="drawer-title" tabindex="-1">${title}</h2>${btn('✕ Close','close','aria-label="Close drawer"')}</div><div class="drawer-body">${content}<p id="drawer-error" class="error" role="alert"></p></div>`;
  if(!dialog.open)dialog.showModal();$('#drawer-title').focus();dirty=false;
}
function renderDrawer() {
  const r=route(),s=store.state,t=currentTrip(),type=r.params.get('drawer'),id=r.params.get('id'),scope=r.params.get('scope')||'trip';
  const canEdit=t&&role(t,s.persona)==='Editor',organizer=t?.organizer===s.persona;
  if(['notes','people','history','payer','event','ideas','apply','snapshot'].includes(type)&&(!t||!role(t,s.persona)))return drawerFrame('No longer available','<p>This persona does not have access.</p>');
  if(type==='details'||type==='candidate') {
    const f=fixtures.find(x=>x.id===id);if(!f)return drawerFrame('No longer available','<p>Unknown candidate.</p>');
    const c=t?.shortlist.find(x=>x.id===id),chosen=t?.blocks.some(x=>x.candidate===id);
    drawerFrame(f.title,`${tag(f.kind,f.kind)} ${tag('Synthetic fixture')}<p>${esc(f.destination)} · $${f.price} ${f.kind==='flight'?'per adult, one-way':'per room per night, USD'}</p><p>${f.kind==='flight'?`${f.origin} → ${f.airport} · ${f.start}–${f.end} UTC<br>${f.cabin}; baggage and airport services unverified.`:'Check-in 15:00 / check-out 11:00 UTC. Family: '+(f.family?'synthetic family option':'unknown')+'. Pets: '+(f.pet===false?'not allowed in this fixture':'unknown')+'. Property URL unavailable.'}</p><section class="context-box"><h3>${icon('sun')} A little local context</h3><p><strong>Weather:</strong> mild autumn is a seasonal illustration, not a forecast.</p><p><strong>Events:</strong> sample market walk; dates and opening hours unverified.</p><p><strong>Reviews:</strong> “A quiet base” is synthetic, not a traveler endorsement.</p><p><strong>Family / pets:</strong> confirm accessibility, child and animal policies independently. Unknown ≠ suitable.</p></section>${c?`<p class="meta">Saved research: ${esc(c.query.start||'undated')} → ${esc(c.query.end||'undated')} · ${c.query.adults} adults</p>${btn(chosen?'Chosen · not booked':'Choose for itinerary','choose',`id="choose-arrangement" data-id="${id}" ${!canEdit||chosen?'disabled':''}`,true)}${chosen?btn('Unschedule linked arrangement','unschedule',`data-id="${id}" ${!canEdit?'disabled':''}`):''}${btn('Candidate notes','notes',`data-scope="${id}"`)}<p>Choosing does not book or open checkout.</p>`:btn('Add to shortlist','save-candidate',`id="save-candidate" data-id="${id}" ${t&&!canEdit?'disabled':''}`,true)}`);
  } else if(type==='choose-trip'||type==='blank') {
    const available=Object.values(s.trips).filter(x=>role(x,s.persona)==='Editor');
    drawerFrame(type==='blank'?'Create a private trip':'A good maybe. Where shall it go?',`<p>Private first. No booking gate, no automatic public itinerary copy.</p>${type!=='blank'&&available.length?`<form id="existing-trip-form">${select('Choose an existing trip','trip',available.map(x=>[x.id,x.title]),available[0].id)}<button type="submit" class="btn">Save to this shortlist</button></form><hr>`:''}${field('New private trip name','tripTitle','My little escape','text','required maxlength="120"')}<p class="meta">Uses your research dates. Undated research needs explicit dates before creating a shared plan.</p>${btn(type==='blank'?'Create blank trip':'Create trip + save candidate','create-candidate',`data-id="${esc(id||'')}"`,true)}`);
  } else if(type==='replace') {
    drawerFrame('Another good option',`<p>Replace only the existing ${esc(fixtures.find(x=>x.id===id)?.kind)} blocks, or keep both? Other activities will not move. Undo is available.</p>${btn('Replace existing arrangement','choose-mode',`data-id="${id}" data-mode="replace"`,true)}${btn('Keep both · warn on overlap','choose-mode',`data-id="${id}" data-mode="both"`)}`);
  } else if(type==='notes') {
    const notes=t.notes.filter(n=>n.scope===scope),draft=s.drafts[`${s.persona}:${t.id}:${scope}`]||'';
    drawerFrame(scope==='trip'?'Group notes':'Candidate / activity notes',`<p class="meta">Private / ${scope==='trip'?'whole trip':esc(scope)} · local, not sent</p>${notes.map(n=>`<article class="note"><strong>${esc(n.actor)} · simulated</strong><p>${esc(n.text)}</p></article>`).join('')||'<p>No notes yet. Leave a little context.</p>'}${['Editor','Commenter'].includes(role(t,s.persona))?`<form id="note-form"><label>Your private note<textarea name="note" rows="4" required>${esc(draft)}</textarea></label><button class="btn primary" type="submit">Add note locally</button></form>`:'<p>Viewer · notes are read-only.</p>'}${scope!=='trip'?btn('Back to details','candidate',`data-id="${scope}"`):''}`);
  } else if(type==='event') {
    const b=id?t.blocks.find(x=>x.id===id):{title:'',date:t.day||t.start,start:'10:00',end:'11:00',zone:'UTC'};
    if(!b)return drawerFrame('Activity unavailable','<p>It may have been deleted.</p>');
    drawerFrame(id?'Activity · move / change duration':'Make a little plan',`<p>Planning values only. UTC only; no provider, DST or timezone conversion. End must follow start on the same day.</p><form id="event-form"><fieldset ${canEdit?'':'disabled'}>${field('Title','title',b.title,'text','required maxlength="180"')}${field('Date · move to another day','date',b.date,'date','required')}<div class="form-grid">${field('Start (UTC)','start',b.start,'time','required step="900"')}${field('End (UTC) · change duration','end',b.end,'time','required step="900"')}</div>${select('Planning time zone','zone',['UTC'],b.zone)}${check('Save even if this overlaps another block','overlap')}<p id="overlap-warning" class="notice" hidden></p><button type="submit" class="btn primary">Save activity</button></fieldset></form>${id?`${btn(b.kind==='hotel'?'Delete linked hotel anchors':'Delete activity','delete-event',`data-id="${id}" ${canEdit?'':'disabled'}`)}${btn('Activity notes','notes',`data-scope="${id}"`)}`:''}<p class="meta">${canEdit?'Save records a local history entry. Delete / move / resize supports Undo.':'Read-only role. Switch to an Editor to change the plan.'}</p>`);
  } else if(type==='ideas') {
    drawerFrame('A little room for discovery',`<p>Optional synthetic suggestions for ${esc(t.destination)}. Opening hours, weather and access are unverified. Nothing gets added automatically.</p>${['Garden wander','Market pause','Riverside ramble'].map(x=>`<article class="panel activity"><h3>${icon('leaf')} ${x}</h3>${btn('Choose date + time','recommend',`data-title="${x}" ${canEdit?'':'disabled'}`)}</article>`).join('')}${btn('Keep this time free','close')}`);
  } else if(type==='apply') {
    const q=currentQuery().draft;
    drawerFrame('Apply research to the shared plan?',`<p><strong>Before:</strong> ${esc(t.destination)} · ${t.start} → ${t.end}</p><p><strong>After:</strong> ${esc(q.destination||'Flexible')} · ${esc(q.start)} → ${esc(q.end)}</p><p>Existing blocks keep their dates, durations and destination. Out-of-range blocks are flagged, never moved or deleted.</p>${btn('Apply these dates explicitly','confirm-apply',canEdit?'':'disabled',true)}${btn('Keep current plan','close')}`);
  } else if(type==='people') {
    drawerFrame('People & access',`<section id="people-access"><p>Local recipient simulation. No email sent, no live collaboration or real security boundary.</p>${Object.entries(t.members).map(([name,access])=>`<div class="person"><strong>${esc(name)}</strong>${tag(access,access.toLowerCase())}${name===t.organizer?tag('Organizer'):''}${name===t.payer?tag('Payer'):''}${btn('Preview recipient','preview-person',`data-name="${esc(name)}"`)}</div>`).join('')}${organizer?`<form id="invite-form">${field('Recipient display name (simulated)','name','Mina','text','required maxlength="60"')}${select('Access role','role',['Viewer','Commenter','Editor'],'Viewer')}<button type="submit" class="btn primary">Create demo invitation</button></form><hr><h3>Anyone with a local link</h3><p>Forwarding grants the selected role in this tab. The preview is read-only; named personas demonstrate editing. No cross-device access.</p><form id="link-form">${select('Link role','linkRole',['Viewer'],t.link?.role||'Viewer')}${check('Already expired (test unavailable view)','expired')}<button class="btn" type="submit">Generate Viewer preview link</button></form><p class="meta">Commenter / Editor anonymous links are not implemented in this sample; use named invitations instead.</p>`:'<p>Only the organizer changes access.</p>'}${t.link?`<p>${tag('Viewer link')} · ${t.link.expires?'expired':'no expiry'}</p><a class="btn" href="#/shared/${t.id}/${t.link.token}">Preview shared view</a>${btn('Revoke local link','revoke',organizer?'':'disabled')}`:''}</section>`);
  } else if(type==='history') {
    drawerFrame('Private plan history',`<p>Saved local edits, not live presence or public history.</p>${t.history.map(h=>`<article class="note"><span class="meta">${esc(h.at)} · ${esc(h.actor)}</span><p>${esc(h.text)}</p></article>`).join('')||'<p>A fresh page. No saved changes yet.</p>'}`);
  } else if(type==='payer') {
    const payer=s.persona===t.payer;
    drawerFrame('One payer. Still just pretend.',`<section id="payer-demo"><p class="notice">SIMULATION · no charge · no card inputs · no receipts or email</p><p>Organizer: <strong>${esc(t.organizer)}</strong><br>Designated payer: <strong>${esc(t.payer)}</strong></p><h3>${tag(t.checkout)}</h3>${select('Nominate one named payer','payer',Object.keys(t.members),t.payer)}${btn('Transfer payer authority','nominate',!organizer||['Active','Unresolved'].includes(t.checkout)?'disabled':'')}<p class="meta">Transfer removes the previous payer’s authority. Active / unresolved checkout blocks transfer and retries, including after reload.</p>${t.checkout==='Ready'?btn('Begin simulated checkout','checkout','data-next="Active" '+(!payer?'disabled':''),true):t.checkout==='Active'?`${btn('Simulate success','checkout','data-next="Success" '+(!payer?'disabled':''))}${btn('Simulate failure','checkout','data-next="Ready" '+(!payer?'disabled':''))}${btn('Simulate timeout → unresolved','checkout','data-next="Unresolved" '+(!payer?'disabled':''))}`:t.checkout==='Unresolved'?`<p>No result is known. No retry or invented receipt. Reconcile this demo explicitly:</p>${btn('Confirm failed · unlock','checkout','data-next="Ready" '+(!payer?'disabled':''))}${btn('Confirm succeeded','checkout','data-next="Success" '+(!payer?'disabled':''))}`:'<p>Simulated success. No transaction occurred.</p>'}${btn('Switch simulated persona','account')}<p>${payer?'You are the sole designated payer.':'This persona cannot operate checkout.'}</p></section>`);
  } else if(type==='snapshot') {
    if(!snapshot||snapshot.trip!==t.id)snapshot={trip:t.id,at:new Date().toISOString(),payload:contributionFrom(t)};
    drawerFrame('Read-only snapshot',`<section id="print-snapshot"><p>Read-only snapshot · ${snapshot.at}</p><p>Public-safe generic labels; private notes, people and payer details excluded. This snapshot will not update.</p>${itinerary(snapshot.payload)}</section>${btn('Print / Save as PDF','print','',true)}${btn('Generate a new snapshot','new-snapshot')}<p class="meta">Browser print, not an emailed PDF. A downloaded copy cannot be revoked. Return to Calendar for current local state.</p>`);
  } else if(type==='preview') {
    if(!preview)return drawerFrame('Preview expired','<p>Return to the editor and review again after reload.</p>');
    drawerFrame('Exact public preview',`<h3>${esc(preview.title)}</h3><p>${esc(preview.destination)}</p>${itinerary(preview)}<p class="notice">Publish only this wording and these stops. No private notes or participants. This is discoverable only in this tab’s Community.</p>${btn('Publish reviewed itinerary','publish','id="publish-contribution"',true)}${btn('Back to edit','close')}`);
  } else if(type==='fork') {
    const c=s.publications[id],v=c?.versions.find(x=>String(x.version)===r.params.get('version'));
    if(!v)return drawerFrame('Version unavailable','<p>No fork was created.</p>');
    drawerFrame(`Fork Version ${v.version}`,`<h3>${esc(v.title)}</h3><p>Copy all ${v.blocks.length} blocks, durations and empty gaps. Independent from the source. Shorten manually; no automatic compression.</p>${field('Day 1 date for your private fork','forkStart','2026-11-01','date')}${btn('Fork whole chosen version','confirm-fork',`data-id="${id}" data-version="${v.version}"`,true)}`);
  } else if(type==='public-history') {
    const c=s.publications[id];drawerFrame('Public version history',c?.versions.map(v=>`<p><a href="#/community/${id}/v/${v.version}">Version ${v.version} · ${esc(v.title)}</a><br><span class="meta">${esc(v.at)} · public edition saved</span></p>`).join('')||'<p>Version unavailable.</p>');
  } else if(type==='account') {
    drawerFrame('Demo controls',`<p>Simulated persona: <strong>${esc(s.persona)}</strong>. Switching does not authenticate anyone or grant invitations.</p>${select('Preview as persona','persona',[...new Set(['Ari','Mina','Jo','Lee',...Object.values(s.trips).flatMap(x=>Object.keys(x.members))])],s.persona)}${btn('Switch persona','switch-persona')}${btn('Same-theme sign-in','signin')}${btn('Browse as Guest','guest')}<hr><h3>Kept in this tab only</h3><p>Refresh retains saved plans. Closing this tab ends the demo. No server / cross-device synchronization.</p>${btn('Reset this prototype…','reset-prompt','id="reset-demo"')}`);
  } else if(type==='reset') drawerFrame('Reset this tab’s prototype?',`<p>Remove trip edits, notes, invitations, payer state, contributions and creator drafts. Other TravelOS / backend / theme storage is untouched.</p>${btn('Confirm reset','reset','',true)}${btn('Cancel · keep everything','close')}`);
  else drawerFrame('No longer available','<p>Unknown drawer. Your saved state is unchanged.</p>');
}

document.addEventListener('submit',e=>{
  const form=e.target;if(!(form instanceof HTMLFormElement))return;e.preventDefault();
  try {
    const r=route(),t=currentTrip(),data=new FormData(form);
    if(form.id==='search-form'){const q=readSearch(form);search(q);saveResearch(true);render();notify('Fixture results updated');}
    else if(form.id==='existing-trip-form'){const id=data.get('trip');mutate('saveCandidate',{trip:id,candidate:r.params.get('id'),query:currentQuery().committed||currentQuery().draft},'Candidate saved');go(`/trip/${id}/research`);}
    else if(form.id==='note-form'){mutate('note',{trip:t.id,scope:r.params.get('scope')||'trip',text:data.get('note')},'Added locally · not sent');renderDrawer();}
    else if(form.id==='event-form') {
      const p=Object.fromEntries(data);p.trip=t.id;p.id=r.params.get('id')||undefined;
      const overlap=t.blocks.some(b=>b.id!==p.id&&b.date===p.date&&b.start<p.end&&p.start<b.end);
      if(overlap&&!data.has('overlap')){const w=$('#overlap-warning');w.hidden=false;w.textContent='Overlap found. Nothing moved. Check Save even if this overlaps to confirm, or adjust times.';return;}
      const id=mutate('event',p,`${p.title} saved · planning only`);dirty=false;close();render();requestAnimationFrame(()=>$(`[data-block-id="${id}"]`)?.classList.add('landed'));
    } else if(form.id==='invite-form'){mutate('invite',{trip:t.id,name:data.get('name'),role:data.get('role')},'Demo invitation created · no email sent');renderDrawer();}
    else if(form.id==='link-form'){mutate('link',{trip:t.id,role:data.get('linkRole'),expired:data.has('expired')},'Local preview link created');renderDrawer();}
    else if(form.id==='demo-signin'){mutate('persona',{name:data.get('persona')},'Demo persona selected');go(returnTo());}
    else if(form.id==='source-form'){const source=data.get('source');if(store.state.creator?.draft&&!confirm('Replace the previous synthetic review with a fresh example?'))return;mutate('extract',{source},'Synthetic example generated · not fetched');render();}
    else if(form.id==='public-form') {
      const draft=readPublic();preview=publicPayload(draft);
      if(r.path==='/creator')mutate('creatorReview',{draft,backlink:data.has('backlink'),reviewed:true},'Stops reviewed locally');
      else mutate('publicDraft',{id:r.parts[1],draft},'Separate public draft saved');
      workingDraft=draft;open('preview');
    }
  } catch(error){const target=form.querySelector('.form-error')||$('#search-error',form)||$('#drawer-error');if(target)target.textContent=error.message;notify(error.message);}
});
function returnTo(){const value=route().params.get('returnTo')?.replace(/^#/,'');return value?.startsWith('/')&&!value.startsWith('//')&&!value.startsWith('/signin')?value:'/search';}
document.addEventListener('click',e=>{
  const target=e.target.closest('[data-action]');if(!target||target.disabled)return;
  const a=target.dataset.action,id=target.dataset.id,r=route(),t=currentTrip();
  try {
    switch(a) {
      case 'close':close();break;
      case 'details':case 'candidate':open(a,{id});break;
      case 'account':open('account');break;
      case 'blank':open('blank');break;
      case 'save-candidate':
        if(t){mutate('saveCandidate',{trip:t.id,candidate:id,query:currentQuery().committed||currentQuery().draft},'Saved candidate');render();open('candidate',{id});}
        else open('choose-trip',{id});break;
      case 'create-candidate': {
        const q=currentQuery().committed||currentQuery().draft;
        const trip=mutate('createTrip',{title:$('[name="tripTitle"]').value,query:q},'Private trip created');
        if(id)mutate('saveCandidate',{trip,candidate:id,query:q},'Candidate saved');go(`/trip/${trip}/research`);break;
      }
      case 'choose':
        try{mutate('choose',{trip:t.id,candidate:id},'Chosen · not booked');render();}
        catch(error){if(error.message.includes('Replace'))open('replace',{id});else throw error;}break;
      case 'choose-mode':mutate('choose',{trip:t.id,candidate:id,mode:target.dataset.mode},'Arrangement chosen · Undo available');open('candidate',{id});render();break;
      case 'unschedule':mutate('unschedule',{trip:t.id,candidate:id},'Unscheduled · candidate retained');render();break;
      case 'resume':go(`/trip/${id}/${store.state.trips[id].lastTab}`);break;
      case 'notes':open('notes',{scope:target.dataset.scope||'trip'});break;
      case 'history':case 'people':case 'payer':case 'ideas':case 'snapshot':case 'apply':open(a);break;
      case 'new-event':open('event');break;
      case 'event':open('event',{id});break;
      case 'recommend':open('event');setTimeout(()=>{if($('[name="title"]'))$('[name="title"]').value=target.dataset.title;},100);break;
      case 'delete-event':if(confirm('Remove this activity? Linked hotel anchors are removed together. Undo is available.')){mutate('deleteEvent',{trip:t.id,id},'Activity removed · Undo available');dirty=false;close();render();}break;
      case 'undo':mutate('undo',{trip:t.id},'Last itinerary change undone');render();break;
      case 'confirm-apply':mutate('applyResearch',{trip:t.id,query:currentQuery().draft},'Dates applied · blocks unchanged');close();render();break;
      case 'clear-search':store.act('research',{scope:t?.id||'search',value:{draft:defaults(),committed:null}});render();notify('Search reset · trips untouched');break;
      case 'previous-day':case 'next-day':mutate('visit',{trip:t.id,tab:'calendar',day:shiftDate(t.day,a==='previous-day'?-1:1)},'Selected day changed');render();break;
      case 'preview-person':mutate('persona',{name:target.dataset.name},'Local recipient preview');close();render();break;
      case 'revoke':mutate('revoke',{trip:t.id},'Local link revoked');renderDrawer();break;
      case 'nominate':mutate('nominate',{trip:t.id,name:$('[name="payer"]').value},'Payer authority transferred');renderDrawer();break;
      case 'checkout':mutate('checkout',{trip:t.id,next:target.dataset.next},'Checkout '+target.dataset.next+' · SIMULATION');renderDrawer();break;
      case 'switch-persona':mutate('persona',{name:$('[name="persona"]').value},'Persona switched · simulation');close();render();break;
      case 'guest':mutate('persona',{name:'Guest'},'Guest browsing · state retained');go('/search');break;
      case 'signin':go(`/signin?returnTo=${encodeURIComponent(r.path)}`);break;
      case 'return':go(returnTo());break;
      case 'reset-prompt':open('reset');break;
      case 'reset':mutate('reset',{},'Only this prototype namespace reset');snapshot=null;preview=null;go('/search');render();break;
      case 'contribute':{const id=mutate('contribute',{trip:t.id},'Separate public draft created');go(`/contribute/${id}`);break;}
      case 'remove-stop':case 'add-stop': {
        workingDraft=readPublic();if(a==='remove-stop')workingDraft.blocks.splice(+target.dataset.index,1);else workingDraft.blocks.push({title:'New public activity',kind:'activity',day:1,start:'10:00',end:'11:00',zone:'UTC'});
        if(r.path==='/creator')store.act('creatorReview',{draft:workingDraft,backlink:!!workingDraft.backlink,reviewed:false});else store.act('publicDraft',{id:r.parts[1],draft:workingDraft});render();break;
      }
      case 'publish': {
        let id=r.parts[1];if(r.path==='/creator')id=mutate('creatorPublish',{},'Published to local Community');else mutate('publish',{id,reviewed:true},'Public version saved');preview=null;go(`/community/${id}`);break;
      }
      case 'fork':open('fork',{id,version:target.dataset.version});break;
      case 'confirm-fork': {const trip=mutate('fork',{id,version:target.dataset.version,start:$('[name="forkStart"]').value},'Independent fork created');go(`/trip/${trip}/calendar`);break;}
      case 'public-history':open('public-history',{id});break;
      case 'print':window.print();break;
      case 'new-snapshot':snapshot=null;renderDrawer();break;
      case 'refresh':render();notify('Current local shared state');break;
    }
  } catch(error){if($('#drawer-error'))$('#drawer-error').textContent=error.message;else notify(error.message);}
});
document.addEventListener('input',e=>{
  try {
    if(e.target.closest('#search-form')){saveResearch();$('#search-stale').textContent='Filters changed · submit to refresh fixture results. Shared plan dates are unchanged.';}
    if(e.target.name==='note'){const t=currentTrip();store.act('draft',{scope:`${t.id}:${route().params.get('scope')||'trip'}`,text:e.target.value});}
    if(e.target.closest('#event-form'))dirty=true;
    if(e.target.id==='creator-source')store.act('source',{source:e.target.value});
  }catch(error){notify(error.message);}
});
document.addEventListener('change',e=>{
  try {
    if(e.target.name==='day'&&currentTrip()){mutate('visit',{trip:currentTrip().id,tab:'calendar',day:e.target.value},'Selected day changed');render();}
    if(e.target.name==='version')go(`/community/${e.target.dataset.public}/v/${e.target.value}`);
    if(e.target.closest('#public-form')){const draft=readPublic();if(route().path==='/creator')store.act('creatorReview',{draft,backlink:!!draft.backlink,reviewed:false});else store.act('publicDraft',{id:route().parts[1],draft});workingDraft=draft;}
  }catch(error){const el=$('.form-error');if(el)el.textContent='Draft not saved: '+error.message;}
});
dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
dialog.addEventListener('keydown',e=>{
  if(e.key!=='Tab')return;const list=[...dialog.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled)')].filter(x=>x.getClientRects().length);
  if(!list.length)return;const first=list[0],last=list.at(-1);
  if(e.shiftKey&&(document.activeElement===first||document.activeElement.id==='drawer-title')){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
});
// Pointer-only grips; touch opens the same labeled fields instead of hijacking scrolling.
document.addEventListener('pointerdown',e=>{
  const grip=e.target.closest('[data-drag]');if(!grip)return;
  if(e.pointerType==='touch'){open('event',{id:grip.dataset.id});return;}
  const t=currentTrip(),b=t?.blocks.find(x=>x.id===grip.dataset.id);if(!b||role(t,store.state.persona)!=='Editor')return;
  e.preventDefault();grip.setPointerCapture(e.pointerId);drag={grip,b,trip:t.id,mode:grip.dataset.drag,y:e.clientY,x:e.clientX,pointer:e.pointerId,delta:0,date:b.date};grip.closest('article').classList.add('dragging');
});
document.addEventListener('pointermove',e=>{
  if(!drag)return;const lane=document.elementFromPoint(e.clientX,e.clientY)?.closest('.day-lane');
  drag.delta=Math.round((e.clientY-drag.y)/.75/15)*15;if(lane&&drag.mode==='move')drag.date=lane.dataset.date;
  const start=minutes(drag.b.start)+(drag.mode==='move'?drag.delta:0),end=minutes(drag.b.end)+drag.delta;
  $('#announcer').textContent=`${drag.mode} preview ${drag.date} ${clock(Math.max(0,start))}–${clock(Math.min(1439,end))}; release to confirm in fields. Escape cancels.`;
  drag.grip.closest('article').style.transform=`translateY(${drag.delta*.75}px)`;
});
document.addEventListener('pointerup',()=>{
  if(!drag)return;const d=drag;drag=null;d.grip.closest('article').classList.remove('dragging');d.grip.closest('article').style.transform='';
  if(!d.delta&&d.date===d.b.date){open('event',{id:d.b.id});return;}
  const start=minutes(d.b.start)+(d.mode==='move'?d.delta:0),end=minutes(d.b.end)+d.delta;
  if(start<0||end>1439||end<=start){notify('Drag rejected: keep ordered times on one UTC day.');return;}
  const p={...d.b,trip:d.trip,date:d.date,start:clock(start),end:clock(end)};
  const t=currentTrip(),overlap=t.blocks.some(b=>b.id!==p.id&&b.date===p.date&&b.start<p.end&&p.start<b.end);
  if(overlap&&!confirm('This overlaps another block. Save anyway without rescheduling?'))return;
  try{mutate('event',p,`${d.mode==='move'?'Moved':'Resized'} ${p.title} to ${p.date} ${p.start}–${p.end} UTC · Undo available`);render();$(`[data-block-id="${p.id}"]`)?.classList.add('landed');}catch(error){notify(error.message);}
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&drag){drag.grip.closest('article').style.transform='';drag.grip.closest('article').classList.remove('dragging');drag=null;notify('Drag cancelled · nothing changed');}if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-drag]')){e.preventDefault();open('event',{id:e.target.dataset.id});}});
window.addEventListener('hashchange',()=>{dirty=false;render();});
if(!location.hash)history.replaceState(null,'','#/search');render();
