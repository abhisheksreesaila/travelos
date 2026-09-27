// Deterministic, tab-local planning. No provider or backend calls.
import {publicPayload, contributionFrom, safeLink} from './connected-public.mjs';
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
export const minutes = value => {const [h,m]=value.split(':').map(Number);return h*60+m;};
export const clock = value => `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
export const shiftDate = (date, days) => new Date(Date.parse(date)+days*86400000).toISOString().slice(0,10);
export function warnings(trip) {
  const out=[];
  for(const [i,b] of trip.blocks.entries()) {
    if(b.date<trip.start || b.date>trip.end) out.push(`${b.title}: outside plan dates.`);
    if(b.destination && b.destination!==trip.destination) out.push(`${b.title}: different destination.`);
    if(trip.blocks.slice(i+1).some(c=>c.date===b.date && c.start<b.end && b.start<c.end)) out.push(`${b.title}: overlap — nothing was rescheduled.`);
  }
  return out;
}
function validateEvent(b) {
  if(!b.title?.trim()) fail('Give the activity a title.');
  if(!dateOK(b.date)) fail('Choose a valid date.');
  if(b.zone!=='UTC') fail('This sample supports UTC planning times only; local/DST conversions are unsupported.');
  if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(b.start) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(b.end) || b.end<=b.start) fail('End must follow start on the same day; split overnight activities manually.');
}
const fresh = () => ({schema:1,seq:0,persona:'Ari',trips:{},research:{},drafts:{},publications:{},creator:null});
export function role(trip, persona) {return trip?.members[persona] || null;}
export function createStore(storage) {
  let state=fresh(), warning='';
  try {
    const raw=storage.getItem(KEY);
    if(raw) {const value=JSON.parse(raw);if(value.schema!==1 || !value.trips || !value.research || !value.publications) throw Error();state=value;}
  } catch {warning='Storage unavailable or corrupt. Changes are only kept until reload; reset to retry.';}
  const persist = () => {try {if(warning) return;storage.setItem(KEY,JSON.stringify(state));} catch {warning='Storage unavailable. Changes are only kept until reload.';}};
  return {
    get state(){return clone(state);}, get warning(){return warning;},
    shared(trip,token) {const t=state.trips[trip];return t?.link?.token===token && (!t.link.expires || t.link.expires>Date.now()) ? clone(t) : null;},
    act(type,p={}) {
      const s=clone(state), id=prefix=>`${prefix}-${++s.seq}`;
      const t=p.trip?s.trips[p.trip]:null;
      if(p.trip && !t) fail('Trip no longer available.');
      const person=s.persona;
      const editor=()=>{if(role(t,person)!=='Editor') fail('Editor access required.');};
      const organizer=()=>{if(t.organizer!==person) fail('Only the organizer can do this.');};
      const record=label=>t.history.unshift({text:label,actor:person,at:new Date().toISOString()});
      const checkpoint=()=>{t.undo={blocks:clone(t.blocks),shortlist:clone(t.shortlist),start:t.start,end:t.end,destination:t.destination};};
      let result;
      switch(type) {
        case 'reset':
          try {storage.removeItem(KEY);warning='';} catch {warning='Storage unavailable. Changes are only kept until reload.';}
          state=fresh();persist();return;
        case 'persona':if(!p.name?.trim()) fail('Choose a demo persona.');s.persona=p.name.trim();break;
        case 'invite':
          organizer();if(!p.name?.trim() || !['Viewer','Commenter','Editor'].includes(p.role)) fail('Choose a named recipient and valid role.');
          if(p.name.trim()===t.organizer) fail('Organizer remains Editor in this sample.');
          t.members[p.name.trim()]=p.role;record('Created demo invitation · no email sent');break;
        case 'link':
          organizer();if(!['Viewer','Commenter','Editor'].includes(p.role)) fail('Choose a valid link role.');
          result=id('link');t.link={token:result,role:p.role,expires:p.expired?Date.now()-1:null};record('Changed local link policy');break;
        case 'revoke':organizer();t.link=null;record('Revoked local link');break;
        case 'nominate':
          organizer();if(['Active','Unresolved'].includes(t.checkout)) fail('Active or unresolved checkout blocks reassignment.');
          if(!t.members[p.name]) fail('Payer must be a named participant.');
          t.payer=p.name;t.checkout='Ready';record('Transferred designated payer authority');break;
        case 'checkout': {
          if(person!==t.payer) fail('Only the designated payer can operate checkout.');
          const transitions={Ready:['Active'],Active:['Success','Ready','Unresolved'],Unresolved:['Ready','Success'],Success:[]};
          if(!transitions[t.checkout].includes(p.next)) fail('Active or unresolved checkout: reconcile explicitly; no duplicate attempt.');
          t.checkout=p.next;record(`Checkout ${p.next} · SIMULATION, no charge`);break;
        }
        case 'source':
          if(s.creator?.source!==p.source) s.creator={source:p.source,reviewed:false,draft:null,owner:person};break;
        case 'extract': {
          const source=safeLink(p.source);if(!source) fail('Enter a source HTTPS URL.');
          s.creator={source,owner:person,reviewed:false,draft:{title:'Lisbon, at walking pace',destination:'Lisbon',backlink:'',blocks:[{title:'Garden wander',kind:'activity',day:1,start:'10:00',end:'11:00',zone:'UTC'},{title:'Market pause',kind:'activity',day:1,start:'12:00',end:'13:00',zone:'UTC'},{title:'Riverside ramble',kind:'activity',day:2,start:'16:00',end:'17:30',zone:'UTC'}]}};break;
        }
        case 'creatorReview':
          if(!s.creator?.draft || s.creator.owner!==person) fail('Generate and review your synthetic example first.');
          s.creator.draft=publicPayload({...p.draft,backlink:p.backlink?safeLink(s.creator.source):''});s.creator.reviewed=!!p.reviewed;s.creator.published=null;break;
        case 'creatorPublish': {
          const c=s.creator;if(!c?.reviewed || c.owner!==person) fail('Review your exact stops before publishing.');
          if(c.published){result=c.published;break;}
          const clean=publicPayload(c.draft);result=id('public');s.publications[result]={id:result,owner:person,draft:clone(clean),versions:[{...clean,version:1,at:new Date().toISOString()}]};c.published=result;break;
        }
        case 'contribute':
          editor();result=id('public');s.publications[result]={id:result,owner:person,draft:contributionFrom(t),versions:[]};break;
        case 'publicDraft': {
          const c=s.publications[p.id];if(!c || c.owner!==person) fail('Only the local contributor may edit this contribution.');
          c.draft=publicPayload(p.draft);break;
        }
        case 'publish': {
          const c=s.publications[p.id];if(!c || c.owner!==person) fail('Only the local contributor may publish.');
          if(!p.reviewed) fail('Review the exact public preview before publishing.');
          const clean=publicPayload(c.draft), previous=c.versions.at(-1);
          if(previous && JSON.stringify(publicPayload(previous))===JSON.stringify(clean)) break;
          c.versions.push({...clean,version:c.versions.length+1,at:new Date().toISOString()});break;
        }
        case 'fork': {
          const c=s.publications[p.id], v=c?.versions.find(x=>x.version===+p.version);
          if(!v) fail('Published version unavailable.');
          if(!dateOK(p.start)) fail('Choose a valid start date for the fork.');
          const clean=publicPayload(v);result=id('trip');
          s.trips[result]={id:result,title:clean.title,destination:clean.destination,start:p.start,end:shiftDate(p.start,Math.max(...clean.blocks.map(x=>x.day))-1),shortlist:[],blocks:clean.blocks.map(b=>({id:id('block'),title:b.title,kind:b.kind,date:shiftDate(p.start,b.day-1),start:b.start,end:b.end,zone:b.zone})),notes:[],history:[],members:{[person]:'Editor'},organizer:person,payer:person,checkout:'Ready',link:null,lastTab:'calendar',day:p.start,provenance:{id:p.id,version:+p.version,backlink:clean.backlink}};
          break;
        }
        case 'createTrip': {
          search(p.query); dates(p.query.start,p.query.end);
          if(!p.title?.trim()) fail('Give the trip a title.');
          result=id('trip');
          s.trips[result]={id:result,title:p.title.trim(),destination:p.query.destination||'Flexible',start:p.query.start,end:p.query.end,shortlist:[],blocks:[],notes:[],history:[],members:{[person]:'Editor'},organizer:person,payer:person,checkout:'Ready',link:null,lastTab:'research',day:p.query.start};
          break;
        }
        case 'research': s.research[`${person}:${p.scope||'search'}`]=clone(p.value);break;
        case 'draft': s.drafts[`${person}:${p.scope}`]=p.text;break;
        case 'visit': if(!role(t,person)) fail('No access to this trip.');t.lastTab=p.tab;t.day=p.day||t.day;break;
        case 'saveCandidate': {
          editor(); const f=fixtures.find(x=>x.id===p.candidate);if(!f) fail('Candidate unavailable.');
          search(p.query);
          if(!t.shortlist.some(x=>x.id===p.candidate)) {checkpoint();t.shortlist.push({id:p.candidate,query:clone(p.query)});record('Added candidate to shortlist');}
          break;
        }
        case 'dateCandidate': {
          editor();dates(p.start,p.end);const c=t.shortlist.find(x=>x.id===p.candidate);
          if(!c) fail('Candidate unavailable.');
          if(t.blocks.some(b=>b.candidate===c.id)) fail('Unschedule before changing candidate dates; chosen blocks never move silently.');
          checkpoint();c.query.start=p.start;c.query.end=p.end;record('Explicitly dated shortlisted candidate');break;
        }
        case 'choose': {
          editor();const c=t.shortlist.find(x=>x.id===p.candidate), f=fixtures.find(x=>x.id===p.candidate);
          if(!c || !f) fail('Candidate unavailable.');
          if(t.blocks.some(x=>x.candidate===c.id)) break;
          if(!c.query.start || !c.query.end) fail('Undated candidate: assign dates in research and save it again first.');
          const same=t.blocks.filter(x=>x.kind===f.kind);
          if(same.length && !['replace','both'].includes(p.mode)) fail('Choose Replace or Keep both explicitly.');
          checkpoint();if(p.mode==='replace') t.blocks=t.blocks.filter(x=>x.kind!==f.kind);
          const block=(title,date,start,end,anchor)=>({id:id('block'),kind:f.kind,title,date,start,end,zone:'UTC',candidate:c.id,destination:f.destination,anchor});
          if(f.kind==='flight') t.blocks.push(block(f.title,c.query.start,f.start,f.end,'flight'));
          else t.blocks.push(block(`${f.title} · check-in`,c.query.start,'15:00','15:30','checkin'),block(`${f.title} · check-out`,c.query.end,'11:00','11:30','checkout'));
          record('Chose arrangement · planned, not booked');break;
        }
        case 'unschedule':editor();checkpoint();t.blocks=t.blocks.filter(x=>x.candidate!==p.candidate);record('Unscheduled linked arrangement');break;
        case 'applyResearch':editor();search(p.query);dates(p.query.start,p.query.end);checkpoint();Object.assign(t,{start:p.query.start,end:p.query.end,destination:p.query.destination||'Flexible'});record('Applied research dates; existing blocks unchanged');break;
        case 'event': {
          editor();const old=p.id?t.blocks.find(x=>x.id===p.id):null;
          if(p.id&&!old) fail('Activity no longer available.');
          const b={...old,id:old?.id||id('block'),kind:old?.kind||'activity',title:p.title?.trim(),date:p.date,start:p.start,end:p.end,zone:p.zone};
          validateEvent(b);
          if(b.kind==='hotel' && b.candidate) {
            const other=t.blocks.find(x=>x.candidate===b.candidate&&x.id!==b.id);
            if(other && (b.anchor==='checkin' ? b.date+b.start>=other.date+other.start : b.date+b.start<=other.date+other.start)) fail('Hotel check-out must follow linked check-in.');
          }
          checkpoint();if(old) t.blocks[t.blocks.indexOf(old)]=b;else t.blocks.push(b);
          record(`${old?'Updated':'Added'} ${b.title} · planning only`);result=b.id;break;
        }
        case 'deleteEvent': {
          editor();const b=t.blocks.find(x=>x.id===p.id);if(!b) fail('Activity no longer available.');
          checkpoint();t.blocks=t.blocks.filter(x=>b.kind==='hotel'&&b.candidate?x.candidate!==b.candidate:x.id!==b.id);record('Removed activity (linked hotel anchors together)');break;
        }
        case 'undo':editor();if(!t.undo) fail('Nothing to undo.');Object.assign(t,t.undo);t.undo=null;record('Undid last itinerary change');break;
        case 'note': {
          if(!['Editor','Commenter'].includes(role(t,person))) fail('Commenter or Editor access required.');
          if(!p.text?.trim()) fail('Write a note first.');
          t.notes.push({scope:p.scope||'trip',text:p.text.trim(),actor:person});s.drafts[`${person}:${t.id}:${p.scope||'trip'}`]='';record('Added local note · not sent');break;
        }
        default: fail(`Unsupported action: ${type}`);
      }
      state=s;persist();return result;
    }
  };
}
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
