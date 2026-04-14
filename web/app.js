const STORAGE_KEYS={workspace:'coachGarmin.workspace',provider:'coachGarmin.provider',baseUrl:'coachGarmin.baseUrl',apiKey:'coachGarmin.apiKey',sourcePath:'coachGarmin.sourcePath',goalText:'coachGarmin.goalText',theme:'coachGarmin.theme',activeSection:'coachGarmin.activeSection',showTerminalMenu:'coachGarmin.showTerminalMenu',startSection:'coachGarmin.startSection',terminalLevels:'coachGarmin.terminalLevels',terminalLogs:'coachGarmin.terminalLogs',bootId:'coachGarmin.bootId',lastGarminSync:'coachGarmin.lastGarminSync',lastGarminAuthTest:'coachGarmin.lastGarminAuthTest'};
const DEFAULT_TERMINAL_LEVELS={debug:true,info:true,warn:true,error:true};
const SECTIONS=['import','dashboard','coach','terminal','settings'];
const APP_VERSION='20260414-navfix17';
window.__coachModuleLoaded=true;
window.__coachModuleReady=false;
const runtimeInfo={serviceWorkerState:'unknown',serviceWorkerScope:'-',serviceWorkerController:false,lastCheckedAt:null};
const sectionMeta={import:{eyebrow:'Import',title:'Import',description:'Commence ici pour voir les données locales, la fraîcheur du workspace et lancer un import ou une sync si besoin.'},dashboard:{eyebrow:'Dashboard',title:'Dashboard',description:'Lis les cartes clés, ouvre une métrique en modal plein écran et regarde les tendances les plus utiles.'},coach:{eyebrow:'Chat',title:'Chat coach',description:'Décris ton objectif, laisse le coach poser les bonnes questions, puis génère un plan lié aux données locales.'},terminal:{eyebrow:'Terminal',title:'Terminal',description:'Inspecte les logs d’action, de réseau et d’erreur avec un filtre de niveau juste au-dessus.'},settings:{eyebrow:'Settings',title:'Settings',description:'Règle le thème, le provider IA, le workspace local et les options techniques utiles.'}};
const state={workspace:localStorage.getItem(STORAGE_KEYS.workspace)||'data',provider:localStorage.getItem(STORAGE_KEYS.provider)||'ollama',baseUrl:localStorage.getItem(STORAGE_KEYS.baseUrl)||'',apiKey:localStorage.getItem(STORAGE_KEYS.apiKey)||'',sourcePath:localStorage.getItem(STORAGE_KEYS.sourcePath)||'',goalText:localStorage.getItem(STORAGE_KEYS.goalText)||'',theme:localStorage.getItem(STORAGE_KEYS.theme)||'data-lab',activeSection:localStorage.getItem(STORAGE_KEYS.activeSection)||'import',showTerminalMenu:localStorage.getItem(STORAGE_KEYS.showTerminalMenu)!=='false',startSection:localStorage.getItem(STORAGE_KEYS.startSection)||'import',terminalLevels:loadTerminalLevels(),terminalLogs:loadTerminalLogs(),currentQuestions:[],answers:{},installPrompt:null,dashboardPayload:null,retryAction:null,bootTrace:[],lastGarminSync:loadLastGarminSync(),lastGarminAuthTest:loadLastGarminAuthTest(),bootId:localStorage.getItem(STORAGE_KEYS.bootId)||String(Date.now())};
const $=(id)=>document.getElementById(id);
const dom={appChip:$('app-chip'),providerChip:$('provider-chip'),dataChip:$('data-chip'),freshnessChip:$('freshness-chip'),objectiveChip:$('objective-chip'),workspaceChip:$('workspace-chip'),buildChip:$('build-chip'),sidebarNav:$('sidebar-nav'),sectionEyebrow:$('section-eyebrow'),sectionTitle:$('section-title'),sectionDescription:$('section-description'),sectionBadges:$('section-badges'),installButton:$('install-button'),diagnosticButton:$('diagnostic-button'),transcript:$('chat-transcript'),questions:$('questions'),coachSummary:$('coach-summary'),planList:$('plan-list'),busyBanner:$('busy-banner'),busyText:$('busy-text'),coachErrorBanner:$('coach-error-banner'),coachErrorTitle:$('coach-error-title'),coachErrorMessage:$('coach-error-message'),retryButton:$('retry-button'),dashboardCards:$('dashboard-cards'),dashboardImportState:$('dashboard-import-state'),dashboardImportDetail:$('dashboard-import-detail'),dashboardBikeState:$('dashboard-bike-state'),dashboardBikeDetail:$('dashboard-bike-detail'),coverageCard:$('coverage-card'),coverageSubtitle:$('coverage-subtitle'),analysisCard:$('analysis-card'),analysisSubtitle:$('analysis-subtitle'),volumeTrendSummary:$('volume-trend-summary'),bikeVolumeTrendSummary:$('bike-volume-trend-summary'),loadRatioTrendSummary:$('load-ratio-trend-summary'),sleepTrendSummary:$('sleep-trend-summary'),restingHrTrendSummary:$('resting-hr-trend-summary'),paceHrTrendSummary:$('pace-hr-trend-summary'),cadenceTrendSummary:$('cadence-trend-summary'),volumeTrend:$('volume-trend'),bikeVolumeTrend:$('bike-volume-trend'),loadRatioTrend:$('load-ratio-trend'),sleepTrend:$('sleep-trend'),restingHrTrend:$('resting-hr-trend'),paceHrTrend:$('pace-hr-trend'),cadenceTrend:$('cadence-trend'),importDataState:$('import-data-state'),importFreshnessDetail:$('import-freshness-detail'),importWorkspace:$('import-workspace'),importWorkspaceDetail:$('import-workspace-detail'),importRunState:$('import-run-state'),importRunDetail:$('import-run-detail'),importAgeState:$('import-age-state'),importAgeDetail:$('import-age-detail'),importSyncState:$('import-sync-state'),importSyncDetail:$('import-sync-detail'),coachStatusStrip:$('coach-status-strip'),terminalLog:$('terminal-log'),terminalSummary:$('terminal-summary'),dashboardModal:$('dashboard-modal'),dashboardModalTitle:$('dashboard-modal-title'),dashboardModalSubtitle:$('dashboard-modal-subtitle'),dashboardModalValue:$('dashboard-modal-value'),dashboardModalText:$('dashboard-modal-text'),dashboardModalChart:$('dashboard-modal-chart'),dashboardModalSignals:$('dashboard-modal-signals'),dashboardModalClose:$('dashboard-modal-close'),diagnosticModal:$('diagnostic-modal'),diagnosticModalTitle:$('diagnostic-modal-title'),diagnosticModalSubtitle:$('diagnostic-modal-subtitle'),diagnosticModalClose:$('diagnostic-modal-close'),diagnosticBuild:$('diagnostic-build'),diagnosticBuildDetail:$('diagnostic-build-detail'),diagnosticUrl:$('diagnostic-url'),diagnosticUrlDetail:$('diagnostic-url-detail'),diagnosticSw:$('diagnostic-sw'),diagnosticSwDetail:$('diagnostic-sw-detail'),diagnosticWorkspace:$('diagnostic-workspace'),diagnosticWorkspaceDetail:$('diagnostic-workspace-detail'),diagnosticImport:$('diagnostic-import'),diagnosticImportDetail:$('diagnostic-import-detail'),diagnosticProvider:$('diagnostic-provider'),diagnosticProviderDetail:$('diagnostic-provider-detail'),diagnosticRefreshButton:$('diagnostic-refresh-button'),diagnosticCopyButton:$('diagnostic-copy-button'),diagnosticSummary:$('diagnostic-summary'),bootTraceState:$('boot-trace-state'),bootTraceDetail:$('boot-trace-detail'),bootTraceLog:$('boot-trace-log'),bootTraceRefreshButton:$('boot-trace-refresh-button'),debugEndpointState:$('debug-endpoint-state'),debugEndpointDetail:$('debug-endpoint-detail'),terminalClearButton:$('clear-terminal-button'),themeSelect:$('theme-select'),startSectionSelect:$('start-section-select'),showTerminalToggle:$('show-terminal-toggle'),settingsProviderSelect:$('settings-provider-select'),baseUrlInput:$('base-url-input'),apiKeyInput:$('api-key-input'),workspaceInput:$('workspace-input'),workspaceInputSettings:$('workspace-input-settings'),sourcePathInput:$('source-path-input'),sourcePathInputSettings:$('source-path-input-settings'),goalInput:$('goal-input'),coachWorkspaceInput:$('coach-workspace-chip-input'),authDebugState:$('auth-debug-state'),authDebugDetail:$('auth-debug-detail'),authTokenstoreState:$('auth-tokenstore-state'),authTokenstoreDetail:$('auth-tokenstore-detail'),authTestButton:$('auth-test-button'),providerSelect:$('provider-select'),saveSettingsButton:$('save-settings-button'),refreshSettingsButton:$('refresh-settings-button'),saveGoalButton:$('save-goal-button'),prepareButton:$('prepare-button'),planButton:$('plan-button'),importButton:$('import-button'),syncButton:$('sync-button'),refreshButton:$('refresh-button'),reprocessButton:$('reprocess-button'),useLastWorkspaceButton:$('use-last-workspace-button'),levelButtons:Array.from(document.querySelectorAll('.level-toggle')),navButtons:Array.from(document.querySelectorAll('.nav-button'))};
const actionButtons=[dom.saveSettingsButton,dom.refreshSettingsButton,dom.saveGoalButton,dom.prepareButton,dom.planButton,dom.importButton,dom.syncButton,dom.refreshButton,dom.reprocessButton,dom.useLastWorkspaceButton,dom.retryButton,dom.terminalClearButton,dom.authTestButton];
function formatNumber(value,digits=0){if(value===null||value===undefined||value==='')return'-';const n=Number(value);if(Number.isNaN(n))return String(value);return new Intl.NumberFormat('fr-FR',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(n)}
function formatKilometers(value){if(value===null||value===undefined||value==='')return'-';return `${formatNumber(value,1)} km`}
function formatPace(value){if(value===null||value===undefined||value==='')return'-';const total=Number(value);if(!Number.isFinite(total)||total<=0)return'-';const minutes=Math.floor(total);const seconds=Math.round((total-minutes)*60);return seconds===60?`${minutes+1}:00/km`:`${minutes}:${String(seconds).padStart(2,'0')}/km`}
function formatHeartRate(value){if(value===null||value===undefined||value==='')return'-';return `${formatNumber(value,0)} bpm`}
function formatBand(low,high,formatter){const hasLow=low!==null&&low!==undefined;const hasHigh=high!==null&&high!==undefined;if(!hasLow&&!hasHigh)return'-';if(hasLow&&hasHigh)return `${formatter(low)} · ${formatter(high)}`;return formatter(hasLow?low:high)}
function formatDateLabel(value){if(!value)return'-';const date=new Date(`${value}T00:00:00`);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{dateStyle:'medium'}).format(date)}
function formatShortDateLabel(value){if(!value)return'-';const date=new Date(`${value}T00:00:00`);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{day:'2-digit',month:'short'}).format(date)}
function formatDateTime(value){if(!value)return'-';const date=new Date(value);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{dateStyle:'medium',timeStyle:'short'}).format(date)}
function daysBetween(a,b){const start=new Date(`${a}T00:00:00`);const end=new Date(`${b}T00:00:00`);if(Number.isNaN(start.getTime())||Number.isNaN(end.getTime()))return null;return Math.round((end.getTime()-start.getTime())/86400000)}
function normalizeText(value){return typeof value==='string'?value.normalize('NFC'):value}
function loadTerminalLevels(){try{const raw=localStorage.getItem(STORAGE_KEYS.terminalLevels);if(!raw)return {...DEFAULT_TERMINAL_LEVELS};const parsed=JSON.parse(raw);return{debug:parsed.debug!==false,info:parsed.info!==false,warn:parsed.warn!==false,error:parsed.error!==false}}catch{return{...DEFAULT_TERMINAL_LEVELS}}}
function loadTerminalLogs(){try{const raw=localStorage.getItem(STORAGE_KEYS.terminalLogs);if(!raw)return[];const parsed=JSON.parse(raw);return Array.isArray(parsed)?parsed.slice(-250):[]}catch{return[]}}
function loadLastGarminSync(){try{const raw=localStorage.getItem(STORAGE_KEYS.lastGarminSync);if(!raw)return{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'};const parsed=JSON.parse(raw);return parsed&&typeof parsed==='object'?parsed:{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'}}catch{return{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'}}}
function loadLastGarminAuthTest(){try{const raw=localStorage.getItem(STORAGE_KEYS.lastGarminAuthTest);if(!raw)return{status:"idle",message:"Aucun test d'auth Garmin enregistré."};const parsed=JSON.parse(raw);return parsed&&typeof parsed==="object"?parsed:{status:"idle",message:"Aucun test d'auth Garmin enregistré."}}catch{return{status:"idle",message:"Aucun test d'auth Garmin enregistré."}}}
function saveTerminalLogs(){localStorage.setItem(STORAGE_KEYS.terminalLogs,JSON.stringify(state.terminalLogs.slice(-250)))}
function applyTheme(){document.documentElement.dataset.theme=state.theme}
function setAppChip(text, tone=''){
  if(!dom.appChip) return;
  dom.appChip.textContent=text;
  dom.appChip.classList.remove('warn','error');
  if(tone) dom.appChip.classList.add(tone);
}
function formatBootTraceEvent(entry){
  const stamp=entry.timestamp?formatDateTime(entry.timestamp):'-';
  const stage=entry.stage||entry.event||'boot';
  const detail=entry.detail?` — ${entry.detail}`:'';
  return `${stamp} | ${stage}${detail}`;
}
function renderBootTrace(events=state.bootTrace){
  const trace=Array.isArray(events)?events.slice(-40):[];
  if(dom.bootTraceState){
    dom.bootTraceState.textContent=trace.length?`Trace active (${trace.length})`:'Aucune trace';
  }
  if(dom.bootTraceDetail){
    const last=trace.at(-1);
    dom.bootTraceDetail.textContent=last?formatBootTraceEvent(last):'Aucun évènement enregistré.';
  }
  if(dom.bootTraceLog){
    dom.bootTraceLog.textContent=trace.length?trace.map((entry)=>formatBootTraceEvent(entry)).join('\n'):'Aucun évènement de boot pour le moment.';
  }
  if(dom.bootTraceRefreshButton){
    dom.bootTraceRefreshButton.disabled=false;
  }
}
function recordBoot(stage, detail='', extra={}){
  const event={
    timestamp:new Date().toISOString(),
    stage,
    event:stage,
    detail,
    app_version:APP_VERSION,
    boot_id:state.bootId,
    workspace:state.workspace,
    provider:state.provider,
    section:state.activeSection,
    url:window.location.href,
    hash:window.location.hash||'#import',
    state:extra.state||'info',
    ...extra,
  };
  state.bootTrace.push(event);
  state.bootTrace=state.bootTrace.slice(-40);
  localStorage.setItem(STORAGE_KEYS.bootId,state.bootId);
  renderBootTrace();
  addTerminalLog('debug','boot',stage,detail||extra.detail||'');
  void requestJson('/api/debug/boot',{method:'POST',body:JSON.stringify({...event,data_dir:state.workspace})},'boot-trace').catch((error)=>{
    addTerminalLog('warn','boot',`Boot trace write failed: ${error.message}`);
  });
  return event;
}
async function refreshBootTrace(){
  if(!dom.bootTraceState&&!dom.bootTraceLog&&!dom.debugEndpointState) return [];
  if(dom.bootTraceRefreshButton) dom.bootTraceRefreshButton.disabled=true;
  try{
    const payload=await requestJson(`/api/debug/boot?data_dir=${encodeURIComponent(state.workspace)}&limit=40`,{},'boot-trace');
    const events=Array.isArray(payload.events)?payload.events:[];
    state.bootTrace=events;
    renderBootTrace(events);
    if(dom.debugEndpointState) dom.debugEndpointState.textContent=`API boot trace ok (${events.length})`;
    if(dom.debugEndpointDetail) dom.debugEndpointDetail.textContent=payload.trace_path||'-';
    recordBoot('boot-trace:refreshed',`${events.length} event(s) chargés`,{state:'info'});
    return events;
  }catch(error){
    if(dom.debugEndpointState) dom.debugEndpointState.textContent='API boot trace indisponible';
    if(dom.debugEndpointDetail) dom.debugEndpointDetail.textContent=error.message;
    renderBootTrace();
    addTerminalLog('warn','boot',`Boot trace endpoint unreachable: ${error.message}`);
    return [];
  }finally{
    if(dom.bootTraceRefreshButton) dom.bootTraceRefreshButton.disabled=false;
  }
}

function renderAuthDebug(payload=null){
  const auth=payload||state.lastGarminAuthTest||{};
  const env=auth.auth_environment||{};
  if(dom.authDebugState) dom.authDebugState.textContent = auth.ok===true ? 'Authentification prête' : auth.ok===false ? 'Authentification en échec' : 'Authentification non testée';
  if(dom.authDebugDetail) dom.authDebugDetail.textContent = auth.ok===true ? (auth.result?.used_existing_tokenstore ? 'Tokenstore réutilisé et login réussi.' : 'Login réussi et tokenstore initialisé.') : auth.error ? `${auth.error}${auth.debug_log_path ? ` · log ${auth.debug_log_path}` : ''}` : 'Lance un test pour remplir ce bloc.';
  if(dom.authTokenstoreState) dom.authTokenstoreState.textContent = env.tokenstore_exists ? 'Tokenstore détecté' : 'Aucun tokenstore';
  if(dom.authTokenstoreDetail) dom.authTokenstoreDetail.textContent = `${env.tokenstore_path || '-'}${env.package_version ? ` · garminconnect ${env.package_version}` : ''}`;
}
async function refreshAuthDebug(){
  try{
    const payload=await requestJson(`/api/auth/debug?tokenstore_path=${encodeURIComponent('.local/garmin/garmin_tokens.json')}`,{},'auth-debug');
    renderAuthDebug({auth_environment:payload});
    return payload;
  }catch(error){
    renderAuthDebug({ok:false,error:error.message});
    addTerminalLog('warn','auth',`Debug auth indisponible: ${error.message}`);
    return null;
  }
}
async function testGarminAuth(){
  persistSettings();
  if(dom.authTestButton) dom.authTestButton.disabled=true;
  setBusy(true,"Test de l'auth Garmin en cours...");
  try{
    const payload=await requestJson('/api/auth/test',{method:'POST',body:JSON.stringify({data_dir:state.workspace,tokenstore_path:'.local/garmin/garmin_tokens.json'})},'auth-test');
    state.lastGarminAuthTest={...payload,timestamp:new Date().toISOString()};
    localStorage.setItem(STORAGE_KEYS.lastGarminAuthTest,JSON.stringify(state.lastGarminAuthTest));
    renderAuthDebug(state.lastGarminAuthTest);
    addTerminalLog(payload.ok?'info':'warn','auth',payload.ok?'Auth Garmin réussie':'Auth Garmin en échec',payload.ok?payload.result?.tokenstore_path||'tokenstore ok':payload.error||'échec');
    if(payload.ok){addMessage('assistant','Auth Garmin réussie.')}else{addMessage('assistant',`Auth Garmin en échec: ${payload.error}`)}
  }catch(error){
    state.lastGarminAuthTest={ok:false,error:error.message,timestamp:new Date().toISOString()};
    localStorage.setItem(STORAGE_KEYS.lastGarminAuthTest,JSON.stringify(state.lastGarminAuthTest));
    renderAuthDebug(state.lastGarminAuthTest);
    addTerminalLog('error','auth',`Auth Garmin impossible: ${error.message}`);
    addMessage('assistant',`Auth Garmin impossible: ${error.message}`);
  }finally{
    if(dom.authTestButton) dom.authTestButton.disabled=false;
    setBusy(false);
  }
}
window.addEventListener('error',(event)=>{setAppChip('App: erreur JS','error');addTerminalLog('error','runtime',event.message||'Erreur JS',event.error?.stack||'');if(dom.coachErrorBanner){dom.coachErrorTitle.textContent='Erreur JavaScript';dom.coachErrorMessage.textContent=event.message||'Une erreur de script a empêché l’initialisation.';dom.coachErrorBanner.classList.remove('hidden')}});
window.addEventListener('unhandledrejection',(event)=>{setAppChip('App: promesse rejetée','error');const reason=event.reason?.message||String(event.reason||'Rejet de promesse');addTerminalLog('error','runtime',reason,event.reason?.stack||'');if(dom.coachErrorBanner){dom.coachErrorTitle.textContent='Erreur asynchrone';dom.coachErrorMessage.textContent=reason;dom.coachErrorBanner.classList.remove('hidden')}});
function currentPayload(){return state.dashboardPayload||{}}
function currentMetrics(){return currentPayload().analysis?.metrics||{}}
function currentImportStatus(){return currentPayload().import_status||{}}
function currentAnalysis(){return currentPayload().analysis||{}}
async function requestJson(url,options={},label='request'){const response=await fetch(url,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});const contentType=response.headers.get('content-type')||'';const body=contentType.includes('application/json')?await response.json():{message:await response.text()};if(!response.ok){const error=new Error(body?.message||body?.error||`${label} failed with HTTP ${response.status}`);error.status=response.status;error.body=body;throw error}return body}
async function withBusy(message,runner){setBusy(true,message);try{return await runner()}finally{setBusy(false)}}
function syncInputsFromState(){dom.workspaceInputSettings.value=state.workspace;dom.providerSelect.value=state.provider;dom.settingsProviderSelect.value=state.provider;dom.baseUrlInput.value=state.baseUrl;dom.apiKeyInput.value=state.apiKey;dom.sourcePathInput.value=state.sourcePath;dom.sourcePathInputSettings.value=state.sourcePath;dom.goalInput.value=state.goalText;dom.themeSelect.value=state.theme;dom.startSectionSelect.value=state.startSection;dom.showTerminalToggle.checked=state.showTerminalMenu;dom.coachWorkspaceInput.value=state.workspace}
function persistSettings(){state.workspace=normalizeText((dom.workspaceInputSettings.value||'data').trim()||'data');state.provider=normalizeText((dom.providerSelect.value||dom.settingsProviderSelect.value||'ollama').trim());state.baseUrl=normalizeText(dom.baseUrlInput.value.trim());state.apiKey=normalizeText(dom.apiKeyInput.value.trim());state.sourcePath=normalizeText((dom.sourcePathInput.value||dom.sourcePathInputSettings.value||'').trim());state.goalText=normalizeText(dom.goalInput.value.trim());state.theme=dom.themeSelect.value;state.startSection=dom.startSectionSelect.value;state.showTerminalMenu=dom.showTerminalToggle.checked;localStorage.setItem(STORAGE_KEYS.workspace,state.workspace);localStorage.setItem(STORAGE_KEYS.provider,state.provider);localStorage.setItem(STORAGE_KEYS.baseUrl,state.baseUrl);localStorage.setItem(STORAGE_KEYS.apiKey,state.apiKey);localStorage.setItem(STORAGE_KEYS.sourcePath,state.sourcePath);localStorage.setItem(STORAGE_KEYS.goalText,state.goalText);localStorage.setItem(STORAGE_KEYS.theme,state.theme);localStorage.setItem(STORAGE_KEYS.activeSection,state.activeSection);localStorage.setItem(STORAGE_KEYS.startSection,state.startSection);localStorage.setItem(STORAGE_KEYS.showTerminalMenu,String(state.showTerminalMenu));localStorage.setItem(STORAGE_KEYS.terminalLevels,JSON.stringify(state.terminalLevels));applyTheme();updateNavVisibility();renderSectionHeader();renderSidebarStatus();dom.coachWorkspaceInput.value=state.workspace}
function addTerminalLog(level,source,message,details=''){state.terminalLogs.push({timestamp:new Date().toISOString(),level,source,message,details});state.terminalLogs=state.terminalLogs.slice(-250);saveTerminalLogs();renderTerminalSection()}
function setBusy(active,message='Analyse en cours...'){dom.busyBanner.classList.toggle('hidden',!active);dom.busyText.textContent=message;document.body.classList.toggle('is-busy',active);actionButtons.forEach((button)=>{if(button&&button!==dom.retryButton)button.disabled=active})}
function buildProviderErrorTitle(error){if(!error)return'Le provider a renvoy? une erreur.';if(error.status===503||error.status===429)return'Provider temporairement indisponible.';return'Le provider a renvoy? une erreur.'}
function buildProviderErrorMessage(error){if(!error)return'R?essaie ou change de provider avant de repartir.';if(error.status===503||error.status===429)return'Le provider est temporairement indisponible. R?essaie, ou change de provider dans le sélecteur avant de relancer.';return error.message||'R?essaie ou change de provider avant de repartir.'}
function setCoachError(message,retryAction=null,title='Le provider a renvoy? une erreur.'){state.retryAction=retryAction;dom.coachErrorTitle.textContent=title;dom.coachErrorMessage.textContent=message;dom.coachErrorBanner.classList.remove('hidden');dom.retryButton.disabled=typeof retryAction!=='function'}
function clearCoachError(){state.retryAction=null;dom.coachErrorBanner.classList.add('hidden');dom.coachErrorTitle.textContent='Le provider a renvoy? une erreur.';dom.coachErrorMessage.textContent='';dom.retryButton.disabled=true}
function addMessage(role,text){const node=document.createElement('div');node.className=`message ${role}`;node.textContent=text;dom.transcript.appendChild(node);dom.transcript.scrollTop=dom.transcript.scrollHeight}
function renderQuestions(questions){dom.questions.innerHTML='';state.currentQuestions=questions||[];state.answers={};if(!state.currentQuestions.length){dom.questions.innerHTML="<p class='status-line'>Aucune question compl?mentaire. Tu peux générer le plan directement.</p>";return}state.currentQuestions.forEach((question)=>{const template=$('question-template');const node=template.content.firstElementChild.cloneNode(true);const label=node.querySelector('.question-label');const input=node.querySelector('input');label.textContent=question.question;input.placeholder=question.key;input.dataset.key=question.key;input.addEventListener('input',()=>{state.answers[question.key]=input.value.trim()});dom.questions.appendChild(node)})}
function buildChartTicks(min,max,count=5){if(!Number.isFinite(min)||!Number.isFinite(max))return[];if(count<=1||min===max)return[min,max].filter((value,index,array)=>array.indexOf(value)===index);const span=max-min||1;const step=span/(count-1);return Array.from({length:count},(_,index)=>Number((min+step*index).toFixed(2)))}
function chartTooltipLabel(container){let tooltip=container.querySelector('.chart-tooltip');if(!tooltip){tooltip=document.createElement('div');tooltip.className='chart-tooltip';container.appendChild(tooltip)}return tooltip}
function renderChartTooltip(tooltip,payload){if(!tooltip)return;tooltip.innerHTML=`<strong>${payload.title}</strong><span>${payload.value}</span>${payload.detail?`<small>${payload.detail}</small>`:''}`;tooltip.style.left=`${payload.x}px`;tooltip.style.top=`${payload.y}px`;tooltip.classList.add('visible')}
function attachChartTooltipHandlers(container,tooltip,points){points.forEach((point)=>{point.addEventListener('mouseenter',()=>{const title=point.dataset.title||'-';const value=point.dataset.value||'-';const detail=point.dataset.detail||'';renderChartTooltip(tooltip,{title,value,detail,x:Number(point.dataset.tx||0),y:Number(point.dataset.ty||0)})});point.addEventListener('mousemove',(event)=>{const rect=container.getBoundingClientRect();renderChartTooltip(tooltip,{title:point.dataset.title||'-',value:point.dataset.value||'-',detail:point.dataset.detail||'',x:event.clientX-rect.left,y:event.clientY-rect.top})});point.addEventListener('mouseleave',()=>{tooltip.classList.remove('visible')})})}
function renderSparkline(container,series,options={}){const input=Array.isArray(series)?series:[];const items=input.map((entry,index)=>{if(typeof entry==='number'&&Number.isFinite(entry))return{value:entry,label:options.labels?.[index]||String(index+1),detail:options.details?.[index]||''};if(entry&&typeof entry==='object'){const value=Number(entry.value??entry.distance_km??entry.load_ratio_7_28??entry.sleep_hours??entry.resting_hr??entry.cadence_spm);return Number.isFinite(value)?{value,label:entry.label||entry.metric_date||options.labels?.[index]||String(index+1),detail:entry.detail||entry.metric_date||''}:null}return null}).filter(Boolean);if(!items.length){container.innerHTML="<p class='status-line'>Pas encore de données exploitables.</p>";return}const width=options.width||360;const height=options.height||120;const padLeft=options.padLeft||42;const padRight=options.padRight||16;const padTop=options.padTop||12;const padBottom=options.padBottom||30;const values=items.map((item)=>Number(item.value));const min=Math.min(...values);const max=Math.max(...values);const span=max-min||1;const xSpan=items.length>1?(width-padLeft-padRight)/(items.length-1):0;const points=items.map((item,index)=>{const x=items.length>1?padLeft+index*xSpan:width/2;const y=height-padBottom-((Number(item.value)-min)/span)*(height-padTop-padBottom);return{x,y,item}});const line=points.map((point)=>`${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');const yTicks=buildChartTicks(min,max,5);const xTicks=items.length>1?[0,Math.floor((items.length-1)/2),items.length-1].filter((index,pos,array)=>array.indexOf(index)===pos):[0];const tickFormatter=options.tickFormatter||((value)=>formatNumber(value,1));const title=options.title||'';const xLabel=options.xLabel||'';const yLabel=options.yLabel||'';container.innerHTML=`<div class="chart-shell"><svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${title||'courbe'}"><defs><linearGradient id="sparkline-fill-${options.id||'base'}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="${options.fill||'rgba(138, 230, 192, 0.34)'}" /><stop offset="100%" stop-color="rgba(138, 230, 192, 0.03)" /></linearGradient></defs><line class="chart-axis-line" x1="${padLeft}" y1="${height-padBottom}" x2="${width-padRight}" y2="${height-padBottom}"></line><line class="chart-axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height-padBottom}"></line>${yTicks.map((tick)=>{const ratio=(tick-min)/span;const y=height-padBottom-ratio*(height-padTop-padBottom);return `<g><line class="chart-grid-line" x1="${padLeft}" y1="${y.toFixed(2)}" x2="${width-padRight}" y2="${y.toFixed(2)}"></line><text class="chart-axis-tick" x="${padLeft-8}" y="${(y+4).toFixed(2)}" text-anchor="end">${tickFormatter(tick)}</text></g>`}).join('')}<path d="M ${points.map((point)=>`${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')}" fill="none" stroke="${options.stroke||'#8ae6c0'}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"></path><polygon points="${`0,${height-padBottom} ${line} ${width},${height-padBottom}`}" fill="url(#sparkline-fill-${options.id||'base'})" opacity="0.8"></polygon>${points.map((point,index)=>`<circle class="chart-point-dot" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${index===points.length-1?4.6:3.8}" fill="${options.stroke||'#8ae6c0'}" data-title="${point.item.label}" data-value="${tickFormatter(point.item.value)}" data-detail="${point.item.detail||''}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle><circle class="chart-point-hit" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="12" data-title="${point.item.label}" data-value="${tickFormatter(point.item.value)}" data-detail="${point.item.detail||''}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle>`).join('')}<text class="chart-axis-title" x="${padLeft}" y="${16}">${yLabel}</text><text class="chart-axis-title" x="${width-padRight}" y="${height-6}" text-anchor="end">${xLabel}</text>${xTicks.map((index)=>{const point=points[index];if(!point)return'';const x=point.x;const label=point.item.label||'';return `<text class="chart-axis-tick" x="${x.toFixed(2)}" y="${height-8}" text-anchor="middle">${label}</text>`}).join('')}</svg><div class="chart-tooltip" aria-hidden="true"></div></div>`;const tooltip=chartTooltipLabel(container);const pointsEls=Array.from(container.querySelectorAll('.chart-point-hit, .chart-point-dot'));attachChartTooltipHandlers(container,tooltip,pointsEls)}
function renderDualSparkline(container,seriesA,seriesB,options={}){const valuesA=Array.isArray(seriesA)?seriesA.filter((value)=>Number.isFinite(Number(value))):[];const valuesB=Array.isArray(seriesB)?seriesB.filter((value)=>Number.isFinite(Number(value))):[];if(!valuesA.length&&!valuesB.length){container.innerHTML="<p class='status-line'>Pas encore de série exploitable.</p>";return}const width=options.width||360;const height=options.height||110;const renderSeries=(series,stroke,fill,id)=>{const values=series.filter((value)=>Number.isFinite(Number(value)));if(!values.length)return'<p class="status-line">Pas de données.</p>';const min=Math.min(...values);const max=Math.max(...values);const span=max-min||1;const step=values.length>1?width/(values.length-1):width;const points=values.map((value,index)=>{const x=values.length>1?index*step:width/2;const y=height-((Number(value)-min)/span)*(height-14)-7;return{x,y}});const line=points.map((point)=>`${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');return`<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="sparkline-fill-${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="${fill}" /><stop offset="100%" stop-color="rgba(138, 180, 255, 0.02)" /></linearGradient></defs><polygon points="0,${height} ${line} ${width},${height}" fill="url(#sparkline-fill-${id})"></polygon><polyline points="${line}" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>${points.map((point)=>`<circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.1" fill="${stroke}"></circle>`).join('')}</svg>`};container.innerHTML=`<div class="stacked-trend"><div class="stacked-row"><span class="card-label">Allure</span>${renderSeries(valuesA,'#8ae6c0','rgba(138, 230, 192, 0.34)',`${options.id||'dual'}-pace`)}</div><div class="stacked-row"><span class="card-label">FC</span>${renderSeries(valuesB,'#8ab4ff','rgba(138, 180, 255, 0.32)',`${options.id||'dual'}-hr`)}</div></div>`}
function weightedIsotonicNonDecreasing(values,weights){if(!Array.isArray(values)||!values.length)return[];const blocks=[];values.forEach((value,index)=>{let block=[Number(value),Math.max(Number(weights?.[index]||1),1),1];blocks.push(block);while(blocks.length>=2&&blocks[blocks.length-2][0]>blocks[blocks.length-1][0]){const right=blocks.pop();const left=blocks.pop();const mergedWeight=left[1]+right[1];const mergedValue=((left[0]*left[1])+(right[0]*right[1]))/mergedWeight;blocks.push([mergedValue,mergedWeight,left[2]+right[2]])}});const result=[];blocks.forEach((block)=>{for(let i=0;i<block[2];i+=1){result.push(Number(block[0].toFixed(2)))}});return result.slice(0,values.length)}
function zoneColorForHeartRate(value,maxHeartRate=null){
  if(!Number.isFinite(Number(value))) return '#8ae6c0';
  const hr=Number(value);
  const maxHr=Number(maxHeartRate);
  const referenceMax=Number.isFinite(maxHr)&&maxHr>0?maxHr:null;
  const threshold=referenceMax||Math.max(160,hr*1.1);
  const ratios=[
    {limit:0.6,color:'#4da3ff'},
    {limit:0.7,color:'#4fd1a5'},
    {limit:0.8,color:'#b6e05c'},
    {limit:0.9,color:'#ffbe55'},
    {limit:1.01,color:'#ff6b6b'},
  ];
  const normalized=referenceMax?hr/referenceMax:hr/threshold;
  return ratios.find((entry)=>normalized<=entry.limit)?.color||'#ff6b6b';
}
function renderMonotonePaceCurve(container,curve,options={}){
  const values=Array.isArray(curve)?curve.filter((point)=>Number.isFinite(Number(point?.pace_min_per_km))&&Number.isFinite(Number(point?.heart_rate))):[];
  if(values.length<3){container.innerHTML="<p class='status-line'>Pas encore assez de points stables pour une courbe pace / FC.</p>";return}
  const width=options.width||360;
  const height=options.height||240;
  const padLeft=48;
  const padRight=22;
  const padTop=20;
  const padBottom=34;
  const sorted=values.slice().sort((a,b)=>Number(b.pace_min_per_km)-Number(a.pace_min_per_km));
  const paces=sorted.map((point)=>Number(point.pace_min_per_km));
  const hrs=sorted.map((point)=>Number(point.heart_rate));
  const weights=sorted.map((point)=>Math.max(Number(point.support||point.point_count||1),1));
  const isotonic=weightedIsotonicNonDecreasing(hrs,weights);
  const heartRates=isotonic.length===sorted.length?isotonic:hrs;
  const paceMin=Math.min(...paces);
  const paceMax=Math.max(...paces);
  const hrMin=Math.min(...heartRates);
  const hrMax=Math.max(...heartRates);
  const paceSpan=paceMax-paceMin||1;
  const hrSpan=hrMax-hrMin||1;
  const points=sorted.map((point,index)=>{
    const pace=Number(point.pace_min_per_km);
    const x=padLeft+((paceMax-pace)/paceSpan)*(width-padLeft-padRight);
    const y=height-padBottom-((Number(heartRates[index])-hrMin)/hrSpan)*(height-padTop-padBottom);
    return {x,y,point,heartRate:Number(heartRates[index]),pace};
  });
  const yTicks=buildChartTicks(hrMin,hrMax,5);
  const xTicks=buildChartTicks(paceMin,paceMax,5);
  const segments=points.slice(1).map((point,index)=>{
    const prev=points[index];
    const stroke=zoneColorForHeartRate(point.heartRate,options.maxHrEstimate);
    return `<line x1="${prev.x.toFixed(2)}" y1="${prev.y.toFixed(2)}" x2="${point.x.toFixed(2)}" y2="${point.y.toFixed(2)}" stroke="${stroke}" stroke-width="4" stroke-linecap="round" />`;
  }).join('');
  const legend=[
    ['Bleu', '#4da3ff'],
    ['Vert', '#4fd1a5'],
    ['Jaune', '#b6e05c'],
    ['Orange', '#ffbe55'],
    ['Rouge', '#ff6b6b'],
  ];
  container.innerHTML=`<div class="chart-shell curve-wrap"><svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Courbe pace et fréquence cardiaque"><defs><linearGradient id="curve-glow-${options.id||'pace'}" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="rgba(74, 163, 255, 0.12)" /><stop offset="100%" stop-color="rgba(255, 107, 107, 0.12)" /></linearGradient></defs><rect x="0" y="0" width="${width}" height="${height}" fill="url(#curve-glow-${options.id||'pace'})" opacity="0.34"></rect><line class="chart-axis-line" x1="${padLeft}" y1="${height-padBottom}" x2="${width-padRight}" y2="${height-padBottom}"></line><line class="chart-axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height-padBottom}"></line>${yTicks.map((tick)=>{const ratio=(tick-hrMin)/hrSpan;const y=height-padBottom-ratio*(height-padTop-padBottom);return `<g><line class="chart-grid-line" x1="${padLeft}" y1="${y.toFixed(2)}" x2="${width-padRight}" y2="${y.toFixed(2)}"></line><text class="chart-axis-tick" x="${padLeft-8}" y="${(y+4).toFixed(2)}" text-anchor="end">${formatNumber(tick,0)} bpm</text></g>`}).join('')}<path d="M ${points.map((point)=>`${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"></path>${segments}${points.map((point,index)=>{const stroke=zoneColorForHeartRate(point.heartRate,options.maxHrEstimate);const label=formatPace(point.pace);return `<circle class="chart-point-dot" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${index===points.length-1?4.8:3.8}" fill="${stroke}" data-title="${label}" data-value="${formatHeartRate(point.heartRate)}" data-detail="${point.point.cadence_spm?`${formatNumber(point.point.cadence_spm,0)} spm · ${point.point.point_count||1} point(s)`:`${point.point.point_count||1} point(s)`}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle><circle class="chart-point-hit" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="12" data-title="${label}" data-value="${formatHeartRate(point.heartRate)}" data-detail="${point.point.cadence_spm?`${formatNumber(point.point.cadence_spm,0)} spm · ${point.point.point_count||1} point(s)`:`${point.point.point_count||1} point(s)`}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle>`}).join('')}<text class="chart-axis-title" x="${padLeft}" y="${16}">FC (bpm)</text><text class="chart-axis-title" x="${width-padRight}" y="${height-6}" text-anchor="end">Allure (min/km)</text>${xTicks.map((tick)=>{const x=padLeft+((paceMax-tick)/paceSpan)*(width-padLeft-padRight);return `<text class="chart-axis-tick" x="${x.toFixed(2)}" y="${height-8}" text-anchor="middle">${formatPace(tick)}</text>`}).join('')}</svg><div class="curve-legend">${legend.map(([label,color])=>`<span><i style="background:${color}"></i>${label}</span>`).join('')}</div><div class="chart-tooltip" aria-hidden="true"></div></div>`;const tooltip=chartTooltipLabel(container);attachChartTooltipHandlers(container,tooltip,Array.from(container.querySelectorAll('.chart-point-hit, .chart-point-dot')))}
function renderSectionHeader(){const meta=sectionMeta[state.activeSection]||sectionMeta.import;dom.sectionEyebrow.textContent=meta.eyebrow;dom.sectionTitle.textContent=meta.title;dom.sectionDescription.textContent=meta.description}
function updateNavVisibility(){if(!state.showTerminalMenu&&state.activeSection==='terminal'){state.activeSection='import';localStorage.setItem(STORAGE_KEYS.activeSection,state.activeSection)}dom.navButtons.forEach((button)=>{const section=button.dataset.section;const active=section===state.activeSection;button.classList.toggle('hidden',section==='terminal'&&!state.showTerminalMenu);button.classList.toggle('active',active);button.setAttribute('aria-current',active?'page':'false');button.setAttribute('aria-pressed',String(active))})}
function renderSidebarStatus(){const payload=currentPayload();const provider=payload.provider||{};const importStatus=currentImportStatus();const analysis=currentAnalysis();const metrics=currentMetrics();const providerLabel=provider.status==='ready'?`Provider ${provider.provider==='ollama'?'Ollama':provider.provider} prêt`:provider.status==='unchecked'?`Provider ${provider.provider||state.provider} en vérification`:`Provider ${provider.provider||state.provider} indisponible`;dom.providerChip.textContent=providerLabel;dom.providerChip.classList.toggle('warn',provider.status==='unchecked');dom.providerChip.classList.toggle('error',provider.status==='unavailable');dom.dataChip.textContent=importStatus.available?'Données locales: oui':'Données locales: non';dom.dataChip.classList.toggle('warn',!importStatus.available);const latestActivityDay=importStatus.latest_activity_day||payload.latest_day||null;if(latestActivityDay){const age=daysBetween(latestActivityDay,new Date().toISOString().slice(0,10));dom.freshnessChip.textContent=`Dernière date: ${age===null?formatDateLabel(latestActivityDay):`${formatDateLabel(latestActivityDay)} ? ${age} j`}`;dom.freshnessChip.classList.toggle('warn',typeof age==='number'&&age>=7)}else{dom.freshnessChip.textContent='Dernière date: -';dom.freshnessChip.classList.add('warn')}const objective=state.goalText||analysis.principal_objective||'';dom.objectiveChip.textContent=objective?`Objectif: ${objective.slice(0,42)}${objective.length>42?'?':''}`:'Objectif: aucun';dom.objectiveChip.classList.toggle('warn',!objective);dom.workspaceChip.textContent=`Workspace: ${state.workspace}`;if(dom.buildChip)dom.buildChip.textContent=`Build: ${APP_VERSION}`;dom.coachWorkspaceInput.value=state.workspace;dom.sectionBadges.innerHTML='';[{label:providerLabel,warn:provider.status==='unchecked'},{label:importStatus.state?`Import: ${importStatus.state}`:'Import: -',warn:importStatus.state==='empty'},{label:analysis.available?'Analyse: prête':'Analyse: en attente',warn:!analysis.available},{label:metrics.weekly_volume_km!==undefined?`Volume 7j: ${formatKilometers(metrics.weekly_volume_km)}`:'Volume 7j: -',warn:metrics.weekly_volume_km===undefined}].forEach((item)=>{const pill=document.createElement('span');pill.className=`pill pill-small${item.warn?' warn':''}`;pill.textContent=item.label;dom.sectionBadges.appendChild(pill)})}
function setActiveSection(section,{persist=true,updateHash=true}={}){state.activeSection=section;if(persist)localStorage.setItem(STORAGE_KEYS.activeSection,section);if(updateHash&&window.location.hash!==`#${section}`){window.location.hash=section}document.documentElement.dataset.activeSection=section;updateNavVisibility();renderSectionHeader();renderAllSections()}
function renderSectionVisibility(){SECTIONS.forEach((section)=>{const node=document.getElementById(`section-${section}`);if(node)node.classList.toggle('hidden',state.activeSection!==section)})}
function renderImportSection(){
  const payload = currentPayload();
  const importStatus = currentImportStatus();
  const latestRun = importStatus.latest_run || payload.health?.latest_sync_run || null;
  const latestDay = importStatus.latest_activity_day || payload.latest_day || null;
  const syncState = importStatus.sync_state || payload.health?.sync_state || {};
  const syncAttempt = state.lastGarminSync || {};
  const sourcePath = state.sourcePath || dom.sourcePathInput.value || dom.sourcePathInputSettings.value || '';
  dom.importDataState.textContent = importStatus.available ? (importStatus.state === 'imported' ? 'Données locales importées' : 'Données locales indexées') : 'Aucune donnée locale détectée';
  if (latestDay) {
    const age = daysBetween(latestDay, new Date().toISOString().slice(0, 10));
    dom.importFreshnessDetail.textContent = `Dernière activité: ${formatDateLabel(latestDay)}${age === null ? '' : ` · ${age} jours`}`;
    dom.importAgeState.textContent = age === null ? formatDateLabel(latestDay) : `${age} jours`;
    dom.importAgeDetail.textContent = age !== null && age >= 7 ? 'Le jeu local semble un peu ancien. Un refresh manuel peut valoir le coup.' : 'La donnée locale paraît récente pour travailler dessus.';
  } else {
    dom.importFreshnessDetail.textContent = 'Aucune activité locale n’est encore indexée pour ce workspace.';
    dom.importAgeState.textContent = '-';
    dom.importAgeDetail.textContent = 'Lance un import Garmin pour rendre le workspace exploitable.';
  }
  dom.importRunState.textContent = latestRun ? (latestRun.run_label || latestRun.run_id || latestRun.source_kind || 'Import récent') : 'Aucun import récent';
  dom.importRunDetail.textContent = latestRun ? `${latestRun.total_records || 0} enregistrements · ${latestRun.dataset_count || 0} datasets · ${formatDateTime(latestRun.finished_at)}` : 'Utilise l’import Garmin pour créer le workspace local.';
  dom.importSyncState.textContent = syncAttempt.status === 'error' ? 'Sync Garmin Connect échouée' : syncAttempt.status === 'running' ? 'Sync Garmin Connect en cours' : latestRun && String(latestRun.source_kind || '').includes('garmin') ? 'Sync Garmin Connect prête' : 'Sync Garmin Connect disponible';
  dom.importSyncDetail.textContent = syncAttempt.message || (latestRun && String(latestRun.source_kind || '').includes('garmin') ? `Dernière sync: ${latestRun.run_label || latestRun.run_id || '-'} · ${latestRun.finished_at ? formatDateTime(latestRun.finished_at) : '-'} · nouveaux ${syncState.new_artifact_count !== undefined ? syncState.new_artifact_count : '-'} · réutilisés ${syncState.reused_artifact_count !== undefined ? syncState.reused_artifact_count : '-'}` : 'La sync peut compléter les données locales sans bloquer l’app.');
  dom.importWorkspace.textContent = sourcePath || '-';
  dom.importWorkspaceDetail.textContent = sourcePath ? 'Le chemin saisi près du bouton Importer Garmin.' : 'Configure une source Garmin locale pour lancer l’import.';
}function dashboardCardSpecs(payload){
  const analysis = payload.analysis || {};
  const metrics = analysis.metrics || {};
  const trend = analysis.trend || {};
  const importStatus = payload.import_status || {};
  const latestRun = importStatus.latest_run || payload.health?.latest_sync_run || null;
  const benchmark = analysis.benchmark || {};
  const paceCurve = Array.isArray(trend.pace_hr_curve) ? trend.pace_hr_curve : [];
  const cadenceSeries = Array.isArray(trend.cadence_daily) ? trend.cadence_daily : [];
  const runningVolumeSeries = Array.isArray(trend.daily_volume) ? trend.daily_volume : [];
  const bikeVolumeSeries = Array.isArray(trend.daily_bike_volume) ? trend.daily_bike_volume : [];
  const loadRatioSeries = Array.isArray(trend.daily_load_ratio) ? trend.daily_load_ratio : [];
  const sleepSeries = Array.isArray(trend.daily_sleep) ? trend.daily_sleep : [];
  const restingHrSeries = Array.isArray(trend.daily_resting_hr) ? trend.daily_resting_hr : [];
  const cadenceValues = cadenceSeries.map((row) => row.cadence_spm || 0);
  const volumeSeries = runningVolumeSeries.map((row) => ({value:row.distance_km || 0,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)}));
  const bikeSeries = bikeVolumeSeries.map((row) => ({value:row.distance_km || 0,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)}));
  const loadSeries = runningVolumeSeries.map((row) => ({value:row.training_load || 0,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)}));
  const loadRatioChartSeries = loadRatioSeries.map((row) => ({value:row.load_ratio_7_28,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row) => Number.isFinite(Number(row.value)));
  const sleepChartSeries = sleepSeries.map((row) => ({value:row.sleep_hours,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row) => Number.isFinite(Number(row.value)));
  const restingHrChartSeries = restingHrSeries.map((row) => ({value:row.resting_hr,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row) => Number.isFinite(Number(row.value)));
  const paceCurveLast = paceCurve.length ? paceCurve[paceCurve.length - 1] : null;
  const paceCurveFirst = paceCurve.length ? paceCurve[0] : null;
  const loadRef = formatBand(metrics.load_reference_low, metrics.load_reference_high, (value) => `${formatNumber(value, 0)} u`);
  const sleepRef = formatBand(metrics.sleep_reference_low, metrics.sleep_reference_high, (value) => `${formatNumber(value, 1)} h`);
  const restingRef = formatBand(metrics.resting_hr_reference_low, metrics.resting_hr_reference_high, formatHeartRate);
  const ratioRef = formatBand(metrics.load_ratio_reference_low ?? 0.9, metrics.load_ratio_reference_high ?? 1.2, (value) => formatNumber(value, 2));
  const cadenceRef = formatBand(metrics.cadence_reference_low, metrics.cadence_reference_high, (value) => `${formatNumber(value, 0)} spm`);
  const benchmarkText = benchmark?.event && benchmark?.pace_min_per_km ? `${benchmark.event} repère ${formatPace(benchmark.pace_min_per_km)}` : 'Courbe construite depuis les sorties utiles';
  const benchmarkSignal = benchmark?.event ? `${benchmark.event} · ${formatPace(benchmark.pace_min_per_km)}` : '-';
  const loadSubtitle = loadRef !== '-' ? `Réf ${loadRef}` : 'Charge de référence indisponible';
  const cadenceSubtitle = cadenceRef !== '-' ? `Réf ${cadenceRef}` : 'Cadence à contextualiser';
  return [
    { key:'weekly-volume', title:'Volume hebdo', value:formatKilometers(metrics.weekly_volume_km ?? metrics.total_distance_km_7d), subtitle:`${formatNumber(metrics.weekly_running_days ?? metrics.recent_running_days ?? 0)} sorties · fenêtre 90j`, detail:'Volume running uniquement. Le vélo et la muscu sont suivis à part pour éviter de contaminer la lecture endurance.', signals:[{label:'Dernier jour local',value:formatDateLabel(payload.latest_day || importStatus.latest_activity_day)},{label:'Dernier import',value:latestRun ? formatDateTime(latestRun.finished_at) : '-'}], chartType:'single', series:volumeSeries, tone:'primary' },
    { key:'bike-volume', title:'Vélo hebdo', value:formatKilometers(metrics.weekly_bike_volume_km), subtitle:`${formatNumber(metrics.weekly_bike_days ?? metrics.recent_bike_days ?? 0)} sorties vélo`, detail:'Le volume vélo est isolé du running pour garder des métriques d’endurance lisibles. Il reste utile, mais à part.', signals:[{label:'7 jours',value:formatKilometers(metrics.weekly_bike_volume_km)},{label:'Dernier import',value:latestRun ? formatDateTime(latestRun.finished_at) : '-'}], chartType:'single', series:bikeSeries },
    { key:'charge', title:'Charge', value:metrics.load_7d === null || metrics.load_7d === undefined ? '-' : formatNumber(metrics.load_7d,0), subtitle:loadSubtitle, detail:'La charge 7 jours doit toujours être lue avec un repère bas et un repère haut. Sans cela, le chiffre seul n’aide pas vraiment le coach.', signals:[{label:'28 jours',value:metrics.load_28d === null || metrics.load_28d === undefined ? '-' : formatNumber(metrics.load_28d,0)},{label:'Progression delta',value:metrics.progression_delta === null || metrics.progression_delta === undefined ? '-' : formatNumber(metrics.progression_delta,2)}], chartType:'single', series:loadSeries },
    { key:'charge-ratio', title:'Charge relative', value:metrics.load_ratio_7_28 === null || metrics.load_ratio_7_28 === undefined ? '-' : formatNumber(metrics.load_ratio_7_28,2), subtitle:`Réf ${ratioRef}`, detail:'Le ratio 7j/28j dit si la dynamique récente reste raisonnable. On le garde, mais avec un cadre de lecture clair pour éviter les fausses interprétations.', signals:[{label:'Fatigue',value:metrics.fatigue_flag ? 'Oui' : 'Non'},{label:'Overreaching',value:metrics.overreaching_flag ? 'Oui' : 'Non'}], chartType:'single', series:loadRatioChartSeries, tickFormatter:(value)=>formatNumber(value,2), stroke:'#ffbe55', fill:'rgba(255, 190, 85, 0.22)' },
    { key:'sleep', title:'Sommeil', value:metrics.sleep_hours_7d === null || metrics.sleep_hours_7d === undefined ? '-' : `${formatNumber(metrics.sleep_hours_7d,1)} h`, subtitle:sleepRef !== '-' ? `Réf ${sleepRef}` : 'Sommeil 7j', detail:'Le sommeil récent correspond à la moyenne des nuits sur 7 jours. Le but n’est pas d’avoir une valeur parfaite, mais un niveau compatible avec la charge du moment.', signals:[{label:'Récupération',value:metrics.overreaching_flag ? 'À surveiller' : 'Correcte'},{label:'Dernière activité',value:importStatus.latest_activity_day ? formatDateLabel(importStatus.latest_activity_day) : '-'}], chartType:'single', series:sleepChartSeries, tickFormatter:(value)=>`${formatNumber(value,1)} h`, stroke:'#8ae6c0', fill:'rgba(138, 230, 192, 0.2)' },
    { key:'resting-hr', title:'FC repos', value:formatHeartRate(metrics.resting_hr_7d), subtitle:restingRef !== '-' ? `Réf ${restingRef}` : 'FC repos 7j', detail:'La FC repos récente complète la lecture récupération / stress. Si elle monte en même temps que la charge, le coach doit rester prudent.', signals:[{label:'HRV 7j',value:metrics.hrv_7d === null || metrics.hrv_7d === undefined ? '-' : formatNumber(metrics.hrv_7d,1)},{label:'Fatigue',value:metrics.fatigue_flag ? 'Oui' : 'Non'}], chartType:'single', series:restingHrChartSeries, tickFormatter:(value)=>`${formatNumber(value,0)} bpm`, stroke:'#8ab4ff', fill:'rgba(138, 180, 255, 0.2)' },
    { key:'pace-hr', title:'Pace / FC', value:paceCurveLast ? `${formatPace(paceCurveLast.pace_min_per_km)} · ${formatHeartRate(paceCurveLast.heart_rate)}` : '-', subtitle:`Courbe monotone · ${paceCurve.length} points utiles`, detail:'La courbe conserve les points utiles des dernières sorties, puis les lisse pour rester monotone. Plus l’allure devient soutenue, plus la FC doit monter.', signals:[{label:'Premier point',value:paceCurveFirst ? `${formatPace(paceCurveFirst.pace_min_per_km)} · ${formatHeartRate(paceCurveFirst.heart_rate)}` : '-'},{label:'Benchmark retenu',value:benchmarkSignal}], chartType:'curve', curve:paceCurve, maxHrEstimate:metrics.max_hr_estimate },
    { key:'cadence', title:'Cadence', value:metrics.cadence_7d === null || metrics.cadence_7d === undefined ? '-' : `${formatNumber(metrics.cadence_7d,0)} spm`, subtitle:cadenceSubtitle, detail:'La cadence suit la qualité du geste et sa régularité sur les dernières sorties. On la lit avec l’allure et le volume, pour voir si la foulée évolue vraiment.', signals:[{label:'28 jours',value:metrics.cadence_28d === null || metrics.cadence_28d === undefined ? '-' : `${formatNumber(metrics.cadence_28d,0)} spm`},{label:'Référence',value:cadenceRef}], chartType:'single', series:cadenceValues, tone:'primary' },
  ];
}
function renderDashboardModal(card){
  if(!card)return;
  dom.dashboardModalTitle.textContent=card.title;
  dom.dashboardModalSubtitle.textContent=card.subtitle||'';
  dom.dashboardModalValue.textContent=card.value||'-';
  dom.dashboardModalText.innerHTML=`<p>${(card.detail||'').replace(/\n/g,'<br>')}</p>`;
  dom.dashboardModalSignals.innerHTML='';
  (card.signals||[]).forEach((signal)=>{
    const node=document.createElement('div');
    node.className='signal-line';
    node.innerHTML=`<strong>${signal.label}</strong><span>${signal.value||'-'}</span>`;
    dom.dashboardModalSignals.appendChild(node);
  });
  if(card.chartType==='single'){
    renderSparkline(dom.dashboardModalChart,card.series||[],{
      id:`modal-${card.key}`,
      stroke:card.stroke||('#8ab4ff'),
      fill:card.fill||'rgba(138, 180, 255, 0.22)',
      width:760,
      height:220,
      tickFormatter:card.tickFormatter,
      title:card.title,
      yLabel:card.key==='sleep'?'h':card.key==='resting-hr'?'bpm':card.key==='charge-ratio'?'ratio':'km',
    });
  }else if(card.chartType==='dual'){
    renderDualSparkline(dom.dashboardModalChart,card.seriesA||[],card.seriesB||[],{id:`modal-${card.key}`,width:760,height:120});
  }else if(card.chartType==='curve'){
    renderMonotonePaceCurve(dom.dashboardModalChart,card.curve||[],{id:`modal-${card.key}`,width:760,height:240,maxHrEstimate:card.maxHrEstimate});
  }else{
    dom.dashboardModalChart.innerHTML="<p class='status-line'>Cette carte n'a pas de courbe dédiée.</p>";
  }
  dom.dashboardModal.classList.remove('hidden');
}
function closeDashboardModal(){dom.dashboardModal.classList.add('hidden')}
function renderDashboardSection(){
  const payload=currentPayload();
  const analysis=currentAnalysis();
  const metrics=currentMetrics();
  const importStatus=currentImportStatus();
  const trend=analysis.trend||{};
  const runningSeries=Array.isArray(trend.daily_volume)?trend.daily_volume:[];
  const bikeSeries=Array.isArray(trend.daily_bike_volume)?trend.daily_bike_volume:[];
  const loadRatioSeries=Array.isArray(trend.daily_load_ratio)?trend.daily_load_ratio:[];
  const sleepSeries=Array.isArray(trend.daily_sleep)?trend.daily_sleep:[];
  const restingHrSeries=Array.isArray(trend.daily_resting_hr)?trend.daily_resting_hr:[];
  const cadenceTrendValues=Array.isArray(trend.cadence_daily)?trend.cadence_daily.map((row)=>row.cadence_spm||0):[];
  dom.dashboardImportState.textContent=metrics.weekly_volume_km===null||metrics.weekly_volume_km===undefined?'-':formatKilometers(metrics.weekly_volume_km);
  dom.dashboardImportDetail.textContent=metrics.weekly_running_days!==null&&metrics.weekly_running_days!==undefined?`${formatNumber(metrics.weekly_running_days,0)} sorties sur 7j · ${Array.isArray(runningSeries)?runningSeries.length:0} jours analysés`:'Volume running non disponible';
  if(dom.dashboardBikeState) dom.dashboardBikeState.textContent=metrics.weekly_bike_volume_km===null||metrics.weekly_bike_volume_km===undefined?'-':formatKilometers(metrics.weekly_bike_volume_km);
  if(dom.dashboardBikeDetail) dom.dashboardBikeDetail.textContent=metrics.weekly_bike_volume_km===null||metrics.weekly_bike_volume_km===undefined?'Volume vélo non disponible':'Vélo isolé du running pour garder les métriques lisibles.';
  dom.coverageCard.textContent=metrics.load_7d===null||metrics.load_7d===undefined?'-':formatNumber(metrics.load_7d,0);
  dom.coverageSubtitle.textContent=metrics.load_reference_low!==null&&metrics.load_reference_low!==undefined&&metrics.load_reference_high!==null&&metrics.load_reference_high!==undefined?`Réf ${formatNumber(metrics.load_reference_low,0)}-${formatNumber(metrics.load_reference_high,0)} u`:'Charge sans référence';
  dom.analysisCard.textContent=metrics.cadence_7d===null||metrics.cadence_7d===undefined?'-':`${formatNumber(metrics.cadence_7d,0)} spm`;
  dom.analysisSubtitle.textContent=metrics.cadence_reference_low!==null&&metrics.cadence_reference_low!==undefined&&metrics.cadence_reference_high!==null&&metrics.cadence_reference_high!==undefined?`Réf ${formatNumber(metrics.cadence_reference_low,0)}-${formatNumber(metrics.cadence_reference_high,0)} spm`:'Cadence sans référence';
  dom.volumeTrendSummary.textContent=runningSeries.length?`${formatKilometers((runningSeries||[]).reduce((sum,row)=>sum+(row.distance_km||0),0))} sur ${runningSeries.length} jours`:'Pas encore de série';
  renderSparkline(dom.volumeTrend,runningSeries.map((row)=>({value:row.distance_km||0,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})),{id:'volume',stroke:'#8ae6c0',fill:'rgba(138, 230, 192, 0.35)',height:128,width:360,title:'Volume running',yLabel:'km'});
  if(dom.bikeVolumeTrendSummary) dom.bikeVolumeTrendSummary.textContent=bikeSeries.length?`${formatKilometers((bikeSeries||[]).reduce((sum,row)=>sum+(row.distance_km||0),0))} sur ${bikeSeries.length} jours`:'Pas encore de série vélo';
  if(dom.bikeVolumeTrend) renderSparkline(dom.bikeVolumeTrend,bikeSeries.map((row)=>({value:row.distance_km||0,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})),{id:'bike-volume',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.26)',height:128,width:360,title:'Volume vélo',yLabel:'km'});
  if(dom.loadRatioTrendSummary) dom.loadRatioTrendSummary.textContent=loadRatioSeries.length?`${formatNumber(loadRatioSeries.at(-1)?.load_ratio_7_28,2)} · ${loadRatioSeries.length} jours`:'Pas encore de ratio';
  if(dom.loadRatioTrend) renderSparkline(dom.loadRatioTrend,loadRatioSeries.map((row)=>({value:row.load_ratio_7_28,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row)=>Number.isFinite(Number(row.value))),{id:'load-ratio',stroke:'#ffbe55',fill:'rgba(255, 190, 85, 0.22)',height:128,width:360,title:'Charge relative',yLabel:'ratio',tickFormatter:(value)=>formatNumber(value,2)});
  if(dom.sleepTrendSummary) dom.sleepTrendSummary.textContent=sleepSeries.length?`${formatNumber(sleepSeries.at(-1)?.sleep_hours,1)} h · ${sleepSeries.length} jours`:'Pas encore de sommeil';
  if(dom.sleepTrend) renderSparkline(dom.sleepTrend,sleepSeries.map((row)=>({value:row.sleep_hours,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row)=>Number.isFinite(Number(row.value))),{id:'sleep',stroke:'#8ae6c0',fill:'rgba(138, 230, 192, 0.2)',height:128,width:360,title:'Sommeil',yLabel:'h',tickFormatter:(value)=>`${formatNumber(value,1)} h`});
  if(dom.restingHrTrendSummary) dom.restingHrTrendSummary.textContent=restingHrSeries.length?`${formatNumber(restingHrSeries.at(-1)?.resting_hr,0)} bpm · ${restingHrSeries.length} jours`:'Pas encore de FC repos';
  if(dom.restingHrTrend) renderSparkline(dom.restingHrTrend,restingHrSeries.map((row)=>({value:row.resting_hr,label:formatShortDateLabel(row.metric_date),detail:formatDateLabel(row.metric_date)})).filter((row)=>Number.isFinite(Number(row.value))),{id:'resting-hr',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.2)',height:128,width:360,title:'FC repos',yLabel:'bpm',tickFormatter:(value)=>`${formatNumber(value,0)} bpm`});
  const paceSummary=Array.isArray(trend.pace_hr_curve)&&trend.pace_hr_curve.length?`${formatPace(trend.pace_hr_curve[0].pace_min_per_km)} → ${formatPace(trend.pace_hr_curve.at(-1).pace_min_per_km)} · ${trend.pace_hr_curve.length} points`:'Pas encore de courbe';
  dom.paceHrTrendSummary.textContent=paceSummary;
  renderMonotonePaceCurve(dom.paceHrTrend,trend.pace_hr_curve||[],{id:'pace-hr',width:360,height:240,maxHrEstimate:metrics.max_hr_estimate});
  dom.cadenceTrendSummary.textContent=cadenceTrendValues.length?`${formatNumber(cadenceTrendValues.at(-1),0)} spm · ${cadenceTrendValues.length} jours`:'Pas encore de cadence';
  renderSparkline(dom.cadenceTrend,cadenceTrendValues.map((value,index)=>({value,label:formatShortDateLabel((trend.cadence_daily||[])[index]?.metric_date),detail:formatDateLabel((trend.cadence_daily||[])[index]?.metric_date)})),{id:'cadence',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.26)',height:128,width:360,title:'Cadence',yLabel:'spm',tickFormatter:(value)=>`${formatNumber(value,0)} spm`});
  dom.dashboardCards.innerHTML='';dashboardCardSpecs(payload).forEach((card)=>{const button=document.createElement('button');button.type='button';button.className=`metric-card${card.tone==='primary'?' is-primary':''}`;button.innerHTML=`<span class='card-label'>${card.title}</span><strong>${card.value}</strong><p>${card.subtitle||''}</p>`;button.addEventListener('click',()=>{addTerminalLog('info','dashboard',`Carte ouverte: ${card.title}`);renderDashboardModal(card)});dom.dashboardCards.appendChild(button)})
}
function renderCoachSection(){const payload=currentPayload();const importStatus=currentImportStatus();const analysis=currentAnalysis();const provider=payload.provider||{};const providerText=provider.status==='ready'?`${provider.provider==='ollama'?'Ollama':provider.provider} prêt`:provider.status==='unchecked'?`${provider.provider||state.provider} en vérification`:`${provider.provider||state.provider} indisponible`;const items=[importStatus.available?'Données locales prêtes':'Pas de données locales',analysis.available?'Analyse locale prête':'Analyse locale partielle',`Provider: ${providerText}`];if(state.goalText)items.push(`Objectif actif: ${state.goalText.slice(0,80)}${state.goalText.length>80?'?':''}`);dom.coachStatusStrip.innerHTML='';items.forEach((text)=>{const pill=document.createElement('span');pill.className=`pill pill-small${/indisponible|partielle|pas de données|attente/i.test(text)?' warn':''}`;pill.textContent=text;dom.coachStatusStrip.appendChild(pill)});dom.coachWorkspaceInput.value=state.workspace;dom.providerSelect.value=state.provider;dom.transcript.dataset.empty='Le coach t?attend ici. Décris un objectif et laisse-le poser les bonnes questions.';dom.planList.dataset.empty='Aucun plan génér? pour le moment.'}
function renderTerminalSection(){const entries=state.terminalLogs.filter((entry)=>state.terminalLevels[entry.level]!==false);dom.terminalLog.innerHTML='';if(!entries.length){dom.terminalLog.dataset.empty='Aucun log visible pour le niveau s?lectionn?.'}else{delete dom.terminalLog.dataset.empty}entries.slice(-250).forEach((entry)=>{const node=document.createElement('article');node.className=`terminal-entry ${entry.level}`;node.innerHTML=`<div class='terminal-entry-header'><span>${formatDateTime(entry.timestamp)} ? ${entry.level.toUpperCase()} ? ${entry.source}</span></div><strong>${entry.message}</strong>${entry.details?`<div class='entry-message'>${entry.details}</div>`:''}`;dom.terminalLog.appendChild(node)});dom.terminalSummary.textContent=`${entries.length} entr?e(s) visible(s) sur ${state.terminalLogs.length} total.`;dom.levelButtons.forEach((button)=>button.classList.toggle('active',state.terminalLevels[button.dataset.level]!==false))}
function renderSettingsSection(){syncInputsFromState();renderBootTrace();renderAuthDebug()}
function buildDiagnosticsSummary(){const payload=currentPayload();const importStatus=currentImportStatus();const provider=payload.provider||{};return[`build=${APP_VERSION}`,`bootId=${state.bootId}`,`bootTraceEvents=${state.bootTrace.length}`,`url=${window.location.href}`,`hash=${window.location.hash||'#import'}`,`activeSection=${state.activeSection}`,`workspace=${state.workspace}`,`provider=${state.provider}`,`providerStatus=${provider.status||'unknown'}`,`dataAvailable=${importStatus.available?'yes':'no'}`,`latestDay=${importStatus.latest_activity_day||payload.latest_day||'-'}`,`swState=${runtimeInfo.serviceWorkerState}`,`swController=${runtimeInfo.serviceWorkerController?'yes':'no'}`,`swScope=${runtimeInfo.serviceWorkerScope}`,`online=${navigator.onLine?'yes':'no'}`].join('\n')}
function renderDiagnostics(){
  const payload = currentPayload();
  const importStatus = currentImportStatus();
  const provider = payload.provider || {};
  const latestDay = importStatus.latest_activity_day || payload.latest_day || null;
  const syncAttempt = state.lastGarminSync || {};
  if (dom.diagnosticBuild) dom.diagnosticBuild.textContent = `Build ${APP_VERSION}`;
  if (dom.diagnosticBuildDetail) dom.diagnosticBuildDetail.textContent = `${window.location.hostname || 'localhost'} · ${navigator.userAgent.includes('Firefox') ? 'Firefox' : 'Browser'} · ${navigator.onLine ? 'online' : 'offline'}`;
  if (dom.diagnosticUrl) dom.diagnosticUrl.textContent = window.location.href;
  if (dom.diagnosticUrlDetail) dom.diagnosticUrlDetail.textContent = `hash ${window.location.hash || '#import'} · active ${state.activeSection}`;
  if (dom.diagnosticSw) dom.diagnosticSw.textContent = `${runtimeInfo.serviceWorkerState}${runtimeInfo.serviceWorkerController ? ' · controller' : ' · no controller'}`;
  if (dom.diagnosticSwDetail) dom.diagnosticSwDetail.textContent = `scope ${runtimeInfo.serviceWorkerScope || '-'} · checked ${runtimeInfo.lastCheckedAt ? formatDateTime(runtimeInfo.lastCheckedAt) : '-'}`;
  if (dom.diagnosticWorkspace) dom.diagnosticWorkspace.textContent = state.workspace;
  if (dom.diagnosticWorkspaceDetail) dom.diagnosticWorkspaceDetail.textContent = payload.workspace?.exists ? 'Workspace local disponible' : 'Workspace local absent';
  if (dom.diagnosticImport) dom.diagnosticImport.textContent = importStatus.available ? 'Données locales prêtes' : 'Aucune donnée locale';
  if (dom.diagnosticImportDetail) dom.diagnosticImportDetail.textContent = latestDay ? `Dernière activité ${formatDateLabel(latestDay)} · données exploitées ${payload.coverage_ratio === null || payload.coverage_ratio === undefined ? '-' : `${formatNumber(payload.coverage_ratio * 100,0)}%`}` : 'Aucune activité indexée';
  if (dom.diagnosticProvider) dom.diagnosticProvider.textContent = provider.status === 'ready' ? `${provider.provider === 'ollama' ? 'Ollama' : provider.provider} prêt` : provider.status === 'unchecked' ? `${provider.provider || state.provider} en vérification` : `${provider.provider || state.provider} indisponible`;
  if (dom.diagnosticProviderDetail) dom.diagnosticProviderDetail.textContent = provider.model ? `model ${provider.model}` : 'provider sans modèle détecté';
  if (dom.diagnosticSummary) dom.diagnosticSummary.textContent = buildDiagnosticsSummary();
  if (dom.bootTraceState) dom.bootTraceState.textContent = state.bootTrace.length ? `Trace active (${state.bootTrace.length})` : 'Aucune trace';
  if (dom.bootTraceDetail) dom.bootTraceDetail.textContent = state.bootTrace.at(-1) ? formatBootTraceEvent(state.bootTrace.at(-1)) : 'Aucun événement enregistré.';
  if (dom.bootTraceLog) dom.bootTraceLog.textContent = state.bootTrace.length ? state.bootTrace.map((entry) => formatBootTraceEvent(entry)).join('\n') : 'Aucun événement de boot pour le moment.';
  if (dom.importSyncState && syncAttempt.status) {
    dom.importSyncState.textContent = syncAttempt.status === 'success' ? 'Sync Garmin Connect prête' : syncAttempt.status === 'running' ? 'Sync Garmin Connect en cours' : syncAttempt.status === 'error' ? 'Sync Garmin Connect échouée' : 'Sync Garmin Connect';
  }
  if (dom.importSyncDetail && syncAttempt.message) dom.importSyncDetail.textContent = syncAttempt.message;
}async function refreshRuntimeDiagnostics(){
  runtimeInfo.lastCheckedAt = new Date().toISOString();
  if ('serviceWorker' in navigator) {
    try {
      const registration = await navigator.serviceWorker.getRegistration();
      runtimeInfo.serviceWorkerState = registration ? (registration.active ? 'active' : 'registered') : 'none';
      runtimeInfo.serviceWorkerScope = registration?.scope || '-';
      runtimeInfo.serviceWorkerController = !!navigator.serviceWorker.controller;
    } catch {
      runtimeInfo.serviceWorkerState = 'error';
      runtimeInfo.serviceWorkerScope = '-';
      runtimeInfo.serviceWorkerController = !!navigator.serviceWorker.controller;
    }
  } else {
    runtimeInfo.serviceWorkerState = 'unsupported';
    runtimeInfo.serviceWorkerScope = '-';
    runtimeInfo.serviceWorkerController = false;
  }
  renderDiagnostics();
}async function openDiagnostics(){await refreshRuntimeDiagnostics();dom.diagnosticModal.classList.remove('hidden')}
function closeDiagnostics(){dom.diagnosticModal.classList.add('hidden')}
function renderAllSections(){renderSectionVisibility();renderSidebarStatus();renderSectionHeader();renderImportSection();renderDashboardSection();renderCoachSection();renderTerminalSection();renderSettingsSection()}
function showRetryableError(error,retryAction){setBusy(false);setCoachError(buildProviderErrorMessage(error),retryAction,buildProviderErrorTitle(error));addMessage('assistant',buildProviderErrorMessage(error))}
async function refreshDashboard({quiet=false,reason='manual'}={}){persistSettings();const runner=async()=>{recordBoot('dashboard:refresh-start',`reason=${reason}`);const payload=await requestJson(`/api/status?data_dir=${encodeURIComponent(state.workspace)}&provider=${encodeURIComponent(state.provider)}&base_url=${encodeURIComponent(state.baseUrl)}&probe=1`,{},'status');state.dashboardPayload=payload;renderAllSections();recordBoot('dashboard:refresh-ok',`reason=${reason}`);return payload};if(quiet)return runner();return withBusy('Lecture du workspace local...',runner)}
async function recalculateData(){persistSettings();if(dom.reprocessButton) dom.reprocessButton.disabled=true;addTerminalLog('info','reprocess','Recalcul local demandé',state.workspace);try{const payload=await withBusy('Recalcul des données locales...',async()=>requestJson('/api/recalculate',{method:'POST',body:JSON.stringify({data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null})},'recalculate'));state.dashboardPayload=payload.dashboard||state.dashboardPayload;addMessage('assistant',payload.message||'Retraitement local terminé.');addTerminalLog('info','reprocess',payload.message||'Retraitement local terminé.',payload.analytics?.report_path||'analytics recalculées');await refreshDashboard({quiet:true,reason:'recalculate'});renderAllSections()}catch(error){addTerminalLog('error','reprocess','Recalcul local échoué',error.message);showRetryableError(error,recalculateData)}finally{if(dom.reprocessButton) dom.reprocessButton.disabled=false}}
async function prepareCoach(){persistSettings();const goalText=normalizeText(dom.goalInput.value.trim());if(!goalText){addMessage('assistant','J\'ai besoin d\'un objectif running pour démarrer.');addTerminalLog('warn','coach','Préparation impossible','Objectif manquant.');return}addMessage('user',goalText);addTerminalLog('info','coach','Préparation du coach',goalText);try{const payload=await withBusy('Le coach analyse les données locales...',async()=>requestJson('/api/coach/prepare',{method:'POST',body:JSON.stringify({goal_text:goalText,data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null})},'coach-prepare'));if(payload.questions?.length){addMessage('assistant','Je veux préciser quelques points avant de proposer un plan.');renderQuestions(payload.questions);addTerminalLog('info','coach','Questions générées',`${payload.questions.length} question(s)`)}else{renderQuestions([]);addTerminalLog('info','coach','Aucune clarification requise')}state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();if(payload.analysis?.analysis_summary)addMessage('assistant',payload.analysis.analysis_summary)}catch(error){showRetryableError(error,prepareCoach)}}
function renderSummary(payload){const analysis=payload.analysis||{};const lines=[];if(payload.coach_summary)lines.push(payload.coach_summary);if(analysis.training_phase)lines.push(`Phase: ${analysis.training_phase}`);if(analysis.benchmark?.event){const pace=analysis.benchmark.pace_min_per_km?` ? ${formatPace(analysis.benchmark.pace_min_per_km)}`:'';lines.push(`Benchmark retenu: ${analysis.benchmark.event}${pace}`)}dom.coachSummary.textContent=lines.join('\n\n')||'Aucun plan génér? pour le moment.';dom.planList.innerHTML='';(payload.weekly_plan||[]).forEach((session)=>{const item=document.createElement('article');item.className='plan-item';item.innerHTML=`<strong>${session.day} - ${session.session_title}</strong><span>${session.duration_minutes} min | ${session.intensity}</span><p>${session.objective||''}</p><p>${session.notes||''}</p>`;dom.planList.appendChild(item)})}
async function generatePlan(){persistSettings();const goalText=normalizeText(dom.goalInput.value.trim());if(!goalText){addMessage('assistant','Entre d\'abord un objectif running.');addTerminalLog('warn','coach','Plan impossible','Objectif manquant.');return}addTerminalLog('info','coach','Génération du plan',goalText);try{const payload=await withBusy('Le modèle prépare le plan...',async()=>requestJson('/api/coach/plan',{method:'POST',body:JSON.stringify({goal_text:goalText,data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null,answers:state.answers})},'coach-plan'));if(payload.needs_clarification){renderQuestions(payload.questions);addMessage('assistant','Il me manque encore quelques réponses pour construire le plan.');addTerminalLog('warn','coach','Clarifications manquantes',`${payload.questions.length} question(s)`);state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();return}addMessage('assistant',payload.coach_summary||'Plan généré.');if(payload.signals_used?.length)addMessage('assistant',`Signaux utilisés: ${payload.signals_used.join(', ')}`);renderSummary(payload);state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();addTerminalLog('info','coach','Plan généré',payload.plan_path||'plan local enregistré')}catch(error){showRetryableError(error,generatePlan)}}
async function importGarmin(){persistSettings();const sourcePath=normalizeText((dom.sourcePathInput.value||dom.sourcePathInputSettings.value).trim());if(!sourcePath){addMessage('assistant','Indique le chemin local de l\'export Garmin à importer.');addTerminalLog('warn','import','Import impossible','Chemin source manquant.');return}addTerminalLog('info','import','Import Garmin demandé',sourcePath);try{const payload=await withBusy('Import Garmin en cours...',async()=>requestJson('/api/import',{method:'POST',body:JSON.stringify({source_path:sourcePath,data_dir:state.workspace,run_label:'pwa-import'})},'import'));state.dashboardPayload=payload.dashboard||state.dashboardPayload;addMessage('assistant',`Import terminé: ${payload.artifacts_imported} artefacts, ${payload.total_records} enregistrements.`);addTerminalLog('info','import','Import terminé',`${payload.artifacts_imported||0} artefacts, ${payload.total_records||0} enregistrements`);await refreshDashboard()}catch(error){addTerminalLog('error','import','Import échoué',error.message);showRetryableError(error,importGarmin)}}
async function syncGarminConnect(){persistSettings();if(dom.syncButton)dom.syncButton.disabled=true;state.lastGarminSync={status:'running',message:'Synchronisation Garmin Connect en cours...',at:new Date().toISOString()};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));renderImportSection();addTerminalLog('info','sync','Synchronisation Garmin Connect demandée',`workspace ${state.workspace}`);try{const payload=await requestJson('/api/sync/garmin-connect',{method:'POST',body:JSON.stringify({data_dir:state.workspace,run_label:'pwa-garmin-sync'})},'garmin-sync');state.dashboardPayload=payload.dashboard||state.dashboardPayload;state.lastGarminSync={status:'success',message:'Synchronisation Garmin Connect réussie',at:new Date().toISOString(),result:payload};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));addTerminalLog('info','sync','Synchronisation Garmin Connect réussie',payload.run_id||payload.source_kind||'sync ok');await refreshDashboard({quiet:true,reason:'garmin-sync'});renderImportSection()}catch(error){state.lastGarminSync={status:'error',message:`Synchronisation Garmin Connect échouée: ${error.message}`,at:new Date().toISOString(),error:error.message};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));renderImportSection();addTerminalLog('warn','sync','Synchronisation Garmin Connect échouée',error.message);addMessage('assistant',state.lastGarminSync.message)}finally{if(dom.syncButton)dom.syncButton.disabled=false}}
function saveGoal(){persistSettings();addTerminalLog('info','coach','Objectif enregistré',state.goalText||'vide');addMessage('assistant','Objectif enregistré localement.');renderSidebarStatus()}
function useLastWorkspace(){const lastWorkspace=localStorage.getItem(STORAGE_KEYS.workspace)||state.workspace||'data';state.workspace=lastWorkspace;syncInputsFromState();persistSettings();addMessage('assistant',`Dernier workspace local réutilisé: ${state.workspace}`);addTerminalLog('info','workspace','Workspace local réutilisé',state.workspace);refreshDashboard({reason:'reuse-last-workspace'}).catch(()=>{})}
function clearTerminal(){state.terminalLogs=[];saveTerminalLogs();renderTerminalSection();addTerminalLog('info','terminal','Journal nettoy?')}
function updateTerminalLevel(level){state.terminalLevels[level]=!state.terminalLevels[level];if(Object.values(state.terminalLevels).every((value)=>value===false)){state.terminalLevels[level]=true}localStorage.setItem(STORAGE_KEYS.terminalLevels,JSON.stringify(state.terminalLevels));renderTerminalSection()}
function wireEvents(){dom.navButtons.forEach((button)=>{button.addEventListener('click',(event)=>{const section=button.dataset.section;if(!section)return;event?.preventDefault?.();setActiveSection(section)})});dom.navButtons.forEach((button)=>{button.setAttribute('aria-pressed',String(button.dataset.section===state.activeSection))});if(dom.diagnosticButton)dom.diagnosticButton.addEventListener('click',openDiagnostics);if(dom.diagnosticModalClose)dom.diagnosticModalClose.addEventListener('click',closeDiagnostics);if(dom.diagnosticRefreshButton)dom.diagnosticRefreshButton.addEventListener('click',refreshRuntimeDiagnostics);if(dom.diagnosticCopyButton)dom.diagnosticCopyButton.addEventListener('click',async()=>{const text=buildDiagnosticsSummary();try{await navigator.clipboard.writeText(text);addTerminalLog('info','diagnostic','Résumé copié',text)}catch{addTerminalLog('warn','diagnostic','Copie impossible','Le navigateur a bloqué le presse-papiers.')}});if(dom.bootTraceRefreshButton)dom.bootTraceRefreshButton.addEventListener('click',()=>{refreshBootTrace().catch(()=>{})});dom.saveSettingsButton.addEventListener('click',async()=>{persistSettings();addMessage('assistant','Réglages sauvegardés localement.');addTerminalLog('info','settings','Réglages sauvegardés');await refreshDashboard()});dom.refreshSettingsButton.addEventListener('click',()=>refreshDashboard({reason:'settings-refresh'}));dom.saveGoalButton.addEventListener('click',saveGoal);dom.prepareButton.addEventListener('click',prepareCoach);dom.planButton.addEventListener('click',generatePlan);dom.importButton.addEventListener('click',importGarmin);if(dom.syncButton)dom.syncButton.addEventListener('click',syncGarminConnect);if(dom.reprocessButton)dom.reprocessButton.addEventListener('click',recalculateData);dom.refreshButton.addEventListener('click',()=>refreshDashboard({reason:'manual-refresh'}));dom.useLastWorkspaceButton.addEventListener('click',useLastWorkspace);dom.retryButton.addEventListener('click',()=>{if(typeof state.retryAction==='function'){addTerminalLog('info','retry','Nouvelle tentative demandée');state.retryAction()}});dom.terminalClearButton.addEventListener('click',clearTerminal);dom.levelButtons.forEach((button)=>button.addEventListener('click',()=>updateTerminalLevel(button.dataset.level)));dom.themeSelect.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`Thème ${state.theme}`)});dom.startSectionSelect.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`Section de départ ${state.startSection}`)});dom.showTerminalToggle.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`Terminal menu ${state.showTerminalMenu?'visible':'masqué'}`);updateNavVisibility();renderAllSections()});dom.providerSelect.addEventListener('change',()=>{state.provider=dom.providerSelect.value;dom.settingsProviderSelect.value=state.provider;persistSettings();addTerminalLog('info','provider',`Provider actif ${state.provider}`);refreshDashboard({reason:'provider-change'}).catch(()=>{})});dom.settingsProviderSelect.addEventListener('change',()=>{state.provider=dom.settingsProviderSelect.value;dom.providerSelect.value=state.provider;persistSettings();addTerminalLog('info','provider',`Provider actif ${state.provider}`);refreshDashboard({reason:'provider-change'}).catch(()=>{})});dom.dashboardModal.addEventListener('click',(event)=>{if(event.target===dom.dashboardModal)closeDashboardModal()});dom.dashboardModalClose.addEventListener('click',closeDashboardModal);dom.diagnosticModal.addEventListener('click',(event)=>{if(event.target===dom.diagnosticModal)closeDiagnostics()});window.addEventListener('keydown',(event)=>{if(event.key==='Escape'){closeDashboardModal();closeDiagnostics()}});[dom.workspaceInputSettings,dom.sourcePathInput,dom.sourcePathInputSettings,dom.baseUrlInput,dom.apiKeyInput,dom.goalInput].forEach((input)=>{input.addEventListener('input',()=>{persistSettings();renderSidebarStatus();if(input===dom.goalInput)dom.coachWorkspaceInput.value=state.workspace})});window.addEventListener('hashchange',()=>{const next=(window.location.hash||'#import').slice(1);if(SECTIONS.includes(next)&&next!==state.activeSection){setActiveSection(next,{updateHash:false})}})}
async function bootstrap(){window.__coachAppReady=false;state.bootId=`${APP_VERSION}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;localStorage.setItem(STORAGE_KEYS.bootId,state.bootId);setAppChip('App: initialisation...');applyTheme();syncInputsFromState();recordBoot('boot:start','bootstrap launched');wireEvents();recordBoot('boot:events','listeners bound');updateNavVisibility();renderSectionHeader();renderSidebarStatus();renderDiagnostics();renderBootTrace();addMessage('assistant','Commence par décrire ton objectif. Je peux ensuite poser les questions manquantes puis générer un plan.');addTerminalLog('info','app','Application d?marr?e',`Workspace ${state.workspace}`);const initialSection=window.location.hash&&SECTIONS.includes(window.location.hash.slice(1))?window.location.hash.slice(1):state.startSection||'import';setActiveSection(initialSection,{persist:false,updateHash:false});renderAllSections();setAppChip('App: prête');window.__coachAppReady=true;window.__coachModuleReady=true;recordBoot('boot:ready',`section=${state.activeSection}`);void refreshRuntimeDiagnostics().catch((error)=>{recordBoot('diagnostic:error',error.message,{state:'warn'});});void refreshBootTrace().catch(()=>{});const bootPendingTimer=setTimeout(()=>{if(!state.dashboardPayload){recordBoot('dashboard:pending','status still loading after 10s',{state:'warn'});addTerminalLog('warn','boot','Dashboard encore en cours','Le chargement du workspace d?passe 10s.')}},10000);void refreshDashboard({quiet:true,reason:'boot'}).then(()=>{recordBoot('dashboard:ready','initial payload loaded')}).catch((error)=>{recordBoot('dashboard:error',error.message,{state:'warn'});addTerminalLog('error','status','Dashboard indisponible',error.message);if(dom.providerChip){dom.providerChip.textContent='Provider indisponible';dom.providerChip.classList.add('error')}if(dom.dataChip){dom.dataChip.textContent='Données: indisponible'}if(dom.workspaceChip){dom.workspaceChip.textContent='Workspace: indisponible'}}).finally(()=>clearTimeout(bootPendingTimer))}
window.addEventListener('beforeinstallprompt',(event)=>{event.preventDefault();state.installPrompt=event;dom.installButton.classList.remove('hidden')});
dom.installButton.addEventListener('click',async()=>{if(!state.installPrompt)return;state.installPrompt.prompt();await state.installPrompt.userChoice;state.installPrompt=null;dom.installButton.classList.add('hidden');addTerminalLog('info','pwa','Installation PWA demand?e')});
function bootApp(){bootstrap().catch((error)=>{addMessage('assistant',error.message);addTerminalLog('error','app','Erreur au d?marrage',error.message);setBusy(false);setAppChip('App: erreur d?marrage','error');if(dom.providerChip){dom.providerChip.textContent='Erreur au d?marrage';dom.providerChip.classList.add('error')}})}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',bootApp,{once:true})}else{queueMicrotask(bootApp)}
if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js?v='+APP_VERSION).catch(()=>{/* best effort */})})}












