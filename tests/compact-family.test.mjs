import test from 'node:test';
import assert from 'node:assert/strict';
import * as api from '../assets/connected-state.mjs';
import * as views from '../assets/connected-views.mjs';
import {publicPayload,contributionFrom} from '../assets/connected-public.mjs';
const memory=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)};};

test('family sample review preserves every supplied endpoint, reviewed aggregate party and California planning zone',()=>{
 const s=api.createStore(memory());s.act('creatorStart',{mode:'family'});
 const d=s.state.creator.draft;
 assert.equal(d.startDate,'2026-10-05');assert.equal(d.zone,'America/Los_Angeles');assert.deepEqual(d.party,{adults:3,children:[4]});
 assert.deepEqual([...new Set(d.blocks.map(b=>b.day))],[1,2,3,4,5,6]);
 const outbound=d.blocks.find(b=>b.kind==='flight'&&b.day===1);assert.equal(outbound.end,'11:30');assert.equal(outbound.timing.end,'supplied');assert.equal(outbound.timing.endMeaning,'arrival');assert.equal(outbound.timing.start,'placement');
 const back=d.blocks.find(b=>b.kind==='flight'&&b.day===6);assert.equal(back.start,'15:56');assert.equal(back.end,'17:38');assert.equal(back.timing.start,'supplied');assert.equal(back.timing.end,'supplied');
 const all=JSON.stringify(d);for(const text of ['Chipotle','bag drop','Hollywood Sign','complimentary chairs','umbrellas','Dallas','15 min','coin blocks','Studio Tour','Harry Potter','Secret Life','Minion','45 min','WEB SLINGERS','rooftop','hero','1.5–2','sandcastles','Africa Tram','30 min','Kids Free October','eligibility','DUPLO','takeout','Del Mar Village','2117'])assert.ok(all.includes(text),text);
 s.act('creatorReview',{draft:d,reviewed:true});const id=s.act('creatorPublish');
 const v=s.state.publications[id].versions[0];assert.deepEqual(publicPayload(v),publicPayload(d));
 const trip=s.act('fork',{id,version:1,start:d.startDate}),t=s.state.trips[trip];
 assert.equal(t.start,'2026-10-05');assert.equal(t.end,'2026-10-10');assert.deepEqual(t.party,d.party);assert.equal(t.zone,d.zone);
 assert.deepEqual(t.blocks.map(({day,date,id,...b})=>b),d.blocks.map(({day,...b})=>b));
 s.act('event',{trip,...t.blocks[0],title:'Independent arrival plan'});assert.deepEqual(s.state.publications[id].versions[0],v);
 assert.throws(()=>s.act('fork',{id,version:1,start:'2026-11-01'}),/California.*October 2026/);
 const bad=structuredClone(d);bad.blocks[0].zone='Europe/Paris';assert.throws(()=>publicPayload(bad),/zone/);
});

test('demo seed migration is idempotent and never overwrites saved edits, settings, drafts or immutable editions',()=>{
 const storage=memory(),s=api.createStore(storage),id=s.act('createTrip',{title:'Existing UTC plan',query:api.defaults()});
 s.act('event',{trip:id,title:'Keep this',date:'2026-10-12',start:'10:00',end:'11:00',zone:'UTC'});
 const legacy=s.state;legacy.publications={};delete legacy.demoSeed;storage.setItem(api.KEY,JSON.stringify(legacy));
 const upgraded=api.createStore(storage),pubs=Object.values(upgraded.state.publications);
 assert.equal(pubs.length,2);assert.deepEqual(upgraded.state.trips,legacy.trips);assert.deepEqual(upgraded.state.research,legacy.research);
 assert.ok(pubs.some(p=>p.versions[0].blocks.some(b=>b.day===6)));assert.ok(pubs.some(p=>p.versions[0].demo==='authored sample'));
 assert.deepEqual(api.createStore(storage).state,upgraded.state);
 const imported=pubs.find(p=>p.versions[0].demo==='imported sample');assert.deepEqual(publicPayload(imported.versions[0]),publicPayload(api.familySample()));
 upgraded.act('creatorStart',{mode:'blank'});
 const saved=upgraded.state;delete saved.demoSeed;delete saved.publications['demo-del-mar'];
 saved.publications[imported.id].versions[0].title='Keep existing edition';
 storage.setItem(api.KEY,JSON.stringify(saved));storage.setItem('travelos.connected.appearance.v1','snap');
 const again=api.createStore(storage).state;
 assert.deepEqual(again.publications[imported.id],saved.publications[imported.id]);
 assert.deepEqual(again.creator,saved.creator);assert.deepEqual(again.trips,saved.trips);
 assert.equal(Object.keys(again.publications).length,2);assert.equal(storage.getItem('travelos.connected.appearance.v1'),'snap');
});

