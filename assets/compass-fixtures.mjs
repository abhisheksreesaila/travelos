// Local synthetic catalog adapter. No provider APIs or persistence.
export async function loadCatalog(fetcher=fetch){
 let data;try{const response=await fetcher('/assets/compass-demo.json',{cache:'no-store'});if(!response.ok)throw Error();data=await response.json();}catch{throw Error('Local demo catalog could not load. Retry; saved work is unchanged.');}
 return createCatalog(data);
}
export const defaultQuery=()=>({destination:'ca',origin:'SFO',airport:'BUR',returnOrigin:'SAN',start:'2026-10-05',end:'2026-10-10',adults:3,childAges:[4],rooms:2});
const copy=v=>structuredClone(v);
const unset=v=>v==null||typeof v==='string'&&!v.trim();
const fail=message=>{throw Error(message);};
function numericFilter(value,label,min=0,max=Number.MAX_SAFE_INTEGER,integer=true){
 if(unset(value))return undefined;
 const validType=typeof value==='number'||typeof value==='string'&&/^\+?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim());
 const number=Number(value);
 if(!validType||!Number.isFinite(number)||number<min||number>max||integer&&!Number.isSafeInteger(number))fail(label+' filter must be '+(integer?'a whole number':'a number')+' between '+min+' and '+max+'.');
 return number;
}
const minutes=t=>{const [h,m]=t.split(':').map(Number);return h*60+m;};
export const nights=q=>(Date.parse(q.end)-Date.parse(q.start))/86400000;
const shift=(date,n)=>new Date(Date.parse(date)+n*86400000).toISOString().slice(0,10);
export const queryKey=q=>JSON.stringify([q.destination,q.origin,q.airport,q.returnOrigin,q.start,q.end,q.adults,q.childAges,q.rooms]);
export function createCatalog(input){
 const data=copy(input);
 const amount=v=>Number.isSafeInteger(v)&&v>=0, time=v=>/^([01]\d|2[0-3]):[0-5]\d$/.test(v);
 const unique=items=>new Set(items.map(x=>x.id)).size===items.length;
 try{
  if(data.schemaVersion!==1||data.currency!=='USD'||!data.fixtureRevision||!data.supportedDateRange||!/^\d{4}-\d{2}-\d{2}$/.test(data.supportedDateRange.start)||!Number.isInteger(data.supportedDateRange.maxNights))throw Error();
  for(const key of ['supportedDestinations','photos','flightOffers','stayOffers','weatherDays','localItems','samplePlans'])if(!Array.isArray(data[key])||!unique(data[key]))throw Error();
  const dest=id=>data.supportedDestinations.some(d=>d.id===id),photo=id=>data.photos.some(p=>p.id===id);
  for(const d of data.supportedDestinations)if(typeof d.name!=='string'||!d.name.trim()||!Array.isArray(d.areas)||!photo(d.photo))throw Error();
  for(const p of data.samplePlans)if(!p.draft||!Array.isArray(p.draft.blocks)||typeof p.draft.title!=='string'||p.fictional!==true||!photo(p.photo))throw Error();
  for(const f of data.flightOffers)if(!Number.isInteger(f.capacity)||f.capacity<1||!f.baggage||typeof f.baggage.description!=='string'||typeof f.baggage.checked!=='boolean')throw Error();
  for(const s of data.stayOffers)if(!s.amenities||typeof s.cancellationPolicy!=='string'||Object.values(s.amenities).some(v=>v!==null&&typeof v!=='boolean'))throw Error();
  for(const p of data.photos)if(p.isPropertyPhoto!==false||!p.sourceUrl.startsWith('https://commons.wikimedia.org/')||!p.license?.url||!/^[-a-z0-9]+\.jpg$/.test(p.file))throw Error();
  for(const f of data.flightOffers){
   if(!dest(f.destination)||f.provenance!=='synthetic'||![f.adultBaseCents,f.taxPerTravelerCents,f.feePerTravelerCents].every(amount)||!Array.isArray(f.childFares)||!f.childFares.every(b=>amount(b.baseCents)))throw Error();
   if(Array.from({length:18},(_,age)=>f.childFares.filter(b=>age>=b.minAge&&age<=b.maxAge).length).some(n=>n!==1))throw Error();
   for(const legs of [f.outbound,f.returning]){if(!legs.length)throw Error();for(const [i,s] of legs.entries())if(!time(s.departure)||!time(s.arrival)||s.arrival<=s.departure||s.zone!=='America/Los_Angeles'||i&&(legs[i-1].destination!==s.origin||legs[i-1].arrival>=s.departure))throw Error();}
  }
  for(const f of data.stayOffers){if(!dest(f.destination)||f.provenance!=='synthetic'||!Number.isFinite(f.rating)||!f.stays.length)throw Error();for(const s of f.stays)if(![s.nightlyRoomBaseCents,s.taxBasisPoints,s.mandatoryFeePerRoomStayCents].every(amount)||!photo(s.photo)||!time(s.checkin)||!time(s.checkout)||s.occupancyPerRoom<1)throw Error();}
  for(const w of data.weatherDays)if(!/^\d{4}-\d{2}-\d{2}$/.test(w.date)||!Number.isFinite(w.high)||!Number.isFinite(w.low)||w.units!=='C')throw Error();
  for(const item of [...data.weatherDays,...data.localItems])if(!dest(item.destination)||item.sample!==true||item.verified!==false)throw Error();
 }catch{fail('Demo catalog is invalid. Retry loading the local catalog; saved work is unchanged.');}
 const date=v=>/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
 function validate(q){
  if(!date(q.start)||!date(q.end)||q.end<=q.start)fail('Choose valid dates; return must follow outbound.');
  if(!Number.isInteger(q.adults)||q.adults<1||q.adults>12)fail('Adults must be 1–12.');
  if(!Number.isInteger(q.rooms)||q.rooms<1||q.rooms>6)fail('Rooms must be 1–6.');
  if(!Array.isArray(q.childAges)||q.childAges.length>6||q.childAges.some(a=>!Number.isInteger(a)||a<0||a>17))fail('Each child age must be 0–17.');
  const d=data.supportedDestinations.find(d=>d.id===q.destination);
  return d&&q.start>=data.supportedDateRange.start&&q.end<=data.supportedDateRange.end&&nights(q)>=d.minNights&&nights(q)<=data.supportedDateRange.maxNights?d:null;
 }
 const flightValid=(q,f)=>{const d=validate(q);return d&&f.destination===q.destination&&q.origin===d.origin&&q.airport===d.airport&&q.returnOrigin===d.returnOrigin&&q.adults+q.childAges.length<=f.capacity;};
 const stayValid=(q,s)=>validate(q)&&s.destination===q.destination&&s.stays.every(x=>q.adults+q.childAges.length<=q.rooms*x.occupancyPerRoom);
 const line=(id,label,amountCents,basis)=>({id,label,amountCents,basis,currency:'USD',included:true});
 const sum=lines=>lines.reduce((n,l)=>n+l.amountCents,0);
 function flight(q,id){
  const f=copy(data.flightOffers.find(f=>f.id===id&&f.destination===q.destination));if(!f)fail('Flight offer unavailable');
  const children=q.childAges.map(age=>f.childFares.find(b=>age>=b.minAge&&age<=b.maxAge)?.baseCents);
  const count=q.adults+children.length;
  const lines=[line(id+'-adult',`${q.adults} adult round-trip fares`,q.adults*f.adultBaseCents,`${q.adults} adults × ${f.adultBaseCents} cents`),...children.map((c,i)=>line(id+'-child-'+i,`Child age ${q.childAges[i]} round-trip fare`,c,'one child')),line(id+'-tax','Flight taxes',count*f.taxPerTravelerCents,`${count} travelers × ${f.taxPerTravelerCents} cents`),line(id+'-fee','Flight mandatory fees',count*f.feePerTravelerCents,`${count} travelers × ${f.feePerTravelerCents} cents`)];
  const outbound=f.outbound.map(s=>({...s,date:q.start})),returning=f.returning.map(s=>({...s,date:q.end}));
  return {...f,outbound,returning,connections:[...outbound.slice(1).map((s,i)=>minutes(s.departure)-minutes(outbound[i].arrival)),...returning.slice(1).map((s,i)=>minutes(s.departure)-minutes(returning[i].arrival))],stops:Math.max(outbound.length,returning.length)-1,lines,totalCents:sum(lines)};
 }
 function stay(q,id){
  const f=copy(data.stayOffers.find(f=>f.id===id&&f.destination===q.destination));if(!f)fail('Stay offer unavailable');
  const stays=f.stays.map((s,i)=>{
   const checkinDate=i?shift(q.start,2):q.start,checkoutDate=f.stays.length>1&&!i?shift(q.start,2):q.end;
   const count=nights({start:checkinDate,end:checkoutDate}),base=q.rooms*count*s.nightlyRoomBaseCents;
   const lines=[line(s.id+'-base',s.name+' · room base',base,`${q.rooms} rooms × ${count} nights × ${s.nightlyRoomBaseCents} cents`),line(s.id+'-tax',s.name+' · sample tax',Math.round(base*s.taxBasisPoints/10000),(s.taxBasisPoints/100)+'% of this stay base; not local tax law'),line(s.id+'-fee',s.name+' · mandatory fees',q.rooms*s.mandatoryFeePerRoomStayCents,`${q.rooms} rooms × ${s.mandatoryFeePerRoomStayCents} cents per room / stay`)];
   return {...s,checkinDate,checkoutDate,nights:count,rooms:q.rooms,lines,totalCents:sum(lines)};
  });
  const lines=stays.flatMap(s=>s.lines);return {...f,stays,lines,totalCents:sum(lines)};
 }
 function search(q,ff={},sf={}){
  ff={...ff,maxCents:numericFilter(ff.maxCents,'Flight maximum price'),stops:ff.stops==='any'?undefined:numericFilter(ff.stops,'Stops'),maxConnection:numericFilter(ff.maxConnection,'Maximum connection',1)};
  sf={...sf,maxCents:numericFilter(sf.maxCents,'Stay maximum price'),minRating:numericFilter(sf.minRating,'Minimum rating',0,10,false)};
  const d=validate(q);if(!d)return {status:'empty',flights:[],stays:[],reason:'No demo fixtures for this destination/date range. October 2026 only; 1–7 nights (California: 3–7).'};
  const flights=data.flightOffers.filter(f=>flightValid(q,f)).map(f=>flight(q,f.id)).filter(f=>(!ff.cabin||ff.cabin==='Any'||f.cabin===ff.cabin)&&(unset(ff.stops)||f.stops<=+ff.stops)&&(!ff.refundable||f.refundable===true)&&(!ff.checked||f.baggage.checked===true)&&(unset(ff.maxCents)||f.totalCents<=+ff.maxCents)&&(!ff.departAfter||f.outbound[0].departure>=ff.departAfter)&&(!ff.arriveBefore||f.outbound.at(-1).arrival<=ff.arriveBefore)&&(!ff.returnAfter||f.returning[0].departure>=ff.returnAfter)&&(!ff.returnBefore||f.returning.at(-1).arrival<=ff.returnBefore)&&(!ff.maxConnection||f.connections.every(n=>n<=+ff.maxConnection)));
  const stays=data.stayOffers.filter(s=>stayValid(q,s)).map(s=>stay(q,s.id)).filter(s=>(!sf.minRating||s.rating>=+sf.minRating)&&(unset(sf.maxCents)||s.totalCents<=+sf.maxCents)&&(!sf.cancellable||s.cancellable===true)&&(!sf.cancelAfter||s.cancellationCutoff?.slice(0,10)>=sf.cancelAfter)&&(sf.amenities||[]).every(a=>s.amenities[a]===true));
  if(ff.sort==='price')flights.sort((a,b)=>a.totalCents-b.totalCents);if(sf.sort==='price')stays.sort((a,b)=>a.totalCents-b.totalCents);
  return {status:flights.length||stays.length?'ready':'empty',flights,stays,reason:'No matching demo offers. Check route, room occupancy or independent filters.'};
 }
 function context(q){
  const d=validate(q);if(!d)return {key:queryKey(q),weather:[],events:[],stories:[]};
  return {key:queryKey(q),revision:data.fixtureRevision,weather:copy(data.weatherDays.filter(w=>w.destination===q.destination&&w.date>=q.start&&w.date<=q.end).map(w=>({...w,area:q.destination==='ca'?(w.date<shift(q.start,2)?'Hollywood':w.date===q.end?'San Diego':'Del Mar'):d.name}))),events:copy(data.localItems.filter(x=>x.destination===q.destination&&x.kind==='event'&&x.date>=q.start&&x.date<=q.end)),stories:copy(data.localItems.filter(x=>x.destination===q.destination&&x.kind==='story'))};
 }
 return {data:copy(data),validate,search,context,flight,stay,quote(q,flightId,stayId){const f=flight(q,flightId),s=stay(q,stayId);if(!flightValid(q,f))fail('Flight offer does not match route, dates or party capacity.');if(!stayValid(q,s))fail('Stay offer does not match dates or room occupancy.');const lines=[...f.lines,...s.lines];return {query:copy(q),key:queryKey(q),revision:data.fixtureRevision,currency:data.currency,flight:f,stay:s,lines,totalCents:sum(lines)};}};
}
