import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
const file = new URL('../assets/connected-state.mjs', import.meta.url);
const api = existsSync(file) ? await import(file) : {};
const query = (extra = {}) => ({destination:'Granada', origin:'LHR', airport:'GRX', start:'2026-10-12', end:'2026-10-15', adults:2, children:0, rooms:1, flights:true, hotels:true, cabin:'Any', maxPrice:500, family:false, pet:false, ...extra});

test('search filters actual destination, airport, dates, group, flight and hotel fixtures', () => {
  assert.equal(typeof api.search, 'function', 'a public fixture-search behavior is required');
  const results = api.search(query());
  assert.equal(results.length, 4);
  assert.ok(results.every(x => x.destination === 'Granada'));
  assert.equal(api.search(query({destination:'Lisbon', airport:'LIS'})).length, 4);
  assert.equal(api.search(query({origin:'JFK'})).length, 2);
  assert.equal(api.search(query({start:'2027-10-12',end:'2027-10-15'})).length, 0);
  assert.equal(api.search(query({flights:false, maxPrice:110})).length, 1);
  assert.equal(api.search(query({flights:false, pet:true})).length, 0);
  assert.equal(api.search(query({flights:false, family:true})).length, 1);
  assert.equal(api.search(query({hotels:false,cabin:'Business'})).length, 1);
  assert.equal(api.search(query({adults:7,rooms:1})).length, 0);
});
const memory = () => {const map = new Map(); return {getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};};
const setup = () => {assert.equal(typeof api.createStore,'function','tab-local planning interface required');return api.createStore(memory());};
function trip(store) {return store.act('createTrip',{title:'Our little escape',query:query()});}

test('candidate → private shortlist → chosen flight and linked hotel; duplicate safe and resumable', () => {
  const storage = memory(), s = api.createStore?.(storage);
  assert.ok(s, 'a connected trip store is required');
  const id = trip(s);
  s.act('saveCandidate',{trip:id,candidate:'f0a',query:query()});
  s.act('saveCandidate',{trip:id,candidate:'f0a',query:query()});
  s.act('saveCandidate',{trip:id,candidate:'h0a',query:query()});
  assert.equal(s.state.trips[id].shortlist.length,2);
  s.act('choose',{trip:id,candidate:'f0a'});
  s.act('choose',{trip:id,candidate:'h0a'});
  s.act('choose',{trip:id,candidate:'h0a'});
  assert.equal(s.state.trips[id].blocks.length,3);
  assert.deepEqual(s.state.trips[id].blocks.map(b=>b.date),['2026-10-12','2026-10-12','2026-10-15']);
  s.act('note',{trip:id,scope:'trip',text:'Quiet mornings, please'});
  assert.equal(api.createStore(storage).state.trips[id].notes[0].text,'Quiet mornings, please');
  s.act('applyResearch',{trip:id,query:query({start:'2026-10-20',end:'2026-10-22'})});
  assert.equal(s.state.trips[id].blocks[0].date,'2026-10-12','apply never silently moves blocks');
  s.act('unschedule',{trip:id,candidate:'h0a'});
  assert.equal(s.state.trips[id].blocks.length,1);
  s.act('undo',{trip:id});
  assert.equal(s.state.trips[id].blocks.length,3);
});

test('calendar fields move and resize; overlap warns, empty gaps stay empty; invalid edits atomic', () => {
  const s=setup(), id=trip(s);
  const a=s.act('event',{trip:id,title:'Garden walk',date:'2026-10-13',start:'10:00',end:'11:00',zone:'UTC'});
  s.act('event',{trip:id,id:a,title:'Garden walk',date:'2026-10-14',start:'11:00',end:'12:30',zone:'UTC'});
  s.act('event',{trip:id,title:'Market',date:'2026-10-14',start:'12:00',end:'13:00',zone:'UTC'});
  assert.match(api.warnings(s.state.trips[id]).join(' '),/overlap/i);
  assert.equal(s.state.trips[id].blocks.length,2);
  const before=JSON.stringify(s.state);
  assert.throws(()=>s.act('event',{trip:id,id:a,title:'Bad',date:'2026-10-14',start:'13:00',end:'12:00',zone:'UTC'}),/end/i);
  assert.equal(JSON.stringify(s.state),before);
  assert.throws(()=>s.act('event',{trip:id,title:'Bad zone',date:'2026-10-14',start:'10:00',end:'11:00',zone:'Europe/Madrid'}),/UTC/);
  s.act('deleteEvent',{trip:id,id:a});
  assert.equal(s.state.trips[id].blocks.length,1);
  s.act('undo',{trip:id});
  assert.equal(s.state.trips[id].blocks.length,2);
});

