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

test('invalid search is rejected rather than silently interpreted', () => {
  for(const change of [{origin:'GRX'},{end:'2026-10-10'},{adults:0},{rooms:0},{origin:'Unknown'},{children:1},{maxPrice:-1}]) {
    assert.throws(() => api.search(query(change)), /airport|date|adult|room|age|budget/i);
  }
  assert.equal(api.search(query({destination:'',origin:'',airport:'',start:'',end:''})).length, 8);
});
