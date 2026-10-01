'use strict';
const $=id=>document.getElementById(id), finite=n=>typeof n==='number'&&Number.isFinite(n);
const fmt=(n,d=2)=>finite(n)?n.toFixed(d):'—';
const pct=n=>finite(n)?`${n>0?'+':''}${n.toFixed(2)}%`:'Unavailable';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const delta=(id,n,suffix='')=>{$(id).textContent=pct(n)+suffix;$(id).className=finite(n)?n<0?'down':n>0?'up':'muted':'muted'};
const dateText=s=>s?new Date(s).toISOString().slice(0,16).replace('T',' '):'Unavailable';
let data, range='all', layer='gpu', displayed=[], current=0;
const ns='http://www.w3.org/2000/svg';
function svgEl(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
function selection(){const a=data.level;if(range==='all')return a;const last=Date.parse(a.at(-1).date);return a.filter(r=>last-Date.parse(r.date)<Number(range)*86400000)}
function renderChart(){
 const svg=$('chart');svg.replaceChildren();$('tooltip').hidden=true;displayed=selection();
 const compare=$('compare').checked,average=$('average').checked,relative=$('relative').checked;
 const colors={acpi_level:'#59dfc0',gpu_index:'#70adff',api_index:'#f4c77c',ma_30:'#b2bbca'};
 const keys=['acpi_level',...(compare?['gpu_index','api_index']:[]),...(average?['ma_30']:[])];
 const baseline=relative?displayed.find(r=>finite(r.acpi_level)):null;
 const value=(r,k)=>finite(r[k])?(relative?finite(baseline?.[k==='ma_30'?'acpi_level':k])?100*r[k]/baseline[k==='ma_30'?'acpi_level':k]:null:r[k]):null;
 const vals=displayed.flatMap(r=>keys.map(k=>value(r,k))).filter(finite);
 $('chart-empty').hidden=vals.length>0;if(!vals.length)return;
 let low=Math.min(100,...vals),high=Math.max(100,...vals),pad=Math.max(1,(high-low)*.15);low-=pad;high+=pad;
 const L=60,R=1040,T=20,B=290;const x=i=>L+i*(R-L)/Math.max(1,displayed.length-1),y=v=>B-(v-low)/(high-low)*(B-T);
 svg.append(svgEl('title',{},'ACPI fixed basket daily quote index'));
 for(let j=0;j<=4;j++){const v=low+(high-low)*j/4;svg.append(svgEl('line',{x1:L,x2:R,y1:y(v),y2:y(v),stroke:'#263345'}));svg.append(svgEl('text',{x:L-12,y:y(v)+4,'text-anchor':'end',fill:'#a4b1c3','font-size':11},v.toFixed(1)))}
 svg.append(svgEl('line',{x1:L,x2:R,y1:y(100),y2:y(100),stroke:'#738297','stroke-dasharray':'4 5'}));
 const ticks=Math.min(5,displayed.length);for(let j=0;j<ticks;j++){const i=Math.round(j*(displayed.length-1)/Math.max(1,ticks-1));svg.append(svgEl('text',{x:x(i),y:B+30,'text-anchor':j===0?'start':j===ticks-1?'end':'middle',fill:'#a4b1c3','font-size':11},displayed[i].date.slice(5)))}
 keys.forEach(k=>{let path='',open=false;displayed.forEach((r,i)=>{const v=value(r,k);if(!finite(v)){open=false;return}path+=`${open?'L':'M'}${x(i).toFixed(2)} ${y(v).toFixed(2)} `;open=true});svg.append(svgEl('path',{d:path,fill:'none',stroke:colors[k],'stroke-width':k==='acpi_level'?2.8:1.7,'stroke-dasharray':k==='ma_30'?'5 5':'none','stroke-linejoin':'round'}));if(displayed.length===1){const v=value(displayed[0],k);if(finite(v))svg.append(svgEl('circle',{cx:x(0),cy:y(v),r:4,fill:colors[k]}))}});
 const cross=svgEl('line',{x1:L,x2:L,y1:T,y2:B,stroke:'#738297','stroke-dasharray':'3 3',visibility:'hidden'});svg.append(cross);
 function inspect(i){current=Math.max(0,Math.min(displayed.length-1,i));const r=displayed[current];cross.setAttribute('x1',x(current));cross.setAttribute('x2',x(current));cross.setAttribute('visibility','visible');$('tooltip').hidden=false;$('tooltip').innerHTML=`<b>${escape(r.date)} · ${escape(r.quality_flag)}</b><br>ACPI ${fmt(r.acpi_level)} · 1D ${pct(r.chg_1d_pct)}<br>GPU ${fmt(r.gpu_index)} / API ${fmt(r.api_index)}${relative?'<br>Chart rebased to selection start':''}`;const width=svg.getBoundingClientRect().width;const left=Math.max(8,Math.min(x(current)/1100*width+12,width-250));$('tooltip').style.left=left+'px'}
 svg.onpointermove=e=>{const rect=svg.getBoundingClientRect();const px=(e.clientX-rect.left)/rect.width*1100;inspect(Math.round((px-L)/(R-L)*Math.max(1,displayed.length-1)))};
 svg.onpointerleave=()=>{cross.setAttribute('visibility','hidden');$('tooltip').hidden=true};
 svg.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();inspect(current+(e.key==='ArrowLeft'?-1:1))}};
 const first=displayed.find(r=>finite(r.acpi_level)),last=displayed.at(-1);const change=first&&finite(last.acpi_level)?(last.acpi_level/first.acpi_level-1)*100:null;
 $('range-summary').textContent=`${displayed[0].date} → ${last.date} · ${pct(change)} over selection${relative?' · rebased':''}`;
 current=displayed.length-1;
}
function renderTable(){
 const latest=data.level.at(-1).date,cs=data.components.filter(r=>r.date===latest&&r.layer===layer);
 $('constituents').innerHTML=cs.map(r=>{const history=data.components.filter(x=>x.item===r.item&&Date.parse(latest)-Date.parse(x.date)<30*86400000&&['observed','carried'].includes(x.status)&&finite(x.price));const prior=data.components.find(x=>x.item===r.item&&Date.parse(latest)-Date.parse(x.date)===86400000);const valid=['observed','carried'].includes(r.status),change=valid&&prior&&['observed','carried'].includes(prior.status)&&prior.price>0?(r.price/prior.price-1)*100:null;const prices=history.map(x=>x.price);return `<tr><td><strong>${escape(r.provider.toUpperCase())}</strong><small>${escape(r.label)}</small></td><td>${valid?'$'+fmt(r.price,3):'Unavailable'}<br><small>${escape(r.status)}</small></td><td class="${change<0?'down':change>0?'up':'muted'}">${pct(change)}</td><td>${prices.length?'$'+fmt(Math.min(...prices),3)+' – $'+fmt(Math.max(...prices),3):'—'}</td><td>${fmt(r.weight*100,2)}%</td><td>${dateText(r.observed_at)}<br><small>${r.age_days??'—'} calendar days old</small></td></tr>`}).join('');
}
function renderContext(){
 const now=Date.parse(data.meta.latest_date);
 const latestBy=(rows,key)=>{const map=new Map();rows.forEach(r=>{if(!map.has(r[key])||r.timestamp>map.get(r[key]).timestamp)map.set(r[key],r)});return [...map.values()].sort((a,b)=>String(a[key]).localeCompare(String(b[key])))};
 $('power').innerHTML=latestBy(data.context.power,'state').map(r=>`<div class="context-row"><span>${escape(r.state)}<small>Source month ${escape(r.period)} · collected ${dateText(r.timestamp)}</small></span><b>${fmt(r.price_cents_per_kwh)} ¢/kWh</b></div>`).join('')||'<p>Unavailable</p>';
 $('equities').innerHTML=latestBy(data.context.market,'ticker').map(r=>{const old=(now-Date.parse(r.date))/86400000>4;return `<div class="context-row"><span>${escape(r.ticker)}<small>${r.quote_date?'Quote date '+escape(r.quote_date):'Historical quote date not recorded'} · collected ${dateText(r.timestamp)}${old?' · stale':''}</small></span><b>${fmt(r.close_usd)} USD</b></div>`}).join('')||'<p>Unavailable</p>';
}
function render(){
 const r=data.level.at(-1);$('index').textContent=fmt(r.acpi_level);delta('daily',r.chg_1d_pct,' · 1D');$('daily').classList.add('delta');delta('week',r.chg_7d_pct);delta('month',r.chg_30d_pct);delta('frombase',finite(r.acpi_level)?r.acpi_level-100:null);delta('peak',r.drawdown_pct);
 $('base').textContent=`Base ${data.meta.base_date} = 100 · GPU 70% / API 30% · ${r.date} provisional UTC daily close`;
 $('updated').textContent=`Last quote ${dateText(data.meta.latest_observed_at)} UTC`;
 const age=(Date.now()-Date.parse(data.meta.latest_observed_at))/3600000;
 if(r.quality_flag!=='observed'||age>24){$('quality').hidden=false;$('quality').textContent=r.expired?`${r.expired} fixed quotes unavailable. ACPI is withheld; stale prices are not reported as new observations.`:age>24?`Latest quote is ${Math.floor(age)} hours old. This is a scheduled daily quote dashboard.`:`Data status: ${r.quality_flag}. ${r.carried} quotes carried forward; check observation dates.`}
 $('position').textContent=finite(r.percentile_90)?`${fmt(r.percentile_90,0)} / 100`:'Unavailable';$('meter').style.left=(r.percentile_90??50)+'%';
 $('position-note').textContent=finite(r.percentile_90)?`Historical price rank, with ties centered. Lower = lower prices relative to available observations in the last 90 calendar days. Equal prices rank at 50; this is not fair value.`:'At least 7 complete observations are needed.';
 $('contributions').innerHTML=['gpu','api'].map(k=>`<div class="contribution"><span>${k==='gpu'?'GPU rentals':'Model APIs'}</span><b class="${r['contrib_'+k+'_log_pct']<0?'down':'muted'}">${finite(r['contrib_'+k+'_log_pct'])?fmt(r['contrib_'+k+'_log_pct'],3)+' log-%':'Unavailable'}</b></div>`).join('');
 $('coverage').textContent=`${r.coverage} / ${data.meta.basket_size} quotes`;$('health').textContent=`${r.coverage-r.carried} observed today · ${r.carried} carried · ${r.expired} unavailable. Carry limit: ${data.meta.max_carry_days} calendar days. Historical data rebuilt using v1 fixed membership.`;
 const corr=data.correlations.at(-1)?.gpu_api_returns,pca=data.pca.findLast(x=>x.date===r.date);
 $('research').textContent=`Price-level z-score (30 calendar days): ${finite(r.z_30)?fmt(r.z_30,3):'Unavailable (no meaningful variation)'}. Trailing 30-day GPU/API daily-return correlation: ${finite(corr)?fmt(corr,3):'Unavailable (insufficient paired variation)'}. PCA: ${pca?'PC1 '+fmt(pca.pc1,3)+', explained variance '+fmt(pca.variance_explained*100,1)+'%':'Unavailable (fewer than two varying dimensions or insufficient history)'}.`;
 renderChart();renderTable();renderContext();
}
document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{range=b.dataset.range;document.querySelectorAll('[data-range]').forEach(x=>x.classList.toggle('active',x===b));renderChart()});
document.querySelectorAll('[data-layer]').forEach(b=>b.onclick=()=>{layer=b.dataset.layer;document.querySelectorAll('[data-layer]').forEach(x=>x.classList.toggle('active',x===b));renderTable()});
['compare','average','relative'].forEach(id=>$(id).onchange=()=>data&&renderChart());
$('chart').addEventListener('wheel',e=>{if(!data)return;e.preventDefault();const options=['7','30','90','all'];const i=options.indexOf(String(range));range=options[Math.max(0,Math.min(3,i+(e.deltaY>0?1:-1)))];document.querySelectorAll('[data-range]').forEach(b=>b.classList.toggle('active',b.dataset.range===range));renderChart()},{passive:false});
$('download').onclick=()=>{if(!data)return;const keys=['date','acpi_level','gpu_index','api_index','chg_1d_pct','quality_flag'];const csv=keys.join(',')+'\n'+selection().map(r=>keys.map(k=>r[k]??'').join(',')).join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='acpi-daily.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
(async()=>{try{const res=await fetch('data.json',{cache:'no-store'});if(!res.ok)throw new Error('Data request returned '+res.status);data=await res.json();if(!data.level?.length||!data.basket?.members?.length)throw new Error('Missing v1 fixed basket data. Run python -m analysis.build_dashboard.');render()}catch(e){$('error').hidden=false;$('error').textContent='Prices could not be loaded. '+e.message;$('updated').textContent='Data unavailable';console.error(e)}})();