test('named/link roles enforced in handlers, revoked previews empty; payer authority transfers and locks persist', () => {
  const storage=memory(),s=api.createStore(storage),id=trip(s);
  s.act('invite',{trip:id,name:'Mina',role:'Editor'});
  s.act('invite',{trip:id,name:'Jo',role:'Commenter'});
  s.act('invite',{trip:id,name:'Lee',role:'Viewer'});
  s.act('nominate',{trip:id,name:'Mina'});
  assert.throws(()=>s.act('checkout',{trip:id,next:'Active'}),/payer/i);
  s.act('persona',{name:'Mina'});
  s.act('checkout',{trip:id,next:'Active'});
  assert.equal(api.createStore(storage).state.trips[id].checkout,'Active');
  s.act('persona',{name:'Ari'});
  assert.throws(()=>s.act('nominate',{trip:id,name:'Ari'}),/active|unresolved/i);
  s.act('persona',{name:'Mina'});
  s.act('checkout',{trip:id,next:'Unresolved'});
  assert.throws(()=>s.act('checkout',{trip:id,next:'Active'}),/unresolved/i);
  s.act('checkout',{trip:id,next:'Ready'});
  s.act('persona',{name:'Jo'});
  s.act('note',{trip:id,text:'A comment'});
  assert.throws(()=>s.act('event',{trip:id,title:'No'}),/Editor/);
  assert.throws(()=>s.act('invite',{trip:id,name:'Other',role:'Editor'}),/organizer/i);
  s.act('persona',{name:'Lee'});
  assert.throws(()=>s.act('note',{trip:id,text:'No'}),/Commenter/);
  s.act('persona',{name:'Ari'});
  const token=s.act('link',{trip:id,role:'Viewer'});
  assert.ok(s.shared(id,token));
  s.act('revoke',{trip:id});
  assert.equal(s.shared(id,token),null);
});
test('storage failure is honest; research isolated by persona and reset only touches namespace', () => {
  const storage=memory();storage.setItem('other','keep');const s=api.createStore(storage);
  s.act('research',{scope:'search',value:{draft:query({origin:'JFK'})}});
  s.act('persona',{name:'Mina'});
  assert.equal(s.state.research['Mina:search'],undefined);
  s.act('reset');assert.equal(storage.getItem('other'),'keep');
  const broken=api.createStore({getItem:()=>'{broken',setItem:()=>{throw Error();},removeItem:()=>{}});
  assert.match(broken.warning,/until reload/);trip(broken);assert.equal(Object.keys(broken.state.trips).length,1);
});

test('public allowlist, immutable versions and whole-version independent forks', () => {
  const s=setup(), id=trip(s);
  s.act('event',{trip:id,title:'PRIVATE Ari secret@example.com REF-123',date:'2026-10-13',start:'10:00',end:'11:30',zone:'UTC'});
  s.act('note',{trip:id,text:'PRIVATE notes'});
  const contribution=s.act('contribute',{trip:id});
  let draft=s.state.publications[contribution].draft;
  assert.doesNotMatch(JSON.stringify(draft),/PRIVATE|secret@|REF-123|Ari|trip-/);
  draft.title='Slow mornings';draft.blocks[0].title='Garden wander';
  s.act('publicDraft',{id:contribution,draft});
  s.act('publish',{id:contribution,approval:approval(s,contribution)});
  s.act('publish',{id:contribution,approval:approval(s,contribution)});
  assert.equal(s.state.publications[contribution].versions.length,1);
  draft.title='Slow mornings, with a market';
  s.act('publicDraft',{id:contribution,draft});s.act('publish',{id:contribution,approval:approval(s,contribution)});
  assert.equal(s.state.publications[contribution].versions[0].title,'Slow mornings');
  const fork=s.act('fork',{id:contribution,version:1,start:'2026-11-01'});
  assert.equal(s.state.trips[fork].blocks[0].date,'2026-11-02');
  assert.equal(s.state.trips[fork].blocks[0].end,'11:30');
  s.act('deleteEvent',{trip:fork,id:s.state.trips[fork].blocks[0].id});
  assert.equal(s.state.publications[contribution].versions[0].blocks.length,1);
  assert.equal(s.state.trips[id].blocks.length,1);
  draft.title='Email secret@example.com';assert.throws(()=>s.act('publicDraft',{id:contribution,draft}),/public|private|email/i);
  s.act('persona',{name:'Mina'});assert.throws(()=>s.act('publish',{id:contribution,approval:approval(s,contribution)}),/contributor/i);
});

