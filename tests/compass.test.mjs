import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const file=new URL('../assets/compass-demo.json',import.meta.url);
const read=()=>fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):null;
import {createCatalog,defaultQuery} from '../assets/compass-fixtures.mjs';
test('quotes use integer cents for both flight legs, child fare, rooms and each stay tax',()=>{
 const c=createCatalog(read()),q=defaultQuery();
 const a=c.quote(q,'ca-direct','ca-standard'),b=c.quote(q,'ca-one-stop','ca-upgrade');
 assert.equal(a.totalCents,413540);assert.equal(b.totalCents,429840);assert.equal(b.totalCents-a.totalCents,16300);
 assert.equal(a.flight.totalCents,171700);assert.equal(a.stay.totalCents,241840);
 assert.equal(a.lines.reduce((sum,l)=>sum+l.amountCents,0),a.totalCents);
 assert.ok(a.lines.every(l=>Number.isSafeInteger(l.amountCents)&&l.currency==='USD'&&l.basis));
 const custom=c.quote({...q,adults:2,childAges:[],rooms:1,end:'2026-10-09'},'ca-direct','ca-standard');
 assert.equal(custom.flight.totalCents,89600);assert.equal(custom.stay.totalCents,99080);assert.equal(custom.totalCents,188680);
 assert.equal(custom.stay.stays[1].nights,2);assert.equal(custom.stay.stays[1].checkoutDate,'2026-10-09');
 assert.equal(a.flight.outbound[0].departure,'09:58');assert.equal(b.flight.connections[0],65);
 assert.throws(()=>c.quote(q,'ca-missing','ca-standard'),/offer/i);
});
test('independent lane filters match schedules, capacities, known amenities and whole totals',()=>{
 const c=createCatalog(read()),q=defaultQuery();assert.equal(typeof c.search,'function','Catalog must search both independent lanes');
 const all=c.search(q);assert.equal(all.flights.length,4);assert.equal(all.stays.length,3);
 assert.deepEqual(c.search(q,{stops:'0',refundable:true}).flights.map(f=>f.id),['ca-flex']);
 assert.equal(c.search(q,{cabin:'Business'}).flights.length,0);
 assert.equal(c.search(q,{departAfter:'12:00'}).flights[0].id,'ca-late');
 assert.equal(c.search(q,{arriveBefore:'11:00'}).flights.length,0);
 assert.equal(c.search(q,{maxConnection:60,stops:'1'}).flights.length,3);
 assert.equal(c.search(q,{maxCents:130000}).flights[0].id,'ca-one-stop');
 assert.deepEqual(c.search(q,{}, {amenities:['breakfast']}).stays.map(s=>s.id),['ca-upgrade']);
 assert.equal(c.search(q,{}, {amenities:['parking']}).stays.length,0);
 assert.equal(c.search(q,{}, {minRating:8.5,cancellable:true}).stays.length,2);
 assert.equal(c.search(q,{}, {maxCents:190000}).stays[0].id,'ca-budget');
 assert.equal(c.search({...q,rooms:1}).stays.length,0);
 for(const d of c.data.supportedDestinations){const x={...q,destination:d.id,airport:d.airport,returnOrigin:d.returnOrigin};const r=c.search(x);assert.equal(r.flights.length,4);assert.ok(r.flights.every(f=>f.outbound.at(-1).destination===d.airport&&f.returning[0].origin===d.returnOrigin));assert.equal(r.stays.length,3);}
 assert.equal(c.search({...q,origin:'LHR'}).flights.length,0);
 assert.equal(c.search({...q,start:'2026-11-02',end:'2026-11-07'}).status,'empty');
 assert.throws(()=>c.quote({...q,rooms:1},'ca-direct','ca-standard'),/occupancy/i);
 assert.throws(()=>c.search({...q,childAges:[-1]}),/age/i);
 assert.throws(()=>c.search({...q,start:'2026-02-30'}),/date/i);
 assert.throws(()=>c.search({...q,adults:1.2}),/adults/i);
});
test('context is date-bound synthetic content, and malformed catalogs fail with a recoverable error',()=>{
 const c=createCatalog(read()),q=defaultQuery();assert.equal(typeof c.context,'function','Catalog must project matching context');
 const x=c.context(q);assert.equal(x.weather.length,6);assert.equal(x.weather[0].high,23);assert.equal(x.events[0].date,'2026-10-08');assert.equal(x.stories.length,1);
 const y=c.context({...q,start:'2026-10-12',end:'2026-10-15'});assert.equal(y.events.length,0);assert.ok(y.weather.every(d=>d.date>='2026-10-12'));
 for(const mutate of [c=>c.flightOffers[0].adultBaseCents=-1,c=>c.stayOffers[0].stays[0].photo='missing',c=>c.flightOffers[0].outbound[0].arrival='07:00',c=>c.weatherDays[0].sample=false]){const bad=read();mutate(bad);assert.throws(()=>createCatalog(bad),/catalog/i);}
});
import {createStore,KEY} from '../assets/connected-state.mjs';
const memory=()=>{const m=new Map();return {getItem:k=>m.get(k),setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)};};
const act=(s,op,p={})=>s.act('compass',{op,catalog:read(),...p});
test('query drafts invalidate both lanes, filters retain hidden selected offers, refresh requires reselect',()=>{
 const s=createStore(memory());act(s,'signin',{name:'Ari'});act(s,'refresh');
 let q=s.state.suite.shopping.Ari;assert.equal(q.flight.id,'ca-direct');assert.equal(q.stay.id,'ca-standard');
 act(s,'filters',{lane:'flight',filters:{maxCents:130000}});assert.equal(s.state.suite.shopping.Ari.flight.id,'ca-direct');
 act(s,'select',{lane:'flight',id:'ca-one-stop'});assert.equal(s.state.suite.shopping.Ari.stay.id,'ca-standard');
 act(s,'draft',{query:{...q.draft,end:'2026-10-11'}});assert.throws(()=>act(s,'save'),/stale/i);
 act(s,'refresh');assert.throws(()=>act(s,'save'),/reselect/i);
 act(s,'select',{lane:'flight',id:'ca-one-stop'});act(s,'select',{lane:'stay',id:'ca-standard'});act(s,'save');
 q=s.state.suite.shopping.Ari;assert.equal(q.saved.status,'Draft');assert.notEqual(q.saved.quote.totalCents,369840);assert.equal(Object.keys(s.state.trips).length,0);
 assert.throws(()=>act(s,'select',{lane:'stay',id:'__proto__'}),/offer/i);
});
test('simulation freezes actual anchors in a canonical trip and is retry-safe after reload',()=>{
 const storage=memory(),s=createStore(storage);act(s,'signin',{name:'Ari'});act(s,'refresh');act(s,'select',{lane:'flight',id:'ca-one-stop'});act(s,'select',{lane:'stay',id:'ca-upgrade'});act(s,'save');act(s,'begin');
 assert.throws(()=>act(s,'confirm'),/acknowledge/i);
 const tId=act(s,'confirm',{acknowledged:true});const t=s.state.trips[tId];assert.equal(t.selectedPackage.totalCents,429840);assert.equal(t.selectedPackage.status,'Confirmed · simulated only');assert.equal(t.blocks.length,7);
 assert.deepEqual(t.blocks.filter(b=>b.kind==='flight').map(b=>[b.date,b.start,b.end]),[['2026-10-05','07:00','08:35'],['2026-10-05','09:40','11:30'],['2026-10-10','15:56','17:38']]);
 assert.ok(t.blocks.some(b=>b.anchor==='checkin'&&b.date==='2026-10-07'&&b.start==='15:30'));
 assert.ok(t.blocks.every(b=>b.zone==='America/Los_Angeles'));
 const loaded=createStore(storage);assert.equal(act(loaded,'confirm',{acknowledged:true}),tId);assert.equal(Object.keys(loaded.state.trips).length,1);assert.equal(loaded.state.trips[tId].blocks.length,7);
 act(loaded,'signout');assert.equal(loaded.state.suite.signedIn,false);assert.equal(loaded.state.trips[tId].blocks.length,7);assert.equal(act(loaded,'signin',{name:'Ari'}),`/trip/${tId}/calendar`);
 loaded.act('invite',{trip:tId,name:'Mina',role:'Editor'});loaded.act('nominate',{trip:tId,name:'Mina'});assert.throws(()=>act(loaded,'confirm',{acknowledged:true}),/payer/i);
});
test('additive suite initialization preserves historical state and storage failures stay honest',()=>{
 const storage=memory(),s=createStore(storage);s.act('creatorStart',{mode:'family'});const old=s.state.creator;act(s,'signin',{name:'Ari'});assert.deepEqual(s.state.creator,old);
 const broken=createStore({getItem:()=>storage.getItem(KEY),setItem(){throw Error('quota');}});act(broken,'signin',{name:'Ari'});assert.match(broken.warning,/until reload/);assert.deepEqual(broken.state.creator,old);
});
test('local catalog provides three real demo destinations, rich offers and five licensed area photos',()=>{
 const c=read();assert.ok(c,'The local catalog must be available without any provider');
 assert.equal(c.schemaVersion,1);assert.equal(c.currency,'USD');assert.equal(c.supportedDestinations.length,3);
 for(const d of c.supportedDestinations){assert.equal(c.flightOffers.filter(f=>f.destination===d.id).length,4);assert.equal(c.stayOffers.filter(f=>f.destination===d.id).length,3);}
 assert.equal(c.photos.length,5);for(const p of c.photos){assert.equal(p.isPropertyPhoto,false);assert.ok(p.sourceUrl.startsWith('https://commons.wikimedia.org/'));assert.ok(p.license.url);}
 assert.equal(c.samplePlans.length,2);assert.ok(c.samplePlans.every(p=>p.fictional&&p.draft.blocks.length>=2));
});

