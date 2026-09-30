// Deterministic, tab-local planning. No provider or backend calls.
import {publicPayload, contributionFrom, safeLink, CALIFORNIA, validateZone, planningMetadata} from './connected-public.mjs';
// One reviewed source for the import sample and its demo public edition.
export function familySample() {
  const stop=(day,title,start,end,detail,{kind='activity',period='',suppliedStart=false,suppliedEnd=false,startMeaning='planning start',endMeaning='planning end'}={})=>({day,title,kind,start,end,zone:CALIFORNIA,detail,...(period?{period}:{}),timing:{start:suppliedStart?'supplied':'placement',end:suppliedEnd?'supplied':'placement',startMeaning,endMeaning,...(suppliedStart?{suppliedStart:start}:{}),...(suppliedEnd?{suppliedEnd:end}:{})}});
  return {title:'California family week · 6 days',destination:'California',startDate:'2026-10-05',zone:CALIFORNIA,party:{adults:3,children:[4]},demo:'imported sample',backlink:'',context:'Based on a user-provided plan; timings, travel estimates and property/flight claims are unverified. Year absent: assume 2026 (Mon Oct 5–Sat Oct 10). Total party: 3 adults + 1 child age 4, including Dallas group. California local time: America/Los_Angeles, PDT UTC−07:00 in October 2026. No bookings verified. Unspecified endpoints are editable demo placements, not confirmed schedules.',blocks:[
    stop(1,'United · SF group lands BUR','10:30','11:30','11:30 AM is the supplied ARRIVAL at BUR on United. SFO origin is assumed from the SF → request. Departure is not supplied; the calendar start is an editable placement, NOT a departure time.',{kind:'flight',suppliedEnd:true,endMeaning:'arrival'}),
    stop(1,'Chipotle → Loews Hollywood bag drop','12:30','13:30','12:30 Chipotle, then Loews Hollywood BAG DROP, not confirmed check-in. Hotel stay Mon–Wed. Directly on Hollywood Walk of Fame / TCL Chinese Theatre with Hollywood Sign views: user-provided, unverified property claims.',{suppliedStart:true}),
    stop(1,'Walk of Fame · Chinese Theatre','14:00','16:30','Afternoon Hollywood Walk of Fame and celebrity handprints at TCL Chinese Theatre. Exact times are not supplied.',{period:'Afternoon'}),
    stop(1,'Dallas group arrives BUR · dinner','18:30','20:00','Evening Dallas flight lands BUR; exact arrival and departure airport are unspecified. Quick 15 min Uber is a USER estimate, unverified. Dinner together; Dallas group is included in total 3 adults + 1 child, not extra participants.',{period:'Evening'}),
    stop(2,'Universal Studios Hollywood','09:00','17:00','Morning 10 min Uber to Universal Hollywood (USER estimate, unverified). Nintendo World coin blocks, Studio Tour, Harry Potter, Secret Life of Pets and Minion play areas. Order follows supplied plan, not verified tickets, opening times or ride availability.',{period:'Morning'}),
    stop(2,'CityWalk OR Hollywood dinner','18:00','19:30','Evening CityWalk OR Hollywood dinner; keep the alternative, no reservation supplied.',{period:'Evening'}),
    stop(3,'Loews checkout · rental → Anaheim','08:00','08:45','08:00 checkout Loews Hollywood; pick up rental and drive to Anaheim ~45 min (USER estimate). Feasibility and pickup time unverified; supplied 09:00 next stop is preserved, not silently corrected.',{kind:'hotel',suppliedStart:true,startMeaning:'checkout'}),
    stop(3,'Avengers Campus · California Adventure','09:00','13:00','09:00–13:00 Avengers Campus at Disney California Adventure: WEB SLINGERS: A Spider-Man Adventure, Spider-Man rooftop stunts and hero meet-and-greets. Admission, availability and travel feasibility are unverified.',{suppliedStart:true,suppliedEnd:true}),
    stop(3,'Drive San Diego','13:30','15:15','13:30 drive San Diego ~1.5–2 hours (USER estimate). End is a placement, not calculated or confirmed arrival. Review feasibility against 15:30 hotel check-in; do not silently correct either supplied time.',{suppliedStart:true}),
    stop(3,'Del Mar Beach Hotel check-in · sunset','15:30','19:00','15:30 check-in Del Mar Beach Hotel, beach and sunset. Stay Wed–Sat. Beachfront, real ocean surf, complimentary chairs and umbrellas are USER claims, unverified; not verified property policy or confirmed check-in.',{kind:'hotel',suppliedStart:true,startMeaning:'check-in'}),
    stop(4,'Del Mar beach · sandcastles & surf','09:00','12:00','Morning Del Mar beach: sandcastles and ocean surf. Unspecified endpoints are editable demo placements.',{period:'Morning'}),
    stop(4,'Safari Park · Africa Tram','13:00','17:00','Afternoon drive ~30 min inland to Safari Park for the Africa Tram (USER estimate, unverified). Park access, tram schedule and travel feasibility unverified.',{period:'Afternoon'}),
    stop(4,'Del Mar sunset walk · dinner','18:00','19:30','Evening return to Del Mar, sunset walk and dinner; exact times unspecified.',{period:'Evening'}),
    stop(5,'LEGOLAND · DUPLO & gentle rides','09:00','16:00','Morning ~15 min drive to LEGOLAND (USER estimate, unverified). DUPLO, gentle rides and LEGO building. Kids Free October promotion is user-provided, UNVERIFIED: check eligibility and terms; no discount calculated or promised.',{period:'Morning'}),
    stop(5,'Final beach night · patio takeout','18:00','19:30','Evening final beach night with takeout on the beachfront patio. Property access and amenities are unverified user claims.',{period:'Evening'}),
    stop(6,'Hotel checkout · coastal lunch','11:00','12:30','11:00 checkout Del Mar Beach Hotel, then coastal lunch in Del Mar Village. Lunch endpoints are not supplied.',{kind:'hotel',suppliedStart:true,startMeaning:'checkout'}),
    stop(6,'Drive SAN · rental drop','13:30','14:30','13:30 drive ~30 min to SAN (USER estimate), rental drop. End includes editable buffer, not a confirmed rental return or airport-arrival time.',{suppliedStart:true}),
    stop(6,'United 2117 · SAN → SFO','15:56','17:38','15:56 United flight #2117 SAN → SFO 17:38. Both endpoints supplied by user, neither reservation nor flight verified.',{kind:'flight',suppliedStart:true,suppliedEnd:true,startMeaning:'departure',endMeaning:'arrival'})
  ]};
}

