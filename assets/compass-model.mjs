import {createCatalog,defaultQuery,queryKey} from './compass-fixtures.mjs';
import {publicPayload} from './connected-public.mjs';
const copy=v=>structuredClone(v);
const fail=message=>{throw Error(message);};
export const shopping=s=>copy(s.suite?.shopping?.[s.persona]||{draft:defaultQuery(),committed:null,flightFilters:{},stayFilters:{},flight:null,stay:null,saved:null});
export function home(s){
 if(!s.suite?.signedIn)return '/landing';
 const trips=Object.values(s.trips).filter(t=>Object.hasOwn(t.members,s.persona));
 const confirmed=trips.find(t=>t.id===s.suite.current?.[s.persona]&&t.selectedPackage)||trips.find(t=>t.selectedPackage);
 return confirmed?`/trip/${confirmed.id}/calendar`:shopping(s).saved?'/draft':trips.length?'/trips':'/search';
}
export function pairStatus(q,c){
 if(!q.committed||queryKey(q.draft)!==queryKey(q.committed))return 'Stale query: refresh both result lanes and context.';
 if(!q.flight||!q.stay)return 'Select a flight and a stay bundle.';
 if([q.flight,q.stay].some(x=>x.key!==queryKey(q.committed)||x.revision!==c.data.fixtureRevision))return 'Query changed: reselect valid offers in both lanes.';
 try{c.quote(q.committed,q.flight.id,q.stay.id);}catch(e){return e.message;}
 return '';
}
export function compassAction(s,p,id){
 s.suite||={signedIn:false,shopping:{},current:{}};
 if(p.op==='signin'){
  if(!['Ari','Mina','Jo','Lee'].includes(p.name))fail('Choose a listed demo persona.');
  s.persona=p.name;s.suite.signedIn=true;return home(s);
 }
 if(p.op==='signout'){s.suite.signedIn=false;return '/landing';}
 const q=shopping(s);s.suite.shopping[s.persona]=q;
 if(p.op==='draft'){q.draft=copy(p.query);return;}
 if(p.op==='filters'){if(!['flight','stay'].includes(p.lane))fail('Unknown result lane.');q[p.lane+'Filters']=copy(p.filters);return;}
 const c=createCatalog(p.catalog);
 if(p.op==='import'){
  const sample=c.data.samplePlans.find(x=>x.id===p.id);if(!sample)fail('Example unavailable.');
  if(s.creator?.draft&&!p.replace)fail('Confirm replacing your edited draft first.');
  s.creator={source:sample.source,mode:'example',owner:s.persona,reviewed:false,draft:publicPayload(sample.draft)};return;
 }
 if(p.op==='refresh'){
  c.search(q.draft);const first=!q.committed;q.committed=copy(q.draft);
  if(first){const r=c.search(q.committed);for(const [lane,list] of [['flight',r.flights],['stay',r.stays]])if(list.length)q[lane]={id:list[0].id,key:queryKey(q.committed),revision:c.data.fixtureRevision};}
  return;
 }
 if(p.op==='select'){
  if(!q.committed||queryKey(q.draft)!==queryKey(q.committed))fail('Stale query: refresh both lanes before selecting.');
  if(!['flight','stay'].includes(p.lane))fail('Unknown result lane.');
  const r=c.search(q.committed);if(!(p.lane==='flight'?r.flights:r.stays).some(f=>f.id===p.id))fail('Offer unavailable for this query.');
  q[p.lane]={id:p.id,key:queryKey(q.committed),revision:c.data.fixtureRevision};return;
 }
 if(!s.suite.signedIn)fail('Sign in to the local demo before saving or checkout.');
 const reason=pairStatus(q,c);if(reason)fail(reason);
 const quote=c.quote(q.committed,q.flight.id,q.stay.id);
 if(p.op==='save'){
  if(q.saved&&JSON.stringify(q.saved.quote)===JSON.stringify(quote))return q.saved.token;
  q.saved={status:'Draft',quote,actor:s.persona,token:id('pair')};return q.saved.token;
 }
 const saved=q.saved;if(!saved||JSON.stringify(saved.quote)!==JSON.stringify(quote))fail('Save and review the current pair first.');
 if(saved.actor!==s.persona)fail('Only the stored shopper can continue checkout.');
 if(p.op==='begin'){if(!saved.trip)saved.status='Active';return;}
 if(p.op==='confirm'){
  if(!p.acknowledged)fail('Please acknowledge that payment and booking are simulated.');
  if(saved.trip){if(s.trips[saved.trip]?.payer!==s.persona)fail('Only the current designated payer can confirm this checkout.');return saved.trip;}
  if(saved.status!=='Active')fail('Review and begin demo checkout first.');
  const trip=id('trip'),blocks=[];
  for(const seg of [...quote.flight.outbound,...quote.flight.returning])blocks.push({id:id('block'),kind:'flight',title:`${seg.origin} → ${seg.destination} · ${seg.flight}`,date:seg.date,start:seg.departure,end:seg.arrival,zone:seg.zone,anchor:'flight',detail:`Synthetic ${seg.carrier} schedule. Departure ${seg.departure}, arrival ${seg.arrival}; no reservation.`,timing:{start:'placement',end:'placement',startMeaning:'departure',endMeaning:'arrival'}});
  for(const stay of quote.stay.stays)for(const anchor of ['checkin','checkout']){
   const start=stay[anchor],n=Number(start.slice(0,2))*60+Number(start.slice(3))+15,end=String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');
   blocks.push({id:id('block'),candidate:stay.id,kind:'hotel',title:`${stay.name} · ${anchor==='checkin'?'check-in':'check-out'}`,date:stay[anchor+'Date'],start,end,zone:'America/Los_Angeles',anchor,detail:`Synthetic ${anchor} anchor at ${start}. Fifteen-minute editable planning marker, not the stay duration. ${stay.rooms} rooms; ${stay.nights} nights. ${quote.stay.cancellationPolicy}.`,timing:{start:'placement',end:'placement',startMeaning:anchor==='checkin'?'check-in':'checkout',endMeaning:'planning end'}});
  }
  const destination=c.data.supportedDestinations.find(d=>d.id===quote.query.destination).name;
  s.trips[trip]={id:trip,title:destination+' · my travel plan',destination,start:quote.query.start,end:quote.query.end,zone:'America/Los_Angeles',party:{adults:quote.query.adults,children:copy(quote.query.childAges)},blocks,shortlist:[],notes:[],history:[{text:'SIMULATED confirmation · nothing purchased',actor:s.persona,at:new Date().toISOString()}],members:{[s.persona]:'Editor'},organizer:s.persona,payer:s.persona,checkout:'Success',link:null,lastTab:'calendar',day:quote.query.start,selectedPackage:{...copy(quote),token:saved.token,status:'Confirmed · simulated only'}};
  saved.trip=trip;saved.status='Confirmed · simulated only';s.suite.current[s.persona]=trip;return trip;
 }
 fail('Unknown Compass action.');
}