import {landing,parallelSearch,packageReview} from '../assets/compass-views.mjs';
import {shopping} from '../assets/compass-model.mjs';
test('landing explains full travel workflow and parallel view keeps all seven actual offers and itemized basis',()=>{
 const c=createCatalog(read()),s=createStore({getItem(){},setItem(){}});s.act('compass',{op:'signin',name:'Ari'});s.act('compass',{op:'refresh',catalog:read()});
 const intro=landing(c);assert.match(intro,/Plan the whole trip/);assert.match(intro,/demo sign-in/i);assert.match(intro,/Calendar/);assert.match(intro,/FAQ/);
 const html=parallelSearch(s.state,c);for(const f of [...c.data.flightOffers,...c.data.stayOffers].filter(x=>x.destination==='ca'))assert.ok(html.includes(f.id),f.id);
 assert.match(html,/4,135.40/);assert.match(html,/Flights/);assert.match(html,/Stay bundles/);assert.match(html,/Sample weather/);assert.match(html,/Synthetic/);
 const review=packageReview(c.quote(shopping(s.state).committed,'ca-direct','ca-standard'));assert.match(review,/Flight taxes/);assert.match(review,/2026-10-07/);assert.match(review,/15:30/);assert.match(review,/not reserved/);
});
test('fictional creator examples require replacement consent and reuse immutable public review and fork',()=>{
 const s=createStore({getItem(){},setItem(){}});s.act('compass',{op:'import',catalog:read(),id:'harbor'});
 assert.equal(s.state.creator.reviewed,false);assert.equal(s.state.creator.draft.demo,'authored sample');assert.equal(s.state.creator.draft.blocks.length,2);assert.throws(()=>s.act('creatorPublish'),/Review/);
 assert.throws(()=>s.act('compass',{op:'import',catalog:read(),id:'shore'}),/replac/i);
 s.act('creatorReview',{draft:s.state.creator.draft,reviewed:true});const pub=s.act('creatorPublish');assert.equal(s.state.publications[pub].versions[0].blocks.length,2);
 s.act('compass',{op:'import',catalog:read(),id:'shore',replace:true});assert.match(s.state.creator.draft.title,/shore/);assert.equal(s.state.publications[pub].versions[0].title,'A harbor weekend');
});

