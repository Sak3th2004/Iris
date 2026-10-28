/* Product guidance is derived from real permission/job state, never a timed demo. */
const guide=document.querySelector('#quick-guide');
document.querySelector('#help-toggle').onclick=()=>{guide.hidden=!guide.hidden;};
document.querySelector('#show-readiness').onclick=()=>document.querySelector('#readiness-dialog').showModal();
document.querySelector('#close-readiness').onclick=()=>document.querySelector('#readiness-dialog').close();
const banner=document.createElement('div');banner.className='run-banner';banner.setAttribute('role','status');banner.innerHTML='<span class="activity-dot"></span><div id="activity-message">Connecting to the isolated browser…</div>';
document.querySelector('.vm-screen').before(banner);
const buttons=document.createElement('div');buttons.className='view-buttons';
const stop=document.querySelector('#stop-agent');stop.before(buttons);buttons.append(stop);
const expand=document.createElement('button');expand.className='secondary';expand.textContent='Expand ↗';expand.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await panel.requestFullscreen();}catch{toast('Full-screen view is unavailable in this browser.');}};buttons.prepend(expand);
const hide=document.createElement('button');hide.className='text-button';hide.textContent='Hide live view';hide.onclick=()=>{const screen=document.querySelector('.vm-screen');screen.hidden=!screen.hidden;hide.textContent=screen.hidden?'Show live view':'Hide live view';};document.querySelector('.vm-caption').prepend(hide);
let desktopState=null,signature='',drafting=false;
function markDraft(){
  drafting=true;
  if(permission && !['running','queued'].includes(desktopState?.job?.state)){
    permission=null;
    document.querySelector('#permission-status').textContent='Draft changed';
    document.querySelector('#permission-status').classList.remove('locked');
    const card=document.querySelector('#permission-card');card.className='empty-permission';card.innerHTML='<h3>Review the updated instruction.</h3><p>The start button stays disabled until a new permission is locked.</p>';
  }
  updateExperience();
}
document.querySelector('#sentence').addEventListener('input',markDraft);
window.addEventListener('iris:desktop',e=>{desktopState=e.detail;updateExperience();});
window.addEventListener('iris:permission',()=>{drafting=false;updateExperience();});
window.addEventListener('iris:state',()=>{renderSuggestions();updateExperience();});
function renderSuggestions(){
  if(!state)return;
  const rows=['booking','order'].map(type=>state.records.find(r=>r.resource_type===type)).filter(Boolean);
  const next=JSON.stringify(rows);if(signature===next)return;signature=next;
  const container=document.querySelector('#suggestions');container.replaceChildren();
  rows.forEach(row=>{const day=row.fields.day==='Thursday'?'Friday':'Thursday';const quantity=row.fields.quantity===4?2:4;const sentence=row.resource_type==='booking'?`Move ${row.fields.name}'s booking to ${day}. Keep the price and all other records unchanged.`:`Set ${row.fields.name}'s order quantity to ${quantity}. Keep the price and all other records unchanged.`;const button=document.createElement('button');button.type='button';button.textContent=row.resource_type==='booking'?`Try: ${row.fields.name} → ${day}`:`Try: ${row.fields.name} → ${quantity} items`;button.onclick=()=>{document.querySelector('#sentence').value=sentence;markDraft();document.querySelector('#sentence').focus();};container.append(button);});
}
function updateExperience(){
  const job=desktopState?.job;
  const active=job&&['running','queued'].includes(job.state);
  const freshPermission=permission&&!(job?.permission_id===permission.id&&['running','queued','complete','stopped','paused'].includes(job.state));
  panel.classList.toggle('is-working',Boolean(active&&desktopState.connected));
  const run=document.querySelector('#run-agent');
  run.disabled=!freshPermission||!desktopState?.connected||Boolean(active);
  run.textContent=active?'Agent is working…':freshPermission?'Start agent ↗':'Review a permission to start';
  let phase='idle',text='<strong>Ready when you are.</strong> Describe a change on the left, then review the permission.';
  let stage='describe';
  if(!desktopState?.connected){phase='offline';text='<strong>Browser disconnected.</strong> Start Docker and run docker compose up -d. Iris will reconnect here.';}
  if(active){phase=job.state;stage='work';const latest=desktopState.events?.[0];text=`<strong>${latest?.action==='reviewing'?'Checking before saving.':'Iris is working. You can step away.'}</strong> ${esc(latest?.detail||'Waiting for the browser worker.')} Keep Docker running; you can close this page.`;if(!desktopState.connected)text='<strong>Connection interrupted.</strong> The last task status is retained. Wait for reconnection or stop the task.';}
  else if(freshPermission){phase='ready';stage='permission';text='<strong>Your boundary is locked.</strong> Review the exact change, then choose Start agent. Nothing has been saved yet.';}
  else if(job?.state==='complete'&&!drafting){phase='complete';stage='receipt';text='<strong>Finished. The database confirms it.</strong> Your receipt below shows the saved values. Describe another change whenever you’re ready.';}
  else if(job&&['paused','stopped'].includes(job.state)&&!drafting){phase=job.state;text=`<strong>${job.state==='stopped'?'Stopped.':'Your attention is needed.'}</strong> ${esc(job.detail)} Review the receipt before creating a new permission.`;}
  banner.dataset.phase=phase;document.querySelector('#activity-message').innerHTML=text;
  ['describe','permission','work','receipt'].forEach(s=>{const item=document.querySelector('#stage-'+s);item.classList.toggle('current',s===stage);if(s===stage)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');});
  if(!active){document.querySelector('#run-status').textContent=freshPermission?'The agent will work in its own browser. You can close this page after starting.':job?.state==='complete'&&!drafting?'Previous task finished. Enter another instruction to begin.':'Describe → review permission → start agent.';}
}
renderSuggestions();updateExperience();
