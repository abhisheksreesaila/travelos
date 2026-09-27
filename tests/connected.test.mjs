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
test('invalid search is rejected rather than silently interpreted', () => {
  for(const change of [{origin:'GRX'},{end:'2026-10-10'},{adults:0},{rooms:0},{origin:'Unknown'},{children:1},{maxPrice:-1}]) {
    assert.throws(() => api.search(query(change)), /airport|date|adult|room|age|budget/i);
  }
  assert.equal(api.search(query({destination:'',origin:'',airport:'',start:'',end:''})).length, 8);
});