import {loadCatalog} from '../assets/compass-fixtures.mjs';
test('catalog GET has retryable errors and returns validated local data without artificial delay',async()=>{
 let url;const c=await loadCatalog(async u=>{url=u;return {ok:true,json:async()=>read()};});assert.equal(url,'/assets/compass-demo.json');assert.equal(c.quote(defaultQuery(),'ca-direct','ca-standard').totalCents,413540);
 await assert.rejects(loadCatalog(async()=>({ok:false,status:503})),/Retry/i);await assert.rejects(loadCatalog(async()=>({ok:true,json:async()=>({})})),/invalid/);await assert.rejects(loadCatalog(async()=>{throw Error('offline');}),/Retry/i);
});

import {tripHeader} from '../assets/connected-views.mjs';
test('saved shopping draft resumes before search and confirmed header names simulation with primary Notes and Invite',()=>{
 const s=createStore({getItem(){},setItem(){}}),act=(op,p={})=>s.act('compass',{op,catalog:read(),...p});act('signin',{name:'Ari'});act('refresh');act('save');act('signout');assert.equal(act('signin',{name:'Ari'}),'/draft');act('begin');const id=act('confirm',{acknowledged:true});const html=tripHeader(s.state.trips[id],'Ari','calendar');assert.match(html,/SIMULATED/);assert.match(html,/Invite/);assert.doesNotMatch(html,/<details id="trip-options" open>/);
});
test('malformed child price coverage, weather dates and root date range are rejected before a partial quote',()=>{
 for(const mutate of [d=>d.flightOffers[0].childFares=[],d=>delete d.supportedDateRange,d=>d.weatherDays[0].date='bad',d=>d.weatherDays[0].high='warm']){const d=read();mutate(d);assert.throws(()=>createCatalog(d),/invalid/);}
});