test('blank author can draft zero stops but must review at least one; replacing or editing invalidates old approval',()=>{
 const s=api.createStore(memory());s.act('creatorStart',{mode:'blank'});assert.equal(s.state.creator.draft.title,'');assert.equal(s.state.creator.draft.blocks.length,0);
 assert.throws(()=>s.act('creatorPublish'),/Review/);
 let d={...s.state.creator.draft,title:'Beach morning',destination:'Del Mar'};s.act('creatorReview',{draft:d,reviewed:false});assert.throws(()=>s.act('creatorReview',{draft:d,reviewed:true}),/at least one/);
 d.blocks=[{title:'Sandcastles',kind:'activity',day:1,start:'09:00',end:'10:00',zone:'UTC'}];s.act('creatorReview',{draft:d,reviewed:true});
 const id=s.act('creatorPublish');assert.equal(s.state.publications[id].versions.length,1);
 s.act('creatorReview',{draft:{...d,title:'Changed'},reviewed:false});assert.throws(()=>s.act('creatorPublish'),/Review/);
 assert.throws(()=>s.act('creatorStart',{mode:'family'}),/Confirm replacing/);
 s.act('creatorStart',{mode:'family',replace:true});assert.equal(s.state.creator.reviewed,false);
});

test('California research filters real fixture fields and chooses only honest supplied flight endpoints and hotel dates',()=>{
 const q={...api.defaults(),destination:'California',origin:'SFO',airport:'BUR',start:'2026-10-05',end:'2026-10-10',adults:3,children:1,ages:'4',family:true};
 const results=api.search(q);assert.equal(results.length,3);assert.ok(results.some(f=>f.title==='Loews Hollywood'));assert.ok(results.some(f=>f.title==='Del Mar Beach Hotel'));
 const f=results.find(f=>f.kind==='flight');assert.equal(f.start,null);assert.equal(f.end,'11:30');assert.equal(f.date,'2026-10-05');assert.equal(api.search({...q,start:'2026-10-12',end:'2026-10-15'}).filter(f=>f.kind==='flight').length,0);
 const s=api.createStore(memory()),trip=s.act('createTrip',{title:'Family research',query:q});s.act('saveCandidate',{trip,candidate:f.id,query:q});s.act('choose',{trip,candidate:f.id});
 const b=s.state.trips[trip].blocks[0];assert.equal(b.end,'11:30');assert.equal(b.zone,'America/Los_Angeles');assert.equal(b.timing.endMeaning,'arrival');assert.equal(b.timing.start,'placement');
 const h=results.find(f=>f.title==='Loews Hollywood');s.act('saveCandidate',{trip,candidate:h.id,query:q});s.act('choose',{trip,candidate:h.id});assert.deepEqual(s.state.trips[trip].blocks.filter(b=>b.kind==='hotel').map(b=>b.date),['2026-10-05','2026-10-07']);
 assert.deepEqual(api.search(api.defaults()).map(f=>f.id),['f0a','f0b','h0a','h0b']);
 const returnFlights=api.search({...q,origin:'SAN',airport:'SFO',hotels:false});assert.equal(returnFlights[0].start,'15:56');assert.equal(returnFlights[0].end,'17:38');
});

