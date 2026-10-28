/* Real frame transport: no placeholder playback or fabricated activity. */
const panel = document.querySelector('.desk-panel');
const viewer = document.createElement('section');
viewer.id = 'vm-view';
viewer.innerHTML = `<div class="vm-heading"><div><h2>The agent’s second desktop.</h2><p id="vm-status">Connecting to the worker gateway…</p></div><button id="stop-agent" class="secondary" disabled>Stop agent</button></div><div class="vm-screen"><img id="vm-frame" alt="Live browser viewport from Iris’s isolated Linux container" hidden><div id="vm-empty"><span>◈</span><h3>No browser connected yet.</h3><p>Start the isolated worker to see its actual session here.</p></div></div><div class="vm-caption"><span id="vm-freshness">No frames received</span><button id="toggle-manual" class="text-button">Open manual test desks</button></div><ol id="vm-events" aria-label="Agent execution events"></ol>`;
panel.querySelector('.section-top').after(viewer);
panel.querySelector('.section-top .pill').textContent = 'Disconnected';
document.querySelector('#toggle-manual').onclick = () => {
  const open = panel.classList.toggle('manual-open');
  document.querySelector('#toggle-manual').textContent = open ? 'Close manual test desks' : 'Open manual test desks';
};
let liveJob = null, lastFrame = null, previousState = null, displayedJob = null;
document.querySelector('#stop-agent').onclick = async () => {
  if (!liveJob) return;
  await busy(document.querySelector('#stop-agent'), async () => {
    await api(`runs/${liveJob.id}/stop`, {});
    toast('Stop requested. The permission has been revoked.');
    await pollDesktop();
  });
};
async function pollDesktop() {
  try {
    const status = await api('desktop');
    liveJob = status.job;
    window.dispatchEvent(new CustomEvent('iris:desktop',{detail:status}));
    if(liveJob && liveJob.id!==displayedJob && !permission && status.permission){
      permission=status.permission;
      renderPermission();
      displayedJob=liveJob.id;
    }
    const image = document.querySelector('#vm-frame');
    const empty = document.querySelector('#vm-empty');
    image.hidden = !status.connected;
    empty.hidden = status.connected;
    panel.querySelector('.section-top .pill').textContent = status.connected ? 'Live · Linux browser' : 'Disconnected';
    document.querySelector('#vm-freshness').textContent = status.connected ? `Frame received ${status.age_seconds}s ago · read-only view` : 'No fresh frames · worker disconnected';
    document.querySelector('#vm-status').textContent = status.connected ? (liveJob ? `${liveJob.state.toUpperCase()} · ${liveJob.detail}` : 'Connected. Lock a permission, then send it to the agent.') : 'Waiting for the isolated browser. No autonomous session is being simulated.';
    if(status.connected && lastFrame !== status.received_at){image.src=`/api/desktop/frame?t=${status.received_at}`;lastFrame=status.received_at;}
    document.querySelector('#stop-agent').disabled = !liveJob || !['queued','running'].includes(liveJob.state);
    document.querySelector('#vm-events').innerHTML = status.events.slice(0,8).map(e=>`<li><span>${esc(e.action)}</span>${esc(e.detail)}</li>`).join('');
    if(liveJob){
      document.querySelector('#run-status').textContent=`${liveJob.state.toUpperCase()} · ${liveJob.detail}`;
      const signature=liveJob.id+liveJob.state;
      if(signature!==previousState && ['complete','paused','stopped'].includes(liveJob.state)){
        await refresh();
        if(permission?.id===liveJob.permission_id){
          permission=null;
          document.querySelector('#permission-status').textContent=liveJob.state==='complete'?'Completed':'Ask again';
          document.querySelector('#permission-status').classList.remove('locked');
        }
      }
      previousState=signature;
    }
  } catch(e) {
    document.querySelector('#vm-status').textContent='Connection interrupted. Reconnecting…';
    document.querySelector('#vm-frame').hidden=true;
    document.querySelector('#vm-empty').hidden=false;
  }
}
document.querySelector('#vm-frame').onerror=()=>{document.querySelector('#vm-frame').hidden=true;lastFrame=null;};
async function followDesktop(){await pollDesktop();setTimeout(followDesktop,1000);}
followDesktop();
