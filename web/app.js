const STORAGE_KEYS={workspace:'coachGarmin.workspace',provider:'coachGarmin.provider',baseUrl:'coachGarmin.baseUrl',apiKey:'coachGarmin.apiKey',sourcePath:'coachGarmin.sourcePath',goalText:'coachGarmin.goalText',theme:'coachGarmin.theme',activeSection:'coachGarmin.activeSection',showTerminalMenu:'coachGarmin.showTerminalMenu',startSection:'coachGarmin.startSection',dashboardWindowDays:'coachGarmin.dashboardWindowDays',terminalLevels:'coachGarmin.terminalLevels',terminalLogs:'coachGarmin.terminalLogs',bootId:'coachGarmin.bootId',lastGarminSync:'coachGarmin.lastGarminSync',lastGarminAuthTest:'coachGarmin.lastGarminAuthTest'};
const DEFAULT_TERMINAL_LEVELS={debug:true,info:true,warn:true,error:true};
const SECTIONS=['import','dashboard','coach','terminal','settings'];
const APP_VERSION='20260415-navfix29';
window.__coachModuleLoaded=true;
window.__coachModuleReady=false;
const runtimeInfo={serviceWorkerState:'unknown',serviceWorkerScope:'-',serviceWorkerController:false,lastCheckedAt:null};
var paceCurveDebug=window.paceCurveDebug||{};
var paceDiagnostics=window.paceDiagnostics||{};
function loadStoredText(key,fallback=''){try{return repairMojibakeText(localStorage.getItem(key)||fallback)}catch{return fallback}}
function loadStoredObject(key,fallback){try{const raw=localStorage.getItem(key);if(!raw)return fallback;return repairTextTree(JSON.parse(raw))}catch{return fallback}}
const sectionMeta={import:{eyebrow:'Import',title:'Import',description:'Commence ici pour voir les données locales, la fraîcheur du workspace et lancer un import ou une sync si besoin.'},dashboard:{eyebrow:'Dashboard',title:'Dashboard',description:'Lis les cartes clés, ouvre une métrique en modal plein écran et regarde les tendances les plus utiles.'},coach:{eyebrow:'Chat',title:'Chat coach',description:'Décris ton objectif, laisse le coach poser les bonnes questions, puis génère un plan lié aux données locales.'},terminal:{eyebrow:'Terminal',title:'Terminal',description:'Inspecte les logs d’action, de réseau et d’erreur avec un filtre de niveau juste au-dessus.'},settings:{eyebrow:'Settings',title:'Settings',description:'Règle le thème, le provider IA, le workspace local et les options techniques utiles.'}};
const state={workspace:loadStoredText(STORAGE_KEYS.workspace,'data'),provider:loadStoredText(STORAGE_KEYS.provider,'ollama'),baseUrl:loadStoredText(STORAGE_KEYS.baseUrl,''),apiKey:loadStoredText(STORAGE_KEYS.apiKey,''),sourcePath:loadStoredText(STORAGE_KEYS.sourcePath,''),goalText:loadStoredText(STORAGE_KEYS.goalText,''),theme:loadStoredText(STORAGE_KEYS.theme,'data-lab'),activeSection:loadStoredText(STORAGE_KEYS.activeSection,'import'),showTerminalMenu:loadStoredText(STORAGE_KEYS.showTerminalMenu,'true')!=='false',startSection:loadStoredText(STORAGE_KEYS.startSection,'import'),dashboardWindowDays:normalizeDashboardWindowDays(loadStoredText(STORAGE_KEYS.dashboardWindowDays,'90')),openTrendKey:null,terminalLevels:loadTerminalLevels(),terminalLogs:loadTerminalLogs(),currentQuestions:[],answers:{},installPrompt:null,dashboardPayload:null,retryAction:null,bootTrace:[],bootErrors:[],lastGarminSync:loadLastGarminSync(),lastGarminAuthTest:loadLastGarminAuthTest(),bootId:loadStoredText(STORAGE_KEYS.bootId,String(Date.now()))};
const $=(id)=>document.getElementById(id);
const dom={appChip:$('app-chip'),providerChip:$('provider-chip'),dataChip:$('data-chip'),freshnessChip:$('freshness-chip'),objectiveChip:$('objective-chip'),workspaceChip:$('workspace-chip'),buildChip:$('build-chip'),sidebarNav:$('sidebar-nav'),sectionEyebrow:$('section-eyebrow'),sectionTitle:$('section-title'),sectionDescription:$('section-description'),sectionBadges:$('section-badges'),installButton:$('install-button'),diagnosticButton:$('diagnostic-button'),transcript:$('chat-transcript'),questions:$('questions'),coachSummary:$('coach-summary'),planList:$('plan-list'),busyBanner:$('busy-banner'),busyText:$('busy-text'),coachErrorBanner:$('coach-error-banner'),coachErrorTitle:$('coach-error-title'),coachErrorMessage:$('coach-error-message'),retryButton:$('retry-button'),dashboardCards:$('dashboard-cards'),dashboardImportState:$('dashboard-import-state'),dashboardImportDetail:$('dashboard-import-detail'),dashboardBikeState:$('dashboard-bike-state'),dashboardBikeDetail:$('dashboard-bike-detail'),dashboardHrvState:$('dashboard-hrv-state'),dashboardHrvDetail:$('dashboard-hrv-detail'),coverageCard:$('coverage-card'),coverageSubtitle:$('coverage-subtitle'),analysisCard:$('analysis-card'),analysisSubtitle:$('analysis-subtitle'),volumeTrendSummary:$('volume-trend-summary'),bikeVolumeTrendSummary:$('bike-volume-trend-summary'),loadRatioTrendSummary:$('load-ratio-trend-summary'),sleepTrendSummary:$('sleep-trend-summary'),restingHrTrendSummary:$('resting-hr-trend-summary'),hrvTrendSummary:$('hrv-trend-summary'),paceHrTrendSummary:$('pace-hr-trend-summary'),cadenceTrendSummary:$('cadence-trend-summary'),paceCadenceHrTrendSummary:$('pace-cadence-hr-trend-summary'),zonesAllSummary:$('zones-all-summary'),zonesRunningSummary:$('zones-running-summary'),volumeTrend:$('volume-trend'),bikeVolumeTrend:$('bike-volume-trend'),loadRatioTrend:$('load-ratio-trend'),sleepTrend:$('sleep-trend'),restingHrTrend:$('resting-hr-trend'),hrvTrend:$('hrv-trend'),paceHrTrend:$('pace-hr-trend'),cadenceTrend:$('cadence-trend'),paceCadenceHrTrend:$('pace-cadence-hr-trend'),zonesAllChart:$('zones-all-chart'),zonesRunningChart:$('zones-running-chart'),importDataState:$('import-data-state'),importFreshnessDetail:$('import-freshness-detail'),importWorkspace:$('import-workspace'),importWorkspaceDetail:$('import-workspace-detail'),importRunState:$('import-run-state'),importRunDetail:$('import-run-detail'),importAgeState:$('import-age-state'),importAgeDetail:$('import-age-detail'),importSyncState:$('import-sync-state'),importSyncDetail:$('import-sync-detail'),coachStatusStrip:$('coach-status-strip'),terminalLog:$('terminal-log'),terminalSummary:$('terminal-summary'),dashboardModal:$('dashboard-modal'),dashboardModalTitle:$('dashboard-modal-title'),dashboardModalSubtitle:$('dashboard-modal-subtitle'),dashboardModalValue:$('dashboard-modal-value'),dashboardModalText:$('dashboard-modal-text'),dashboardModalChart:$('dashboard-modal-chart'),dashboardModalSignals:$('dashboard-modal-signals'),dashboardModalClose:$('dashboard-modal-close'),diagnosticModal:$('diagnostic-modal'),diagnosticModalTitle:$('diagnostic-modal-title'),diagnosticModalSubtitle:$('diagnostic-modal-subtitle'),diagnosticModalClose:$('diagnostic-modal-close'),diagnosticBuild:$('diagnostic-build'),diagnosticBuildDetail:$('diagnostic-build-detail'),diagnosticUrl:$('diagnostic-url'),diagnosticUrlDetail:$('diagnostic-url-detail'),diagnosticSw:$('diagnostic-sw'),diagnosticSwDetail:$('diagnostic-sw-detail'),diagnosticWorkspace:$('diagnostic-workspace'),diagnosticWorkspaceDetail:$('diagnostic-workspace-detail'),diagnosticImport:$('diagnostic-import'),diagnosticImportDetail:$('diagnostic-import-detail'),diagnosticProvider:$('diagnostic-provider'),diagnosticProviderDetail:$('diagnostic-provider-detail'),diagnosticRefreshButton:$('diagnostic-refresh-button'),diagnosticCopyButton:$('diagnostic-copy-button'),diagnosticSummary:$('diagnostic-summary'),bootTraceState:$('boot-trace-state'),bootTraceDetail:$('boot-trace-detail'),bootTraceLog:$('boot-trace-log'),bootTraceRefreshButton:$('boot-trace-refresh-button'),debugEndpointState:$('debug-endpoint-state'),debugEndpointDetail:$('debug-endpoint-detail'),terminalClearButton:$('clear-terminal-button'),themeSelect:$('theme-select'),startSectionSelect:$('start-section-select'),showTerminalToggle:$('show-terminal-toggle'),settingsProviderSelect:$('settings-provider-select'),baseUrlInput:$('base-url-input'),apiKeyInput:$('api-key-input'),workspaceInput:$('workspace-input'),workspaceInputSettings:$('workspace-input-settings'),sourcePathInput:$('source-path-input'),sourcePathInputSettings:$('source-path-input-settings'),goalInput:$('goal-input'),coachWorkspaceInput:$('coach-workspace-chip-input'),authDebugState:$('auth-debug-state'),authDebugDetail:$('auth-debug-detail'),authTokenstoreState:$('auth-tokenstore-state'),authTokenstoreDetail:$('auth-tokenstore-detail'),authTestButton:$('auth-test-button'),providerSelect:$('provider-select'),saveSettingsButton:$('save-settings-button'),refreshSettingsButton:$('refresh-settings-button'),saveGoalButton:$('save-goal-button'),prepareButton:$('prepare-button'),planButton:$('plan-button'),importButton:$('import-button'),syncButton:$('sync-button'),refreshButton:$('refresh-button'),reprocessButton:$('reprocess-button'),useLastWorkspaceButton:$('use-last-workspace-button'),levelButtons:Array.from(document.querySelectorAll('.level-toggle')),navButtons:Array.from(document.querySelectorAll('.nav-button'))};
const actionButtons=[dom.saveSettingsButton,dom.refreshSettingsButton,dom.saveGoalButton,dom.prepareButton,dom.planButton,dom.importButton,dom.syncButton,dom.refreshButton,dom.reprocessButton,dom.useLastWorkspaceButton,dom.retryButton,dom.terminalClearButton,dom.authTestButton];
function repairMojibakeText(value){if(typeof value!=='string')return value;const text=value.replace(/^\ufeff/,'');if(!/[ÃÂâ�]/.test(text))return text.normalize('NFC');try{return decodeURIComponent(escape(text)).normalize('NFC')}catch{return text.normalize('NFC')}}
function repairTextTree(value){if(typeof value==='string')return repairMojibakeText(value);if(Array.isArray(value))return value.map(repairTextTree);if(value&&typeof value==='object'){const output={};for(const [key,item] of Object.entries(value)){output[repairTextTree(key)]=repairTextTree(item)}return output}return value}
function installTextRepairHooks(){if(window.__coachTextRepairInstalled)return;window.__coachTextRepairInstalled=true;const patchProperty=(prototype,property)=>{const descriptor=Object.getOwnPropertyDescriptor(prototype,property);if(!descriptor?.set||!descriptor?.get)return;Object.defineProperty(prototype,property,{configurable:true,enumerable:descriptor.enumerable,get(){return descriptor.get.call(this)},set(value){descriptor.set.call(this,repairMojibakeText(value))}})};patchProperty(Node.prototype,'textContent');patchProperty(Element.prototype,'innerHTML');patchProperty(Element.prototype,'textContent');patchProperty(HTMLInputElement.prototype,'value');patchProperty(HTMLTextAreaElement.prototype,'value');patchProperty(Element.prototype,'title');patchProperty(HTMLElement.prototype,'title');const originalSetAttribute=Element.prototype.setAttribute;Element.prototype.setAttribute=function(name,value){return originalSetAttribute.call(this,name,typeof value==='string'?repairMojibakeText(value):value)}}
installTextRepairHooks();
function formatNumber(value,digits=0){if(value===null||value===undefined||value==='')return'-';const n=Number(value);if(Number.isNaN(n))return String(value);return new Intl.NumberFormat('fr-FR',{maximumFractionDigits:digits,minimumFractionDigits:digits}).format(n)}
function formatKilometers(value){if(value===null||value===undefined||value==='')return'-';return `${formatNumber(value,1)} km`}
function formatPace(value){if(value===null||value===undefined||value==='')return'-';const total=Number(value);if(!Number.isFinite(total)||total<=0)return'-';const minutes=Math.floor(total);const seconds=Math.round((total-minutes)*60);return seconds===60?`${minutes+1}:00/km`:`${minutes}:${String(seconds).padStart(2,'0')}/km`}
function formatHeartRate(value){if(value===null||value===undefined||value==='')return'-';return `${formatNumber(value,0)} bpm`}
function formatBand(low,high,formatter){const hasLow=low!==null&&low!==undefined;const hasHigh=high!==null&&high!==undefined;if(!hasLow&&!hasHigh)return'-';if(hasLow&&hasHigh)return `${formatter(low)} Â· ${formatter(high)}`;return formatter(hasLow?low:high)}
function formatDateLabel(value){if(!value)return'-';const date=new Date(`${value}T00:00:00`);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{dateStyle:'medium'}).format(date)}
function formatShortDateLabel(value){if(!value)return'-';const date=new Date(`${value}T00:00:00`);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{day:'2-digit',month:'short'}).format(date)}
function formatDateTime(value){if(!value)return'-';const date=new Date(value);if(Number.isNaN(date.getTime()))return String(value);return new Intl.DateTimeFormat('fr-FR',{dateStyle:'medium',timeStyle:'short'}).format(date)}
function daysBetween(a,b){const start=new Date(`${a}T00:00:00`);const end=new Date(`${b}T00:00:00`);if(Number.isNaN(start.getTime())||Number.isNaN(end.getTime()))return null;return Math.round((end.getTime()-start.getTime())/86400000)}
function normalizeText(value){return typeof value==='string'?repairMojibakeText(value).normalize('NFC'):value}
function safeChartText(value){return repairMojibakeText(typeof value==='string'?value:String(value??''))}
function loadTerminalLevels(){try{const raw=localStorage.getItem(STORAGE_KEYS.terminalLevels);if(!raw)return {...DEFAULT_TERMINAL_LEVELS};const parsed=JSON.parse(raw);return{debug:parsed.debug!==false,info:parsed.info!==false,warn:parsed.warn!==false,error:parsed.error!==false}}catch{return{...DEFAULT_TERMINAL_LEVELS}}}
function loadTerminalLogs(){try{const raw=localStorage.getItem(STORAGE_KEYS.terminalLogs);if(!raw)return[];const parsed=repairTextTree(JSON.parse(raw));return Array.isArray(parsed)?parsed.slice(-250):[]}catch{return[]}}
function loadLastGarminSync(){try{const raw=localStorage.getItem(STORAGE_KEYS.lastGarminSync);if(!raw)return{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'};const parsed=repairTextTree(JSON.parse(raw));return parsed&&typeof parsed==='object'?parsed:{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'}}catch{return{status:'idle',message:'Aucune tentative Garmin Connect enregistrée.'}}}
function loadLastGarminAuthTest(){try{const raw=localStorage.getItem(STORAGE_KEYS.lastGarminAuthTest);if(!raw)return{status:'idle',message:"Aucun test d'auth Garmin enregistré."};const parsed=repairTextTree(JSON.parse(raw));return parsed&&typeof parsed==='object'?parsed:{status:'idle',message:"Aucun test d'auth Garmin enregistré."}}catch{return{status:'idle',message:"Aucun test d'auth Garmin enregistré."}}}
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
  const detail=entry.detail?` â€” ${entry.detail}`:'';
  return `${stamp} | ${stage}${detail}`;
}
function renderBootTrace(events=state.bootTrace){
  const trace=Array.isArray(events)?events.slice(-40):[];
  if(dom.bootTraceState){
    dom.bootTraceState.textContent=trace.length?`Trace active (${trace.length})`:'Aucune trace';
  }
  if(dom.bootTraceDetail){
    const last=trace.at(-1);
    dom.bootTraceDetail.textContent=last?formatBootTraceEvent(last):'Aucun Ã©vÃ¨nement enregistrÃ©.';
  }
  if(dom.bootTraceLog){
    dom.bootTraceLog.textContent=trace.length?trace.map((entry)=>formatBootTraceEvent(entry)).join('\n'):'Aucun Ã©vÃ¨nement de boot pour le moment.';
  }
  if(dom.bootTraceRefreshButton){
    dom.bootTraceRefreshButton.disabled=false;
  }
}
function recordBoot(stage, detail='', extra={}){
  const event={
    timestamp:new Date().toISOString(),
    stage:repairMojibakeText(stage),
    event:repairMojibakeText(stage),
    detail:repairMojibakeText(detail),
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
function safeBootStep(step, callback){
  try{
    return callback();
  }catch(error){
    state.bootErrors=Array.isArray(state.bootErrors)?state.bootErrors:[];
    state.bootErrors.push({step,message:error?.message||String(error),stack:error?.stack||'',timestamp:new Date().toISOString()});
    state.bootErrors=state.bootErrors.slice(-20);
    recordBoot('boot:error',`${step}: ${error?.message||String(error)}`,{state:'error',stack:error?.stack||''});
    addTerminalLog('error','boot',`Étape ${step} en échec`,error?.message||String(error));
    return null;
  }
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
    recordBoot('boot-trace:refreshed',`${events.length} event(s) chargÃ©s`,{state:'info'});
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
  if(dom.authDebugState) dom.authDebugState.textContent = auth.ok===true ? 'Authentification prÃªte' : auth.ok===false ? 'Authentification en Ã©chec' : 'Authentification non testÃ©e';
  if(dom.authDebugDetail) dom.authDebugDetail.textContent = auth.ok===true ? (auth.result?.used_existing_tokenstore ? 'Tokenstore rÃ©utilisÃ© et login rÃ©ussi.' : 'Login rÃ©ussi et tokenstore initialisÃ©.') : auth.error ? `${auth.error}${auth.debug_log_path ? ` Â· log ${auth.debug_log_path}` : ''}` : 'Lance un test pour remplir ce bloc.';
  if(dom.authTokenstoreState) dom.authTokenstoreState.textContent = env.tokenstore_exists ? 'Tokenstore dÃ©tectÃ©' : 'Aucun tokenstore';
  if(dom.authTokenstoreDetail) dom.authTokenstoreDetail.textContent = `${env.tokenstore_path || '-'}${env.package_version ? ` Â· garminconnect ${env.package_version}` : ''}`;
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
    addTerminalLog(payload.ok?'info':'warn','auth',payload.ok?'Auth Garmin rÃ©ussie':'Auth Garmin en Ã©chec',payload.ok?payload.result?.tokenstore_path||'tokenstore ok':payload.error||'Ã©chec');
    if(payload.ok){addMessage('assistant','Auth Garmin rÃ©ussie.')}else{addMessage('assistant',`Auth Garmin en Ã©chec: ${payload.error}`)}
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
window.addEventListener('error',(event)=>{setAppChip('App: erreur JS','error');addTerminalLog('error','runtime',event.message||'Erreur JS',event.error?.stack||'');if(dom.coachErrorBanner){dom.coachErrorTitle.textContent='Erreur JavaScript';dom.coachErrorMessage.textContent=event.message||'Une erreur de script a empÃªchÃ© lâ€™initialisation.';dom.coachErrorBanner.classList.remove('hidden')}});
window.addEventListener('unhandledrejection',(event)=>{setAppChip('App: promesse rejetÃ©e','error');const reason=event.reason?.message||String(event.reason||'Rejet de promesse');addTerminalLog('error','runtime',reason,event.reason?.stack||'');if(dom.coachErrorBanner){dom.coachErrorTitle.textContent='Erreur asynchrone';dom.coachErrorMessage.textContent=reason;dom.coachErrorBanner.classList.remove('hidden')}});
function currentPayload(){return state.dashboardPayload||{}}
function currentMetrics(){return currentPayload().analysis?.metrics||{}}
function currentImportStatus(){return currentPayload().import_status||{}}
function currentAnalysis(){return currentPayload().analysis||{}}
async function requestJson(url,options={},label='request'){const response=await fetch(url,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});const contentType=response.headers.get('content-type')||'';const body=contentType.includes('application/json')?await response.json():{message:await response.text()};if(!response.ok){const error=new Error(body?.message||body?.error||`${label} failed with HTTP ${response.status}`);error.status=response.status;error.body=body;throw error}return body}
async function withBusy(message,runner){setBusy(true,message);try{return await runner()}finally{setBusy(false)}}
function syncInputsFromState(){if(dom.workspaceInputSettings) dom.workspaceInputSettings.value=state.workspace;if(dom.providerSelect) dom.providerSelect.value=state.provider;if(dom.settingsProviderSelect) dom.settingsProviderSelect.value=state.provider;if(dom.baseUrlInput) dom.baseUrlInput.value=state.baseUrl;if(dom.apiKeyInput) dom.apiKeyInput.value=state.apiKey;if(dom.sourcePathInput) dom.sourcePathInput.value=state.sourcePath;if(dom.sourcePathInputSettings) dom.sourcePathInputSettings.value=state.sourcePath;if(dom.goalInput) dom.goalInput.value=state.goalText;if(dom.themeSelect) dom.themeSelect.value=state.theme;if(dom.startSectionSelect) dom.startSectionSelect.value=state.startSection;if(dom.showTerminalToggle) dom.showTerminalToggle.checked=state.showTerminalMenu;if(dom.coachWorkspaceInput) dom.coachWorkspaceInput.value=state.workspace}
function persistSettings(){state.workspace=normalizeText((dom.workspaceInputSettings?.value||'data').trim()||'data');state.provider=normalizeText((dom.providerSelect?.value||dom.settingsProviderSelect?.value||'ollama').trim());state.baseUrl=normalizeText((dom.baseUrlInput?.value||'').trim());state.apiKey=normalizeText((dom.apiKeyInput?.value||'').trim());state.sourcePath=normalizeText((dom.sourcePathInput?.value||dom.sourcePathInputSettings?.value||'').trim());state.goalText=normalizeText((dom.goalInput?.value||'').trim());state.theme=dom.themeSelect?.value||state.theme;state.startSection=dom.startSectionSelect?.value||state.startSection;state.dashboardWindowDays=normalizeDashboardWindowDays(state.dashboardWindowDays||90);state.showTerminalMenu=!!dom.showTerminalToggle?.checked;localStorage.setItem(STORAGE_KEYS.workspace,state.workspace);localStorage.setItem(STORAGE_KEYS.provider,state.provider);localStorage.setItem(STORAGE_KEYS.baseUrl,state.baseUrl);localStorage.setItem(STORAGE_KEYS.apiKey,state.apiKey);localStorage.setItem(STORAGE_KEYS.sourcePath,state.sourcePath);localStorage.setItem(STORAGE_KEYS.goalText,state.goalText);localStorage.setItem(STORAGE_KEYS.theme,state.theme);localStorage.setItem(STORAGE_KEYS.activeSection,state.activeSection);localStorage.setItem(STORAGE_KEYS.startSection,state.startSection);localStorage.setItem(STORAGE_KEYS.dashboardWindowDays,String(state.dashboardWindowDays));localStorage.setItem(STORAGE_KEYS.showTerminalMenu,String(state.showTerminalMenu));localStorage.setItem(STORAGE_KEYS.terminalLevels,JSON.stringify(state.terminalLevels));applyTheme();updateNavVisibility();renderSectionHeader();renderSidebarStatus();if(dom.coachWorkspaceInput) dom.coachWorkspaceInput.value=state.workspace}
function addTerminalLog(level,source,message,details=''){state.terminalLogs.push({timestamp:new Date().toISOString(),level,source,message:repairMojibakeText(message),details:repairMojibakeText(details)});state.terminalLogs=state.terminalLogs.slice(-250);saveTerminalLogs();if(dom.terminalLog) renderTerminalSection()}
function setBusy(active,message='Analyse en cours...'){if(dom.busyBanner) dom.busyBanner.classList.toggle('hidden',!active);if(dom.busyText) dom.busyText.textContent=message;document.body.classList.toggle('is-busy',active);actionButtons.forEach((button)=>{if(button&&button!==dom.retryButton)button.disabled=active})}
function buildProviderErrorTitle(error){if(!error)return'Le provider a renvoyé une erreur.';if(error.status===503||error.status===429)return'Provider temporairement indisponible.';return'Le provider a renvoyé une erreur.'}
function buildProviderErrorMessage(error){if(!error)return'Essaie ou change de provider avant de repartir.';if(error.status===503||error.status===429)return'Le provider est temporairement indisponible. Essaie, ou change de provider dans le sélecteur avant de relancer.';return error.message||'Essaie ou change de provider avant de repartir.'}
function setCoachError(message,retryAction=null,title='Le provider a renvoyé une erreur.'){state.retryAction=retryAction;if(dom.coachErrorTitle) dom.coachErrorTitle.textContent=title;if(dom.coachErrorMessage) dom.coachErrorMessage.textContent=message;if(dom.coachErrorBanner) dom.coachErrorBanner.classList.remove('hidden');if(dom.retryButton) dom.retryButton.disabled=typeof retryAction!=='function'}
function clearCoachError(){state.retryAction=null;if(dom.coachErrorBanner) dom.coachErrorBanner.classList.add('hidden');if(dom.coachErrorTitle) dom.coachErrorTitle.textContent='Le provider a renvoyé une erreur.';if(dom.coachErrorMessage) dom.coachErrorMessage.textContent='';if(dom.retryButton) dom.retryButton.disabled=true}
function addMessage(role,text){const node=document.createElement('div');node.className=`message ${role}`;node.textContent=text;if(dom.transcript){dom.transcript.appendChild(node);dom.transcript.scrollTop=dom.transcript.scrollHeight}}
function renderQuestions(questions){dom.questions.innerHTML='';state.currentQuestions=questions||[];state.answers={};if(!state.currentQuestions.length){dom.questions.innerHTML="<p class='status-line'>Aucune question compl?mentaire. Tu peux gÃ©nÃ©rer le plan directement.</p>";return}state.currentQuestions.forEach((question)=>{const template=$('question-template');const node=template.content.firstElementChild.cloneNode(true);const label=node.querySelector('.question-label');const input=node.querySelector('input');label.textContent=question.question;input.placeholder=question.key;input.dataset.key=question.key;input.addEventListener('input',()=>{state.answers[question.key]=input.value.trim()});dom.questions.appendChild(node)})}
function buildChartTicks(min,max,count=5){if(!Number.isFinite(min)||!Number.isFinite(max))return[];if(count<=1||min===max)return[min,max].filter((value,index,array)=>array.indexOf(value)===index);const span=max-min||1;const step=span/(count-1);return Array.from({length:count},(_,index)=>Number((min+step*index).toFixed(2)))}
function chartTooltipLabel(container){let tooltip=container.querySelector('.chart-tooltip');if(!tooltip){tooltip=document.createElement('div');tooltip.className='chart-tooltip';container.appendChild(tooltip)}return tooltip}
function renderChartTooltip(tooltip,payload){if(!tooltip)return;const title=safeChartText(payload?.title||'Point');const value=safeChartText(payload?.value||'-');const detail=safeChartText(payload?.detail||'');tooltip.innerHTML=`<strong>${title}</strong><span>${value}</span>${detail?`<small>${detail}</small>`:''}`;tooltip.style.left=`${Number(payload?.x||0)}px`;tooltip.style.top=`${Number(payload?.y||0)}px`;tooltip.classList.add('visible')}
function attachChartTooltipHandlers(container,tooltip,points){points.forEach((point)=>{point.addEventListener('mouseenter',()=>{const title=point.dataset.title||'-';const value=point.dataset.value||'-';const detail=point.dataset.detail||'';renderChartTooltip(tooltip,{title,value,detail,x:Number(point.dataset.tx||0),y:Number(point.dataset.ty||0)})});point.addEventListener('mousemove',(event)=>{const rect=container.getBoundingClientRect();renderChartTooltip(tooltip,{title:point.dataset.title||'-',value:point.dataset.value||'-',detail:point.dataset.detail||'',x:event.clientX-rect.left,y:event.clientY-rect.top})});point.addEventListener('mouseleave',()=>{tooltip.classList.remove('visible')})})}
function renderSparkline(container,series,options={}){
  const input=Array.isArray(series)?series:[];
  const referenceLines=Array.isArray(options.referenceLines)?options.referenceLines.filter((entry)=>Number.isFinite(Number(entry?.value))):[];
  const referenceBands=Array.isArray(options.referenceBands)?options.referenceBands.filter((entry)=>Number.isFinite(Number(entry?.low))&&Number.isFinite(Number(entry?.high))):[];
  const items=input.map((entry,index)=>{
    if(typeof entry==='number'&&Number.isFinite(entry))return{value:entry,label:options.labels?.[index]||String(index+1),detail:options.details?.[index]||''};
    if(entry&&typeof entry==='object'){
      const value=Number(entry.value??entry.distance_km??entry.load_ratio_7_28??entry.sleep_hours??entry.resting_hr??entry.cadence_spm??entry.hrv_ms??entry.pace_min_per_km??entry.heart_rate);
      return Number.isFinite(value)?{value,label:entry.label||entry.metric_date||options.labels?.[index]||String(index+1),detail:entry.detail||entry.metric_date||''}:null;
    }
    return null;
  }).filter(Boolean);
  if(!items.length){
    const emptyTitle=safeChartText(options.emptyTitle||'Pas encore de données exploitables.');
    const emptyReason=safeChartText(options.emptyReason||'');
    const emptyAdvice=safeChartText(options.emptyAdvice||'');
    const emptyNotes=Array.isArray(options.emptyNotes)?options.emptyNotes.filter(Boolean):[];
    container.innerHTML=`<div class="chart-shell"><p class="status-line">${emptyTitle}</p>${emptyReason||emptyAdvice||emptyNotes.length?`<div class="detail-block">${emptyReason?`<p>${emptyReason}</p>`:''}${emptyAdvice?`<p>${emptyAdvice}</p>`:''}${emptyNotes.length?`<ul class="detail-list">${emptyNotes.map((note)=>`<li>${safeChartText(note)}</li>`).join('')}</ul>`:''}</div>`:''}</div>`;
    return;
  }
  const width=options.width||360;
  const height=options.height||120;
  const padLeft=options.padLeft||46;
  const padRight=options.padRight||18;
  const padTop=options.padTop||12;
  const padBottom=options.padBottom||34;
  const values=items.map((item)=>Number(item.value));
  const referenceValues=[...referenceLines.map((entry)=>Number(entry.value)),...referenceBands.flatMap((band)=>[Number(band.low),Number(band.high)])].filter((value)=>Number.isFinite(value));
  const domain=buildChartDomain(values,referenceValues,{padRatio:options.padRatio??0.06,minSpan:options.minSpan??0});
  const min=domain.min;
  const max=domain.max;
  const span=domain.span||1;
  const xSpan=items.length>1?(width-padLeft-padRight)/(items.length-1):0;
  const points=items.map((item,index)=>{
    const x=items.length>1?padLeft+index*xSpan:width/2;
    const y=height-padBottom-((Number(item.value)-min)/span)*(height-padTop-padBottom);
    return{x,y,item,index};
  });
  const line=points.map((point)=>`${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
  const yTicks=buildChartTicks(min,max,options.yTickCount||(height>=220?7:5));
  const xTicks=buildIndexedTicks(items.length,options.xTickCount||(width>=900?7:5));
  const tickFormatter=options.tickFormatter||((value)=>formatNumber(value,1));
  const areaFill=options.drawArea===false?'':`<polygon points="${`0,${height-padBottom} ${line} ${width},${height-padBottom}`}" fill="url(#sparkline-fill-${options.id||'base'})" opacity="0.8"></polygon>`;
  const title=options.title||'';
  const xLabel=options.xLabel||'';
  const yLabel=options.yLabel||'';
  const xTickFormatter=options.xTickFormatter||((item,index,total)=>item.label||formatRelativeDayLabel(index,total));
  container.innerHTML=`<div class="chart-shell"><svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${safeChartText(title||'courbe')}"><defs><linearGradient id="sparkline-fill-${options.id||'base'}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="${options.fill||'rgba(138, 230, 192, 0.34)'}" /><stop offset="100%" stop-color="rgba(138, 230, 192, 0.03)" /></linearGradient></defs><line class="chart-axis-line" x1="${padLeft}" y1="${height-padBottom}" x2="${width-padRight}" y2="${height-padBottom}"></line><line class="chart-axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height-padBottom}"></line>${yTicks.map((tick)=>{const ratio=(tick-min)/span;const y=height-padBottom-ratio*(height-padTop-padBottom);return `<g><line class="chart-grid-line" x1="${padLeft}" y1="${y.toFixed(2)}" x2="${width-padRight}" y2="${y.toFixed(2)}"></line><text class="chart-axis-tick" x="${padLeft-8}" y="${(y+4).toFixed(2)}" text-anchor="end">${safeChartText(tickFormatter(tick))}</text></g>`}).join('')}${xTicks.map((index)=>{const point=points[index];if(!point)return'';return `<g><line class="chart-grid-line vertical" x1="${point.x.toFixed(2)}" y1="${padTop}" x2="${point.x.toFixed(2)}" y2="${height-padBottom}"></line></g>`}).join('')}${referenceBands.map((band)=>{const low=Math.min(Number(band.low),Number(band.high));const high=Math.max(Number(band.low),Number(band.high));const highRatio=(high-min)/span;const lowRatio=(low-min)/span;const topY=height-padBottom-highRatio*(height-padTop-padBottom);const bottomY=height-padBottom-lowRatio*(height-padTop-padBottom);return `<rect x="${padLeft}" y="${Math.min(topY,bottomY).toFixed(2)}" width="${width-padLeft-padRight}" height="${Math.abs(bottomY-topY).toFixed(2)}" fill="${band.color||'rgba(138, 230, 192, 0.08)'}" opacity="0.28"></rect>`}).join('')}${referenceLines.map((lineItem)=>{const ratio=(Number(lineItem.value)-min)/span;const y=height-padBottom-ratio*(height-padTop-padBottom);return `<g><line class="chart-grid-line" x1="${padLeft}" y1="${y.toFixed(2)}" x2="${width-padRight}" y2="${y.toFixed(2)}" stroke-dasharray="4 4"></line><text class="chart-axis-tick" x="${width-padRight}" y="${(y-4).toFixed(2)}" text-anchor="end">${safeChartText(lineItem.label||tickFormatter(lineItem.value))}</text></g>`}).join('')}<path d="M ${points.map((point)=>`${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')}" fill="none" stroke="${options.stroke||'#8ae6c0'}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"></path>${areaFill}${points.map((point,index)=>`<circle class="chart-point-dot" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${index===points.length-1?4.6:3.8}" fill="${options.stroke||'#8ae6c0'}" data-title="${safeChartText(point.item.label||title||'Point')}" data-value="${safeChartText(tickFormatter(point.item.value))}" data-detail="${safeChartText(point.item.detail||'')}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle><circle class="chart-point-hit" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="12" data-title="${safeChartText(point.item.label||title||'Point')}" data-value="${safeChartText(tickFormatter(point.item.value))}" data-detail="${safeChartText(point.item.detail||'')}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle>`).join('')}<text class="chart-axis-title" x="${padLeft}" y="${16}">${safeChartText(yLabel)}</text><text class="chart-axis-title" x="${width-padRight}" y="${height-6}" text-anchor="end">${safeChartText(xLabel)}</text>${xTicks.map((index)=>{const point=points[index];if(!point)return'';const x=point.x;const label=xTickFormatter(point.item,index,items.length);return `<text class="chart-axis-tick" x="${x.toFixed(2)}" y="${height-8}" text-anchor="middle">${safeChartText(label)}</text>`}).join('')}</svg><div class="chart-tooltip" aria-hidden="true"></div></div>`;const tooltip=chartTooltipLabel(container);const pointsEls=Array.from(container.querySelectorAll('.chart-point-hit, .chart-point-dot'));attachChartTooltipHandlers(container,tooltip,pointsEls)
}function renderDualSparkline(container,seriesA,seriesB,options={}){const valuesA=Array.isArray(seriesA)?seriesA.filter((value)=>Number.isFinite(Number(value))):[];const valuesB=Array.isArray(seriesB)?seriesB.filter((value)=>Number.isFinite(Number(value))):[];if(!valuesA.length&&!valuesB.length){container.innerHTML="<p class='status-line'>Pas encore de sÃ©rie exploitable.</p>";return}const width=options.width||360;const height=options.height||110;const renderSeries=(series,stroke,fill,id)=>{const values=series.filter((value)=>Number.isFinite(Number(value)));if(!values.length)return'<p class="status-line">Pas de donnÃ©es.</p>';const min=Math.min(...values);const max=Math.max(...values);const span=max-min||1;const step=values.length>1?width/(values.length-1):width;const points=values.map((value,index)=>{const x=values.length>1?index*step:width/2;const y=height-((Number(value)-min)/span)*(height-14)-7;return{x,y}});const line=points.map((point)=>`${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');return`<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="sparkline-fill-${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="${fill}" /><stop offset="100%" stop-color="rgba(138, 180, 255, 0.02)" /></linearGradient></defs><polygon points="0,${height} ${line} ${width},${height}" fill="url(#sparkline-fill-${id})"></polygon><polyline points="${line}" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>${points.map((point)=>`<circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.1" fill="${stroke}"></circle>`).join('')}</svg>`};container.innerHTML=`<div class="stacked-trend"><div class="stacked-row"><span class="card-label">Allure</span>${renderSeries(valuesA,'#8ae6c0','rgba(138, 230, 192, 0.34)',`${options.id||'dual'}-pace`)}</div><div class="stacked-row"><span class="card-label">FC</span>${renderSeries(valuesB,'#8ab4ff','rgba(138, 180, 255, 0.32)',`${options.id||'dual'}-hr`)}</div></div>`}
function buildIndexedTicks(length,count=5){if(!Number.isFinite(length)||length<=1)return[0];const raw=[0,0.25,0.5,0.75,1].slice(0,Math.max(2,Math.min(count,5))).map((fraction)=>Math.round((length-1)*fraction));return Array.from(new Set(raw.filter((index)=>index>=0&&index<length)));}
function formatRelativeDayLabel(index,total){const distance=Math.max(total-1-index,0);return distance===0?'J0':distance===1?'J-1':`J-${distance}`}
function formatAxisKilometers(value){const numeric=Number(value);if(!Number.isFinite(numeric))return'-';const decimals=Math.abs(numeric)>=10||Math.abs(numeric-Math.round(numeric))<0.05?0:1;return `${formatNumber(numeric,decimals)} km`}
function classifyPlanSession(session){const title=normalizeText(`${session?.session_title||''} ${session?.intensity||''} ${session?.objective||''} ${session?.notes||''}`.toLowerCase());if(!title.trim())return'neutral';if(/repos|rest|off|récupération passive|recovery day/.test(title))return'rest';if(/footing|easy|endurance fondamentale|endurance|facile|récup|recovery run/.test(title))return'easy';if(/seuil|tempo|fractionn|qualit|qualité|vma|spécifique|sp[eé]cifique|longue|long run|sortie longue|côte|cotes|côtes|allure/.test(title))return'quality';return'neutral'}
function resolveDashboardModalCard(key){const payload=currentPayload();const dashboardCard=dashboardCardSpecs(payload).find((item)=>item.key===key);if(dashboardCard)return dashboardCard;return buildTrendModalCard(key)}
function parseSeriesDate(value){if(value===null||value===undefined||value==='')return null;if(value instanceof Date)return Number.isNaN(value.getTime())?null:value;const raw=String(value).trim();if(!raw)return null;const candidate=/^\d{4}-\d{2}-\d{2}$/.test(raw)?`${raw}T00:00:00Z`:raw;const date=new Date(candidate);return Number.isNaN(date.getTime())?null:date}
function buildChartDomain(values,referenceValues=[],options={}){const numbers=[...(Array.isArray(values)?values:[]),...(Array.isArray(referenceValues)?referenceValues:[])].map((value)=>Number(value)).filter((value)=>Number.isFinite(value));if(!numbers.length)return{min:0,max:1,span:1};const rawMin=Math.min(...numbers);const rawMax=Math.max(...numbers);const rawSpan=rawMax-rawMin;const padRatio=Number.isFinite(Number(options.padRatio))?Number(options.padRatio):0.06;const minSpan=Number.isFinite(Number(options.minSpan))?Number(options.minSpan):0;const padding=Math.max(rawSpan*padRatio,0);if(rawSpan<=0){const delta=Math.max(Math.abs(rawMin)*0.08,minSpan||1);return{min:rawMin-delta,max:rawMax+delta,span:(rawMax+delta)-(rawMin-delta)||1}}return{min:rawMin-padding,max:rawMax+padding,span:(rawMax+padding)-(rawMin-padding)||1}}
function chartWindowTickCount(days){return days<=30?4:days<=90?6:8}
function windowedChartSeries(rows,days,{valueKey='value',dateKeys=['metric_date','date','activity_date','started_at'],labelMode='relative'}={}){const input=Array.isArray(rows)?rows:[];const items=input.map((row,index)=>{if(row===null||row===undefined)return null;if(typeof row==='number'){return Number.isFinite(row)?{value:row,row:{value:row},index,date:null}:null}const value=Number(row?.[valueKey]??row?.value??row?.distance_km??row?.load_ratio_7_28??row?.sleep_hours??row?.resting_hr??row?.cadence_spm??row?.hrv_ms??row?.pace_min_per_km??row?.heart_rate);if(!Number.isFinite(value))return null;const rawDate=dateKeys.map((key)=>row?.[key]).find((candidate)=>candidate!==undefined&&candidate!==null&&candidate!=='');return{value,row,index,date:parseSeriesDate(rawDate)}}).filter(Boolean);if(!items.length)return[];const dated=items.filter((item)=>item.date instanceof Date);const source=(dated.length?(() => {const ordered=dated.slice().sort((a,b)=>a.date-b.date||a.index-b.index);const latest=ordered.at(-1).date;const windowDays=normalizeDashboardWindowDays(days);const windowStart=new Date(latest);windowStart.setHours(0,0,0,0);windowStart.setDate(windowStart.getDate()-(windowDays-1));const filtered=ordered.filter((item)=>item.date>=windowStart);return filtered.length?filtered:ordered;})():items);return source.map((item,index)=>({...item.row,value:item.value,label:labelMode==='date'&&item.date?formatShortDateLabel(item.date.toISOString().slice(0,10)):formatRelativeDayLabel(index,source.length),detail:item.date?formatDateLabel(item.date.toISOString().slice(0,10)):(item.row?.detail||''),metric_date:item.date?item.date.toISOString().slice(0,10):(item.row?.metric_date||item.row?.date||item.row?.activity_date||''),source:item.row||null}))}
function buildTrendWindowSeries(trend,days){return{runningSeries:windowedChartSeries(trend.daily_volume,days,{valueKey:'distance_km'}),bikeSeries:windowedChartSeries(trend.daily_bike_volume,days,{valueKey:'distance_km'}),loadRatioSeries:windowedChartSeries(trend.daily_load_ratio,days,{valueKey:'load_ratio_7_28'}),sleepSeries:windowedChartSeries(trend.daily_sleep,days,{valueKey:'sleep_hours'}),restingHrSeries:windowedChartSeries(trend.daily_resting_hr,days,{valueKey:'resting_hr'}),hrvSeries:windowedChartSeries(trend.daily_hrv,days,{valueKey:'hrv_ms'}),cadenceSeries:windowedChartSeries(trend.cadence_daily,days,{valueKey:'cadence_spm'}),runningPaceSeries:windowedChartSeries(trend.daily_running_pace,days,{valueKey:'pace_min_per_km'}),runningHrSeries:windowedChartSeries(trend.daily_running_hr,days,{valueKey:'heart_rate'}),paceCurve:Array.isArray(trend.pace_hr_curve)?trend.pace_hr_curve:[],paceCurveDebug:trend.pace_hr_curve_debug||{}}}
function buildSeriesReadiness(series,{name='Série',minPoints=1,emptyReason=''}={}){const points=Array.isArray(series)?series.filter((entry)=>entry!==null&&entry!==undefined):[];if(points.length>=minPoints){return{state:'ready',label:'Prête',reason:'',points:points.length}}if(points.length>0){return{state:'partial_data',label:'Partielle',reason:`${name}: ${points.length} point(s) exploitable(s), minimum attendu ${minPoints}.`,points:points.length}}return{state:'unavailable',label:'Indisponible',reason:emptyReason||`${name}: aucune donnée exploitable.`,points:0}}
function buildPaceCurveReadiness(curveDebug,curve){const ready=curveDebug?.ready===true&&Array.isArray(curve)&&curve.length>=3;const inputPoints=Number(curveDebug?.input_points||0);const validPoints=Number(curveDebug?.valid_points||0);const reasons=[];if(Array.isArray(curveDebug?.blocking_reasons)&&curveDebug.blocking_reasons.length){reasons.push(...curveDebug.blocking_reasons.slice(0,5))}if(inputPoints<=0&&validPoints<=0&&(!Array.isArray(curve)||!curve.length)){reasons.push('Aucun point running exploitable pour construire la courbe.')}if(validPoints>0&&Array.isArray(curve)&&curve.length<3){reasons.push('Pas encore assez de points stables pour lisser la courbe correctement.')}const state=ready?'ready':(inputPoints>0||validPoints>0||reasons.length?'recalculation_required':'unavailable');const label=ready?'Prête':state==='recalculation_required'?'Recalcul nécessaire':'Indisponible';return{state,label,reason:reasons[0]||'Courbe pace / FC indisponible.',details:reasons,points:Array.isArray(curve)?curve.length:0,inputPoints,validPoints}}
function buildDashboardReadiness(payload,{windowed=null}={}){const analysis=payload?.analysis||{};const metrics=analysis.metrics||{};const trend=analysis.trend||{};const importStatus=payload?.import_status||{};const latestRun=importStatus.latest_run||payload?.health?.latest_sync_run||null;const activeWindow=windowed||buildTrendWindowSeries(trend,state.dashboardWindowDays);const readiness={volume:buildSeriesReadiness(activeWindow.runningSeries,{name:'Volume running'}),bike:buildSeriesReadiness(activeWindow.bikeSeries,{name:'Volume vélo'}),loadRatio:buildSeriesReadiness(activeWindow.loadRatioSeries,{name:'Charge relative',emptyReason:'Le ratio 7j/28j nécessite des séries de charge locales.'}),sleep:buildSeriesReadiness(activeWindow.sleepSeries,{name:'Sommeil',emptyReason:'Le sommeil est calculé à partir des signaux wellness locaux.'}),restingHr:buildSeriesReadiness(activeWindow.restingHrSeries,{name:'FC repos',emptyReason:'La FC repos demande des mesures wellness exploitables.'}),hrv:buildSeriesReadiness(activeWindow.hrvSeries,{name:'HRV',emptyReason:'La HRV dépend des mesures wellness locales.'}),cadence:buildSeriesReadiness(activeWindow.cadenceSeries,{name:'Cadence',emptyReason:'La cadence doit remonter depuis les activités running.'}),runningPace:buildSeriesReadiness(activeWindow.runningPaceSeries,{name:'Allure running',emptyReason:'Les activités running sont nécessaires pour reconstruire l’allure.'}),runningHr:buildSeriesReadiness(activeWindow.runningHrSeries,{name:'FC running',emptyReason:'Les activités running sont nécessaires pour reconstruire la FC.'}),paceCurve:buildPaceCurveReadiness(activeWindow.paceCurveDebug||metrics.pace_hr_curve_debug||{},activeWindow.paceCurve||[])};const anySeries=Object.values(readiness).some((entry)=>Number(entry.points||0)>0);const requiredReady=['volume','loadRatio','sleep','restingHr','hrv','cadence','runningPace','runningHr'].every((key)=>readiness[key].state==='ready');const paceReady=readiness.paceCurve.state==='ready';const hasDb=payload?.db_available===true;const hasImport=importStatus.available===true;let stateLabel='unavailable';let label='Données indisponibles';const details=[];if(!hasDb||!hasImport){stateLabel='unavailable';label='Données indisponibles';details.push('Le workspace local n’est pas encore complètement chargé.')}else if(requiredReady&&paceReady){stateLabel='ready';label='Analyse prête';details.push('Les séries clés sont présentes et la courbe pace / FC est exploitable.')}else if(readiness.paceCurve.state==='recalculation_required'||(hasDb&&anySeries&&(!paceReady||!requiredReady))){stateLabel='recalculation_required';label='Recalcul nécessaire';if(readiness.paceCurve.reason)details.push(readiness.paceCurve.reason);if(!readiness.cadence.points)details.push('La cadence ne remonte pas correctement sur la fenêtre active.');if(!readiness.runningPace.points||!readiness.runningHr.points)details.push('Les séries running utiles à la courbe ne sont pas assez stables.')}else if(anySeries){stateLabel='partial_data';label='Données partielles';details.push('Certaines cartes sont prêtes, d’autres attendent encore des points exploitables.')}else{stateLabel='unavailable';label='Données indisponibles';details.push('Aucune série exploitable n’a encore été chargée.')}const primaryReason=details[0]||readiness.paceCurve.reason||'Lecture des données indisponible.';return repairTextTree({state:stateLabel,label,reason:primaryReason,details,latestRun,chartStates:readiness})}
function buildCardReadiness(card){if(!card)return{state:'unavailable',label:'Indisponible',reason:'Carte indisponible.',details:[]};if(card.chartType==='curve'){return card.diagnostics?.ready===true?{state:'ready',label:'Prête',reason:'Courbe pace / FC exploitable.',details:[]} : buildPaceCurveReadiness(card.diagnostics||{},card.curve||[])}if(card.chartType==='triptych'){const pace=buildSeriesReadiness(card.paceSeries||[],{name:'Allure',minPoints:1,emptyReason:'Aucune allure running exploitable.'});const cadence=buildSeriesReadiness(card.cadenceSeries||[],{name:'Cadence',minPoints:1,emptyReason:'Aucune cadence running exploitable.'});const hr=buildSeriesReadiness(card.hrSeries||[],{name:'FC',minPoints:1,emptyReason:'Aucune FC running exploitable.'});const parts=[pace,cadence,hr];const ready=parts.every((item)=>item.state==='ready');const unavailable=parts.every((item)=>item.state==='unavailable');const state=ready?'ready':unavailable?'unavailable':'partial_data';return{state,label:ready?'Prête':state==='partial_data'?'Partielle':'Indisponible',reason:parts.find((item)=>item.state!=='ready')?.reason||'Le triptyque attend des données running stables.',details:parts.filter((item)=>item.state!=='ready').map((item)=>item.reason).filter(Boolean),parts}}if(card.chartType==='zones'){const overallSeconds=Number(card.zonesAll?.total_seconds||0);const runningSeconds=Number(card.zonesRunning?.total_seconds||0);const total=Math.max(overallSeconds,runningSeconds);return total>0?{state:'ready',label:'Prête',reason:'Répartition des zones disponible.',details:[]}:{state:'unavailable',label:'Indisponible',reason:'Aucune répartition de zones disponible.',details:[]}}const series=Array.isArray(card.series)?card.series:[];const minPoints=card.key==='weekly-volume'||card.key==='bike-volume'||card.key==='charge'||card.key==='charge-ratio'||card.key==='sleep'||card.key==='resting-hr'||card.key==='hrv'||card.key==='cadence'?1:1;return buildSeriesReadiness(series,{name:card.title||'Carte',minPoints,emptyReason:`Aucune série exploitable pour ${card.title||'cette carte'}.`})}
function buildEmptyChartOptions(readiness){const chartReadiness=readiness||{};return{emptyTitle:chartReadiness.label||'Données indisponibles',emptyReason:chartReadiness.reason||'',emptyNotes:Array.isArray(chartReadiness.details)?chartReadiness.details:[],emptyAdvice:'Si les données existent déjà, lance un recalcul pour reconstruire les dérivées.'}}
function normalizeDashboardWindowDays(value){const parsed=Number(value);if(!Number.isFinite(parsed))return 90;const allowed=[30,90,365];return allowed.includes(parsed)?parsed:(parsed<=30?30:parsed<=90?90:365)}
function dashboardWindowLabel(days){return days<=30?'1 mois':days<=90?'3 mois':'1 an'}
function dashboardWindowDetail(days){return `${dashboardWindowLabel(days)} · ${days} jours`}
function renderDashboardWindowControls(activeDays=90){const buttons=Array.from(document.querySelectorAll('.dashboard-window-button'));buttons.forEach((button)=>{const days=normalizeDashboardWindowDays(button.dataset.days);const active=days===normalizeDashboardWindowDays(activeDays);button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));button.textContent=dashboardWindowLabel(days)})}
async function setDashboardWindowDays(days){state.dashboardWindowDays=normalizeDashboardWindowDays(days);localStorage.setItem(STORAGE_KEYS.dashboardWindowDays,String(state.dashboardWindowDays));renderDashboardWindowControls(state.dashboardWindowDays);await refreshDashboard({reason:'dashboard-window-change',days:state.dashboardWindowDays});if(state.openTrendKey){const refreshedCard=resolveDashboardModalCard(state.openTrendKey);if(refreshedCard)renderDashboardModal(refreshedCard)}}
function dashboardWindowOptions(){return [30,90,365]}
function renderDetailBlocks(container,card){
  const parts=[];
  if(card.calculation)parts.push(`<div class="detail-block"><h4>Calcul</h4><p>${safeChartText(card.calculation)}</p></div>`);
  if(card.provenance)parts.push(`<div class="detail-block"><h4>Provenance</h4><p>${safeChartText(card.provenance)}</p></div>`);
  if(card.reading)parts.push(`<div class="detail-block"><h4>Lecture</h4><p>${safeChartText(card.reading)}</p></div>`);
  if(Array.isArray(card.referenceNotes)&&card.referenceNotes.length)parts.push(`<div class="detail-block"><h4>Références</h4><ul class="detail-list">${card.referenceNotes.map((note)=>`<li>${safeChartText(note)}</li>`).join('')}</ul></div>`);
  container.innerHTML=parts.join('');
}function renderDonutComparison(container,overall,running,options={}){
  const zones=[
    {key:1,label:'Z1',color:'#4da3ff'},
    {key:2,label:'Z2',color:'#4fd1a5'},
    {key:3,label:'Z3',color:'#b6e05c'},
    {key:4,label:'Z4',color:'#ffbe55'},
    {key:5,label:'Z5',color:'#ff6b6b'},
  ];
  const normalize=(distribution)=>zones.map((zone)=>{
    const match=Array.isArray(distribution)?distribution.find((entry)=>Number(entry.zone)===zone.key):null;
    return {
      zone: zone.label,
      color: zone.color,
      minutes: Number(match?.minutes||0),
      seconds: Number(match?.seconds||0),
      share: Number(match?.share||0),
    };
  });
  const renderDonut=(distribution,title,id)=>{
    const total=distribution.reduce((sum,entry)=>sum+Number(entry.seconds||0),0)||1;
    const size=190;
    const radius=68;
    const cx=95;
    const cy=95;
    let offset=25;
    const segments=distribution.map((entry)=>{
      const percent=Math.max(Number(entry.seconds||0)/total,0);
      const length=percent*360;
      const segment=`<circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="${entry.color}" stroke-width="18" stroke-linecap="round" stroke-dasharray="${length.toFixed(3)} ${Math.max(360-length,0.001).toFixed(3)}" stroke-dashoffset="${offset.toFixed(3)}" transform="rotate(-90 ${cx} ${cy})"></circle>`;
      offset-=length;
      return segment;
    }).join('');
    return `<div class="zone-donut"><svg viewBox="0 0 190 190" aria-label="${title}"><circle cx="${cx}" cy="${cy}" r="${radius}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="18"></circle>${segments}<circle cx="${cx}" cy="${cy}" r="48" fill="rgba(6, 10, 18, 0.88)"></circle><text x="95" y="90" text-anchor="middle" class="chart-axis-title">${title}</text><text x="95" y="109" text-anchor="middle" class="chart-note">${formatNumber(total/60,1)} h</text></svg><div class="zone-legend">${distribution.map((entry)=>`<div class="zone-legend-row"><span><i style="background:${entry.color};width:10px;height:10px;border-radius:999px;display:inline-block;margin-right:8px"></i>${entry.zone}</span><span>${formatNumber(entry.minutes,1)} min Â· ${formatNumber((entry.share||0)*100,0)}%</span></div>`).join('')}</div></div>`;
  };
  const overallData=normalize(overall?.distribution||[]);
  const runningData=normalize(running?.distribution||[]);
  container.innerHTML=`<div class="zone-comparison"><div class="zone-comparison-grid">${renderDonut(overallData, options.overallLabel || 'Toutes activitÃ©s', `${options.id||'zones'}-all`)}${renderDonut(runningData, options.runningLabel || 'Running', `${options.id||'zones'}-run`)}</div><p class="status-line">${options.note||'RÃ©partition approximative du temps passÃ© par zones FC Ã  partir de la FC moyenne des activitÃ©s.'}</p></div>`;
}
function renderTriptychChart(container,paceSeries,cadenceSeries,hrSeries,options={}){
  const labels=options.labels||{};
  const paceItems=Array.isArray(paceSeries)?paceSeries.filter((item)=>item&&Number.isFinite(Number(item.value??item.pace_min_per_km??item.distance_km??item.load_ratio_7_28??item.sleep_hours??item.resting_hr??item.cadence_spm??item.hrv_ms??item.heart_rate))):[];
  const cadenceItems=Array.isArray(cadenceSeries)?cadenceSeries.filter((item)=>item&&Number.isFinite(Number(item.value??item.cadence_spm))):[];
  const hrItems=Array.isArray(hrSeries)?hrSeries.filter((item)=>item&&Number.isFinite(Number(item.value??item.heart_rate))):[];
  if(!paceItems.length&&!cadenceItems.length&&!hrItems.length){
    const emptyTitle=safeChartText(options.emptyTitle||'Courbe indisponible');
    const emptyReason=safeChartText(options.emptyReason||'Les trois panneaux n’ont pas encore de séries exploitables.');
    const emptyNotes=Array.isArray(options.emptyNotes)?options.emptyNotes.filter(Boolean):[];
    container.innerHTML=`<div class="chart-shell"><p class="status-line">${emptyTitle}</p><div class="detail-block"><p>${emptyReason}</p>${emptyNotes.length?`<ul class="detail-list">${emptyNotes.map((note)=>`<li>${safeChartText(note)}</li>`).join('')}</ul>`:''}</div></div>`;
    return;
  }
  container.innerHTML=`<div class="triptych-grid"><div class="triptych-panel"><span class="card-label">${safeChartText(labels.pace||'Allure')}</span><div class="triptych-chart" data-triptych="pace"></div></div><div class="triptych-panel"><span class="card-label">${safeChartText(labels.cadence||'Cadence')}</span><div class="triptych-chart" data-triptych="cadence"></div></div><div class="triptych-panel"><span class="card-label">${safeChartText(labels.hr||'FC')}</span><div class="triptych-chart" data-triptych="hr"></div></div></div>`;
  const paceNode=container.querySelector('[data-triptych="pace"]');
  const cadenceNode=container.querySelector('[data-triptych="cadence"]');
  const hrNode=container.querySelector('[data-triptych="hr"]');
  const width=options.width||760;
  const height=options.height||190;
  const tickCount=options.xTickCount||(width>=900?7:5);
  renderSparkline(paceNode,paceSeries,{id:`${options.id||'triptych'}-pace`,stroke:'#8ae6c0',fill:'rgba(138, 230, 192, 0.18)',width,height,title:'Allure',yLabel:'min/km',tickFormatter:(value)=>formatPace(value),xTickFormatter:options.xTickFormatter,xTickCount:tickCount,yTickCount:options.yTickCount||5,referenceLines:options.paceReferenceLines||[],referenceBands:options.paceReferenceBands||[]});
  renderSparkline(cadenceNode,cadenceSeries,{id:`${options.id||'triptych'}-cadence`,stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.18)',width,height,title:'Cadence',yLabel:'spm',tickFormatter:(value)=>`${formatNumber(value,0)} spm`,xTickFormatter:options.xTickFormatter,xTickCount:tickCount,yTickCount:options.yTickCount||5,referenceLines:options.cadenceReferenceLines||[]});
  renderSparkline(hrNode,hrSeries,{id:`${options.id||'triptych'}-hr`,stroke:'#ffbe55',fill:'rgba(255, 190, 85, 0.18)',width,height,title:'FC',yLabel:'bpm',tickFormatter:(value)=>`${formatNumber(value,0)} bpm`,xTickFormatter:options.xTickFormatter,xTickCount:tickCount,yTickCount:options.yTickCount||5,referenceLines:options.hrReferenceLines||[],referenceBands:options.hrReferenceBands||[]});
}function buildTrendModalCard(key){const payload=currentPayload();const analysis=currentAnalysis();const metrics=currentMetrics();const trend=analysis.trend||{};const importStatus=currentImportStatus();const benchmark=analysis.benchmark||{};const windowed=buildTrendWindowSeries(trend,state.dashboardWindowDays);const paceCurve=Array.isArray(windowed.paceCurve)?windowed.paceCurve:[];const paceCurveDebug=windowed.paceCurveDebug||metrics.pace_hr_curve_debug||{};const runningSeries=Array.isArray(windowed.runningSeries)?windowed.runningSeries:[];const bikeSeries=Array.isArray(windowed.bikeSeries)?windowed.bikeSeries:[];const loadRatioSeries=Array.isArray(windowed.loadRatioSeries)?windowed.loadRatioSeries:[];const sleepSeries=Array.isArray(windowed.sleepSeries)?windowed.sleepSeries:[];const restingHrSeries=Array.isArray(windowed.restingHrSeries)?windowed.restingHrSeries:[];const hrvSeries=Array.isArray(windowed.hrvSeries)?windowed.hrvSeries:[];const cadenceSeries=Array.isArray(windowed.cadenceSeries)?windowed.cadenceSeries:[];const runningPaceSeries=Array.isArray(windowed.runningPaceSeries)?windowed.runningPaceSeries:[];const runningHrSeries=Array.isArray(windowed.runningHrSeries)?windowed.runningHrSeries:[];const zonesAll=metrics.heart_rate_zone_share||trend.heart_rate_zone_share||{distribution:[]};const zonesRunning=metrics.heart_rate_zone_share_running||trend.heart_rate_zone_share_running||{distribution:[]};const cadenceTarget=metrics.cadence_target_spm||170;const cadenceRefLow=metrics.cadence_reference_low||cadenceTarget-5;const cadenceRefHigh=metrics.cadence_reference_high||cadenceTarget+5;const curveGap=paceCurveDebug.ready?`${paceCurveDebug.curve_points||paceCurve.length} points utiles`:[`Points source: ${paceCurveDebug.input_points||0}`,`Points valides: ${paceCurveDebug.valid_points||0}`,`Points cadence manquants: ${paceCurveDebug.missing_cadence||0}`,`Points allure/FC manquants: ${paceCurveDebug.missing_pace_or_hr||0}`,...(Array.isArray(paceCurveDebug.blocking_reasons)?paceCurveDebug.blocking_reasons.slice(0,4):[])].filter(Boolean).join(' · ') || 'Données insuffisantes';const runLatest=runningSeries.at(-1)?.distance_km||metrics.weekly_volume_km||null;const bikeLatest=bikeSeries.at(-1)?.distance_km||metrics.weekly_bike_volume_km||null;const loadLatest=loadRatioSeries.at(-1)?.load_ratio_7_28;const sleepLatest=sleepSeries.at(-1)?.sleep_hours;const restingLatest=restingHrSeries.at(-1)?.resting_hr;const hrvLatest=hrvSeries.at(-1)?.hrv_ms;const cadenceLatest=cadenceSeries.at(-1)?.cadence_spm||metrics.cadence_7d;const paceLatest=runningPaceSeries.at(-1)?.pace_min_per_km||metrics.running_pace_7d;const hrLatest=runningHrSeries.at(-1)?.heart_rate||metrics.running_hr_7d;switch(key){case'hrv':return{key,title:'HRV',value:hrvLatest===null||hrvLatest===undefined?'-':`${formatNumber(hrvLatest,1)} ms`,subtitle:`R?f ${formatBand(metrics.hrv_reference_low,metrics.hrv_reference_high,(value)=>`${formatNumber(value,1)} ms`)}`,detail:'HRV en moyenne glissante sur 7 jours ? partir des mesures wellness locales. Plus la valeur remonte vers la bande haute, plus la r?cup?ration est g?n?ralement favorable.',calculation:'Moyenne glissante 7 jours sur la s?rie wellness locale, avec filtrage des jours sans HRV exploitable.',provenance:'Donn?es wellness locales Garmin / export normalis?.',reading:'Bande basse = alerte r?cup?ration, bande haute = zone plus confortable. La bonne lecture se fait avec le sommeil et la FC repos.',referenceNotes:[`R?f basse: ${formatBand(metrics.hrv_reference_low,metrics.hrv_reference_high,(value)=>`${formatNumber(value,1)} ms`)}`,'Comparer avec la FC repos et la charge 7j/28j avant de conclure.'],chartType:'single',series:hrvSeries,tickFormatter:(value)=>`${formatNumber(value,1)} ms`,stroke:'#a38bff',fill:'rgba(163, 139, 255, 0.18)' };case'zones-all':return{key,title:'Zones FC globales',value:`${formatNumber((zonesAll.total_seconds||0)/3600,1)} h`,subtitle:'Toutes activit?s',detail:'R?partition approximative du temps pass? en zones FC sur toutes les activit?s index?es. La part de chaque zone est pond?r?e par la dur?e de l?activit? et la FC moyenne d?tect?e.',calculation:'Dur?e des activit?s pond?r?e par la FC moyenne de chaque activit?.',provenance:'Activit?s locales Garmin + seuils de zones issus du profil de zones enregistr?.',reading:'Les zones basses doivent dominer la base. Les zones hautes doivent rester des ?pisodes intentionnels, sinon la charge cardio d?rive trop vite.',referenceNotes:['Lecture globale des zones cardio sur le mix complet des sports.','Les fractions tr?s courtes ou les activit?s incompl?tes sont sous-pond?r?es.'],chartType:'zones',zonesAll, zonesRunning, note:'Vue globale sur toutes les activit?s.'};case'zones-running':return{key,title:'Zones FC running',value:`${formatNumber((zonesRunning.total_seconds||0)/3600,1)} h`,subtitle:'Running uniquement',detail:'M?me logique que la vue globale, mais filtr?e sur le running. C?est la vue ? privil?gier pour discuter de la charge cardio utile au coach.',calculation:'Dur?e des activit?s running pond?r?e par la FC moyenne de chaque activit?.',provenance:'Activit?s running locales Garmin + zones cardio d?tect?es dans le profil utilisateur.',reading:'Cette vue permet d??viter que le v?lo ou la muscu masquent la lecture cardio running.',referenceNotes:['Comparer cette vue ? la vue globale pour mesurer le poids r?el du running.'],chartType:'zones',zonesAll, zonesRunning, note:'Vue running uniquement.'};case'pace-cadence-hr':return{key,title:'Pace / cadence / FC',value:`${paceLatest?formatPace(paceLatest):'-'} ? ${cadenceLatest===null||cadenceLatest===undefined?'-':`${formatNumber(cadenceLatest,0)} spm`} ? ${hrLatest===null||hrLatest===undefined?'-':formatHeartRate(hrLatest)}`,subtitle:`Triptyque ${dashboardWindowDetail(state.dashboardWindowDays)} ? ${paceCurveDebug.ready?`${paceCurveDebug.curve_points} points courbe`:'diagnostic requis'}`,detail:`Triptyque align? sur ${dashboardWindowLabel(state.dashboardWindowDays).toLowerCase()} pour voir si l'allure, la cadence et la FC ?voluent ensemble. ${paceCurveDebug.ready ? 'La modal donne la lecture compl?te avec axes et rep?res.' : `Courbe pace / FC indisponible: ${curveGap}`}`,calculation:`S?ries journali?res running + cadence + FC, align?es sur ${dashboardWindowDetail(state.dashboardWindowDays).toLowerCase()} et affich?es en trois panneaux synchronis?s.`,provenance:'Activit?s running, cadence issue des activit?s normalis?es, FC issue des r?sum?s running.',reading:'L?objectif est de voir la cadence monter vers 170 spm sans explosion de FC ? allure donn?e.',referenceNotes:[`Cadence cible: ${cadenceTarget} spm (bande ${cadenceRefLow}-${cadenceRefHigh} spm).`,`Regarder la coh?rence des trois panneaux plut?t qu?une valeur isol?e.`],chartType:'triptych',paceSeries:runningPaceSeries,cadenceSeries:cadenceSeries,hrSeries:runningHrSeries,xTickFormatter:(item)=>item.label||'',paceReferenceLines:[{value:paceCurve[0]?.pace_min_per_km,label:'allure lente',color:'#8ae6c0'},{value:paceCurve.at(-1)?.pace_min_per_km,label:'allure rapide',color:'#ffbe55'}].filter((item)=>Number.isFinite(Number(item.value))),cadenceReferenceLines:[{value:cadenceRefLow,label:`bande basse ${formatNumber(cadenceRefLow,0)}`,color:'#8ab4ff'},{value:cadenceTarget,label:`cible ${cadenceTarget}`,color:'#8ae6c0'},{value:cadenceRefHigh,label:`bande haute ${formatNumber(cadenceRefHigh,0)}`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))),hrReferenceBands:[{low:metrics.resting_hr_reference_low,high:metrics.resting_hr_reference_high,color:'#8ab4ff',label:'FC repos'}]};default:return null;}}
function openTrendModal(key){
  const payload=currentPayload();
  const aliasMap={
    'running-volume':'weekly-volume',
    'load-ratio':'charge-ratio',
    'pace-hr':'pace-hr',
  };
  const cardKey=aliasMap[key]||key;
  const dashboardCard=dashboardCardSpecs(payload).find((item)=>item.key===cardKey);
  if(dashboardCard){
    state.openTrendKey=dashboardCard.key;
    addTerminalLog('info','dashboard',`Carte ouverte: ${dashboardCard.title}`);
    renderDashboardModal(dashboardCard);
    return;
  }
  const card=buildTrendModalCard(key);
  if(!card){return}
  state.openTrendKey=cardKey;
  addTerminalLog('info','dashboard',`Carte ouverte: ${card.title}`);
  renderDashboardModal(card)
}
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
  const diagnostics=options.diagnostics||{};
  const values=Array.isArray(curve)?curve.filter((point)=>Number.isFinite(Number(point?.pace_min_per_km))&&Number.isFinite(Number(point?.heart_rate))):[];
  if(values.length<3){
    const reasons=Array.isArray(diagnostics.blocking_reasons)&&diagnostics.blocking_reasons.length?diagnostics.blocking_reasons:['Pas encore assez de points stables pour une courbe pace / FC.'];
    const diagnosticLabel=diagnostics.ready===false&&(diagnostics.input_points||diagnostics.valid_points)?'Recalcul nécessaire':'Courbe indisponible';
    container.innerHTML=`<div class="chart-shell"><p class="status-line">${safeChartText(diagnosticLabel)}</p><div class="detail-block"><h4>Pourquoi</h4><ul class="detail-list">${reasons.map((reason)=>`<li>${safeChartText(reason)}</li>`).join('')}</ul></div><div class="detail-block"><h4>Lecture</h4><p>On attend au minimum ${diagnostics.stability_threshold?.min_points || 3} sorties running stables avec allure et FC exploitables. Les fractions très courtes, les échauffements et les retours au calme sont sous-pondérés.</p><p>Si les données existent déjà mais que la courbe reste vide, relance le recalcul pour régénérer les dérivées et vérifier les filtres.</p></div></div>`;
    return;
  }
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
  const paceReferenceValues=[...(Array.isArray(options.paceReferenceLines)?options.paceReferenceLines.map((entry)=>Number(entry.value)):[]),...(Array.isArray(options.paceReferenceBands)?options.paceReferenceBands.flatMap((band)=>[Number(band.low),Number(band.high)]):[])].filter((value)=>Number.isFinite(value));
  const hrReferenceValues=[...(Array.isArray(options.hrReferenceLines)?options.hrReferenceLines.map((entry)=>Number(entry.value)):[]),...(Array.isArray(options.hrReferenceBands)?options.hrReferenceBands.flatMap((band)=>[Number(band.low),Number(band.high)]):[])].filter((value)=>Number.isFinite(value));
  const paceDomain=buildChartDomain(paces,paceReferenceValues,{padRatio:options.pacePadRatio??0.04,minSpan:0.25});
  const hrDomain=buildChartDomain(heartRates,hrReferenceValues,{padRatio:options.hrPadRatio??0.06,minSpan:8});
  const paceMin=paceDomain.min;
  const paceMax=paceDomain.max;
  const hrMin=hrDomain.min;
  const hrMax=hrDomain.max;
  const paceSpan=paceDomain.span||1;
  const hrSpan=hrDomain.span||1;
  const points=sorted.map((point,index)=>{
    const pace=Number(point.pace_min_per_km);
    const x=padLeft+((paceMax-pace)/paceSpan)*(width-padLeft-padRight);
    const y=height-padBottom-((Number(heartRates[index])-hrMin)/hrSpan)*(height-padTop-padBottom);
    return {x,y,point,heartRate:Number(heartRates[index]),pace};
  });
  const yTicks=buildChartTicks(hrMin,hrMax,options.yTickCount||(height>=300?7:5));
  const xTicks=buildChartTicks(paceMin,paceMax,options.xTickCount||(width>=900?7:5));
  const segments=points.slice(1).map((point,index)=>{
    const prev=points[index];
    const stroke=zoneColorForHeartRate(point.heartRate,options.maxHrEstimate);
    return `<line x1="${prev.x.toFixed(2)}" y1="${prev.y.toFixed(2)}" x2="${point.x.toFixed(2)}" y2="${point.y.toFixed(2)}" stroke="${stroke}" stroke-width="4" stroke-linecap="round" />`;
  }).join('');
  const legend=[['Bleu', '#4da3ff'],['Vert', '#4fd1a5'],['Jaune', '#b6e05c'],['Orange', '#ffbe55'],['Rouge', '#ff6b6b']];
  container.innerHTML=`<div class="chart-shell curve-wrap"><svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${safeChartText('Courbe pace et fréquence cardiaque')}"><defs><linearGradient id="curve-glow-${options.id||'pace'}" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="rgba(74, 163, 255, 0.12)" /><stop offset="100%" stop-color="rgba(255, 107, 107, 0.12)" /></linearGradient></defs><rect x="0" y="0" width="${width}" height="${height}" fill="url(#curve-glow-${options.id||'pace'})" opacity="0.34"></rect><line class="chart-axis-line" x1="${padLeft}" y1="${height-padBottom}" x2="${width-padRight}" y2="${height-padBottom}"></line><line class="chart-axis-line" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${height-padBottom}"></line>${yTicks.map((tick)=>{const ratio=(tick-hrMin)/hrSpan;const y=height-padBottom-ratio*(height-padTop-padBottom);return `<g><line class="chart-grid-line" x1="${padLeft}" y1="${y.toFixed(2)}" x2="${width-padRight}" y2="${y.toFixed(2)}"></line><text class="chart-axis-tick" x="${padLeft-8}" y="${(y+4).toFixed(2)}" text-anchor="end">${formatNumber(tick,0)} bpm</text></g>`}).join('')}<path d="M ${points.map((point)=>`${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"></path>${segments}${points.map((point,index)=>{const stroke=zoneColorForHeartRate(point.heartRate,options.maxHrEstimate);const label=formatPace(point.pace);return `<circle class="chart-point-dot" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${index===points.length-1?4.8:3.8}" fill="${stroke}" data-title="${safeChartText(label)}" data-value="${safeChartText(formatHeartRate(point.heartRate))}" data-detail="${safeChartText(point.point.cadence_spm?`${formatNumber(point.point.cadence_spm,0)} spm · ${point.point.point_count||1} point(s)`:`${point.point.point_count||1} point(s)`)}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle><circle class="chart-point-hit" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="12" data-title="${safeChartText(label)}" data-value="${safeChartText(formatHeartRate(point.heartRate))}" data-detail="${safeChartText(point.point.cadence_spm?`${formatNumber(point.point.cadence_spm,0)} spm · ${point.point.point_count||1} point(s)`:`${point.point.point_count||1} point(s)`)}" data-tx="${Math.max(8, Math.min(width-180, point.x+12)).toFixed(2)}" data-ty="${Math.max(18, point.y-12).toFixed(2)}"></circle>`}).join('')}<text class="chart-axis-title" x="${padLeft}" y="${16}">FC (bpm)</text><text class="chart-axis-title" x="${width-padRight}" y="${height-6}" text-anchor="end">Allure (min/km)</text>${xTicks.map((tick)=>{const x=padLeft+((paceMax-tick)/paceSpan)*(width-padLeft-padRight);return `<text class="chart-axis-tick" x="${x.toFixed(2)}" y="${height-8}" text-anchor="middle">${formatPace(tick)}</text>`}).join('')}</svg><div class="curve-legend">${legend.map(([label,color])=>`<span><i style="background:${color}"></i>${safeChartText(label)}</span>`).join('')}</div><div class="chart-tooltip" aria-hidden="true"></div></div>`;const tooltip=chartTooltipLabel(container);attachChartTooltipHandlers(container,tooltip,Array.from(container.querySelectorAll('.chart-point-hit, .chart-point-dot')))
}function renderSectionHeader(){const meta=sectionMeta[state.activeSection]||sectionMeta.import;if(dom.sectionEyebrow) dom.sectionEyebrow.textContent=meta.eyebrow;if(dom.sectionTitle) dom.sectionTitle.textContent=meta.title;if(dom.sectionDescription) dom.sectionDescription.textContent=meta.description}
function updateNavVisibility(){if(!state.showTerminalMenu&&state.activeSection==='terminal'){state.activeSection='import';localStorage.setItem(STORAGE_KEYS.activeSection,state.activeSection)}dom.navButtons.forEach((button)=>{const section=button.dataset.section;const active=section===state.activeSection;button.classList.toggle('hidden',section==='terminal'&&!state.showTerminalMenu);button.classList.toggle('active',active);button.setAttribute('aria-current',active?'page':'false');button.setAttribute('aria-pressed',String(active))})}
function renderSidebarStatus(){
  const payload=currentPayload();
  const provider=payload.provider||{};
  const importStatus=currentImportStatus();
  const analysis=currentAnalysis();
  const metrics=currentMetrics();
  const readiness=analysis.readiness||buildDashboardReadiness(payload)||{};
  const providerLabel=provider.status==='ready'
    ? `Provider ${provider.provider==='ollama'?'Ollama':provider.provider} prêt`
    : provider.status==='unchecked'
      ? `Provider ${provider.provider||state.provider} en vérification`
      : `Provider ${provider.provider||state.provider} indisponible`;
  dom.providerChip.textContent=providerLabel;
  dom.providerChip.classList.toggle('warn',provider.status==='unchecked');
  dom.providerChip.classList.toggle('error',provider.status==='unavailable');
  dom.dataChip.textContent=importStatus.available?'Données locales: oui':'Données locales: non';
  dom.dataChip.classList.toggle('warn',!importStatus.available);
  const latestActivityDay=importStatus.latest_activity_day||payload.latest_day||null;
  if(latestActivityDay){
    const age=daysBetween(latestActivityDay,new Date().toISOString().slice(0,10));
    dom.freshnessChip.textContent=`Dernière date: ${age===null?formatDateLabel(latestActivityDay):`${formatDateLabel(latestActivityDay)} · ${age} j`}`;
    dom.freshnessChip.classList.toggle('warn',typeof age==='number'&&age>=7);
  }else{
    dom.freshnessChip.textContent='Dernière date: -';
    dom.freshnessChip.classList.add('warn');
  }
  const objective=state.goalText||analysis.principal_objective||'';
  dom.objectiveChip.textContent=objective?`Objectif: ${objective.slice(0,42)}${objective.length>42?'…':''}`:'Objectif: aucun';
  dom.objectiveChip.classList.toggle('warn',!objective);
  dom.workspaceChip.textContent=`Workspace: ${state.workspace}`;
  if(dom.buildChip) dom.buildChip.textContent=`Build: ${APP_VERSION}`;
  if(dom.coachWorkspaceInput) dom.coachWorkspaceInput.value=state.workspace;
  if(dom.sectionBadges) dom.sectionBadges.innerHTML='';
  [
    {label:providerLabel,warn:provider.status==='unchecked'},
    {label:importStatus.state?`Import: ${importStatus.state}`:'Import: -',warn:importStatus.state==='empty'},
    {label:`Analyse: ${readiness.label|| (analysis.available?'prête':'en attente')}`,warn:readiness.state&&readiness.state!=='ready'},
    {label:metrics.weekly_volume_km!==undefined?`Volume 7j: ${formatKilometers(metrics.weekly_volume_km)}`:'Volume 7j: -',warn:metrics.weekly_volume_km===undefined},
  ].forEach((item)=>{
    const pill=document.createElement('span');
    pill.className=`pill pill-small${item.warn?' warn':''}`;
    pill.textContent=item.label;
    if(dom.sectionBadges) dom.sectionBadges.appendChild(pill);
  });
}
function setActiveSection(section,{persist=true,updateHash=true}={}){state.activeSection=section;if(persist)localStorage.setItem(STORAGE_KEYS.activeSection,section);if(updateHash&&window.location.hash!==`#${section}`){window.location.hash=section}document.documentElement.dataset.activeSection=section;updateNavVisibility();renderSectionHeader();renderAllSections()}
function renderSectionVisibility(){SECTIONS.forEach((section)=>{const node=document.getElementById(`section-${section}`);if(node)node.classList.toggle('hidden',state.activeSection!==section)})}
function renderImportSection(){
  const payload=currentPayload();
  const importStatus=currentImportStatus();
  const latestRun=importStatus.latest_run||payload.health?.latest_sync_run||null;
  const latestDay=importStatus.latest_activity_day||payload.latest_day||null;
  const syncState=importStatus.sync_state||payload.health?.sync_state||{};
  const syncAttempt=state.lastGarminSync||{};
  const sourcePath=state.sourcePath||dom.sourcePathInput.value||dom.sourcePathInputSettings.value||'';
  if(dom.importDataState) dom.importDataState.textContent=importStatus.available?(importStatus.state==='imported'?'Données locales importées':'Données locales indexées'):'Aucune donnée locale détectée';
  if(latestDay){
    const age=daysBetween(latestDay,new Date().toISOString().slice(0,10));
    if(dom.importFreshnessDetail) dom.importFreshnessDetail.textContent=`Dernière activité: ${formatDateLabel(latestDay)}${age===null?'':` · ${age} jours`}`;
    if(dom.importAgeState) dom.importAgeState.textContent=age===null?formatDateLabel(latestDay):`${age} jours`;
    if(dom.importAgeDetail) dom.importAgeDetail.textContent=age!==null&&age>=7?'Le jeu local semble un peu ancien. Un refresh manuel peut valoir le coup.':'La donnée locale paraît récente pour travailler dessus.';
  }else{
    if(dom.importFreshnessDetail) dom.importFreshnessDetail.textContent='Aucune activité locale n’est encore indexée pour ce workspace.';
    if(dom.importAgeState) dom.importAgeState.textContent='-';
    if(dom.importAgeDetail) dom.importAgeDetail.textContent='Lance un import Garmin pour rendre le workspace exploitable.';
  }
  if(dom.importRunState) dom.importRunState.textContent=latestRun?(latestRun.run_label||latestRun.run_id||latestRun.source_kind||'Import récent'):'Aucun import récent';
  if(dom.importRunDetail) dom.importRunDetail.textContent=latestRun?`${latestRun.total_records||0} enregistrements · ${latestRun.dataset_count||0} datasets · ${formatDateTime(latestRun.finished_at)}`:'Utilise l’import Garmin pour créer le workspace local.';
  if(dom.importSyncState) dom.importSyncState.textContent=syncAttempt.status==='error'?'Sync Garmin Connect échouée':syncAttempt.status==='running'?'Sync Garmin Connect en cours':latestRun&&String(latestRun.source_kind||'').includes('garmin')?'Sync Garmin Connect prête':'Sync Garmin Connect disponible';
  if(dom.importSyncDetail) dom.importSyncDetail.textContent=syncAttempt.message||(latestRun&&String(latestRun.source_kind||'').includes('garmin')?`Dernière sync: ${latestRun.run_label||latestRun.run_id||'-'} · ${latestRun.finished_at?formatDateTime(latestRun.finished_at):'-'} · nouveaux ${syncState.new_artifact_count!==undefined?syncState.new_artifact_count:'-'} · réutilisés ${syncState.reused_artifact_count!==undefined?syncState.reused_artifact_count:'-'}`:'La sync peut compléter les données locales sans bloquer l’app.');
  if(dom.importWorkspace) dom.importWorkspace.textContent=sourcePath||'-';
  if(dom.importWorkspaceDetail) dom.importWorkspaceDetail.textContent=sourcePath?'Le chemin saisi près du bouton Importer Garmin.':'Configure une source Garmin locale pour lancer l’import.';
}
function dashboardCardSpecs(payload){
  const analysis = payload.analysis || {};
  const metrics = analysis.metrics || {};
  const trend = analysis.trend || {};
  const importStatus = payload.import_status || {};
  const latestRun = importStatus.latest_run || payload.health?.latest_sync_run || null;
  const benchmark = analysis.benchmark || {};
  const windowed = buildTrendWindowSeries(trend, state.dashboardWindowDays);
  const paceCurveDebug = windowed.paceCurveDebug || metrics.pace_hr_curve_debug || {};
  const paceCurve = Array.isArray(windowed.paceCurve) ? windowed.paceCurve : [];
  const cadenceSeries = Array.isArray(windowed.cadenceSeries) ? windowed.cadenceSeries : [];
  const runningVolumeSeries = Array.isArray(windowed.runningSeries) ? windowed.runningSeries : [];
  const bikeVolumeSeries = Array.isArray(windowed.bikeSeries) ? windowed.bikeSeries : [];
  const loadRatioSeries = Array.isArray(windowed.loadRatioSeries) ? windowed.loadRatioSeries : [];
  const sleepSeries = Array.isArray(windowed.sleepSeries) ? windowed.sleepSeries : [];
  const restingHrSeries = Array.isArray(windowed.restingHrSeries) ? windowed.restingHrSeries : [];
  const cadenceTarget = metrics.cadence_target_spm || 170;
  const cadenceRefLow = metrics.cadence_reference_low || cadenceTarget - 5;
  const cadenceRefHigh = metrics.cadence_reference_high || cadenceTarget + 5;
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
  const benchmarkText = benchmark?.event && benchmark?.pace_min_per_km ? `${benchmark.event} repÃ¨re ${formatPace(benchmark.pace_min_per_km)}` : 'Courbe construite depuis les sorties utiles';
  const benchmarkSignal = benchmark?.event ? `${benchmark.event} Â· ${formatPace(benchmark.pace_min_per_km)}` : '-';
  const loadSubtitle = loadRef !== '-' ? `RÃ©f ${loadRef}` : 'Charge de rÃ©fÃ©rence indisponible';
  const cadenceSubtitle = cadenceRef !== '-' ? `RÃ©f ${cadenceRef}` : 'Cadence Ã  contextualiser';
  return [
    { key:'weekly-volume', title:'Volume hebdo', value:formatKilometers(metrics.weekly_volume_km ?? metrics.total_distance_km_7d), subtitle:`${formatNumber(metrics.weekly_running_days ?? metrics.recent_running_days ?? 0)} sorties · ${dashboardWindowDetail(state.dashboardWindowDays)}`, detail:'Volume running uniquement. Le vélo et la muscu sont suivis à part pour éviter de contaminer la lecture endurance.', calculation:`Somme des kilomètres running visibles sur ${dashboardWindowDetail(state.dashboardWindowDays).toLowerCase()}, issue du retraitement local des activités running.`, provenance:'Activités running locales Garmin normalisées dans le workspace.', reading:'On lit surtout la régularité du volume et les ruptures de charge. Le vélo reste sur une courbe séparée pour garder une lecture running propre.', referenceNotes:['Le volume affiché ici exclut le vélo et la musculation.','Les jours à zéro sont normaux si aucune sortie running n’a eu lieu.'], signals:[{label:'Dernier jour local',value:formatDateLabel(payload.latest_day || importStatus.latest_activity_day)},{label:'Dernier import',value:latestRun ? formatDateTime(latestRun.finished_at) : '-'}], chartType:'single', series:volumeSeries, tickFormatter:formatAxisKilometers, yLabel:'km', tone:'primary' },
    { key:'bike-volume', title:'Vélo hebdo', value:formatKilometers(metrics.weekly_bike_volume_km), subtitle:`${formatNumber(metrics.weekly_bike_days ?? metrics.recent_bike_days ?? 0)} sorties vélo · ${dashboardWindowDetail(state.dashboardWindowDays)}`, detail:'Le volume vélo est isolé du running pour garder des métriques d’endurance lisibles. Il reste utile, mais à part.', calculation:`Somme des kilomètres vélo visibles sur ${dashboardWindowDetail(state.dashboardWindowDays).toLowerCase()}, séparée volontairement du running.`, provenance:'Activités vélo locales Garmin normalisées dans le workspace.', reading:'La courbe vélo sert à lire la charge croisée sans polluer le tableau de bord running.', referenceNotes:['Le vélo n’entre pas dans le volume running principal.','Comparer surtout les semaines hautes, pas un point isolé.'], signals:[{label:'7 jours',value:formatKilometers(metrics.weekly_bike_volume_km)},{label:'Dernier import',value:latestRun ? formatDateTime(latestRun.finished_at) : '-'}], chartType:'single', series:bikeSeries, tickFormatter:formatAxisKilometers, yLabel:'km' },
    { key:'charge', title:'Charge', value:metrics.load_7d === null || metrics.load_7d === undefined ? '-' : formatNumber(metrics.load_7d,0), subtitle:loadSubtitle, detail:'La charge 7 jours doit toujours Ãªtre lue avec un repÃ¨re bas et un repÃ¨re haut. Sans cela, le chiffre seul nâ€™aide pas vraiment le coach.', signals:[{label:'28 jours',value:metrics.load_28d === null || metrics.load_28d === undefined ? '-' : formatNumber(metrics.load_28d,0)},{label:'Progression delta',value:metrics.progression_delta === null || metrics.progression_delta === undefined ? '-' : formatNumber(metrics.progression_delta,2)}], chartType:'single', series:loadSeries },
    { key:'charge-ratio', title:'Charge relative', value:metrics.load_ratio_7_28 === null || metrics.load_ratio_7_28 === undefined ? '-' : formatNumber(metrics.load_ratio_7_28,2), subtitle:`RÃ©f ${ratioRef}`, detail:'Le ratio compare la charge des 7 derniers jours à celle des 28 derniers jours. Autour de 1, la dynamique reste stable. Sous la bande basse, on ralentit. Au-dessus de la bande haute, on surveille le risque de fatigue ou d’overreaching.', signals:[{label:'Fatigue',value:metrics.fatigue_flag ? 'Oui' : 'Non'},{label:'Overreaching',value:metrics.overreaching_flag ? 'Oui' : 'Non'}], chartType:'single', series:loadRatioChartSeries, tickFormatter:(value)=>formatNumber(value,2), stroke:'#ffbe55', fill:'rgba(255, 190, 85, 0.22)', referenceLines:[{value:metrics.load_ratio_reference_low,label:`bande basse ${formatNumber(metrics.load_ratio_reference_low,2)}`,color:'#8ab4ff'},{value:1.0,label:'Ã©quilibre 1.00',color:'#8ae6c0'},{value:metrics.load_ratio_reference_high,label:`bande haute ${formatNumber(metrics.load_ratio_reference_high,2)}`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))), referenceBands:[{low:metrics.load_ratio_reference_low,high:metrics.load_ratio_reference_high,color:'rgba(255, 190, 85, 0.14)'}].filter((band)=>Number.isFinite(Number(band.low))&&Number.isFinite(Number(band.high))) },
    { key:'sleep', title:'Sommeil', value:metrics.sleep_hours_7d === null || metrics.sleep_hours_7d === undefined ? '-' : `${formatNumber(metrics.sleep_hours_7d,1)} h`, subtitle:sleepRef !== '-' ? `Réf ${sleepRef}` : 'Sommeil 7j', detail:'Le sommeil récent correspond à la moyenne des nuits sur 7 jours. Le but n’est pas d’avoir une valeur parfaite, mais un niveau compatible avec la charge du moment.', calculation:'Moyenne glissante sur 7 jours des nuits locales exploitables.', provenance:'Mesures wellness locales Garmin / export normalisé.', reading:'Une baisse simultanée du sommeil, de la HRV et une hausse de FC repos peuvent signaler une récupération moins bonne.', referenceNotes:[sleepRef !== '-' ? `Bande de référence ${sleepRef}` : 'Références non disponibles sur cette fenêtre.','Le graphe reste volontairement peu lissé pour garder la variabilité réelle.'], signals:[{label:'Récupération',value:metrics.overreaching_flag ? 'À surveiller' : 'Correcte'},{label:'Dernière activité',value:importStatus.latest_activity_day ? formatDateLabel(importStatus.latest_activity_day) : '-'}], chartType:'single', series:sleepChartSeries, tickFormatter:(value)=>`${formatNumber(value,1)} h`, stroke:'#8ae6c0', fill:'rgba(138, 230, 192, 0.2)', yLabel:'h', drawArea:false, referenceLines:[{value:metrics.sleep_reference_low,label:`bande basse ${formatNumber(metrics.sleep_reference_low,1)} h`,color:'#8ab4ff'},{value:metrics.sleep_reference_high,label:`bande haute ${formatNumber(metrics.sleep_reference_high,1)} h`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))), referenceBands:[{low:metrics.sleep_reference_low,high:metrics.sleep_reference_high,color:'rgba(138, 230, 192, 0.12)'}].filter((band)=>Number.isFinite(Number(band.low))&&Number.isFinite(Number(band.high))) },
    { key:'resting-hr', title:'FC repos', value:formatHeartRate(metrics.resting_hr_7d), subtitle:restingRef !== '-' ? `Réf ${restingRef}` : 'FC repos 7j', detail:'La FC repos récente complète la lecture récupération / stress. Si elle monte en même temps que la charge, le coach doit rester prudent.', calculation:'Moyenne glissante sur 7 jours des mesures de FC repos locales.', provenance:'Mesures wellness locales Garmin / export normalisé.', reading:'Une dérive vers le haut peut signaler fatigue, stress ou récupération incomplète. La lecture se fait avec la HRV et le sommeil.', referenceNotes:[restingRef !== '-' ? `Bande de référence ${restingRef}` : 'Références non disponibles sur cette fenêtre.','Le graphe garde les variations journalières utiles, sans lisser à outrance.'], signals:[{label:'HRV 7j',value:metrics.hrv_7d === null || metrics.hrv_7d === undefined ? '-' : formatNumber(metrics.hrv_7d,1)},{label:'Fatigue',value:metrics.fatigue_flag ? 'Oui' : 'Non'}], chartType:'single', series:restingHrChartSeries, tickFormatter:(value)=>`${formatNumber(value,0)} bpm`, stroke:'#8ab4ff', fill:'rgba(138, 180, 255, 0.2)', yLabel:'bpm', drawArea:false, referenceLines:[{value:metrics.resting_hr_reference_low,label:`bande basse ${formatNumber(metrics.resting_hr_reference_low,0)} bpm`,color:'#8ab4ff'},{value:metrics.resting_hr_reference_high,label:`bande haute ${formatNumber(metrics.resting_hr_reference_high,0)} bpm`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))), referenceBands:[{low:metrics.resting_hr_reference_low,high:metrics.resting_hr_reference_high,color:'rgba(138, 180, 255, 0.12)'}].filter((band)=>Number.isFinite(Number(band.low))&&Number.isFinite(Number(band.high))) },
    { key:'pace-hr', title:'Pace / FC', value:paceCurveLast ? `${formatPace(paceCurveLast.pace_min_per_km)} · ${formatHeartRate(paceCurveLast.heart_rate)}` : '-', subtitle:`Courbe monotone · ${paceCurve.length} points utiles`, detail:'La courbe conserve les points utiles des dernières sorties, puis les lisse pour rester monotone. Plus l’allure devient soutenue, plus la FC doit monter.', calculation:'Agrégation des points running utiles, exclusion des fractions trop courtes, puis lissage monotone de la relation allure / FC.', provenance:'Activités running locales Garmin, enrichies cadence et FC.', reading:'Si la courbe se décale vers le bas pour une allure donnée, l’efficacité aérobie progresse en général. Si elle est vide, ouvrir le diagnostic pour voir quels points manquent.', referenceNotes:[benchmark?.event ? `Repère actuel: ${benchmarkText}` : 'Pas de benchmark retenu sur cette fenêtre.','Les points courts, instables ou sans FC exploitable sont retirés de la courbe.'], signals:[{label:'Premier point',value:paceCurveFirst ? `${formatPace(paceCurveFirst.pace_min_per_km)} · ${formatHeartRate(paceCurveFirst.heart_rate)}` : '-'},{label:'Benchmark retenu',value:benchmarkSignal}], chartType:'curve', curve:paceCurve, maxHrEstimate:metrics.max_hr_estimate, diagnostics:paceCurveDebug },
    { key:'cadence', title:'Cadence', value:metrics.cadence_7d === null || metrics.cadence_7d === undefined ? '-' : `${formatNumber(metrics.cadence_7d,0)} spm`, subtitle:cadenceSubtitle, detail:'La cadence suit la qualité du geste et sa régularité sur les dernières sorties. Ici on parle bien de pas par minute, pas de kilomètres ni de cadence par jambe.', calculation:'Cadence running convertie en steps per minute à partir des champs Garmin double cadence quand ils existent, sinon conversion depuis la cadence par jambe.', provenance:'Activités running locales Garmin / payloads normalisés.', reading:'La cible actuelle reste proche de 170 spm. Une valeur autour de 150 spm est cohérente avec tes sorties actuelles ; une valeur proche de 70 signalerait une mauvaise unité.', referenceNotes:[`Cible ${cadenceTarget} spm, bande ${cadenceRefLow}-${cadenceRefHigh} spm.`,`La cadence doit être lue avec l’allure: monter la cadence sans regarder l’effort n’a pas de sens.`], signals:[{label:'28 jours',value:metrics.cadence_28d === null || metrics.cadence_28d === undefined ? '-' : `${formatNumber(metrics.cadence_28d,0)} spm`},{label:'Référence',value:cadenceRef}], chartType:'single', series:cadenceSeries, tone:'primary', yLabel:'spm', tickFormatter:(value)=>`${formatNumber(value,0)} spm`, drawArea:false, referenceLines:[{value:cadenceRefLow,label:`bande basse ${formatNumber(cadenceRefLow,0)} spm`,color:'#8ab4ff'},{value:cadenceTarget,label:`cible ${cadenceTarget} spm`,color:'#8ae6c0'},{value:cadenceRefHigh,label:`bande haute ${formatNumber(cadenceRefHigh,0)} spm`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))) },
  ];
}
function renderDashboardModal(card){
  if(!card)return;
  try{
    state.openTrendKey=card.key||state.openTrendKey||null;
    dom.dashboardModalTitle.textContent=card.title;
    dom.dashboardModalSubtitle.textContent=card.subtitle||'';
    renderDashboardWindowControls(state.dashboardWindowDays);
    const windowLabelNode=document.getElementById('dashboard-modal-window');
    if(windowLabelNode)windowLabelNode.textContent=dashboardWindowDetail(state.dashboardWindowDays);
    dom.dashboardModalValue.textContent=card.value||'-';
    renderDetailBlocks(dom.dashboardModalText,card);
    dom.dashboardModalSignals.innerHTML='';
    (card.signals||[]).forEach((signal)=>{
      const node=document.createElement('div');
      node.className='signal-line';
      node.innerHTML=`<strong>${safeChartText(signal.label)}</strong><span>${safeChartText(signal.value||'-')}</span>`;
      dom.dashboardModalSignals.appendChild(node);
    });
    const readiness=card.readiness||buildCardReadiness(card);
    const emptyReason=readiness.reason||card.detail||'';
    const emptyNotes=Array.isArray(readiness.details)&&readiness.details.length?readiness.details:[];
    if(card.chartType==='single'){
      renderSparkline(dom.dashboardModalChart,card.series||[],{id:`modal-${card.key}`,stroke:card.stroke||('#8ab4ff'),fill:card.fill||'rgba(138, 180, 255, 0.22)',width:1200,height:380,tickFormatter:card.tickFormatter,xTickCount:chartWindowTickCount(state.dashboardWindowDays),yTickCount:7,title:card.title,yLabel:card.yLabel||(card.key==='sleep'?'h':card.key==='resting-hr'?'bpm':card.key==='charge-ratio'?'ratio':'km'),referenceLines:card.referenceLines||[],referenceBands:card.referenceBands||[],emptyTitle:readiness.label||'Données indisponibles',emptyReason,emptyNotes,emptyAdvice:'Lance un recalcul si les données existent mais ne s’affichent pas encore.',drawArea:card.drawArea});
    }else if(card.chartType==='dual'){
      renderDualSparkline(dom.dashboardModalChart,card.seriesA||[],card.seriesB||[],{id:`modal-${card.key}`,width:1040,height:160});
    }else if(card.chartType==='curve'){
      renderMonotonePaceCurve(dom.dashboardModalChart,card.curve||[],{id:`modal-${card.key}`,width:1200,height:420,maxHrEstimate:card.maxHrEstimate,diagnostics:card.diagnostics,xTickCount:chartWindowTickCount(state.dashboardWindowDays),yTickCount:7});
    }else if(card.chartType==='zones'){
      renderDonutComparison(dom.dashboardModalChart,card.zonesAll,card.zonesRunning,{id:`modal-${card.key}`,overallLabel:'Toutes activités',runningLabel:'Running',note:card.note});
    }else if(card.chartType==='triptych'){
      renderTriptychChart(dom.dashboardModalChart,card.paceSeries||[],card.cadenceSeries||[],card.hrSeries||[],{id:`modal-${card.key}`,labels:{pace:'Allure',cadence:'Cadence',hr:'FC'},xTickFormatter:(item)=>item.label||'',width:1200,height:280,xTickCount:chartWindowTickCount(state.dashboardWindowDays),emptyTitle:readiness.label||'Courbe indisponible',emptyReason,emptyNotes,cadenceReferenceLines:card.cadenceReferenceLines||[],paceReferenceLines:card.paceReferenceLines||[],hrReferenceBands:card.hrReferenceBands||[]});
    }else{
      dom.dashboardModalChart.innerHTML="<p class='status-line'>Cette carte n'a pas de courbe dédiée.</p>";
    }
    dom.dashboardModal.classList.remove('hidden');
  }catch(error){
    addTerminalLog('error','dashboard',`Erreur de rendu modal ${card?.key||'unknown'}`,error.message);
    if(dom.dashboardModalTitle) dom.dashboardModalTitle.textContent=card?.title||'Carte indisponible';
    if(dom.dashboardModalSubtitle) dom.dashboardModalSubtitle.textContent='Le rendu a été protégé pour éviter un plantage.';
    if(dom.dashboardModalValue) dom.dashboardModalValue.textContent='-';
    if(dom.dashboardModalText) dom.dashboardModalText.innerHTML=`<div class="detail-block"><h4>Erreur de rendu</h4><p>${safeChartText(error.message)}</p></div>`;
    if(dom.dashboardModalSignals) dom.dashboardModalSignals.innerHTML='';
    if(dom.dashboardModalChart) dom.dashboardModalChart.innerHTML=`<div class="chart-shell"><p class="status-line">Carte en erreur récupérée</p><div class="detail-block"><p>${safeChartText(error.message)}</p><p>Ouvre le terminal pour plus de détails, puis lance un recalcul si les données existent déjà.</p></div></div>`;
    dom.dashboardModal.classList.remove('hidden');
  }
}
function closeDashboardModal(){dom.dashboardModal.classList.add('hidden');state.openTrendKey=null}
function safeRenderSection(name, callback){
  try{
    return callback();
  }catch(error){
    addTerminalLog('error','render',`Section ${name} en échec`,error?.message||String(error));
    recordBoot('render:error',`${name}: ${error?.message||String(error)}`,{state:'warn'});
    if(name==='dashboard'&&dom.dashboardCards){
      dom.dashboardCards.innerHTML=`<div class="detail-block"><h4>Rendu du dashboard bloqué</h4><p>${safeChartText(error?.message||'Erreur inconnue')}</p><p>Le shell reste actif. Lance un recalcul ou ouvre le terminal pour diagnostiquer la source.</p></div>`;
    }
    return null;
  }
}
function renderDashboardSection(){
  const payload=currentPayload();
  const analysis=currentAnalysis();
  const metrics=currentMetrics();
  const importStatus=currentImportStatus();
  const trend=analysis.trend||{};
  const windowed=buildTrendWindowSeries(trend,state.dashboardWindowDays);
  const readiness=buildDashboardReadiness(payload,{windowed});
  const runningSeries=Array.isArray(windowed.runningSeries)?windowed.runningSeries:[];
  const bikeSeries=Array.isArray(windowed.bikeSeries)?windowed.bikeSeries:[];
  const loadRatioSeries=Array.isArray(windowed.loadRatioSeries)?windowed.loadRatioSeries:[];
  const sleepSeries=Array.isArray(windowed.sleepSeries)?windowed.sleepSeries:[];
  const restingHrSeries=Array.isArray(windowed.restingHrSeries)?windowed.restingHrSeries:[];
  const hrvSeries=Array.isArray(windowed.hrvSeries)?windowed.hrvSeries:[];
  const cadenceSeries=Array.isArray(windowed.cadenceSeries)?windowed.cadenceSeries:[];
  const runningPaceSeries=Array.isArray(windowed.runningPaceSeries)?windowed.runningPaceSeries:[];
  const runningHrSeries=Array.isArray(windowed.runningHrSeries)?windowed.runningHrSeries:[];
  const zonesAll=metrics.heart_rate_zone_share||trend.heart_rate_zone_share||{distribution:[]};
  const zonesRunning=metrics.heart_rate_zone_share_running||trend.heart_rate_zone_share_running||{distribution:[]};
  const paceCurveDebug=windowed.paceCurveDebug||metrics.pace_hr_curve_debug||{};
  const cadenceTarget=metrics.cadence_target_spm||170;
  const cadenceRefLow=metrics.cadence_reference_low||cadenceTarget-5;
  const cadenceRefHigh=metrics.cadence_reference_high||cadenceTarget+5;
  const cadenceTrendValues=cadenceSeries.map((row)=>Number(row.cadence_spm)||0);
  const runningPaceChartSeries=runningPaceSeries;
  const runningHrChartSeries=runningHrSeries;
  const cadenceChartSeries=cadenceSeries;
  const chartTicks=chartWindowTickCount(state.dashboardWindowDays);
  const windowText=dashboardWindowDetail(state.dashboardWindowDays);['volume-trend-window','bike-volume-trend-window','load-ratio-trend-window','sleep-trend-window','resting-hr-trend-window','hrv-trend-window','pace-hr-trend-window','cadence-trend-window','pace-cadence-hr-trend-window'].forEach((id)=>{const node=document.getElementById(id);if(node)node.textContent=windowText});
  dom.dashboardImportState.textContent=metrics.weekly_volume_km===null||metrics.weekly_volume_km===undefined?'-':formatKilometers(metrics.weekly_volume_km);
  dom.dashboardImportDetail.textContent=metrics.weekly_running_days!==null&&metrics.weekly_running_days!==undefined?`${formatNumber(metrics.weekly_running_days,0)} sorties sur 7j Â· ${Array.isArray(runningSeries)?runningSeries.length:0} jours analysÃ©s`:'Volume running non disponible';
  if(dom.dashboardBikeState) dom.dashboardBikeState.textContent=metrics.weekly_bike_volume_km===null||metrics.weekly_bike_volume_km===undefined?'-':formatKilometers(metrics.weekly_bike_volume_km);
  if(dom.dashboardBikeDetail) dom.dashboardBikeDetail.textContent=metrics.weekly_bike_volume_km===null||metrics.weekly_bike_volume_km===undefined?'Volume vÃ©lo non disponible':'VÃ©lo isolÃ© du running pour garder les mÃ©triques lisibles.';
  if(dom.dashboardHrvState) dom.dashboardHrvState.textContent=metrics.hrv_7d===null||metrics.hrv_7d===undefined?'-':`${formatNumber(metrics.hrv_7d,1)} ms`;
  if(dom.dashboardHrvDetail) dom.dashboardHrvDetail.textContent=metrics.hrv_reference_low!==null&&metrics.hrv_reference_low!==undefined&&metrics.hrv_reference_high!==null&&metrics.hrv_reference_high!==undefined?`RÃ©f ${formatNumber(metrics.hrv_reference_low,1)}-${formatNumber(metrics.hrv_reference_high,1)} ms`:'HRV sans rÃ©fÃ©rence';
  dom.coverageCard.textContent=metrics.load_7d===null||metrics.load_7d===undefined?'-':formatNumber(metrics.load_7d,0);
  dom.coverageSubtitle.textContent=metrics.load_reference_low!==null&&metrics.load_reference_low!==undefined&&metrics.load_reference_high!==null&&metrics.load_reference_high!==undefined?`RÃ©f ${formatNumber(metrics.load_reference_low,0)}-${formatNumber(metrics.load_reference_high,0)} u`:'Charge sans rÃ©fÃ©rence';
  dom.analysisCard.textContent=readiness.label||'Analyse';dom.analysisSubtitle.textContent=(readiness.details||[]).join(' · ')||readiness.reason||'Aucun diagnostic disponible';
  dom.volumeTrendSummary.textContent=runningSeries.length?`${formatKilometers((runningSeries||[]).reduce((sum,row)=>sum+(row.distance_km||0),0))} sur ${runningSeries.length} jours`:'Pas encore de sÃ©rie';
  renderSparkline(dom.volumeTrend,runningSeries,{...buildEmptyChartOptions(readiness.chartStates.volume),id:'volume',stroke:'#8ae6c0',fill:'rgba(138, 230, 192, 0.35)',height:128,width:360,title:'Volume running',yLabel:'km',tickFormatter:formatAxisKilometers,xTickCount:chartTicks});
  if(dom.bikeVolumeTrendSummary) dom.bikeVolumeTrendSummary.textContent=bikeSeries.length?`${formatKilometers((bikeSeries||[]).reduce((sum,row)=>sum+(row.distance_km||0),0))} sur ${bikeSeries.length} jours`:'Pas encore de sÃ©rie vÃ©lo';
  if(dom.bikeVolumeTrend) renderSparkline(dom.bikeVolumeTrend,bikeSeries,{...buildEmptyChartOptions(readiness.chartStates.bike),id:'bike-volume',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.26)',height:128,width:360,title:'Volume vélo',yLabel:'km',tickFormatter:formatAxisKilometers,xTickCount:chartTicks});
  if(dom.loadRatioTrendSummary) dom.loadRatioTrendSummary.textContent=loadRatioSeries.length?`${formatNumber(loadRatioSeries.at(-1)?.load_ratio_7_28,2)} Â· ${loadRatioSeries.length} jours`:'Pas encore de ratio';
  if(dom.loadRatioTrend) renderSparkline(dom.loadRatioTrend,loadRatioSeries,{...buildEmptyChartOptions(readiness.chartStates.loadRatio),id:'load-ratio',stroke:'#ffbe55',fill:'rgba(255, 190, 85, 0.22)',height:128,width:360,title:'Charge relative',yLabel:'ratio',tickFormatter:(value)=>formatNumber(value,2),xTickCount:chartTicks});
  if(dom.sleepTrendSummary) dom.sleepTrendSummary.textContent=sleepSeries.length?`${formatNumber(sleepSeries.at(-1)?.sleep_hours,1)} h Â· ${sleepSeries.length} jours`:'Pas encore de sommeil';
  if(dom.sleepTrend) renderSparkline(dom.sleepTrend,sleepSeries,{...buildEmptyChartOptions(readiness.chartStates.sleep),id:'sleep',stroke:'#8ae6c0',fill:'rgba(138, 230, 192, 0.16)',height:128,width:360,title:'Sommeil',yLabel:'h',tickFormatter:(value)=>`${formatNumber(value,1)} h`,xTickCount:chartTicks,drawArea:false});
  if(dom.restingHrTrendSummary) dom.restingHrTrendSummary.textContent=restingHrSeries.length?`${formatNumber(restingHrSeries.at(-1)?.resting_hr,0)} bpm Â· ${restingHrSeries.length} jours`:'Pas encore de FC repos';
  if(dom.restingHrTrend) renderSparkline(dom.restingHrTrend,restingHrSeries,{...buildEmptyChartOptions(readiness.chartStates.restingHr),id:'resting-hr',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.16)',height:128,width:360,title:'FC repos',yLabel:'bpm',tickFormatter:(value)=>`${formatNumber(value,0)} bpm`,xTickCount:chartTicks,drawArea:false});
  if(dom.hrvTrendSummary) dom.hrvTrendSummary.textContent=hrvSeries.length?`${formatNumber(hrvSeries.at(-1)?.hrv_ms,1)} ms Â· ${hrvSeries.length} jours`:'Pas encore de HRV';
  if(dom.hrvTrend) renderSparkline(dom.hrvTrend,hrvSeries,{...buildEmptyChartOptions(readiness.chartStates.hrv),id:'hrv',stroke:'#a38bff',fill:'rgba(163, 139, 255, 0.16)',height:128,width:360,title:'HRV',yLabel:'ms',tickFormatter:(value)=>`${formatNumber(value,1)} ms`,referenceBands:[{low:metrics.hrv_reference_low,high:metrics.hrv_reference_high,color:'rgba(163, 139, 255, 0.12)'}],xTickCount:chartTicks,drawArea:false});
  const paceSummary=Array.isArray(trend.pace_hr_curve)&&trend.pace_hr_curve.length?`${formatPace(trend.pace_hr_curve[0].pace_min_per_km)} -> ${formatPace(trend.pace_hr_curve.at(-1).pace_min_per_km)} · ${trend.pace_hr_curve.length} points`:'Pas encore de courbe';
  dom.paceHrTrendSummary.textContent=paceSummary;
  renderMonotonePaceCurve(dom.paceHrTrend,windowed.paceCurve||[],{id:'pace-hr',width:360,height:240,maxHrEstimate:metrics.max_hr_estimate,diagnostics:windowed.paceCurveDebug||paceCurveDebug});
  dom.cadenceTrendSummary.textContent=cadenceTrendValues.length?`${formatNumber(cadenceTrendValues.at(-1),0)} spm Â· ${cadenceTrendValues.length} jours`:'Pas encore de cadence';
  renderSparkline(dom.cadenceTrend,cadenceSeries,{...buildEmptyChartOptions(readiness.chartStates.cadence),id:'cadence',stroke:'#8ab4ff',fill:'rgba(138, 180, 255, 0.26)',height:128,width:360,title:'Cadence',yLabel:'spm',tickFormatter:(value)=>`${formatNumber(value,0)} spm`,referenceLines:[{value:metrics.cadence_target_spm||170,label:`cible ${formatNumber(metrics.cadence_target_spm||170,0)} spm`,color:'#8ae6c0'}],xTickCount:chartTicks});
  if(dom.paceCadenceHrTrendSummary) dom.paceCadenceHrTrendSummary.textContent=runningPaceSeries.length&&runningHrSeries.length&&cadenceSeries.length?`${formatPace(runningPaceSeries.at(-1)?.pace_min_per_km)} Â· ${formatNumber(cadenceSeries.at(-1)?.cadence_spm||metrics.cadence_7d||0,0)} spm Â· ${formatHeartRate(runningHrSeries.at(-1)?.heart_rate || metrics.running_hr_7d)}`:'Triptyque en attente';
  if(dom.paceCadenceHrTrend) renderTriptychChart(dom.paceCadenceHrTrend,runningPaceChartSeries,cadenceChartSeries,runningHrChartSeries,{id:'pace-cadence-hr',labels:{pace:'Allure',cadence:'Cadence',hr:'FC'},xTickFormatter:(item)=>item.label||'',paceReferenceLines:[{value:metrics.running_pace_reference_low,label:`allure lente ${formatPace(metrics.running_pace_reference_low)}`,color:'#8ae6c0'},{value:metrics.running_pace_reference_high,label:`allure rapide ${formatPace(metrics.running_pace_reference_high)}`,color:'#ffbe55'}].filter((item)=>Number.isFinite(Number(item.value))),cadenceReferenceLines:[{value:metrics.cadence_reference_low,label:`bande basse ${formatNumber(metrics.cadence_reference_low,0)}`,color:'#8ab4ff'},{value:metrics.cadence_target_spm||170,label:`cible ${metrics.cadence_target_spm||170}`,color:'#8ae6c0'},{value:metrics.cadence_reference_high,label:`bande haute ${formatNumber(metrics.cadence_reference_high,0)}`,color:'#8ab4ff'}].filter((item)=>Number.isFinite(Number(item.value))),hrReferenceBands:[{low:metrics.resting_hr_reference_low,high:metrics.resting_hr_reference_high,color:'#8ab4ff',label:'FC repos'}].filter((band)=>Number.isFinite(Number(band.low))&&Number.isFinite(Number(band.high))),xTickCount:chartTicks});
  if(dom.zonesAllSummary) dom.zonesAllSummary.textContent=zonesAll?.total_seconds?`${formatNumber((zonesAll.total_seconds||0)/3600,1)} h`:'-';
  if(dom.zonesRunningSummary) dom.zonesRunningSummary.textContent=zonesRunning?.total_seconds?`${formatNumber((zonesRunning.total_seconds||0)/3600,1)} h`:'-';
  if(dom.zonesAllChart) renderDonutComparison(dom.zonesAllChart,zonesAll,zonesRunning,{id:'zones',overallLabel:'Toutes activitÃ©s',runningLabel:'Running'});
  if(dom.zonesRunningChart) renderDonutComparison(dom.zonesRunningChart,zonesAll,zonesRunning,{id:'zones-running',overallLabel:'Toutes activitÃ©s',runningLabel:'Running'});
  dom.dashboardCards.innerHTML='';dashboardCardSpecs(payload).forEach((card)=>{const button=document.createElement('button');button.type='button';button.className=`metric-card${card.tone==='primary'?' is-primary':''}`;button.innerHTML=`<span class='card-label'>${safeChartText(card.title)}</span><strong>${safeChartText(card.value)}</strong><p>${safeChartText(card.subtitle||'')}</p>`;button.addEventListener('click',()=>{state.openTrendKey=card.key;addTerminalLog('info','dashboard',`Carte ouverte: ${card.title}`);renderDashboardModal(card)});dom.dashboardCards.appendChild(button)})
  document.querySelectorAll('.trend-card[data-trend-key]').forEach((card)=>{if(card.dataset.bound==='true')return;card.dataset.bound='true';card.classList.add('is-clickable');card.setAttribute('role','button');card.setAttribute('tabindex','0');const open=()=>openTrendModal(card.dataset.trendKey);card.addEventListener('click',open);card.addEventListener('keydown',(event)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open()}})})
}
function renderCoachSection(){
  const payload=currentPayload();
  const importStatus=currentImportStatus();
  const analysis=currentAnalysis();
  const readiness=analysis.readiness||buildDashboardReadiness(payload)||{};
  const provider=payload.provider||{};
  const providerText=provider.status==='ready'?`${provider.provider==='ollama'?'Ollama':provider.provider} prêt`:provider.status==='unchecked'?`${provider.provider||state.provider} en vérification`:`${provider.provider||state.provider} indisponible`;
  const items=[importStatus.available?'Données locales prêtes':'Pas de données locales',`Analyse: ${readiness.label|| (analysis.available?'prête':'partielle')}`,`Provider: ${providerText}`];
  if(state.goalText) items.push(`Objectif actif: ${state.goalText.slice(0,80)}${state.goalText.length>80?'…':''}`);
  if(dom.coachStatusStrip) dom.coachStatusStrip.innerHTML='';
  items.forEach((text)=>{
    const pill=document.createElement('span');
    pill.className=`pill pill-small${/indisponible|partielle|pas de données|attente/i.test(text)?' warn':''}`;
    pill.textContent=text;
    if(dom.coachStatusStrip) dom.coachStatusStrip.appendChild(pill);
  });
  if(dom.coachWorkspaceInput) dom.coachWorkspaceInput.value=state.workspace;
  if(dom.providerSelect) dom.providerSelect.value=state.provider;
  if(dom.transcript) dom.transcript.dataset.empty='Le coach t’attend ici. Décris un objectif et laisse-le poser les bonnes questions.';
  if(dom.planList) dom.planList.dataset.empty='Aucun plan généré pour le moment.';
}
function renderTerminalSection(){
  if(!dom.terminalLog){
    if(dom.terminalSummary) dom.terminalSummary.textContent=`${state.terminalLogs.length} entrée(s) total.`;
    return;
  }
  const entries=state.terminalLogs.filter((entry)=>state.terminalLevels[entry.level]!==false);
  dom.terminalLog.innerHTML='';
  if(!entries.length){
    dom.terminalLog.dataset.empty='Aucun log visible pour le niveau sélectionné.';
  }else{
    delete dom.terminalLog.dataset.empty;
  }
  entries.slice(-250).forEach((entry)=>{
    const node=document.createElement('article');
    node.className=`terminal-entry ${entry.level}`;
    node.innerHTML=`<div class='terminal-entry-header'><span>${formatDateTime(entry.timestamp)} · ${entry.level.toUpperCase()} · ${entry.source}</span></div><strong>${entry.message}</strong>${entry.details?`<div class='entry-message'>${entry.details}</div>`:''}`;
    dom.terminalLog.appendChild(node);
  });
  dom.terminalSummary.textContent=`${entries.length} entrée(s) visible(s) sur ${state.terminalLogs.length} total.`;
  dom.levelButtons.forEach((button)=>button.classList.toggle('active',state.terminalLevels[button.dataset.level]!==false));
}
function renderSettingsSection(){syncInputsFromState();renderBootTrace();renderAuthDebug()}
function buildDiagnosticsSummary(){const payload=currentPayload();const importStatus=currentImportStatus();const provider=payload.provider||{};const readiness=(payload.analysis||{}).readiness||buildDashboardReadiness(payload)||{};return[`build=${APP_VERSION}`,`bootId=${state.bootId}`,`bootTraceEvents=${state.bootTrace.length}`,`bootErrors=${Array.isArray(state.bootErrors)?state.bootErrors.length:0}`,`url=${window.location.href}`,`hash=${window.location.hash||'#import'}`,`activeSection=${state.activeSection}`,`workspace=${state.workspace}`,`provider=${state.provider}`,`providerStatus=${provider.status||'unknown'}`,`dataAvailable=${importStatus.available?'yes':'no'}`,`analysisReadiness=${readiness.label||'unknown'}`,`analysisReason=${readiness.reason||'-'}`,`latestDay=${importStatus.latest_activity_day||payload.latest_day||'-'}`,`swState=${runtimeInfo.serviceWorkerState}`,`swController=${runtimeInfo.serviceWorkerController?'yes':'no'}`,`swScope=${runtimeInfo.serviceWorkerScope}`,`online=${navigator.onLine?'yes':'no'}`].join('\n')}
function renderDiagnostics(){
  const payload = currentPayload();
  const importStatus = currentImportStatus();
  const provider = payload.provider || {};
  const latestDay = importStatus.latest_activity_day || payload.latest_day || null;
  const syncAttempt = state.lastGarminSync || {};
  if (dom.diagnosticBuild) dom.diagnosticBuild.textContent = `Build ${APP_VERSION}`;
  if (dom.diagnosticBuildDetail) dom.diagnosticBuildDetail.textContent = `${window.location.hostname || 'localhost'} Â· ${navigator.userAgent.includes('Firefox') ? 'Firefox' : 'Browser'} Â· ${navigator.onLine ? 'online' : 'offline'}`;
  if (dom.diagnosticUrl) dom.diagnosticUrl.textContent = window.location.href;
  if (dom.diagnosticUrlDetail) dom.diagnosticUrlDetail.textContent = `hash ${window.location.hash || '#import'} Â· active ${state.activeSection}`;
  if (dom.diagnosticSw) dom.diagnosticSw.textContent = `${runtimeInfo.serviceWorkerState}${runtimeInfo.serviceWorkerController ? ' Â· controller' : ' Â· no controller'}`;
  if (dom.diagnosticSwDetail) dom.diagnosticSwDetail.textContent = `scope ${runtimeInfo.serviceWorkerScope || '-'} Â· checked ${runtimeInfo.lastCheckedAt ? formatDateTime(runtimeInfo.lastCheckedAt) : '-'}`;
  if (dom.diagnosticWorkspace) dom.diagnosticWorkspace.textContent = state.workspace;
  if (dom.diagnosticWorkspaceDetail) dom.diagnosticWorkspaceDetail.textContent = payload.workspace?.exists ? 'Workspace local disponible' : 'Workspace local absent';
  if (dom.diagnosticImport) dom.diagnosticImport.textContent = importStatus.available ? 'DonnÃ©es locales prÃªtes' : 'Aucune donnÃ©e locale';
  if (dom.diagnosticImportDetail) dom.diagnosticImportDetail.textContent = latestDay ? `DerniÃ¨re activitÃ© ${formatDateLabel(latestDay)} Â· donnÃ©es exploitÃ©es ${payload.coverage_ratio === null || payload.coverage_ratio === undefined ? '-' : `${formatNumber(payload.coverage_ratio * 100,0)}%`}` : 'Aucune activitÃ© indexÃ©e';
  if (dom.diagnosticProvider) dom.diagnosticProvider.textContent = provider.status === 'ready' ? `${provider.provider === 'ollama' ? 'Ollama' : provider.provider} prÃªt` : provider.status === 'unchecked' ? `${provider.provider || state.provider} en vÃ©rification` : `${provider.provider || state.provider} indisponible`;
  if (dom.diagnosticProviderDetail) dom.diagnosticProviderDetail.textContent = provider.model ? `model ${provider.model}` : 'provider sans modÃ¨le dÃ©tectÃ©';
  if (dom.diagnosticSummary) dom.diagnosticSummary.textContent = buildDiagnosticsSummary();
  if (dom.bootTraceState) dom.bootTraceState.textContent = state.bootTrace.length ? `Trace active (${state.bootTrace.length})` : 'Aucune trace';
  if (dom.bootTraceDetail) dom.bootTraceDetail.textContent = state.bootTrace.at(-1) ? formatBootTraceEvent(state.bootTrace.at(-1)) : 'Aucun Ã©vÃ©nement enregistrÃ©.';
  if (dom.bootTraceLog) dom.bootTraceLog.textContent = state.bootTrace.length ? state.bootTrace.map((entry) => formatBootTraceEvent(entry)).join('\n') : 'Aucun Ã©vÃ©nement de boot pour le moment.';
  if (dom.importSyncState && syncAttempt.status) {
    dom.importSyncState.textContent = syncAttempt.status === 'success' ? 'Sync Garmin Connect prÃªte' : syncAttempt.status === 'running' ? 'Sync Garmin Connect en cours' : syncAttempt.status === 'error' ? 'Sync Garmin Connect Ã©chouÃ©e' : 'Sync Garmin Connect';
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
function renderAllSections(){safeBootStep('renderSectionVisibility',renderSectionVisibility);safeBootStep('renderSidebarStatus',renderSidebarStatus);safeBootStep('renderSectionHeader',renderSectionHeader);safeBootStep('renderImportSection',renderImportSection);safeRenderSection('dashboard',renderDashboardSection);safeRenderSection('coach',renderCoachSection);safeRenderSection('terminal',renderTerminalSection);safeRenderSection('settings',renderSettingsSection)}
function showRetryableError(error,retryAction){setBusy(false);setCoachError(buildProviderErrorMessage(error),retryAction,buildProviderErrorTitle(error));addMessage('assistant',buildProviderErrorMessage(error))}
async function refreshDashboard({quiet=false,reason='manual',days=state.dashboardWindowDays}={}){persistSettings();const runner=async()=>{recordBoot('dashboard:refresh-start',`reason=${reason}`);const payload=await requestJson(`/api/status?data_dir=${encodeURIComponent(state.workspace)}&provider=${encodeURIComponent(state.provider)}&base_url=${encodeURIComponent(state.baseUrl)}&probe=1&days=${encodeURIComponent(normalizeDashboardWindowDays(days))}`,{},'status');state.dashboardPayload=payload;renderAllSections();recordBoot('dashboard:refresh-ok',`reason=${reason}`);return payload};if(quiet)return runner();return withBusy('Lecture du workspace local...',runner)}
async function recalculateData(){persistSettings();if(dom.reprocessButton) dom.reprocessButton.disabled=true;addTerminalLog('info','reprocess','Recalcul local demandÃ©',state.workspace);try{const payload=await withBusy('Recalcul des donnÃ©es locales...',async()=>requestJson('/api/recalculate',{method:'POST',body:JSON.stringify({data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null})},'recalculate'));state.dashboardPayload=payload.dashboard||state.dashboardPayload;addMessage('assistant',payload.message||'Retraitement local terminÃ©.');addTerminalLog('info','reprocess',payload.message||'Retraitement local terminÃ©.',payload.analytics?.report_path||'analytics recalculÃ©es');await refreshDashboard({quiet:true,reason:'recalculate'});renderAllSections()}catch(error){addTerminalLog('error','reprocess','Recalcul local Ã©chouÃ©',error.message);showRetryableError(error,recalculateData)}finally{if(dom.reprocessButton) dom.reprocessButton.disabled=false}}
async function prepareCoach(){persistSettings();const goalText=normalizeText(dom.goalInput.value.trim());if(!goalText){addMessage('assistant','J\'ai besoin d\'un objectif running pour dÃ©marrer.');addTerminalLog('warn','coach','PrÃ©paration impossible','Objectif manquant.');return}addMessage('user',goalText);addTerminalLog('info','coach','PrÃ©paration du coach',goalText);try{const payload=await withBusy('Le coach analyse les donnÃ©es locales...',async()=>requestJson('/api/coach/prepare',{method:'POST',body:JSON.stringify({goal_text:goalText,data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null})},'coach-prepare'));if(payload.questions?.length){addMessage('assistant','Je veux prÃ©ciser quelques points avant de proposer un plan.');renderQuestions(payload.questions);addTerminalLog('info','coach','Questions gÃ©nÃ©rÃ©es',`${payload.questions.length} question(s)`)}else{renderQuestions([]);addTerminalLog('info','coach','Aucune clarification requise')}state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();if(payload.analysis?.analysis_summary)addMessage('assistant',payload.analysis.analysis_summary)}catch(error){showRetryableError(error,prepareCoach)}}
function renderSummary(payload){const analysis=payload.analysis||{};const lines=[];if(payload.coach_summary)lines.push(payload.coach_summary);if(analysis.training_phase)lines.push(`Phase: ${analysis.training_phase}`);if(analysis.benchmark?.event){const pace=analysis.benchmark.pace_min_per_km?` · ${formatPace(analysis.benchmark.pace_min_per_km)}`:'';lines.push(`Benchmark retenu: ${analysis.benchmark.event}${pace}`)}dom.coachSummary.textContent=lines.join('\n\n')||'Aucun plan généré pour le moment.';dom.planList.innerHTML='';(payload.weekly_plan||[]).forEach((session)=>{const item=document.createElement('article');const sessionKind=classifyPlanSession(session);item.className=`plan-item${sessionKind==='rest'?' is-rest':sessionKind==='easy'?' is-easy':sessionKind==='quality'?' is-quality':''}`;item.innerHTML=`<strong>${safeChartText(session.day)} - ${safeChartText(session.session_title)}</strong><span>${safeChartText(`${session.duration_minutes} min | ${session.intensity}`)}</span><p>${safeChartText(session.objective||'')}</p><p>${safeChartText(session.notes||'')}</p>`;dom.planList.appendChild(item)})}
async function generatePlan(){persistSettings();const goalText=normalizeText(dom.goalInput.value.trim());if(!goalText){addMessage('assistant','Entre d\'abord un objectif running.');addTerminalLog('warn','coach','Plan impossible','Objectif manquant.');return}addTerminalLog('info','coach','GÃ©nÃ©ration du plan',goalText);try{const payload=await withBusy('Le modÃ¨le prÃ©pare le plan...',async()=>requestJson('/api/coach/plan',{method:'POST',body:JSON.stringify({goal_text:goalText,data_dir:state.workspace,provider:state.provider,base_url:state.baseUrl||null,api_key:state.apiKey||null,answers:state.answers})},'coach-plan'));if(payload.needs_clarification){renderQuestions(payload.questions);addMessage('assistant','Il me manque encore quelques rÃ©ponses pour construire le plan.');addTerminalLog('warn','coach','Clarifications manquantes',`${payload.questions.length} question(s)`);state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();return}addMessage('assistant',payload.coach_summary||'Plan gÃ©nÃ©rÃ©.');if(payload.signals_used?.length)addMessage('assistant',`Signaux utilisÃ©s: ${payload.signals_used.join(', ')}`);renderSummary(payload);state.dashboardPayload=payload.dashboard||state.dashboardPayload;renderAllSections();addTerminalLog('info','coach','Plan gÃ©nÃ©rÃ©',payload.plan_path||'plan local enregistrÃ©')}catch(error){showRetryableError(error,generatePlan)}}
async function importGarmin(){persistSettings();const sourcePath=normalizeText((dom.sourcePathInput.value||dom.sourcePathInputSettings.value).trim());if(!sourcePath){addMessage('assistant','Indique le chemin local de l\'export Garmin Ã  importer.');addTerminalLog('warn','import','Import impossible','Chemin source manquant.');return}addTerminalLog('info','import','Import Garmin demandÃ©',sourcePath);try{const payload=await withBusy('Import Garmin en cours...',async()=>requestJson('/api/import',{method:'POST',body:JSON.stringify({source_path:sourcePath,data_dir:state.workspace,run_label:'pwa-import'})},'import'));state.dashboardPayload=payload.dashboard||state.dashboardPayload;addMessage('assistant',`Import terminÃ©: ${payload.artifacts_imported} artefacts, ${payload.total_records} enregistrements.`);addTerminalLog('info','import','Import terminÃ©',`${payload.artifacts_imported||0} artefacts, ${payload.total_records||0} enregistrements`);await refreshDashboard()}catch(error){addTerminalLog('error','import','Import Ã©chouÃ©',error.message);showRetryableError(error,importGarmin)}}
async function syncGarminConnect(){persistSettings();if(dom.syncButton)dom.syncButton.disabled=true;state.lastGarminSync={status:'running',message:'Synchronisation Garmin Connect en cours...',at:new Date().toISOString()};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));renderImportSection();addTerminalLog('info','sync','Synchronisation Garmin Connect demandÃ©e',`workspace ${state.workspace}`);try{const payload=await requestJson('/api/sync/garmin-connect',{method:'POST',body:JSON.stringify({data_dir:state.workspace,run_label:'pwa-garmin-sync'})},'garmin-sync');state.dashboardPayload=payload.dashboard||state.dashboardPayload;state.lastGarminSync={status:'success',message:'Synchronisation Garmin Connect rÃ©ussie',at:new Date().toISOString(),result:payload};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));addTerminalLog('info','sync','Synchronisation Garmin Connect rÃ©ussie',payload.run_id||payload.source_kind||'sync ok');await refreshDashboard({quiet:true,reason:'garmin-sync'});renderImportSection()}catch(error){state.lastGarminSync={status:'error',message:`Synchronisation Garmin Connect Ã©chouÃ©e: ${error.message}`,at:new Date().toISOString(),error:error.message};localStorage.setItem(STORAGE_KEYS.lastGarminSync,JSON.stringify(state.lastGarminSync));renderImportSection();addTerminalLog('warn','sync','Synchronisation Garmin Connect Ã©chouÃ©e',error.message);addMessage('assistant',state.lastGarminSync.message)}finally{if(dom.syncButton)dom.syncButton.disabled=false}}
function saveGoal(){persistSettings();addTerminalLog('info','coach','Objectif enregistrÃ©',state.goalText||'vide');addMessage('assistant','Objectif enregistrÃ© localement.');renderSidebarStatus()}
function useLastWorkspace(){const lastWorkspace=localStorage.getItem(STORAGE_KEYS.workspace)||state.workspace||'data';state.workspace=lastWorkspace;syncInputsFromState();persistSettings();addMessage('assistant',`Dernier workspace local rÃ©utilisÃ©: ${state.workspace}`);addTerminalLog('info','workspace','Workspace local rÃ©utilisÃ©',state.workspace);refreshDashboard({reason:'reuse-last-workspace'}).catch(()=>{})}
function clearTerminal(){state.terminalLogs=[];saveTerminalLogs();renderTerminalSection();addTerminalLog('info','terminal','Journal nettoy?')}
function updateTerminalLevel(level){state.terminalLevels[level]=!state.terminalLevels[level];if(Object.values(state.terminalLevels).every((value)=>value===false)){state.terminalLevels[level]=true}localStorage.setItem(STORAGE_KEYS.terminalLevels,JSON.stringify(state.terminalLevels));renderTerminalSection()}
function wireEvents(){dom.navButtons.forEach((button)=>{button.addEventListener('click',(event)=>{const section=button.dataset.section;if(!section)return;event?.preventDefault?.();setActiveSection(section)})});dom.navButtons.forEach((button)=>{button.setAttribute('aria-pressed',String(button.dataset.section===state.activeSection))});if(dom.diagnosticButton)dom.diagnosticButton.addEventListener('click',openDiagnostics);if(dom.diagnosticModalClose)dom.diagnosticModalClose.addEventListener('click',closeDiagnostics);if(dom.diagnosticRefreshButton)dom.diagnosticRefreshButton.addEventListener('click',refreshRuntimeDiagnostics);if(dom.diagnosticCopyButton)dom.diagnosticCopyButton.addEventListener('click',async()=>{const text=buildDiagnosticsSummary();try{await navigator.clipboard.writeText(text);addTerminalLog('info','diagnostic','RÃ©sumÃ© copiÃ©',text)}catch{addTerminalLog('warn','diagnostic','Copie impossible','Le navigateur a bloquÃ© le presse-papiers.')}});if(dom.bootTraceRefreshButton)dom.bootTraceRefreshButton.addEventListener('click',()=>{refreshBootTrace().catch(()=>{})});dom.saveSettingsButton.addEventListener('click',async()=>{persistSettings();addMessage('assistant','RÃ©glages sauvegardÃ©s localement.');addTerminalLog('info','settings','RÃ©glages sauvegardÃ©s');await refreshDashboard()});dom.refreshSettingsButton.addEventListener('click',()=>refreshDashboard({reason:'settings-refresh'}));dom.saveGoalButton.addEventListener('click',saveGoal);dom.prepareButton.addEventListener('click',prepareCoach);dom.planButton.addEventListener('click',generatePlan);dom.importButton.addEventListener('click',importGarmin);if(dom.syncButton)dom.syncButton.addEventListener('click',syncGarminConnect);if(dom.reprocessButton)dom.reprocessButton.addEventListener('click',recalculateData);dom.refreshButton.addEventListener('click',()=>refreshDashboard({reason:'manual-refresh'}));dom.useLastWorkspaceButton.addEventListener('click',useLastWorkspace);dom.retryButton.addEventListener('click',()=>{if(typeof state.retryAction==='function'){addTerminalLog('info','retry','Nouvelle tentative demandÃ©e');state.retryAction()}});dom.terminalClearButton.addEventListener('click',clearTerminal);dom.levelButtons.forEach((button)=>button.addEventListener('click',()=>updateTerminalLevel(button.dataset.level)));dom.themeSelect.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`ThÃ¨me ${state.theme}`)});dom.startSectionSelect.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`Section de dÃ©part ${state.startSection}`)});dom.showTerminalToggle.addEventListener('change',()=>{persistSettings();addTerminalLog('info','settings',`Terminal menu ${state.showTerminalMenu?'visible':'masquÃ©'}`);updateNavVisibility();renderAllSections()});dom.providerSelect.addEventListener('change',()=>{state.provider=dom.providerSelect.value;dom.settingsProviderSelect.value=state.provider;persistSettings();addTerminalLog('info','provider',`Provider actif ${state.provider}`);refreshDashboard({reason:'provider-change'}).catch(()=>{})});dom.settingsProviderSelect.addEventListener('change',()=>{state.provider=dom.settingsProviderSelect.value;dom.providerSelect.value=state.provider;persistSettings();addTerminalLog('info','provider',`Provider actif ${state.provider}`);refreshDashboard({reason:'provider-change'}).catch(()=>{})});dom.dashboardModal.addEventListener('click',(event)=>{if(event.target===dom.dashboardModal)closeDashboardModal()});dom.dashboardModalClose.addEventListener('click',closeDashboardModal);document.querySelectorAll('.dashboard-window-button').forEach((button)=>{if(button.dataset.bound==='true')return;button.dataset.bound='true';button.addEventListener('click',()=>setDashboardWindowDays(button.dataset.days))});dom.diagnosticModal.addEventListener('click',(event)=>{if(event.target===dom.diagnosticModal)closeDiagnostics()});window.addEventListener('keydown',(event)=>{if(event.key==='Escape'){closeDashboardModal();closeDiagnostics()}});[dom.workspaceInputSettings,dom.sourcePathInput,dom.sourcePathInputSettings,dom.baseUrlInput,dom.apiKeyInput,dom.goalInput].forEach((input)=>{input.addEventListener('input',()=>{persistSettings();renderSidebarStatus();if(input===dom.goalInput)dom.coachWorkspaceInput.value=state.workspace})});window.addEventListener('hashchange',()=>{const next=(window.location.hash||'#import').slice(1);if(SECTIONS.includes(next)&&next!==state.activeSection){setActiveSection(next,{updateHash:false})}})}
async function bootstrap(){window.__coachAppReady=false;state.bootId=`${APP_VERSION}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`;localStorage.setItem(STORAGE_KEYS.bootId,state.bootId);setAppChip('App: initialisation...');applyTheme();safeBootStep('syncInputsFromState',syncInputsFromState);recordBoot('boot:start','bootstrap launched');safeBootStep('wireEvents',wireEvents);recordBoot('boot:events','listeners bound');safeBootStep('updateNavVisibility',updateNavVisibility);safeBootStep('renderSectionHeader',renderSectionHeader);safeBootStep('renderSidebarStatus',renderSidebarStatus);safeBootStep('renderDiagnostics',renderDiagnostics);safeBootStep('renderBootTrace',renderBootTrace);safeBootStep('welcomeMessage',()=>addMessage('assistant','Commence par décrire ton objectif. Je peux ensuite poser les questions manquantes puis générer un plan.'));safeBootStep('bootLog',()=>addTerminalLog('info','app','Application démarrée',`Workspace ${state.workspace}`));const initialSection=window.location.hash&&SECTIONS.includes(window.location.hash.slice(1))?window.location.hash.slice(1):state.startSection||'import';safeBootStep('setActiveSection',()=>setActiveSection(initialSection,{persist:false,updateHash:false}));safeBootStep('renderAllSections',renderAllSections);setAppChip('App: prête');window.__coachAppReady=true;window.__coachModuleReady=true;recordBoot('boot:ready',`section=${state.activeSection}`);void refreshRuntimeDiagnostics().catch((error)=>{recordBoot('diagnostic:error',error.message,{state:'warn'});});void refreshBootTrace().catch(()=>{});const bootPendingTimer=setTimeout(()=>{if(!state.dashboardPayload){recordBoot('dashboard:pending','status still loading after 10s',{state:'warn'});addTerminalLog('warn','boot','Dashboard encore en cours','Le chargement du workspace dépasse 10s.')}},10000);void refreshDashboard({quiet:true,reason:'boot'}).then(()=>{recordBoot('dashboard:ready','initial payload loaded')}).catch((error)=>{recordBoot('dashboard:error',error.message,{state:'warn'});addTerminalLog('error','status','Dashboard indisponible',error.message);if(dom.providerChip){dom.providerChip.textContent='Provider indisponible';dom.providerChip.classList.add('error')}if(dom.dataChip){dom.dataChip.textContent='Données: indisponible'}if(dom.workspaceChip){dom.workspaceChip.textContent='Workspace: indisponible'}}).finally(()=>clearTimeout(bootPendingTimer))}
window.addEventListener('beforeinstallprompt',(event)=>{event.preventDefault();state.installPrompt=event;if(dom.installButton) dom.installButton.classList.remove('hidden')});
if(dom.installButton) dom.installButton.addEventListener('click',async()=>{if(!state.installPrompt)return;state.installPrompt.prompt();await state.installPrompt.userChoice;state.installPrompt=null;dom.installButton.classList.add('hidden');addTerminalLog('info','pwa','Installation PWA demandée')});
function bootApp(){bootstrap().catch((error)=>{const detail=error?.stack||error?.message||String(error);addMessage('assistant',error?.message||String(error));addTerminalLog('error','app','Erreur au démarrage',detail);recordBoot('boot:failure',error?.message||String(error),{state:'error',stack:detail});setBusy(false);setAppChip('App: erreur démarrage','error');if(dom.providerChip){dom.providerChip.textContent='Erreur au démarrage';dom.providerChip.classList.add('error')}if(dom.coachErrorBanner){dom.coachErrorTitle.textContent='Erreur de démarrage';dom.coachErrorMessage.textContent=error?.message||String(error);dom.coachErrorBanner.classList.remove('hidden')}})}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',bootApp,{once:true})}else{queueMicrotask(bootApp)}
if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js?v='+APP_VERSION).catch(()=>{/* best effort */})})}































