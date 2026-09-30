import test from 'node:test';
import assert from 'node:assert/strict';
import {createStore,publicPreview} from '../assets/connected-state.mjs';
import {publicPayload} from '../assets/connected-public.mjs';
import {itinerary,publicPage,esc} from '../assets/connected-views.mjs';
const store=()=>createStore({getItem(){return null;},setItem(){}});
const detail='Public stop details <em>plain text</em> & "chairs"';

for(const mode of ['import','blank']) test(`${mode}: every reviewed public field is rendered as text, without private fields or demo dependency`,()=>{
 const s=store();
 if(mode==='import')s.act('extract',{source:'https://example.com/synthetic-itinerary'});
 else s.act('creatorStart',{mode:'blank'});
 const d={...s.state.creator.draft,title:'Reviewed walking plan',destination:'California',startDate:'2026-10-05',zone:'America/Los_Angeles',party:{adults:3,children:[4],names:['SENSITIVE_NAME']},context:'Public assumptions <em>unverified</em>',notes:['SENSITIVE_NOTE'],payment:'SENSITIVE_PAYMENT',blocks:[{title:'Garden <em>pause</em>',kind:'hotel',day:1,start:'10:15',end:'11:30',zone:'America/Los_Angeles',period:'Morning',detail,timing:{start:'edited',end:'supplied',startMeaning:'check-in',endMeaning:'checkout',suppliedStart:'10:00',suppliedEnd:'11:30',secret:'SENSITIVE_TIMING'},booking:'SENSITIVE_BOOKING'}]};
 if(mode==='import')assert.equal(d.demo,undefined);
 s.act('creatorReview',{draft:d,backlink:mode==='import',reviewed:true});
 const reviewed=publicPayload(s.state.creator.draft),preview=itinerary(reviewed);
 if(mode==='import')assert.doesNotMatch(preview,/Demo ·|Synthetic plan/,'ordinary publications must not acquire a demo classification from their presentation');
 const id=s.act('creatorPublish'),c=s.state.publications[id],v=c.versions[0],page=publicPage(c,v,'Ari');
 assert.deepEqual(publicPayload(v),reviewed);
 for(const html of [preview,page]){
  for(const text of [detail,d.context,d.blocks[0].title])assert.ok(html.includes(esc(text)),`missing public wording: ${text}`);
  for(const text of ['2026-10-05','3 adults + 1 child (age 4)','California','UTC−07:00','Morning','hotel','10:15 check-in','edited placement','10:00','11:30 checkout','user supplied','11:30'])assert.ok(html.includes(text),`missing public metadata: ${text}`);
  if(mode==='import')assert.ok(html.includes('https://example.com/synthetic-itinerary'));
  else assert.ok(html.includes('authored sample'),'review includes the published demo label');
  assert.doesNotMatch(html,/<em>|SENSITIVE_/);
 }
 assert.ok(page.includes(preview),'published itinerary uses the identical reviewed renderer');
 const summaries=[...preview.matchAll(/<summary>([\s\S]*?)<\/summary>/g)].map(m=>m[1]);
 assert.ok(summaries.length>0,'full stop details remain reachable from compact summaries');
 assert.ok(summaries.every(text=>!text.includes(esc(detail))),'full descriptions must not bloat the compact summary');
});

test('public detail edits require fresh exact approval and earlier selected versions render only their own wording',()=>{
 const s=store();s.act('extract',{source:'https://example.com/synthetic-itinerary'});
 const draft=structuredClone(s.state.creator.draft);draft.blocks[0].detail='First reviewed stop details';
 s.act('creatorReview',{draft,reviewed:true});const id=s.act('creatorPublish');
 const first=structuredClone(s.state.publications[id].versions[0]),old=publicPreview(s.state.publications[id]);
 const changed=structuredClone(old.payload);changed.blocks[0].detail='Updated public stop details <em>literal</em>';
 s.act('publicDraft',{id,draft:changed});
 assert.throws(()=>s.act('publish',{id,approval:old}),/preview/i);
 s.act('publicDraft',{id,draft:old.payload});assert.throws(()=>s.act('publish',{id,approval:old}),/preview/i);
 s.act('publicDraft',{id,draft:changed});const fresh=publicPreview(s.state.publications[id]);
 assert.ok(itinerary(fresh.payload).includes(esc(changed.blocks[0].detail)));
 s.act('publish',{id,approval:fresh});const c=s.state.publications[id];
 assert.deepEqual(c.versions[0],first);assert.deepEqual(publicPayload(c.versions[1]),fresh.payload);
 for(const v of c.versions){const html=publicPage(c,v,'Ari');assert.ok(html.includes(esc(v.blocks[0].detail)));assert.ok(!html.includes(esc(c.versions[v.version===1?1:0].blocks[0].detail)));}
});

test('retained supplied endpoint values remain reviewable for every allowlisted provenance basis',()=>{
 for(const basis of ['supplied','placement','edited']){
  const payload=publicPayload({title:'Endpoint review',destination:'Lisbon',blocks:[{title:'Arrival plan',kind:'flight',day:1,start:'10:15',end:'11:30',zone:'UTC',timing:{start:basis,end:basis,startMeaning:'departure',endMeaning:'arrival',suppliedStart:'10:00',suppliedEnd:'11:00'}}]});
  const html=itinerary(payload);
  for(const value of ['10:15 departure','11:30 arrival','10:00','11:00'])assert.ok(html.includes(value),basis+': missing '+value);
 }
});
