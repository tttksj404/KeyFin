/* Supplied asset or cumulative-consumption paths; missing points are not invented. */
(function(global){'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const day=s=>Date.parse(s+'T00:00:00Z')/86400000;
const numeric=v=>v!=null&&typeof v==='number'&&Number.isFinite(v)&&Math.abs(v)<=Number.MAX_SAFE_INTEGER;
function segments(rows,key,gap){let result=[],part=[];for(const r of rows){if(!numeric(r[key])){if(part.length)result.push(part);part=[];continue;}if(part.length&&day(r.date)-day(part.at(-1).date)>gap){result.push(part);part=[];}part.push(r);}if(part.length)result.push(part);return result;}
function validate(b,meta){
 meta=KeyFinChart.budgetPeriod(meta);
 if(!b)return;
 if(!Object.prototype.hasOwnProperty.call(KeyFinChart.KIND,b.kind))throw new TypeError('자산 범위(kind)를 명시하세요.');
 const date=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(day(v))&&new Date(day(v)*86400000).toISOString().slice(0,10)===v;
 if(!date(meta.as_of)||!date(meta.horizon_end)||meta.horizon_end<meta.as_of)throw new TypeError('자산 기준일/종료일을 확인하세요.');
 for(const field of ['current_krw','baseline_p50_krw'])if(b[field]!=null&&!numeric(b[field]))throw new TypeError('자산 수치가 유효하지 않습니다.');
 if(b.budget_krw!=null&&(!numeric(b.budget_krw)||b.budget_krw<0))throw new TypeError('기간 예산은 0 이상의 숫자여야 합니다.');
 if(b.max_gap_days!=null&&(!Number.isInteger(b.max_gap_days)||b.max_gap_days<1))throw new TypeError('허용 날짜 간격은 양의 정수여야 합니다.');
 for(const name of ['history','forecast','baseline']){
  const seen=new Set();if(b[name]!=null&&!Array.isArray(b[name]))throw new TypeError('자산 경로는 배열이어야 합니다.');
  for(const r of b[name]||[]){
   if(!date(r.date)||seen.has(r.date))throw new TypeError('유효하지 않거나 중복된 날짜입니다.');seen.add(r.date);
   if(meta.period_start&&r.date<meta.period_start||name==='history'&&r.date>meta.as_of||name!=='history'&&(r.date<meta.as_of||r.date>meta.horizon_end))throw new TypeError('날짜가 계산 기간을 벗어났습니다.');
   for(const key of name==='history'?['value_krw']:['p10_krw','p50_krw','p90_krw'])if(r[key]!=null&&!numeric(r[key]))throw new TypeError('자산 경로 수치를 확인하세요.');
   if(name!=='history'){
    const q=[r.p10_krw,r.p50_krw,r.p90_krw].filter(numeric);if(q.some((v,i)=>i&&v<q[i-1]))throw new TypeError('P10 ≤ P50 ≤ P90 순서가 아닙니다.');
    if(r.p50_krw==null&&(r.p10_krw!=null||r.p90_krw!=null))throw new TypeError('구간에는 P50이 필요합니다.');
   }
   if(name==='history'&&r.date===meta.as_of&&r.value_krw!==b.current_krw)throw new TypeError('현재 자산과 이력 기준일 값이 다릅니다.');
   if(name==='forecast'&&r.date===meta.as_of&&r.p50_krw!=null&&r.p50_krw!==b.current_krw)throw new TypeError('예측 시작과 현재 자산이 다릅니다.');
  }
 }
 const terminal=b.terminal||{};const q=[terminal.p10_krw,terminal.p50_krw,terminal.p90_krw].filter(numeric);
 for(const k of ['p10_krw','p50_krw','p90_krw'])if(terminal[k]!=null&&!numeric(terminal[k]))throw new TypeError('종료 수치를 확인하세요.');
 if(q.some((v,i)=>i&&v<q[i-1]))throw new TypeError('종료 분위수 순서가 잘못됐습니다.');
 const last=(b.forecast||[]).find(r=>r.date===meta.horizon_end);
 if(last&&['p10_krw','p50_krw','p90_krw'].some(k=>(last[k]??null)!==(terminal[k]??null)))throw new TypeError('종료 요약과 경로의 값이 다릅니다.');
}
function svg(input,style={}){
 const d=KeyFinChart.normalize(input),b=d.balance,meta=d.meta;validate(b,meta);
 if(!b)return '<div class="kf-empty">총자산 경로를 입력하면 흐름이 표시됩니다.</div>';
 const consumption=b.kind==='cumulative_expense';
 if(consumption&&[[b.current_krw,d.totalCurrent],[b.terminal?.p50_krw,d.totalForecast],[b.budget_krw,d.totalBudget]].some(([a,v])=>a!=null&&v!=null&&Math.abs(a-v)>.02))throw new TypeError('소비 차트 합계와 누적 소비 경로의 값이 다릅니다. 시계열도 함께 갱신하세요.');
 const c=KeyFinChart.colors({...KeyFinChart.DEFAULT_STYLE,...style});
 const history=(b.history||[]).slice().sort((a,b)=>a.date.localeCompare(b.date)),forecast=(b.forecast||[]).slice().sort((a,b)=>a.date.localeCompare(b.date)),baseline=(b.baseline||[]).slice().sort((a,b)=>a.date.localeCompare(b.date));
 const all=[...history.map(r=>({...r,p50_krw:r.value_krw})),...forecast,...baseline];
 const values=all.flatMap(r=>[r.p10_krw,r.p50_krw,r.p90_krw]).filter(numeric);
 if(!values.length)return '<div class="kf-empty">표시할 자산 수치가 없습니다.</div>';
 values.push(...[b.current_krw,b.terminal?.p50_krw,b.budget_krw].filter(numeric));
 if(consumption)values.push(0);
 const W=363,H=190,L=44,R=18,T=15,B=154,now=day(meta.as_of),end=day(meta.horizon_end),start=meta.period_start?day(meta.period_start):Math.min(now-1,...all.map(r=>day(r.date)));
 let low=Math.min(...values),high=Math.max(...values),span=high-low||Math.max(Math.abs(high)*.1,10000);low-=span*.15;high+=span*.17;
 if(consumption&&Math.min(...values)>=0)low=0;
 const x=date=>L+(day(date)-start)/Math.max(1,end-start)*(W-L-R),y=v=>B-(v-low)/(high-low)*(B-T),gap=b.max_gap_days||1;
 let text=`<svg class="kf-flow-svg" data-start="${new Date(start*86400000).toISOString().slice(0,10)}" data-end="${meta.horizon_end}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(KeyFinChart.KIND[b.kind])} 흐름: ${esc(meta.period_range||'')} 관측은 실선, 예측은 점선" style="display:block;width:100%;height:auto;font-family:Arial,'Noto Sans CJK KR',sans-serif"><title>입력된 시계열의 실제 날짜 간격을 사용합니다.</title>`;
 text+=`<rect x="${x(meta.as_of)}" y="${T}" width="${W-R-x(meta.as_of)}" height="${B-T}" rx="8" fill="${c.forecast}" fill-opacity=".08"/>`;
 for(let i=0;i<3;i++){
  const v=low+(high-low)*i/2;
  const label=Math.abs(v)>=100000000?Number((v/100000000).toFixed(1))+'억':Math.abs(v)>=10000?Number((v/10000).toFixed(1))+'만':KeyFinChart.fmt(v);
  text+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#efedf5"/><text x="${L-7}" y="${y(v)+3}" font-size="8.5" text-anchor="end" fill="#8c879d">${label}</text>`;
 }
 const band=forecast.map(r=>({...r,band:numeric(r.p10_krw)&&numeric(r.p90_krw)?1:null}));
 for(const s of segments(band,'band',gap))if(s.length>1){text+=`<polygon class="forecast-band" points="${[...s.map(r=>`${x(r.date)},${y(r.p10_krw)}`),...s.slice().reverse().map(r=>`${x(r.date)},${y(r.p90_krw)}`)].join(' ')}" fill="${c.forecast}" fill-opacity=".16"/>`;}
 const line=(rows,key,cls,color,dash,opacity=1)=>segments(rows,key,gap).map(s=>`<path class="${cls}" d="${s.map((r,i)=>(i?'L':'M')+x(r.date).toFixed(3)+' '+y(r[key]).toFixed(3)).join(' ')}" stroke="${color}" stroke-width="2.2" stroke-opacity="${opacity}" fill="none" stroke-dasharray="${dash}" stroke-linecap="round" stroke-linejoin="round"/>`+(s.length===1?`<circle cx="${x(s[0].date)}" cy="${y(s[0][key])}" r="2.2" fill="${color}"/>`:'')).join('');
 text+=line(baseline,'p50_krw','baseline-line','#a39bbd','3 4',.7)+line(history,'value_krw','history-line',c.current,'none')+line(forecast,'p50_krw','forecast-line',c.forecastLine,'3 4',.8);
 text+=`<line x1="${x(meta.as_of)}" x2="${x(meta.as_of)}" y1="${T}" y2="${B}" stroke="#bcb5d4" stroke-dasharray="2 4"/>`;
 if(low<0&&high>0)text+=`<line class="zero-line" x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="${c.pink}" stroke-dasharray="2 3"/>`;
 for(const r of forecast)if(numeric(r.p50_krw))text+=`<circle class="flow-hit" cx="${x(r.date)}" cy="${y(r.p50_krw)}" r="5" fill="transparent" tabindex="0" aria-label="${esc(r.date+' '+KeyFinChart.money(r.p50_krw))}"><title>${r.date} · ${KeyFinChart.money(r.p50_krw)}</title></circle>`;
 if(numeric(b.current_krw))text+=`<circle class="current-dot" cx="${x(meta.as_of)}" cy="${y(b.current_krw)}" r="3.5" fill="${c.current}" stroke="white" stroke-width="1.5"/>`;
 if(numeric(b.terminal?.p50_krw))text+=`<circle class="terminal-dot" data-value="${b.terminal.p50_krw}" cx="${x(meta.horizon_end)}" cy="${y(b.terminal.p50_krw)}" r="3.5" fill="${c.forecastLine}" fill-opacity=".8" stroke="white" stroke-width="1.5"/>`;
 if(numeric(b.budget_krw)){const by=y(b.budget_krw);text+=`<line class="monthly-budget-line" x1="${L}" x2="${W-R}" y1="${by}" y2="${by}" stroke="#af3760" stroke-dasharray="5 3"/><text class="budget-value" x="${W-R}" y="${by-5}" text-anchor="end" font-size="9" fill="#973052">기간 예산 ${KeyFinChart.money(b.budget_krw)}</text>`;}
 if(consumption){
  if(numeric(b.current_krw))text+=`<text class="current-value" x="${x(meta.as_of)+(now-start<(end-start)*.3?5:-5)}" y="${Math.max(T+10,y(b.current_krw)-10)}" text-anchor="${now-start<(end-start)*.3?'start':'end'}" font-size="9" fill="#236db9">${KeyFinChart.money(b.current_krw)}</text>`;
  if(numeric(b.terminal?.p50_krw))text+=`<text class="forecast-value" x="${x(meta.horizon_end)-3}" y="${numeric(b.budget_krw)&&b.terminal.p50_krw>b.budget_krw?Math.max(T+10,y(b.terminal.p50_krw)-10):Math.min(B-5,y(b.terminal.p50_krw)+15)}" text-anchor="end" font-size="9" fill="${c.forecastLine}">${KeyFinChart.money(b.terminal.p50_krw)}</text>`;
 }
 const dates=[...new Set([start,now,end])];
 for(let i=0;i<dates.length;i++){
  if(dates[i]===now&&now!==start&&now!==end&&Math.min(now-start,end-now)<(end-start)*.18)continue;
  const n=dates[i],date=new Date(n*86400000).toISOString().slice(0,10);
  text+=`<text x="${x(date)}" y="${B+21}" text-anchor="${i===0?'start':i===dates.length-1?'end':'middle'}" fill="${n===now?'#236db9':'#8c879d'}" font-size="9">${date.slice(5).replace('-','/')}${n===now?' 현재':''}</text>`;
 }
 return text+'</svg>';
}
// Optional daily category amounts supplied by the caller; never infer them from a total P50.
const categoryColors=KeyFinChart.categoryColors;
function dailySvg(input){
 const d=KeyFinChart.normalize(input),m=d.meta,rows=d.balance?.daily;
 if(rows==null)return '<div class="kf-empty">일별 카테고리 데이터 미제공</div>';
 if(!m.period_start||!Array.isArray(rows))throw new TypeError('일별 소비에는 예산 시작일과 daily 배열이 필요합니다.');
 const seen=new Set(),points=rows.map(r=>{
  if(!KeyFinChart.validDate(r.date)||r.date<m.period_start||r.date>m.horizon_end||seen.has(r.date))throw new TypeError('일별 소비 날짜가 중복되었거나 예산 기간을 벗어났습니다.');
  seen.add(r.date);
  if(!Array.isArray(r.amounts_krw)||r.amounts_krw.length!==d.categories.length||r.amounts_krw.some(v=>!numeric(v)||v<0))throw new TypeError('일별 소비는 카테고리 순서대로 0 이상의 금액을 전달하세요.');
  const total=r.amounts_krw.reduce((s,v)=>s+v,0);
  if(!numeric(total))throw new TypeError('일별 소비 합계가 유효하지 않습니다.');
  return {...r,total};
 }).sort((a,b)=>a.date.localeCompare(b.date));
 if(!points.length)return '<div class="kf-empty">일별 카테고리 데이터 미제공</div>';
 const W=363,H=132,L=44,R=18,T=14,B=106,start=day(m.period_start),end=day(m.horizon_end),step=(W-L-R)/m.period_days,bw=step*.72;
 const x=date=>L+(day(date)-start+.5)*step,high=Math.max(1,...points.map(r=>r.total))*1.15,y=v=>B-v/high*(B-T);
 let out=`<svg class="kf-daily-svg" data-start="${m.period_start}" data-end="${m.horizon_end}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(m.period_range)} 일별 소비와 카테고리 구성. 예측 막대는 옅게 표시합니다.">`;
 out+=`<rect x="${x(m.as_of)+step/2}" y="${T}" width="${Math.max(0,W-R-x(m.as_of)-step/2)}" height="${B-T}" fill="#ffd84d" fill-opacity=".08"/>`;
 for(let i=0;i<3;i++){
  const v=high*i/2;
  out+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#efedf5"/><text x="${L-7}" y="${y(v)+3}" text-anchor="end" font-size="8.5" fill="#767085">${v>=10000?Number((v/10000).toFixed(1))+'만':KeyFinChart.fmt(v)}</text>`;
 }
 for(const r of points){
  const tip=`${r.date} · ${r.date<=m.as_of?'기록':'예측'} · ${KeyFinChart.money(r.total)}\n`+d.categories.map((c,i)=>c.label+' '+KeyFinChart.money(r.amounts_krw[i])).join(' · ');
  out+=`<g class="daily-bar" tabindex="0" data-date="${r.date}" data-value="${r.total}" aria-label="${esc(tip)}"><title>${esc(tip)}</title><rect x="${x(r.date)-step/2}" y="${T}" width="${step}" height="${B-T}" fill="transparent"/>`;
  let sum=0;
  r.amounts_krw.forEach((value,i)=>{sum+=value;out+=`<rect x="${x(r.date)-bw/2}" y="${y(sum)}" width="${bw}" height="${value/high*(B-T)}" fill="${categoryColors[i%categoryColors.length]}" fill-opacity="${r.date<=m.as_of?1:.4}"/>`;});
  out+='</g>';
 }
 out+=`<line x1="${x(m.as_of)}" x2="${x(m.as_of)}" y1="${T}" y2="${B}" stroke="#827a98" stroke-dasharray="2 3"/>`;
 for(const n of [...new Set([start,day(m.as_of),end])]){
  if(n!==start&&n!==end&&Math.min(n-start,end-n)<(end-start)*.18)continue;
  const date=new Date(n*86400000).toISOString().slice(0,10);
  out+=`<text x="${x(date)}" y="${B+19}" text-anchor="${n===start?'start':n===end?'end':'middle'}" font-size="9" fill="#767085">${date.slice(5).replace('-','/')}${date===m.as_of?' 기준':''}</text>`;
 }
 return out+'</svg>';
}
const api={svg,validate,segments,dailySvg,categoryColors};global.KeyFinFlow=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