import {compassAction} from './compass-model.mjs';
export const KEY = 'travelos.connected.v1';
export const airports = {SFO:'San Francisco (SFO)',BUR:'Burbank (BUR)',SAN:'San Diego (SAN)',LHR:'London · Heathrow (LHR)', GRX:'Granada · Federico García Lorca (GRX)', LIS:'Lisbon · Humberto Delgado (LIS)', JFK:'New York · John F. Kennedy (JFK)'};
export const defaults = () => ({destination:'Granada',origin:'LHR',airport:'GRX',start:'2026-10-12',end:'2026-10-15',adults:2,children:0,ages:'',rooms:1,flights:true,hotels:true,cabin:'Any',maxPrice:500,family:false,pet:false});
export const familyQuery = () => ({...defaults(),destination:'California',origin:'SFO',airport:'BUR',start:'2026-10-05',end:'2026-10-10',adults:3,children:1,ages:'4',family:true});
export const fixtures = ['Granada','Lisbon'].flatMap((destination,i) => [
  {id:`f${i}a`,kind:'flight',title:i?'Lisbon light hop':'Sierra morning hop',destination,origin:'LHR',airport:i?'LIS':'GRX',price:145,cabin:'Economy',capacity:6,start:'09:00',end:'12:00'},
  {id:`f${i}b`,kind:'flight',title:'A little more legroom',destination,origin:'LHR',airport:i?'LIS':'GRX',price:320,cabin:'Business',capacity:4,start:'14:00',end:'17:00'},
  {id:`h${i}a`,kind:'hotel',title:i?'Tile & Tide House':'Patio & Orange House',destination,price:98,capacity:2,family:false,pet:'Unknown',start:'15:00',end:'11:00'},
  {id:`h${i}b`,kind:'hotel',title:i?'River Garden Rooms':'Little Garden Rooms',destination,price:165,capacity:4,family:true,pet:false,start:'15:00',end:'11:00'}
 ]).concat([
  {id:'fca-out',kind:'flight',title:'United · SF group to BUR',destination:'California',origin:'SFO',airport:'BUR',price:185,cabin:'Economy',capacity:4,start:null,end:'11:30',date:'2026-10-05',zone:CALIFORNIA,planningStart:'10:30',detail:'User-supplied 11:30 arrival; SFO origin assumed from SF. Departure not supplied. Price, cabin and capacity are synthetic fixture values, not confirmed fares.',timing:{start:'placement',end:'supplied',startMeaning:'planning start',endMeaning:'arrival',suppliedEnd:'11:30'}},
  {id:'fca-back',kind:'flight',title:'United 2117 · SAN → SFO',destination:'California',origin:'SAN',airport:'SFO',price:210,cabin:'Economy',capacity:4,start:'15:56',end:'17:38',date:'2026-10-10',zone:CALIFORNIA,detail:'User-supplied flight and endpoints; unverified. Price, cabin and capacity are synthetic fixture values.',timing:{start:'supplied',end:'supplied',startMeaning:'departure',endMeaning:'arrival',suppliedStart:'15:56',suppliedEnd:'17:38'}},
  {id:'hca-loews',kind:'hotel',title:'Loews Hollywood',destination:'California',location:'Hollywood',price:225,capacity:4,family:true,pet:'Unknown',start:'15:00',end:'11:00',zone:CALIFORNIA,stayStart:'2026-10-05',stayEnd:'2026-10-07',detail:'User proposes Mon–Wed. Walk of Fame / TCL Chinese Theatre and Hollywood Sign views are user claims, unverified. Monday 12:30 is bag drop, not check-in. Price/capacity are synthetic. Check-in/out times below are editable demo defaults, not property policy.'},
  {id:'hca-delmar',kind:'hotel',title:'Del Mar Beach Hotel',destination:'California',location:'Del Mar',price:195,capacity:4,family:true,pet:'Unknown',start:'15:30',end:'11:00',zone:CALIFORNIA,stayStart:'2026-10-07',stayEnd:'2026-10-10',detail:'User proposes Wed–Sat. Beachfront, real ocean surf, complimentary chairs and umbrellas are user claims, unverified. Synthetic price/capacity; no verified policies or reservation. Calendar defaults are editable.'}
]);
export const clone = value => structuredClone(value);
export const publicPreview = c => ({id:c.id,revision:c.revision||0,payload:publicPayload(c.draft)});
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
  validateZone(b.zone,b.date);
  if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(b.start) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(b.end) || b.end<=b.start) fail('End must follow start on the same day; split overnight activities manually.');
}
function seedDemos(state) {
  if(state.demoSeed===1)return state;
  const authored={title:'Del Mar beach morning · 1 day',destination:'Del Mar',startDate:'2026-10-08',zone:CALIFORNIA,demo:'authored sample',backlink:'',context:'Synthetic authored example, not a traveler publication. Access and conditions unverified.',blocks:[{title:'Sandcastles and a coastal stroll',kind:'activity',day:1,start:'09:00',end:'11:00',zone:CALIFORNIA,period:'Morning',detail:'A relaxed beach morning with time left free for lunch. Both times are editable demo placements.',timing:{start:'placement',end:'placement'}}]};
  for(const [id,draft] of [['demo-california-family',familySample()],['demo-del-mar',authored]]){
    if(!Object.hasOwn(state.publications,id)){const clean=publicPayload(draft);state.publications[id]={id,owner:'Demo fixture',draft:clone(clean),versions:[{...clean,version:1,at:'2026-09-27T00:00:00Z'}]};}
  }
  state.demoSeed=1;return state;
}
const fresh = () => seedDemos({schema:1,seq:0,persona:'Ari',trips:{},research:{},drafts:{},publications:{},creator:null});
const own = (map,id) => map && Object.hasOwn(map,id) ? map[id] : null;
const object = value => !!value && typeof value==='object' && !Array.isArray(value);
const entity = (map,id) => {const value=own(map,id);return object(value)&&value.id===id?value:null;};
export function tripById(s,id) {
  const t=entity(s.trips,id);
  return t&&object(t.members)&&['blocks','shortlist','notes','history'].every(k=>Array.isArray(t[k]))&&['title','destination','start','end'].every(k=>typeof t[k]==='string')?t:null;
}
export function publicationById(s,id) {
  const c=entity(s.publications,id),payload=v=>object(v)&&typeof v.title==='string'&&typeof v.destination==='string'&&Array.isArray(v.blocks);
  return c&&typeof c.owner==='string'&&payload(c.draft)&&Array.isArray(c.versions)&&c.versions.every(v=>payload(v)&&Number.isInteger(v.version)&&typeof v.at==='string')?c:null;
}
export function role(trip, persona) {const value=own(trip?.members,persona);return ['Viewer','Commenter','Editor'].includes(value)?value:null;}
export function createStore(storage) {
  let state=fresh(), warning='';
  try {
    const raw=storage.getItem(KEY);
    if(raw) {const value=JSON.parse(raw);if(value.schema!==1 || !value.trips || !value.research || !value.publications) throw Error();state=value;}
  } catch {warning='Storage unavailable or corrupt. Changes are only kept until reload; reset to retry.';}
  seedDemos(state);
  const persist = () => {try {if(warning) return;storage.setItem(KEY,JSON.stringify(state));} catch {warning='Storage unavailable. Changes are only kept until reload.';}};
  persist();
  return {
    get state(){return clone(state);}, get warning(){return warning;},
    shared(trip,token) {const t=tripById(state,trip);return t?.link && typeof token==='string' && t.link.token===token && (!t.link.expires || t.link.expires>Date.now()) ? clone(t) : null;},
    act(type,p={}) {
      const s=clone(state), id=prefix=>`${prefix}-${++s.seq}`;
      const t=p.trip?tripById(s,p.trip):null;
      if(p.trip && !t) fail('Trip no longer available.');
      const person=s.persona;
      const editor=()=>{if(role(t,person)!=='Editor') fail('Editor access required.');};
      const organizer=()=>{if(t.organizer!==person) fail('Only the organizer can do this.');};
      const record=label=>t.history.unshift({text:label,actor:person,at:new Date().toISOString()});
      const checkpoint=()=>{t.undo={blocks:clone(t.blocks),shortlist:clone(t.shortlist),start:t.start,end:t.end,destination:t.destination};};
      let result;
      switch(type) {
        case 'compass':result=compassAction(s,p,id);break;
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
        case 'creatorStart':
          if(s.creator?.draft&&!p.replace) fail('Confirm replacing the edited draft first.');
          if(!['family','blank'].includes(p.mode)) fail('Choose a supported authoring mode.');
          s.creator={source:'',mode:p.mode,owner:person,reviewed:false,draft:p.mode==='family'?publicPayload(familySample()):{title:'',destination:'',zone:'UTC',backlink:'',blocks:[],demo:'authored sample'}};break;
        case 'source':
          if(s.creator?.source!==p.source) s.creator={draft:null,owner:person,...s.creator,source:p.source,reviewed:false,outdated:!!s.creator?.draft};break;
        case 'extract': {
          if(s.creator?.draft&&!p.replace) fail('Confirm replacing the edited synthetic example first.');
          const source=safeLink(p.source);if(!source) fail('Enter a source HTTPS URL.');
          s.creator={source,owner:person,reviewed:false,draft:{title:'Lisbon, at walking pace',destination:'Lisbon',backlink:'',blocks:[{title:'Garden wander',kind:'activity',day:1,start:'10:00',end:'11:00',zone:'UTC'},{title:'Market pause',kind:'activity',day:1,start:'12:00',end:'13:00',zone:'UTC'},{title:'Riverside ramble',kind:'activity',day:2,start:'16:00',end:'17:30',zone:'UTC'}]}};break;
        }
        case 'creatorReview':
          if(!s.creator?.draft || s.creator.owner!==person) fail('Generate and review your synthetic example first.');
          if(s.creator.outdated&&p.reviewed) fail('Source changed. Confirm replacement before reviewing a fresh example.');
          s.creator.draft=publicPayload({...p.draft,backlink:p.backlink?safeLink(s.creator.source):''},{draft:!p.reviewed});s.creator.reviewed=!!p.reviewed;s.creator.published=null;break;
        case 'creatorPublish': {
          const c=s.creator;if(!c?.reviewed || c.outdated || c.owner!==person) fail('Review your exact stops for the current source before publishing.');
          if(c.published){result=c.published;break;}
          const clean=publicPayload(c.draft);result=id('public');s.publications[result]={id:result,owner:person,draft:clone(clean),versions:[{...clean,version:1,at:new Date().toISOString()}]};c.published=result;break;
        }
        case 'contribute':
          editor();result=id('public');s.publications[result]={id:result,owner:person,draft:contributionFrom(t),versions:[]};break;
        case 'publicDraft': {
          const c=publicationById(s,p.id);if(!c || c.owner!==person) fail('Only the local contributor may edit this contribution.');
          const draft=publicPayload(p.draft);
          if(JSON.stringify(draft)!==JSON.stringify(c.draft))c.revision=(c.revision||0)+1;
          c.draft=draft;break;
        }
        case 'publish': {
          const c=publicationById(s,p.id);if(!c || c.owner!==person) fail('Only the local contributor may publish.');
          if(JSON.stringify(p.approval)!==JSON.stringify(publicPreview(c))) fail('Review the exact public preview again before publishing.');
          const clean=publicPayload(c.draft), previous=c.versions.at(-1);
          if(previous && JSON.stringify(publicPayload(previous))===JSON.stringify(clean)) break;
          c.versions.push({...clean,version:c.versions.length+1,at:new Date().toISOString()});break;
        }
        case 'fork': {
          const c=publicationById(s,p.id), v=c?.versions.find(x=>x.version===+p.version);
          if(!v) fail('Published version unavailable.');
          if(!dateOK(p.start)) fail('Choose a valid start date for the fork.');
          const clean=publicPayload(v);result=id('trip');
          for(const b of clean.blocks)validateZone(b.zone,shiftDate(p.start,b.day-1));
          s.trips[result]={...planningMetadata({...clean,startDate:p.start}),id:result,title:clean.title,destination:clean.destination,start:p.start,end:shiftDate(p.start,Math.max(...clean.blocks.map(x=>x.day))-1),shortlist:[],blocks:clean.blocks.map(({day,...b})=>({...b,id:id('block'),date:shiftDate(p.start,day-1)})),notes:[],history:[],members:{[person]:'Editor'},organizer:person,payer:person,checkout:'Ready',link:null,lastTab:'calendar',day:p.start,provenance:{id:p.id,version:+p.version,backlink:clean.backlink}};
          break;
        }
        case 'createTrip': {
          search(p.query); dates(p.query.start,p.query.end);
          if(!p.title?.trim()) fail('Give the trip a title.');
          result=id('trip');
          s.research[`${person}:${result}`]={draft:clone(p.query),committed:clone(p.query)};
          s.trips[result]={...(p.query.destination==='California'?{zone:CALIFORNIA,party:{adults:+p.query.adults,children:String(p.query.ages).split(',').filter(Boolean).map(Number)}}:{}),id:result,title:p.title.trim(),destination:p.query.destination||'Flexible',start:p.query.start,end:p.query.end,shortlist:[],blocks:[],notes:[],history:[],members:{[person]:'Editor'},organizer:person,payer:person,checkout:'Ready',link:null,lastTab:'research',day:p.query.start};
          break;
        }
        case 'research': s.research[`${person}:${p.scope||'search'}`]=clone(p.value);break;
        case 'draft': s.drafts[`${person}:${p.scope}`]=p.text;break;
        case 'visit': if(!role(t,person)) fail('No access to this trip.');t.lastTab=p.tab;t.day=p.day||t.day;break;
        case 'saveCandidate': {
          editor(); const f=fixtures.find(x=>x.id===p.candidate);if(!f) fail('Candidate unavailable.');
          search(p.query);
          if(!t.shortlist.some(x=>x.id===p.candidate)) {checkpoint();t.shortlist.push({id:p.candidate,query:clone(f.stayStart?{...p.query,start:f.stayStart,end:f.stayEnd}:p.query)});record('Added candidate to shortlist');}
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
          if(!c.query.start || !c.query.end) fail('Undated candidate: explicitly assign dates in this candidate drawer first.');
          if(f.date && (c.query.start>f.date||c.query.end<f.date))fail('This supplied flight is only placed on its stated date. Assign dates that include '+f.date);
          const same=t.blocks.filter(x=>x.kind===f.kind);
          if(same.length && !['replace','both'].includes(p.mode)) fail('Choose Replace or Keep both explicitly.');
          checkpoint();if(p.mode==='replace') t.blocks=t.blocks.filter(x=>x.kind!==f.kind);
          const block=(title,date,start,end,anchor)=>({id:id('block'),kind:f.kind,title,date,start,end,zone:f.zone||'UTC',candidate:c.id,destination:f.destination,anchor,...(f.detail?{detail:f.detail}:{}),...(f.timing?{timing:clone(f.timing)}:f.zone===CALIFORNIA?{timing:{start:'placement',end:'placement'}}:{})});
          if(f.kind==='flight') t.blocks.push(block(f.title,f.date||c.query.start,f.start||f.planningStart,f.end,'flight'));
          else t.blocks.push(block(`${f.title} · check-in`,c.query.start,f.start,clock(minutes(f.start)+30),'checkin'),block(`${f.title} · check-out`,c.query.end,f.end,clock(minutes(f.end)+30),'checkout'));
          for(const b of t.blocks)validateEvent(b);
          record('Chose arrangement · planned, not booked');break;
        }
        case 'unschedule':editor();checkpoint();t.blocks=t.blocks.filter(x=>x.candidate!==p.candidate);record('Unscheduled linked arrangement');break;
        case 'applyResearch':editor();search(p.query);dates(p.query.start,p.query.end);checkpoint();Object.assign(t,{start:p.query.start,end:p.query.end,destination:p.query.destination||'Flexible'});record('Applied research dates; existing blocks unchanged');break;
        case 'event': {
          editor();const old=p.id?t.blocks.find(x=>x.id===p.id):null;
          if(p.id&&!old) fail('Activity no longer available.');
          const b={...old,id:old?.id||id('block'),kind:old?.kind||'activity',title:p.title?.trim(),date:p.date,start:p.start,end:p.end,zone:p.zone};
          if(old&&old.zone!==b.zone)fail('Planning zone cannot change without an explicit conversion; keep the original zone.');
          if(!old&&t.zone&&t.zone!==b.zone)fail('Planning zone must match this plan; no automatic conversion.');
          if(old?.timing)b.timing={...old.timing,...Object.fromEntries(['start','end'].filter(edge=>old[edge]!==b[edge]||old.date!==b.date).map(edge=>[edge,'edited']))};
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
    (!f.date || !!q.start && q.start<=f.date && q.end>=f.date) &&
    (!f.stayStart || !!q.start && q.start<=f.stayStart && q.end>=f.stayEnd) &&
    (f.kind === 'flight' ? q.flights && (!q.origin || f.origin === q.origin) && (!q.airport || f.airport === q.airport) && (q.cabin === 'Any' || f.cabin === q.cabin) && +q.adults + +q.children <= f.capacity :
      q.hotels && f.price <= +q.maxPrice && +q.adults + +q.children <= f.capacity * +q.rooms && (!q.family || f.family === true) && (!q.pet || f.pet === true)));
}
