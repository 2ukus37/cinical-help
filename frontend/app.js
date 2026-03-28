const API = 'http://localhost:8000';
let currentDisease = 'heart_disease';
let uploadDisease = 'heart_disease';
let extractedData = {};
let selectedFile = null;

// ── Clock ──────────────────────────────────────────────────────────────────
function tick(){
  const n = new Date();
  const el = document.getElementById('hdr-time');
  if(el) el.textContent = n.toUTCString().replace('GMT','UTC');
}
tick(); setInterval(tick, 1000);

// ── Navigation ─────────────────────────────────────────────────────────────
function nav(page){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nl').forEach(n=>n.classList.remove('active'));
  const pg = document.getElementById('page-'+page);
  const nl = document.getElementById('n-'+page);
  if(pg) pg.classList.add('active');
  if(nl) nl.classList.add('active');
  if(page==='home') loadHomeStats();
  if(page==='history') loadHistory('heart_disease');
}

// ── Health check ───────────────────────────────────────────────────────────
async function checkHealth(){
  try{
    const r = await fetch(API+'/health');
    if(!r.ok) throw new Error();
    document.getElementById('hdr-dot').className='w-2 h-2 rounded-full bg-[#8aebff] pulse';
    document.getElementById('hdr-status').className='text-[9px] text-[#8aebff] font-bold uppercase tracking-wider';
    document.getElementById('hdr-status').textContent='System Online';
    return true;
  }catch{
    document.getElementById('hdr-dot').className='w-2 h-2 rounded-full bg-[#ffb4ab] pulse';
    document.getElementById('hdr-status').className='text-[9px] text-[#ffb4ab] font-bold uppercase tracking-wider';
    document.getElementById('hdr-status').textContent='API Offline';
    return false;
  }
}

// ── Home stats ─────────────────────────────────────────────────────────────
async function loadHomeStats(){
  await checkHealth();
  try{
    const [mh, md] = await Promise.all([
      fetch(API+'/metrics?disease=heart_disease').then(r=>r.json()),
      fetch(API+'/metrics?disease=diabetes').then(r=>r.json())
    ]);
    const total = (mh.total_predictions||0) + (md.total_predictions||0);
    const el = document.getElementById('home-total');
    if(el) el.textContent = total;
  }catch{}
}

// ── Disease toggle ─────────────────────────────────────────────────────────
function setDisease(d){
  currentDisease = d;
  document.getElementById('heart-fields').classList.toggle('hidden', d!=='heart_disease');
  document.getElementById('diabetes-fields').classList.toggle('hidden', d!=='diabetes');
  document.getElementById('btn-heart').className = d==='heart_disease'
    ? 'px-4 py-2 text-[10px] font-bold uppercase tracking-wider vg text-[#00363e]'
    : 'px-4 py-2 text-[10px] font-bold uppercase tracking-wider border border-[#3c494c]/40 text-[#bbc9cd] hover:border-[#8aebff]/30 hover:text-[#dbe2fd] transition-colors';
  document.getElementById('btn-diab').className = d==='diabetes'
    ? 'px-4 py-2 text-[10px] font-bold uppercase tracking-wider vg text-[#00363e]'
    : 'px-4 py-2 text-[10px] font-bold uppercase tracking-wider border border-[#3c494c]/40 text-[#bbc9cd] hover:border-[#8aebff]/30 hover:text-[#dbe2fd] transition-colors';
}

function setUploadDisease(d){
  uploadDisease = d;
  document.getElementById('up-btn-heart').className = d==='heart_disease'
    ? 'flex-1 py-2 text-[10px] font-bold uppercase vg text-[#00363e]'
    : 'flex-1 py-2 text-[10px] font-bold uppercase border border-[#3c494c]/40 text-[#bbc9cd] hover:border-[#8aebff]/30 transition-colors';
  document.getElementById('up-btn-diab').className = d==='diabetes'
    ? 'flex-1 py-2 text-[10px] font-bold uppercase vg text-[#00363e]'
    : 'flex-1 py-2 text-[10px] font-bold uppercase border border-[#3c494c]/40 text-[#bbc9cd] hover:border-[#8aebff]/30 transition-colors';
}