test('family public/private presentations lead with six dated summaries and expose exact local endpoints before review',()=>{
 const s=api.createStore(memory()),c=s.state.publications['demo-california-family'],v=c.versions[0];
 const pub=views.publicPage(c,v,'Ari');assert.equal((pub.match(/data-summary-day=/g)||[]).length,6);assert.match(pub,/Mon, Oct 5/);assert.match(pub,/11:30 arrival/);assert.match(pub,/15:56 departure/);assert.match(pub,/17:38 arrival/);assert.match(pub,/editable placement/);
 const id=s.act('fork',{id:c.id,version:1,start:'2026-10-05'}),t=s.state.trips[id],html=views.calendar(t,'Ari');assert.equal((html.match(/data-summary-day=/g)||[]).length,6);assert.ok(html.indexOf('Trip at a glance')<html.indexOf('calendar-grid'));assert.match(html,/Edit calendar/);assert.match(html,/data-action="open-day"/);
 const editor=views.publicEditor(v,true);assert.match(editor,/California/);assert.match(editor,/Public stop details/);assert.match(editor,/arrival.*supplied/);assert.match(editor,/Aggregate party/);
 const creator=views.creatorPage(null);assert.match(creator,/Load family sample for review/);assert.match(creator,/Author from blank/);
});

test('editing a supplied endpoint retains its source value, marks the edit, and never silently converts UTC or leaks private metadata',()=>{
 const s=api.createStore(memory()),trip=s.act('fork',{id:'demo-california-family',version:1,start:'2026-10-05'}),b=s.state.trips[trip].blocks[0];
 s.act('event',{trip,...b,end:'11:45'});const t=s.state.trips[trip],changed=t.blocks[0];assert.equal(changed.timing.end,'edited');assert.equal(changed.timing.suppliedEnd,'11:30');
 assert.throws(()=>s.act('event',{trip,...changed,zone:'UTC'}),/zone.*conversion/);
 assert.throws(()=>s.act('event',{trip,...changed,date:'2026-11-01'}),/October 2026/);
 const draft=contributionFrom({...t,title:'Mina private title',notes:['secret'],party:{...t.party,names:['Mina'],payment:'hidden'},privateID:'hidden'});
 assert.equal(draft.zone,'America/Los_Angeles');assert.equal(draft.startDate,'2026-10-05');assert.equal(draft.blocks[0].zone,'America/Los_Angeles');assert.deepEqual(draft.blocks[0].timing,changed.timing);
 const clean=publicPayload({...draft,notes:['secret'],blocks:draft.blocks.map(b=>({...b,privateID:'hidden',booking:'hidden',payment:'hidden'}))});assert.doesNotMatch(JSON.stringify(clean),/Mina|privateID|secret|payment|hidden/);
 const utc=s.act('createTrip',{title:'UTC stays UTC',query:api.defaults()});s.act('event',{trip:utc,title:'Untouched',date:'2026-10-12',start:'10:00',end:'11:00',zone:'UTC'});assert.equal(s.state.trips[utc].blocks[0].zone,'UTC');
});

test('comparison rows expose route, local times, capacity, policies and distinct price units; workspace entries stay named',()=>{
 const flight=views.resultCard(api.fixtures[0]);
 assert.match(flight,/09:00–12:00 UTC/);
 assert.match(flight,/6 passengers/);
 assert.match(flight,/Stops, baggage, flexibility: not supplied/);
 assert.match(flight,/adult · one-way/);
 const hotel=views.resultCard(api.fixtures[3]);
 assert.match(hotel,/4 per room/);assert.match(hotel,/Family: sample option/);assert.match(hotel,/Pets: not allowed/);assert.match(hotel,/room.*night/);
 const shell=views.shell({persona:'Ari'},'', 'creator');assert.match(shell,/href="#\/creator" aria-current="page"/);assert.match(shell,/Import \/ Author/);
});