test('catalog rejects missing rendering-critical policy, baggage, destination and sample fields',()=>{
 for(const mutate of [d=>delete d.flightOffers[0].baggage,d=>delete d.stayOffers[0].amenities,d=>delete d.samplePlans[0].draft,d=>delete d.supportedDestinations[0].name,d=>d.flightOffers[0].capacity=0]){const d=read();mutate(d);assert.throws(()=>createCatalog(d),/invalid/);}
});
test('tax basis text and totals derive from catalog rates rather than a fixed marketing label',()=>{const d=read();d.stayOffers[0].stays[0].taxBasisPoints=1500;const quote=createCatalog(d).quote(defaultQuery(),'ca-direct','ca-standard');const tax=quote.lines.find(l=>l.id==='ca-standard-0-tax');assert.equal(tax.amountCents,13500);assert.match(tax.basis,/15%/);assert.equal(quote.totalCents,416240);});

test('both price ceilings distinguish zero from unlimited and compare exact integer cents',()=>{
 const c=createCatalog(read()),q=defaultQuery(),all=c.search(q);
 for(const lane of ['flights','stays']){
  const search=maxCents=>lane==='flights'?c.search(q,{maxCents}).flights:c.search(q,{}, {maxCents}).stays;
  for(const absent of [undefined,null,'','  '])assert.deepEqual(search(absent),all[lane]);
  for(const zero of [0,'0'])assert.deepEqual(search(zero),[],lane+' zero must exclude paid offers');
  const min=Math.min(...all[lane].map(o=>o.totalCents));
  assert.equal(search(min-1).length,0);
  assert.ok(search(min).some(o=>o.totalCents===min));
  assert.deepEqual(search(String(min)),search(min));
 }
});

test('numeric filter bounds reject invalid values consistently before selecting either lane',()=>{
 const c=createCatalog(read());
 for(const lane of ['flight','stay']){
  const search=(filters,q=defaultQuery())=>lane==='flight'?c.search(q,filters):c.search(q,{},filters);
  const keys=lane==='flight'?['maxCents','stops','maxConnection']:['maxCents','minRating'];
  for(const key of keys){
   for(const value of [-1,'-1',NaN,Infinity,-Infinity,'NaN','Infinity','no',true,false,[],{},'1e999']){
    assert.throws(()=>search({[key]:value}),/filter/i,lane+' '+key+' '+String(value));
    assert.throws(()=>search({[key]:value},{...defaultQuery(),destination:'unsupported'}),/filter/i);
   }
   for(const value of [undefined,null,'','  '])assert.doesNotThrow(()=>search({[key]:value}));
  }
  for(const value of [0.1,'0.1',Number.MAX_SAFE_INTEGER+1])assert.throws(()=>search({maxCents:value}),/filter/i);
 }
 assert.throws(()=>c.search(defaultQuery(),{stops:0.5}),/filter/i);
 assert.throws(()=>c.search(defaultQuery(),{maxConnection:0}),/filter/i);
 assert.throws(()=>c.search(defaultQuery(),{maxConnection:1.5}),/filter/i);
 assert.throws(()=>c.search(defaultQuery(),{},{minRating:10.1}),/filter/i);
 assert.doesNotThrow(()=>c.search(defaultQuery(),{stops:'any',maxConnection:1},{minRating:0}));
 assert.equal(c.search(defaultQuery(),{stops:0}).flights.every(f=>f.stops===0),true);
 assert.equal(c.search(defaultQuery(),{},{minRating:8.5}).stays.every(s=>s.rating>=8.5),true);
});
