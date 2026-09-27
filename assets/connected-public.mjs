// Public payloads are built by allowlist, never by serializing a private trip.
export function safeLink(value) {
  if(!value) return '';
  let url;try{url=new URL(value);}catch{throw Error('Enter a full HTTPS source URL.');}
  if(url.protocol!=='https:' || url.username || url.password || url.search || url.hash || !url.hostname.includes('.') || /localhost|127\.0\.0\.1/.test(url.hostname)) throw Error('Use a public HTTPS URL without credentials, query tokens or fragments.');
  return url.href;
}
function wording(text) {
  if(typeof text!=='string' || !text.trim() || text.length>180) throw Error('Public wording must contain 1–180 characters.');
  if(/@|\b(?:booking|receipt|token|password|private|ref)[\s:#=-]|\b\d{7,}\b/i.test(text)) throw Error('Remove likely private/email/booking details from public wording.');
  return text.trim();
}
export function publicPayload(input) {
  const title=wording(input.title),destination=wording(input.destination);
  if(!Array.isArray(input.blocks) || input.blocks.length>100 || !input.blocks.length) throw Error('Review at least one public stop, maximum 100.');
  const blocks=input.blocks.map(b=>{
    if(!Number.isInteger(+b.day) || +b.day<1 || +b.day>60) throw Error('Public day must be 1–60.');
    if(b.zone!=='UTC' || !/^([01]\d|2[0-3]):[0-5]\d$/.test(b.start) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(b.end) || b.end<=b.start) throw Error('Use ordered same-day UTC times.');
    return {title:wording(b.title),kind:['flight','hotel','activity'].includes(b.kind)?b.kind:'activity',day:+b.day,start:b.start,end:b.end,zone:'UTC'};
  }).sort((a,b)=>a.day-b.day||a.start.localeCompare(b.start));
  return {title,destination,blocks,backlink:safeLink(input.backlink||'')};
}
export function contributionFrom(trip) {
  return {title:'A little escape',destination:['Granada','Lisbon'].includes(trip.destination)?trip.destination:'Destination to review',backlink:'',blocks:trip.blocks.map(b=>({title:b.kind==='flight'?'Flight plan':b.kind==='hotel'?(b.anchor==='checkin'?'Stay check-in':'Stay check-out'):'Activity to describe',kind:b.kind,day:Math.round((Date.parse(b.date)-Date.parse(trip.start))/86400000)+1,start:b.start,end:b.end,zone:'UTC'}))};
}