test('creator synthetic source, edited preview and publish match; unsafe URLs rejected and source changes invalidate', () => {
  const s=setup();
  assert.throws(()=>s.act('extract',{source:'javascript:alert(1)'}),/HTTPS/);
  s.act('source',{source:'https://example.com/lisbon'});
  s.act('extract',{source:'https://example.com/lisbon'});
  const draft=s.state.creator.draft;
  assert.equal(draft.blocks.length,3);
  draft.blocks.splice(1,1);draft.blocks[0].title='My reviewed garden';
  s.act('creatorReview',{draft,backlink:true,reviewed:true});
  const id=s.act('creatorPublish');
  assert.deepEqual(s.state.publications[id].versions[0].blocks,draft.blocks);
  assert.equal(s.act('creatorPublish'),id,'repeated publish must not duplicate');
  s.act('source',{source:'https://example.com/other'});
  assert.equal(s.state.creator.reviewed,false);
  assert.throws(()=>s.act('creatorPublish'),/review/i);
});

test('forked hotel edits and deletes do not remove unrelated unlinked activities', () => {
  const s=setup(),id=trip(s);
  s.act('saveCandidate',{trip:id,candidate:'h0a',query:query()});s.act('choose',{trip:id,candidate:'h0a'});
  s.act('event',{trip:id,title:'Garden',date:'2026-10-13',start:'10:00',end:'11:00',zone:'UTC'});
  const c=s.act('contribute',{trip:id});s.act('publish',{id:c,approval:approval(s,c)});
  const f=s.act('fork',{id:c,version:1,start:'2026-11-01'}),hotel=s.state.trips[f].blocks.find(x=>x.kind==='hotel');
  s.act('deleteEvent',{trip:f,id:hotel.id});
  assert.equal(s.state.trips[f].blocks.length,2,'unlinked public hotel is one editable block, not a private reservation');
});
test('undated shortlist candidates can be explicitly dated without duplicate saves', () => {
  const s=setup(),id=trip(s);
  s.act('saveCandidate',{trip:id,candidate:'h0a',query:query({start:'',end:''})});
  assert.throws(()=>s.act('choose',{trip:id,candidate:'h0a'}),/Undated/);
  s.act('dateCandidate',{trip:id,candidate:'h0a',start:'2026-10-14',end:'2026-10-16'});
  s.act('choose',{trip:id,candidate:'h0a'});
  assert.equal(s.state.trips[id].shortlist.length,1);
  assert.equal(s.state.trips[id].blocks[0].date,'2026-10-14');
});

test('invalid search is rejected rather than silently interpreted', () => {
  for(const change of [{origin:'GRX'},{end:'2026-10-10'},{adults:0},{rooms:0},{origin:'Unknown'},{children:1},{maxPrice:-1}]) {
    assert.throws(() => api.search(query(change)), /airport|date|adult|room|age|budget/i);
  }
  assert.equal(api.search(query({destination:'',origin:'',airport:'',start:'',end:''})).length, 8);
});

test('new trip research retains the actual Lisbon four-adult Business result query by persona', () => {
  const storage=memory(), s=api.createStore(storage), committed=query({destination:'Lisbon',airport:'LIS',adults:4,cabin:'Business'});
  s.act('research',{scope:'search',value:{draft:query(),committed}});
  const id=s.act('createTrip',{title:'Lisbon together',query:committed});
  s.act('saveCandidate',{trip:id,candidate:'f1b',query:committed});
  const value=s.state.research[`Ari:${id}`];
  assert.deepEqual(value,{draft:committed,committed});
  assert.deepEqual(api.search(value.committed).map(f=>f.id),['f1b','h1b']);
  assert.deepEqual(s.state.trips[id].shortlist[0].query,value.committed);
  assert.deepEqual(api.createStore(storage).state.research[`Ari:${id}`],value);
  s.act('persona',{name:'Mina'});assert.equal(s.state.research[`Mina:${id}`],undefined);
});

