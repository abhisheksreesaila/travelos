import test from 'node:test';
import assert from 'node:assert/strict';
import {calendar} from '../assets/connected-views.mjs';
import {createStore,defaults} from '../assets/connected-state.mjs';
const store=()=>createStore({getItem(){return null;},setItem(){}});
test('calendar exposes an accurate full 24 hour scale and enlarged readable event positions without changing data',()=>{
 const s=store(),id=s.act('createTrip',{title:'Time fidelity',query:defaults()});s.act('event',{trip:id,title:'Garden',date:'2026-10-12',start:'10:00',end:'11:00',zone:'UTC'});
 const t=s.state.trips[id],before=structuredClone(t),html=calendar(t,'Ari');
 assert.match(html,/--hour-height:96px/);assert.match(html,/--day-height:2304px/);assert.match(html,/top:2208px/);assert.match(html,/top:960px/);assert.match(html,/--duration:96px/);assert.deepEqual(t,before);
});
test('short overlapping activities retain individually reachable direct operations and accurate duration markers',()=>{
 const s=store(),id=s.act('createTrip',{title:'Dense day',query:defaults()});for(let i=0;i<8;i++)s.act('event',{trip:id,title:`Short stop ${i}`,date:'2026-10-12',start:'10:00',end:'10:15',zone:'UTC',overlap:true});
 const t=s.state.trips[id],before=structuredClone(t),html=calendar(t,'Ari');
 assert.match(html,/Timed activity list/);assert.match(html,/height:24px/);
 for(const b of t.blocks){assert.equal(html.split(`data-block-id="${b.id}"`).length-1,1);assert.match(html,new RegExp(`data-drag="move" data-id="${b.id}"`));assert.match(html,new RegExp(`data-drag="resize" data-id="${b.id}"`));}
 assert.deepEqual(t,before);
});
test('wrapped activity controls remain separate from a nearby activity entered at an arbitrary minute',()=>{
 const s=store(),id=s.act('createTrip',{title:'Wrap boundary',query:defaults()});
 s.act('event',{trip:id,title:'W'.repeat(36),date:'2026-10-12',start:'10:00',end:'10:15',zone:'UTC'});
 s.act('event',{trip:id,title:'Next stop',date:'2026-10-12',start:'12:05',end:'12:20',zone:'UTC'});
 const t=s.state.trips[id],before=structuredClone(t),html=calendar(t,'Ari');
 assert.match(html,/Timed activity list/);
 assert.match(html,/12:05–12:20 UTC/);
 assert.deepEqual(t,before);
});
