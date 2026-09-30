// Public payloads are built by allowlist, never by serializing a private trip.
export function safeLink(value) {
  if(!value) return '';
  let url;try{url=new URL(value);}catch{throw Error('Enter a full HTTPS source URL.');}
  if(url.protocol!=='https:' || url.username || url.password || url.search || url.hash || !url.hostname.includes('.') || /localhost|127\.0\.0\.1/.test(url.hostname)) throw Error('Use a public HTTPS URL without credentials, query tokens or fragments.');
  return url.href;
}
export const CALIFORNIA='America/Los_Angeles';
export function validateZone(zone,date) {
  if(zone==='UTC') return;
  if(zone!==CALIFORNIA) throw Error('Unsupported planning zone. Choose UTC or California.');
  if(!/^2026-10-(0[1-9]|[12]\d|3[01])$/.test(date||'')) throw Error('California planning supports October 2026 only (PDT, UTC−07:00); choose supported dates, no automatic conversion.');
}
export const zoneLabel=zone=>zone===CALIFORNIA?'California · PDT (UTC−07:00)':'UTC';
export function planningMetadata(input) {
  const out={};
  if(input.zone){validateZone(input.zone,input.startDate||input.start);out.zone=input.zone;}
  if(input.startDate){if(!/^\d{4}-\d{2}-\d{2}$/.test(input.startDate)||!Number.isFinite(Date.parse(input.startDate))||new Date(input.startDate).toISOString().slice(0,10)!==input.startDate)throw Error('Review a valid Day 1 date.');out.startDate=input.startDate;}
  if(input.party){const {adults,children}=input.party;if(!Number.isInteger(adults)||adults<1||adults>12||!Array.isArray(children)||children.length>6||children.some(n=>!Number.isInteger(n)||n<0||n>17))throw Error('Review aggregate adults and child ages.');out.party={adults,children:[...children]};}
  if(['imported sample','authored sample'].includes(input.demo))out.demo=input.demo;
  if(input.context)out.context=wording(input.context,2000);
  return out;
}
function publicTiming(b) {
  if(!b.timing)return {};
  const timing={};
  for(const edge of ['start','end']){
    if(!['supplied','placement','edited'].includes(b.timing[edge]))throw Error('Review each endpoint as supplied, placement or edited.');
    timing[edge]=b.timing[edge];
    const meaning=b.timing[edge+'Meaning'];if(meaning){if(!['arrival','departure','planning start','planning end','check-in','checkout'].includes(meaning))throw Error('Review endpoint meaning.');timing[edge+'Meaning']=meaning;}
    const supplied=b.timing['supplied'+(edge==='start'?'Start':'End')];if(supplied){if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(supplied))throw Error('Review supplied endpoint time.');timing['supplied'+(edge==='start'?'Start':'End')]=supplied;}
  }
  return {timing};
}
function wording(text,max=180) {
  if(typeof text!=='string' || !text.trim() || text.length>max) throw Error(`Public wording must contain 1–${max} characters.`);
  if(/@|\b(?:booking|receipt|token|password|private|ref)[\s:#=-]|\b\d{7,}\b/i.test(text)) throw Error('Remove likely private/email/booking details from public wording.');
  return text.trim();
}
export function publicPayload(input,{draft=false}={}) {
  const label=value=>draft&&value===''?'':wording(value);
  const title=label(input.title),destination=label(input.destination);
  if(!Array.isArray(input.blocks) || input.blocks.length>100 || !draft&&!input.blocks.length) throw Error('Review at least one public stop, maximum 100.');
  const blocks=input.blocks.map(b=>{
    if(!Number.isInteger(+b.day) || +b.day<1 || +b.day>60) throw Error('Public day must be 1–60.');
    validateZone(b.zone,input.startDate?new Date(Date.parse(input.startDate)+(+b.day-1)*86400000).toISOString().slice(0,10):null);
    if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(b.start) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(b.end) || b.end<=b.start) throw Error('Use ordered same-day planning times.');
    return {title:wording(b.title),kind:['flight','hotel','activity'].includes(b.kind)?b.kind:'activity',day:+b.day,start:b.start,end:b.end,zone:b.zone,...(b.detail?{detail:wording(b.detail,2000)}:{}),...(['Morning','Afternoon','Evening'].includes(b.period)?{period:b.period}:{}),...publicTiming(b)};
  }).sort((a,b)=>a.day-b.day||a.start.localeCompare(b.start));
  return {title,destination,blocks,backlink:safeLink(input.backlink||''),...planningMetadata(input)};
}
// Snapshot wording belongs to the itinerary; group notes, identities and payment data do not.
export function snapshotFrom(trip) {
  const payload={...contributionFrom(trip),end:trip.end};
  payload.blocks=payload.blocks.map((b,i)=>({...b,title:trip.blocks[i].title,...(trip.blocks[i].detail?{detail:trip.blocks[i].detail}:{}),...(['Morning','Afternoon','Evening'].includes(trip.blocks[i].period)?{period:trip.blocks[i].period}:{})}));
  return payload;
}
export function contributionFrom(trip) {
  return {title:'A little escape',destination:['Granada','Lisbon','California','Del Mar'].includes(trip.destination)?trip.destination:'Destination to review',backlink:'',...planningMetadata({...trip,startDate:trip.start}),blocks:trip.blocks.map(b=>({title:b.kind==='flight'?'Flight plan':b.kind==='hotel'?(b.anchor==='checkin'?'Stay check-in':'Stay check-out'):'Activity to describe',kind:b.kind,day:Math.round((Date.parse(b.date)-Date.parse(trip.start))/86400000)+1,start:b.start,end:b.end,zone:b.zone,...publicTiming(b)}))};
}