test('source typing preserves edited creator work across reload and requires confirmed replacement', () => {
  const storage=memory(),s=api.createStore(storage);
  s.act('extract',{source:'https://example.com/lisbon'});
  const draft=s.state.creator.draft;draft.title='My edited route';draft.blocks[0].title='My garden';draft.blocks.splice(1,1);
  s.act('creatorReview',{draft,reviewed:true});
  s.act('source',{source:'https://example.com/lisbonx'});
  assert.deepEqual(s.state.creator.draft,draft);
  assert.equal(s.state.creator.outdated,true);assert.equal(s.state.creator.reviewed,false);
  const resumed=api.createStore(storage),before=resumed.state;
  assert.deepEqual(resumed.state.creator.draft,draft);
  assert.throws(()=>resumed.act('creatorReview',{draft,reviewed:true}),/source|outdated/i);
  assert.throws(()=>resumed.act('creatorPublish'),/source|review/i);
  assert.throws(()=>resumed.act('extract',{source:before.creator.source}),/confirm|replace/i);
  assert.deepEqual(resumed.state,before,'blocked review/publish/replacement must not discard edits');
  resumed.act('extract',{source:before.creator.source,replace:true});
  assert.equal(resumed.state.creator.draft.blocks.length,3);
  assert.notEqual(resumed.state.creator.draft.title,draft.title);
  assert.ok(!resumed.state.creator.outdated);
  resumed.act('creatorReview',{draft:resumed.state.creator.draft,reviewed:true});
  assert.ok(resumed.act('creatorPublish'));
});

test('user-controlled inherited entity IDs are unavailable, never executable objects', () => {
  const s=setup();
  for(const id of ['constructor','__proto__','toString','hasOwnProperty','valueOf','missing']){
    const before=s.state;
    assert.throws(()=>s.act('fork',{id,version:1,start:'2026-10-12'}),/Published version unavailable/);
    assert.throws(()=>s.act('visit',{trip:id,tab:'research'}),/Trip no longer available/);
    assert.throws(()=>s.act('publicDraft',{id,draft:{}}),/contributor/);
    assert.throws(()=>s.act('publish',{id,reviewed:true}),/contributor/);
    assert.equal(s.shared(id,'token'),null);assert.equal(s.shared(id,undefined),null);
    assert.deepEqual(s.state,before);
  }
});

test('own but malformed trip and publication records also resolve as unavailable', () => {
  const storage=memory(),s=api.createStore(storage),value=s.state;
  for(const [id,entry] of Object.entries({null:null,array:[],partial:{id:'partial'},wrong:{id:'wrong',members:{},blocks:[],versions:{}},wrongID:{id:'another'}})){
    value.trips[id]=entry;value.publications[id]=entry;
  }
  storage.setItem(api.KEY,JSON.stringify(value));const resumed=api.createStore(storage);
  for(const id of Object.keys(value.trips)){
    assert.throws(()=>resumed.act('fork',{id,version:1,start:'2026-10-12'}),/Published version unavailable/);
    assert.throws(()=>resumed.act('visit',{trip:id,tab:'research'}),/Trip no longer available/);
    assert.equal(resumed.shared(id,undefined),null);
  }
});

const approval = (s,id) => api.publicPreview(s.state.publications[id]);
for(const published of [false,true]) test(`publication rejects stale, cross-contribution and changed-back approvals atomically (existing version: ${published})`, () => {
  const s=setup(), t=trip(s);
  s.act('event',{trip:t,title:'Garden',date:'2026-10-12',start:'10:00',end:'11:00',zone:'UTC'});
  const id=s.act('contribute',{trip:t});
  if(published)s.act('publish',{id,reviewed:true,approval:approval(s,id)});
  const reviewed=approval(s,id), changed=structuredClone(reviewed.payload);changed.title='Changed after preview';
  s.act('publicDraft',{id,draft:changed});
  const before=s.state;
  assert.throws(()=>s.act('publish',{id,reviewed:true,approval:reviewed}),/preview/i);
  assert.deepEqual(s.state,before,'rejection must leave all state unchanged');
  s.act('publicDraft',{id,draft:reviewed.payload});
  assert.throws(()=>s.act('publish',{id,reviewed:true,approval:reviewed}),/preview/i,'editing back does not restore approval');
  const other=s.act('contribute',{trip:t});
  assert.throws(()=>s.act('publish',{id:other,reviewed:true,approval:approval(s,id)}),/preview/i);
  assert.throws(()=>s.act('publish',{id,reviewed:true}),/preview/i,'a boolean alone is not approval');
  const fresh=approval(s,id), differentPayload=structuredClone(fresh);
  differentPayload.payload.title='Not the reviewed wording';
  const unchanged=s.state;
  assert.throws(()=>s.act('publish',{id,approval:differentPayload}),/preview/i,'same ID and revision cannot approve a different payload');
  assert.deepEqual(s.state,unchanged);
  s.act('publish',{id,approval:fresh});
  assert.equal(s.state.publications[id].versions.at(-1).title,fresh.payload.title);
});
