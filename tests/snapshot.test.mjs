import test from 'node:test';
import assert from 'node:assert/strict';
import {createStore,defaults} from '../assets/connected-state.mjs';
import {snapshotFrom} from '../assets/connected-public.mjs';
import {snapshotItinerary,esc} from '../assets/connected-views.mjs';
const store=()=>createStore({getItem(){return null;},setItem(){}});

for(const source of ['import','demo-california-family','demo-del-mar'])test(`${source}: snapshot contains every itinerary stop, endpoint and detail without interactive disclosure or private data`,()=>{
 const s=store();let id=source;
 if(source==='import'){
  s.act('extract',{source:'https://example.com/synthetic-itinerary'});
  const d=s.state.creator.draft;d.blocks[0].detail='Stop detail <em>literal</em> & shaded chairs';
  s.act('creatorReview',{draft:d,reviewed:true});id=s.act('creatorPublish');
 }
 const publication=structuredClone(s.state.publications[id]);
 const trip=s.act('fork',{id,version:1,start:source==='demo-california-family'?'2026-10-05':'2026-10-12'});
 const t=structuredClone(s.state.trips[trip]);
 Object.assign(t,{title:'SENSITIVE_TITLE',notes:['SENSITIVE_NOTE'],members:{SENSITIVE_PERSON:'Editor'},receipt:'SENSITIVE_RECEIPT',link:'https://payments.example.com'});
 t.blocks.forEach(b=>Object.assign(b,{privateNotes:'SENSITIVE_BLOCK',booking:'SENSITIVE_BOOKING',payment:'SENSITIVE_PAYMENT'}));
 const payload=snapshotFrom(t),frozen=structuredClone(payload),html=snapshotItinerary(payload);
 assert.equal(payload.blocks.length,t.blocks.length);
 for(const [i,b] of t.blocks.entries()){
  for(const key of ['title','start','end','zone','kind','detail','period','timing'])assert.deepEqual(payload.blocks[i][key],b[key],key);
  for(const value of [b.title,b.start,b.end,b.detail].filter(Boolean))assert.ok(html.includes(esc(value)),value);
 }
 assert.doesNotMatch(JSON.stringify(payload),/SENSITIVE_|payments\.example/);
 assert.doesNotMatch(html,/<details|<summary|<button|<input|<select|<textarea|<em>/);
 assert.equal((html.match(/aria-label="Full stop details"/g)||[]).length,Math.max(...payload.blocks.map(b=>b.day)));
 if(source==='demo-california-family')for(const value of ['11:30 arrival','15:56 departure','17:38 arrival','PDT (UTC−07:00)','2026-10-10',esc(t.context)])assert.ok(html.includes(value),value);
 if(source==='import'){assert.match(html,/UTC/);assert.doesNotMatch(html,/PDT/);}
 if(source==='demo-del-mar')assert.match(html,/California · PDT \(UTC−07:00\)/);
 t.blocks[0].title='Changed after export';if(t.blocks[0].timing)t.blocks[0].timing.start='edited';if(t.party)t.party.children.push(8);
 assert.deepEqual(payload,frozen,'snapshot shares no mutable nested itinerary data');
 assert.equal(snapshotItinerary(payload),html);
 assert.deepEqual(s.state.publications[id],publication);
});

test('ordinary UTC itinerary snapshot excludes private plan metadata and remains detached after saved edits',()=>{
 const s=store(),trip=s.act('createTrip',{title:'SENSITIVE_TITLE',query:defaults()});
 s.act('event',{trip,title:'UTC picnic',date:'2026-10-12',start:'10:00',end:'11:00',zone:'UTC'});
 const t=s.state.trips[trip],payload=snapshotFrom(t),html=snapshotItinerary(payload);
 for(const value of ['UTC picnic','10:00','11:00','UTC','2026-10-12'])assert.ok(html.includes(value));
 assert.doesNotMatch(html,/SENSITIVE_|PDT/);
 for(const day of [1,2,3,4])assert.ok(html.includes('Day '+day),'include unscheduled days too');
 s.act('event',{trip,...t.blocks[0],title:'Later plan',start:'10:15'});
 assert.equal(snapshotItinerary(payload),html);
 assert.match(snapshotItinerary(snapshotFrom(s.state.trips[trip])),/Later plan/);
});