// ── Error display ──────────────────────────────────────────────────────────
function showErr(id, msg){
  const e = document.getElementById(id);
  if(!e) return;
  e.innerHTML = msg.replace(/\n/g,'<br>');
  e.classList.remove('hidden');
}
function hideErr(id){ const e=document.getElementById(id); if(e){e.classList.add('hidden');e.innerHTML='';} }

function parseApiError(detail){
  if(Array.isArray(detail)){
    return 'Please check these values:\n• ' + detail.map(e=>{
      const field = (e.loc||[]).slice(-1)[0]||'field';
      const label = field.replace(/_/g,' ');
      if(e.type==='greater_than_equal') return `${label}: must be ≥ ${e.ctx?.ge} (you entered: ${e.input})`;
      if(e.type==='less_than_equal')    return `${label}: must be ≤ ${e.ctx?.le} (you entered: ${e.input})`;
      if(e.type==='missing')            return `${label}: this field is required`;
      return e.msg || `${label}: invalid value`;
    }).join('\n• ');
  }
  return typeof detail==='string' ? detail : 'Something went wrong. Please check your values.';
}

// ── Prediction ─────────────────────────────────────────────────────────────
async function submitPrediction(){
  hideErr('form-error');
  const age = parseInt(document.getElementById('f-age').value);
  const sex = parseInt(document.getElementById('f-sex').value);
  if(!age||isNaN(age)){ showErr('form-error','Your age is required'); return; }
  if(age<1||age>120){ showErr('form-error','Age must be between 1 and 120'); return; }

  let body = { age, sex, disease_target: currentDisease };

  if(currentDisease==='heart_disease'){
    const rbp=document.getElementById('f-rbp').value;
    const chol=document.getElementById('f-chol').value;
    const mhr=document.getElementById('f-mhr').value;
    if(!rbp||!chol||!mhr){ showErr('form-error','Blood pressure, cholesterol, and max heart rate are required'); return; }
    if(parseFloat(rbp)<50||parseFloat(rbp)>250){ showErr('form-error','Blood pressure must be between 50–250 mmHg'); return; }
    if(parseFloat(chol)<100||parseFloat(chol)>600){ showErr('form-error','Cholesterol must be between 100–600 mg/dL'); return; }
    if(parseFloat(mhr)<60||parseFloat(mhr)>220){ showErr('form-error','Max heart rate must be between 60–220 bpm'); return; }
    const cp=document.getElementById('f-cp').value;
    body = {...body,
      chest_pain_type: cp!==''?parseInt(cp):null,
      resting_bp: parseFloat(rbp), cholesterol: parseFloat(chol), max_heart_rate: parseFloat(mhr),
      fasting_blood_sugar: parseInt(document.getElementById('f-fbs').value),
      resting_ecg: document.getElementById('f-recg').value!==''?parseInt(document.getElementById('f-recg').value):null,
      exercise_angina: parseInt(document.getElementById('f-exang').value),
      st_depression: document.getElementById('f-std').value!==''?parseFloat(document.getElementById('f-std').value):null,
      st_slope: document.getElementById('f-slope').value!==''?parseInt(document.getElementById('f-slope').value):null,
      num_vessels: document.getElementById('f-ca').value!==''?parseInt(document.getElementById('f-ca').value):null,
      thal: document.getElementById('f-thal').value!==''?parseInt(document.getElementById('f-thal').value):null,
    };
  } else {
    const gluc=document.getElementById('f-gluc').value;
    const bmi=document.getElementById('f-bmi').value;
    if(!gluc||!bmi){ showErr('form-error','Blood sugar and BMI are required'); return; }
    if(parseFloat(gluc)<0||parseFloat(gluc)>500){ showErr('form-error','Blood sugar must be between 0–500 mg/dL'); return; }
    if(parseFloat(bmi)<10||parseFloat(bmi)>70){ showErr('form-error','BMI must be between 10–70 kg/m²'); return; }
    body = {...body,
      pregnancies: document.getElementById('f-preg').value!==''?parseInt(document.getElementById('f-preg').value):null,
      glucose: parseFloat(gluc), bmi: parseFloat(bmi),
      blood_pressure: document.getElementById('f-bp').value!==''?parseFloat(document.getElementById('f-bp').value):null,
      skin_thickness: document.getElementById('f-skin').value!==''?parseFloat(document.getElementById('f-skin').value):null,
      insulin: document.getElementById('f-ins').value!==''?parseFloat(document.getElementById('f-ins').value):null,
      diabetes_pedigree: document.getElementById('f-dpf').value!==''?parseFloat(document.getElementById('f-dpf').value):null,
    };
  }

  const btn=document.getElementById('submit-btn');
  btn.disabled=true;
  document.getElementById('submit-label').textContent='Analyzing...';
  document.getElementById('submit-icon').className='ms text-base spin';

  try{
    const r = await fetch(API+'/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await r.json();
    if(!r.ok){ showErr('form-error', parseApiError(data.detail)); return; }
    renderResult(data);
  }catch{ showErr('form-error','Cannot reach the server. Please make sure the app is running.'); }
  finally{
    btn.disabled=false;
    document.getElementById('submit-label').textContent='Get My Risk Assessment';
    document.getElementById('submit-icon').className='ms text-base';
  }
}

function renderResult(d, prefix=''){
  const p = prefix;
  const prob = d.probability;
  const level = d.risk_level||'';
  const isHigh = level.toLowerCase().includes('high');
  const isMod = level.toLowerCase().includes('moderate');
  const color = isHigh?'#ffb4ab':isMod?'#ffc640':'#4ade80';
  const borderColor = isHigh?'border-[#ffb4ab]':isMod?'border-[#ffc640]':'border-[#4ade80]';
  const bgColor = isHigh?'bg-[#ffb4ab]/5':isMod?'bg-[#ffc640]/5':'bg-[#4ade80]/5';
  const icon = isHigh?'dangerous':isMod?'warning':'check_circle';

  const banner = document.getElementById(p+'risk-banner');
  if(banner) banner.className = `p-6 border-l-4 ${borderColor} ${bgColor}`;

  const riskIcon = document.getElementById(p+'risk-icon');
  if(riskIcon){ riskIcon.textContent=icon; riskIcon.style.color=color; }

  const riskLabel = document.getElementById(p+'risk-label');
  if(riskLabel){ riskLabel.textContent=level; riskLabel.style.color=color; }

  const riskDisease = document.getElementById(p+'risk-disease');
  if(riskDisease) riskDisease.textContent = d.disease_target.replace('_',' ').replace(/\b\w/g,c=>c.toUpperCase());

  const riskProb = document.getElementById(p+'risk-prob');
  if(riskProb){ riskProb.textContent=(prob*100).toFixed(1)+'%'; riskProb.style.color=color; }

  const riskPid = document.getElementById(p+'risk-pid');
  if(riskPid) riskPid.textContent = d.patient_id;

  const riskConf = document.getElementById(p+'risk-conf');
  if(riskConf){
    const conf = d.confidence_flag||'';
    const confColor = conf.includes('UNCERTAIN')?'text-[#ffb4ab] border-[#ffb4ab]/30':conf.includes('LOW')?'text-[#ffc640] border-[#ffc640]/30':'text-[#8aebff] border-[#8aebff]/30';
    riskConf.className=`text-[9px] mt-1 px-2 py-0.5 border inline-block ${confColor}`;
    riskConf.textContent = conf.includes('UNCERTAIN')?'Needs Review':conf.includes('LOW')?'Borderline':'Confident Result';
  }

  const needle = document.getElementById(p+'prob-needle');
  if(needle) setTimeout(()=>{ needle.style.left=(prob*100)+'%'; },100);

  // SHAP bars
  const shapDiv = document.getElementById(p+'shap-bars');
  if(shapDiv){
    const factors = d.explanation?.top_factors||{};
    const interp = d.explanation?.interpretation||{};
    const maxAbs = Math.max(...Object.values(factors).map(Math.abs),0.001);
    const friendlyNames = {
      resting_bp:'Blood Pressure', cholesterol:'Cholesterol', max_heart_rate:'Max Heart Rate',
      age:'Age', chest_pain_type:'Chest Pain', st_depression:'ST Depression',
      num_vessels:'Blood Vessels', thal:'Heart Scan Result', exercise_angina:'Exercise Pain',
      glucose:'Blood Sugar', bmi:'Body Mass Index (BMI)', insulin:'Insulin Level',
      blood_pressure:'Blood Pressure', diabetes_pedigree:'Family History', pregnancies:'Pregnancies',
      fasting_blood_sugar:'Fasting Sugar', resting_ecg:'ECG Reading', st_slope:'ST Slope',
      skin_thickness:'Skin Thickness',
    };
    if(!Object.keys(factors).length){
      shapDiv.innerHTML='<p class="text-[10px] text-[#bbc9cd]">Factor breakdown unavailable</p>';
    } else {
      shapDiv.innerHTML = Object.entries(factors).map(([feat,val])=>{
        const pos=val>=0;
        const pct=Math.round((Math.abs(val)/maxAbs)*100);
        const col=pos?'bg-gradient-to-r from-[#ffb4ab] to-[#ff6b6b]':'bg-gradient-to-r from-[#4ade80] to-[#22c55e]';
        const tcol=pos?'text-[#ffb4ab]':'text-[#4ade80]';
        const dir=pos?'↑ Increases risk':'↓ Reduces risk';
        const name=friendlyNames[feat]||feat.replace(/_/g,' ');
        return `<div>
          <div class="flex justify-between items-center mb-1">
            <span class="text-xs font-medium text-[#dbe2fd]">${name}</span>
            <span class="text-[9px] ${tcol} font-bold">${dir}</span>
          </div>
          <div class="w-full bg-[#060d20] h-2"><div class="${col} h-full transition-all duration-700" style="width:${pct}%"></div></div>
        </div>`;
      }).join('');
    }
  }

  // Narrative
  const narr = document.getElementById(p+'narrative');
  if(narr) narr.textContent = d.clinical_narrative||'—';
  const narrativeText = document.getElementById(p==='up-'?'up-narrative':'narrative-text');
  if(narrativeText) narrativeText.textContent = d.clinical_narrative||'—';

  // Next steps
  const nextSteps = document.getElementById('next-steps');
  if(nextSteps && !p){
    const steps = isHigh
      ? ['Schedule an appointment with your doctor as soon as possible','Share these results with your healthcare provider','Avoid strenuous activity until you speak with a doctor']
      : isMod
      ? ['Book a routine check-up with your doctor','Discuss these results at your next appointment','Consider lifestyle changes like diet and exercise']
      : ['Keep up your healthy habits','Continue regular check-ups with your doctor','Re-check in 6–12 months'];
    nextSteps.innerHTML = steps.map(s=>`
      <div class="flex items-start gap-2 p-2 bg-[#131b2e]">
        <span class="ms text-[#8aebff] text-sm mt-0.5" style="font-variation-settings:'FILL' 1">arrow_right</span>
        <p class="text-[11px] text-[#bbc9cd]">${s}</p>
      </div>`).join('');
  }

  // Show result card
  if(!p){
    document.getElementById('result-placeholder').classList.add('hidden');
    document.getElementById('result-card').classList.remove('hidden');
    document.getElementById('result-card').classList.add('fade-in');
  }
}

// ── File Upload ────────────────────────────────────────────────────────────
function handleFileSelect(event){
  const file = event.target.files[0];
  if(file) setFile(file);
}

function handleDrop(event){
  event.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag-over');
  const file = event.dataTransfer.files[0];
  if(file) setFile(file);
}

function setFile(file){
  selectedFile = file;
  const icons = {'application/pdf':'picture_as_pdf','image/jpeg':'image','image/png':'image','image/webp':'image'};
  document.getElementById('file-icon').textContent = icons[file.type]||'description';
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-size').textContent = (file.size/1024).toFixed(1)+' KB · '+file.type;
  document.getElementById('file-preview').classList.remove('hidden');
  document.getElementById('drop-zone').querySelector('p').textContent = 'File selected — ready to analyze';
}

function clearFile(){
  selectedFile = null;
  document.getElementById('file-input').value='';
  document.getElementById('file-preview').classList.add('hidden');
  document.getElementById('drop-zone').querySelector('p').textContent = 'Drop your document here';
  document.getElementById('extracted-panel').classList.add('hidden');
  document.getElementById('upload-placeholder').classList.remove('hidden');
  hideErr('upload-error');
}

async function processUpload(){
  if(!selectedFile){ showErr('upload-error','Please select a file first'); return; }
  hideErr('upload-error');

  const btn = document.getElementById('upload-btn');
  btn.disabled=true;
  document.getElementById('upload-label').textContent='Reading document...';
  document.getElementById('upload-icon').className='ms text-base spin';

  try{
    const formData = new FormData();
    formData.append('file', selectedFile);

    const r = await fetch(API+'/upload-document', {method:'POST', body: formData});
    const data = await r.json();

    if(!r.ok){ showErr('upload-error', data.detail||'Could not process this document. Try a clearer image or PDF.'); return; }

    const fields = data.extracted_fields||{};
    extractedData = {...fields, disease_target: uploadDisease};

    // Show extracted panel
    document.getElementById('upload-placeholder').classList.add('hidden');
    document.getElementById('extracted-panel').classList.remove('hidden');
    document.getElementById('doc-summary').textContent = fields.document_summary||'Medical document processed';

    // Render extracted fields
    const container = document.getElementById('extracted-fields');
    const friendlyNames = {
      age:'Age', sex:'Sex', resting_bp:'Blood Pressure', cholesterol:'Cholesterol',
      max_heart_rate:'Max Heart Rate', glucose:'Blood Sugar', bmi:'BMI',
      blood_pressure:'Blood Pressure', insulin:'Insulin', fasting_blood_sugar:'Fasting Sugar',
      chest_pain_type:'Chest Pain Type', num_vessels:'Vessels', thal:'Thal',
      st_depression:'ST Depression', pregnancies:'Pregnancies', diabetes_pedigree:'Family History',
    };
    const displayFields = Object.entries(fields).filter(([k])=>k!=='document_summary'&&k!=='error');
    if(!displayFields.length){
      container.innerHTML='<p class="col-span-2 text-[10px] text-[#bbc9cd]">No clinical values could be extracted. Try a clearer image or enter values manually.</p>';
    } else {
      container.innerHTML = displayFields.map(([k,v])=>`
        <div class="bg-[#131b2e] p-3">
          <p class="text-[9px] uppercase tracking-widest text-[#bbc9cd]">${friendlyNames[k]||k.replace(/_/g,' ')}</p>
          <p class="text-sm font-bold text-[#8aebff] mt-0.5">${v}</p>
        </div>`).join('');
    }

    // Auto-run prediction if we have enough data
    if(displayFields.length >= 2){
      document.getElementById('upload-label').textContent='Running analysis...';
      await runPredictionFromExtracted(fields);
    }

  }catch(e){
    showErr('upload-error','Cannot reach the server. Please make sure the app is running.');
  } finally {
    btn.disabled=false;
    document.getElementById('upload-label').textContent='Extract & Analyze';
    document.getElementById('upload-icon').className='ms text-base';
  }
}

async function runPredictionFromExtracted(fields){
  const body = {
    age: fields.age||30,
    sex: fields.sex!==undefined?fields.sex:1,
    disease_target: uploadDisease,
    ...fields,
  };
  delete body.document_summary;

  try{
    const r = await fetch(API+'/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await r.json();
    if(!r.ok) return;
    document.getElementById('upload-result-card').classList.remove('hidden');
    renderResult(data, 'up-');
  }catch{}
}

function useExtractedData(){
  // Pre-fill the check form with extracted values
  const d = extractedData;
  if(d.age) document.getElementById('f-age').value = d.age;
  if(d.sex!==undefined) document.getElementById('f-sex').value = d.sex;
  if(d.resting_bp) document.getElementById('f-rbp').value = d.resting_bp;
  if(d.cholesterol) document.getElementById('f-chol').value = d.cholesterol;
  if(d.max_heart_rate) document.getElementById('f-mhr').value = d.max_heart_rate;
  if(d.chest_pain_type!==undefined) document.getElementById('f-cp').value = d.chest_pain_type;
  if(d.st_depression!==undefined) document.getElementById('f-std').value = d.st_depression;
  if(d.num_vessels!==undefined) document.getElementById('f-ca').value = d.num_vessels;
  if(d.thal!==undefined) document.getElementById('f-thal').value = d.thal;
  if(d.glucose) document.getElementById('f-gluc').value = d.glucose;
  if(d.bmi) document.getElementById('f-bmi').value = d.bmi;
  if(d.blood_pressure) document.getElementById('f-bp').value = d.blood_pressure;
  if(d.insulin!==undefined) document.getElementById('f-ins').value = d.insulin;
  if(d.pregnancies!==undefined) document.getElementById('f-preg').value = d.pregnancies;
  if(d.diabetes_pedigree!==undefined) document.getElementById('f-dpf').value = d.diabetes_pedigree;
  setDisease(uploadDisease);
  nav('check');
}

// ── History ────────────────────────────────────────────────────────────────
async function loadHistory(disease){
  document.getElementById('hist-btn-heart').className = disease==='heart_disease'
    ? 'px-3 py-1.5 text-[10px] font-bold border border-[#8aebff]/20 text-[#8aebff] uppercase vg text-[#00363e]'
    : 'px-3 py-1.5 text-[10px] font-bold border border-[#3c494c]/30 text-[#bbc9cd] uppercase hover:border-[#8aebff]/30 transition-colors';
  document.getElementById('hist-btn-diab').className = disease==='diabetes'
    ? 'px-3 py-1.5 text-[10px] font-bold border border-[#8aebff]/20 text-[#8aebff] uppercase vg text-[#00363e]'
    : 'px-3 py-1.5 text-[10px] font-bold border border-[#3c494c]/30 text-[#bbc9cd] uppercase hover:border-[#8aebff]/30 transition-colors';

  try{
    const [audit, mon] = await Promise.all([
      fetch(API+'/audit?disease='+disease+'&limit=50').then(r=>r.json()),
      fetch(API+'/monitoring?disease='+disease).then(r=>r.json())
    ]);
    const dist = mon.risk_distribution||{};
    document.getElementById('hist-total').textContent = mon.total_predictions||0;
    document.getElementById('hist-high').textContent = dist['High Risk']||0;
    document.getElementById('hist-low').textContent = dist['Low Risk']||0;

    const tbody = document.getElementById('hist-tbody');
    if(!audit.length){
      tbody.innerHTML='<tr><td colspan="5" class="px-5 py-8 text-center text-[#bbc9cd] text-[10px]">No health checks yet. <button onclick="nav(\'check\')" class="text-[#8aebff] underline">Run your first check</button></td></tr>';
      return;
    }
    tbody.innerHTML = audit.map(r=>{
      const isHigh=r.risk_level.toLowerCase().includes('high');
      const isMod=r.risk_level.toLowerCase().includes('moderate');
      const col=isHigh?'text-[#ffb4ab]':isMod?'text-[#ffc640]':'text-[#4ade80]';
      const badge=isHigh?'bg-[#ffb4ab]/10 text-[#ffb4ab] border-[#ffb4ab]/20':isMod?'bg-[#ffc640]/10 text-[#ffc640] border-[#ffc640]/20':'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20';
      return `<tr class="hover:bg-[#2d3449] transition-colors">
        <td class="px-5 py-3 font-mono text-[#8aebff] text-xs">${r.patient_id}</td>
        <td class="px-5 py-3"><span class="${r.prediction==='Positive'?'text-[#ffb4ab]':'text-[#4ade80]'} font-bold text-xs">${r.prediction==='Positive'?'At Risk':'Low Risk'}</span></td>
        <td class="px-5 py-3"><span class="px-2 py-0.5 border text-[9px] uppercase ${badge}">${r.risk_level}</span></td>
        <td class="px-5 py-3 font-mono text-sm font-bold ${col}">${(r.probability*100).toFixed(1)}%</td>
        <td class="px-5 py-3 text-[10px] text-[#bbc9cd]">${r.timestamp.slice(0,19).replace('T',' ')} UTC</td>
      </tr>`;
    }).join('');
  }catch(e){ console.error(e); }
}

// ── Init ───────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', ()=>{
  checkHealth();
  loadHomeStats();
  setInterval(checkHealth, 30000);
});
