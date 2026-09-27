// Deterministic, tab-local planning. No provider or backend calls.
export const KEY = 'travelos.connected.v1';
export const airports = {LHR:'London · Heathrow (LHR)', GRX:'Granada · Federico García Lorca (GRX)', LIS:'Lisbon · Humberto Delgado (LIS)', JFK:'New York · John F. Kennedy (JFK)'};
export const defaults = () => ({destination:'Granada',origin:'LHR',airport:'GRX',start:'2026-10-12',end:'2026-10-15',adults:2,children:0,ages:'',rooms:1,flights:true,hotels:true,cabin:'Any',maxPrice:500,family:false,pet:false});
export const fixtures = ['Granada','Lisbon'].flatMap((destination,i) => [
  {id:`f${i}a`,kind:'flight',title:i?'Lisbon light hop':'Sierra morning hop',destination,origin:'LHR',airport:i?'LIS':'GRX',price:145,cabin:'Economy',capacity:6,start:'09:00',end:'12:00'},
  {id:`f${i}b`,kind:'flight',title:'A little more legroom',destination,origin:'LHR',airport:i?'LIS':'GRX',price:320,cabin:'Business',capacity:4,start:'14:00',end:'17:00'},
  {id:`h${i}a`,kind:'hotel',title:i?'Tile & Tide House':'Patio & Orange House',destination,price:98,capacity:2,family:false,pet:'Unknown',start:'15:00',end:'11:00'},
  {id:`h${i}b`,kind:'hotel',title:i?'River Garden Rooms':'Little Garden Rooms',destination,price:165,capacity:4,family:true,pet:false,start:'15:00',end:'11:00'}
]);
export const clone = value => structuredClone(value);
const fail = message => {throw new Error(message);};
const dateOK = value => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0,10) === value;
export function dates(start,end) {
  if (!dateOK(start) || !dateOK(end) || end <= start) fail('Choose valid dates; end date must follow start.');
}
export function search(q) {
  for (const key of ['origin','airport']) if(q[key] && !airports[q[key]]) fail('Choose a listed airport, or Any airport.');
  if(q.origin && q.origin === q.airport) fail('Origin and destination airport must differ.');
  if(q.start || q.end) dates(q.start,q.end);
  if(!Number.isInteger(+q.adults) || +q.adults < 1 || +q.adults > 12) fail('Adults must be 1–12.');
  if(!Number.isInteger(+q.rooms) || +q.rooms < 1 || +q.rooms > 6) fail('Rooms must be 1–6.');
  if(!Number.isInteger(+q.children) || +q.children < 0 || +q.children > 6) fail('Children must be 0–6, with ages.');
  const ages = String(q.ages || '').split(',').map(x=>x.trim()).filter(Boolean);
  if(ages.length !== +q.children || ages.some(x=>!/^\d+$/.test(x) || +x>17)) fail('Enter one child age (0–17) per child, separated by commas.');
  if(!Number.isFinite(+q.maxPrice) || +q.maxPrice < 0) fail('Enter a non-negative hotel budget.');
  if(!['Any','Economy','Business'].includes(q.cabin)) fail('Cabin is not supported by these fixtures.');
  return fixtures.filter(f => (!q.destination || f.destination.toLowerCase().includes(q.destination.toLowerCase())) &&
    (!q.start || q.start >= '2026-10-01' && q.end <= '2026-11-01') &&
    (f.kind === 'flight' ? q.flights && (!q.origin || f.origin === q.origin) && (!q.airport || f.airport === q.airport) && (q.cabin === 'Any' || f.cabin === q.cabin) && +q.adults + +q.children <= f.capacity :
      q.hotels && f.price <= +q.maxPrice && +q.adults + +q.children <= f.capacity * +q.rooms && (!q.family || f.family === true) && (!q.pet || f.pet === true)));
}
