/* KeyFin chart v2. Pure SVG; style parameters never modify financial data. */
(function (global) {
'use strict';
const DEFAULT_STYLE = {
  bgR:56,bgG:40,bgB:190,mintR:8,mintG:212,mintB:180,
  yellowR:255,yellowG:169,yellowB:3,pinkR:255,pinkG:33,pinkB:97,
  trackR:241,trackG:241,trackB:250,mutedAlpha:.72,
  currentR:56,currentG:148,currentB:244,forecastR:255,forecastG:216,forecastB:77,
  forecastLineR:152,forecastLineG:108,forecastLineB:0,
  radius:25,bottomRadius:5,padX:23,titleY:42,titleSize:16,titleWeight:600,
  statusSize:12,statusY:41,amountY:101,amountSize:36,amountWeight:700,
  amountSpacing:-1.0,subtitleY:129,subtitleSize:12.5,
  progressY:151,progressH:9,headingY:190,headingSize:12,
  helperSize:10,barTop:219,barHeight:97,barWidth:24,barRadius:7,
  firstCenter:42,barStep:46,labelY:213,labelSize:11,labelWeight:600,
  categoryY:331,categorySize:11,letterSpacing:-.25,fontIndex:0,
  numberFontIndex:0,fadeBottom:.04
};
const FONTS = ['"Noto Sans CJK KR",sans-serif','"NanumGothic",sans-serif','"NanumSquare",sans-serif','"Arial","Noto Sans CJK KR",sans-serif'];
const NFONTS = ['"Arial","Noto Sans CJK KR",sans-serif','"Inter","Noto Sans CJK KR",sans-serif','"Noto Sans CJK KR",sans-serif'];
const categoryColors=['#eaa23a','#65aaf0','#60cdbb','#a283ec','#db68a6','#a8c847','#eed452'];
const KIND = {cumulative_expense:'누적 소비',total_assets:'총자산',cash_balance:'현금 잔액',resource_change:'지출 준비 여력 변화'};
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = v => v == null ? '—' : new Intl.NumberFormat('ko-KR',{maximumFractionDigits:0}).format(v);
const money = v => v == null ? '정보 없음' : fmt(v)+'원';
const pct = v => v == null ? '—' : (Math.abs(v)>9999 ? fmt(v) : Number(v.toFixed(1)).toString())+'%';
const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
const round = n => Number(n.toFixed(4));
const day = s => Date.parse(s+'T00:00:00Z')/86400000;
const validDate = s => typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(day(s))&&new Date(day(s)*86400000).toISOString().slice(0,10)===s;
function budgetPeriod(meta={}) {
  if(meta.period_start==null)return {...meta}; // Legacy inputs keep their explicitly supplied horizon.
  if(!validDate(meta.period_start)||!validDate(meta.as_of))throw new TypeError('예산 시작일과 기준일은 YYYY-MM-DD 날짜여야 합니다.');
  const start=new Date(day(meta.period_start)*86400000),next=new Date(start);
  next.setUTCDate(1);next.setUTCMonth(next.getUTCMonth()+1);
  const last=new Date(next);last.setUTCMonth(last.getUTCMonth()+1);last.setUTCDate(0);
  next.setUTCDate(Math.min(start.getUTCDate(),last.getUTCDate()));
  const end=new Date(next.getTime()-86400000).toISOString().slice(0,10);
  if(meta.horizon_end!=null&&meta.horizon_end!==end)throw new TypeError('예측 종료일은 예산 시작일부터 한 달 뒤 시작일의 전날이어야 합니다: '+end);
  if(meta.as_of<meta.period_start||meta.as_of>end)throw new TypeError('기준일이 예산 기간을 벗어났습니다.');
  return {...meta,horizon_end:end,next_start:next.toISOString().slice(0,10),period_days:day(end)-day(meta.period_start)+1,
    period_range:meta.period_start.replaceAll('-','/')+' ~ '+end.replaceAll('-','/'),
    headline:'예산 기간 예상 소비',period_label:end.slice(5).replace('-','/')+'까지 누적'};
}
let seq = 0;
function finite(v,path,{negative=true}={}) {
  if(v==null)return null;
  if(typeof v!=='number'||!Number.isFinite(v)||Math.abs(v)>Number.MAX_SAFE_INTEGER||(!negative&&v<0))throw new TypeError(path+': 유효한 숫자 또는 null이 필요합니다.');
  return v;
}
function normalize(input) {
  if(!input||typeof input!=='object'||Array.isArray(input))throw new TypeError('결과 객체가 필요합니다.');
  const old = input.schema_version === '1.0';
  const e = old ? input.envelopes : input;
  if(!e || !Array.isArray(old?e.rows:e.categories)) throw new TypeError('categories 배열 또는 v1 envelopes.rows가 필요합니다.');
  const semantics = old?e.value_semantics:(e.value_semantics||'period_total');
  if(!['period_total','snapshot','future_only'].includes(semantics))throw new TypeError('소비 집계 의미를 확인하세요.');
  const ids = new Set();
  const categories = (old?e.rows:e.categories).map((r,i)=>{
    const id = String(r.id??i),label=String(r.short_label||r.label||'');
    if(ids.has(id)||!label)throw new TypeError('봉투 id는 고유하고 이름이 있어야 합니다.'); ids.add(id);
    const current=finite(old?r.current_krw:r.current,'현재');
    let forecast=finite(old?r.p50_krw:r.forecast,'예측');
    if(semantics==='future_only')forecast=forecast==null||current==null?null:forecast+current;
    return {id,label,fullLabel:String(r.label||label),budget:finite(old?r.budget_krw:r.budget,'예산',{negative:false}),current,forecast};
  });
  if(categories.length>70)throw new TypeError('한 카드에는 최대 70개 봉투를 전달하세요.');
  const sum = key=>categories.length&&categories.every(r=>r[key]!=null)?categories.reduce((s,r)=>s+r[key],0):null;
  const unallocatedCurrent=finite(old?e.unallocated_current_krw:e.unallocatedCurrent,'미분류 현재 소비');
  let totalBudget=finite(old?e.total_budget_krw:e.totalBudget,'총예산',{negative:false});
  let totalCurrent=finite(old?e.total_current_krw:e.totalCurrent,'총현재');
  let totalForecast=finite(old?e.total_future_p50_krw:e.totalForecast,'총예측');
  // Budget and current are additive. P50 of a joint path is not the sum of marginal P50s.
  if(totalBudget==null)totalBudget=sum('budget');
  if(totalCurrent==null){const currentSum=sum('current');totalCurrent=currentSum==null?null:currentSum+(unallocatedCurrent??0);}
  if(semantics==='future_only')totalForecast=totalForecast==null||totalCurrent==null?null:totalForecast+totalCurrent;
  if(!old&&totalForecast==null&&input.forecastAggregation==='sum')totalForecast=sum('forecast');
  for(const [key,total] of [['budget',totalBudget],['current',totalCurrent]]){
    const s=sum(key),expected=key==='current'&&s!=null?s+(unallocatedCurrent??0):s;
    if(expected!=null&&total!=null&&Math.abs(expected-total)>.02)throw new TypeError(key+' 합계와 전체 수치가 다릅니다.');
  }
  const meta=budgetPeriod(input.meta||{});
  const normalized={schema_version:'2.0',id:String(input.id||'result'),question:String(input.question||''),answer:String(input.answer||''),
    value_semantics:'period_total',totalBudget,totalCurrent,totalForecast,unallocatedCurrent,categories,meta,
    balance:input.balance||null,source:old?input.meta.provenance:(input.source||'demo'),
    sourceSemantics:semantics,forecastAggregation:input.forecastAggregation||'joint_p50',
    unavailable:old&&!['ok','partial'].includes(input.status)};
  return normalized;
}
function colors(style) {
  style={...DEFAULT_STYLE,...style};
  const c={};for(const k of ['bg','mint','yellow','pink','track','current','forecast','forecastLine'])c[k]=`rgb(${Math.round(style[k+'R'])},${Math.round(style[k+'G'])},${Math.round(style[k+'B'])})`;
  return c;
}
function state(value,budget){if(value==null||budget==null)return 'unknown';if(budget===0)return value>0?'pink':'unknown';return value/budget>1?'pink':value/budget>.7?'yellow':'mint';}
function model(input,style={},options={}) {
  const d=normalize(input),s={...DEFAULT_STYLE,...style};
  const scaling=options.scale||'reference';if(!['reference','linear'].includes(scaling))throw new TypeError('scale은 reference 또는 linear입니다.');
  const ratios=d.categories.flatMap(r=>[r.current,r.forecast].filter(v=>v!=null&&r.budget>0).map(v=>v/r.budget));
  let maxRatio=scaling==='linear'?Math.max(1,...ratios):1;
  let minRatio=scaling==='linear'?Math.min(0,...ratios):0;
  if(maxRatio===minRatio)maxRatio=minRatio+1;
  const trackLeft=s.padX+82,trackWidth=363-s.padX-trackLeft-40,rowHeight=30,barHeight=14;
  const xRatio = v=>trackLeft+(clamp(v,minRatio,maxRatio)-minRatio)/(maxRatio-minRatio)*trackWidth;
  const rows=d.categories.map((r,i)=>{
    const baseline=xRatio(0),trackTop=s.barTop+i*rowHeight;
    function geometry(value){
      if(value==null||r.budget==null||r.budget===0)return null;
      const ratio=value/r.budget,x=xRatio(ratio);
      return {value,ratio,percent:ratio*100,x:Math.min(x,baseline),y:trackTop,endpoint:x,width:Math.abs(x-baseline),height:barHeight,baseline,clipped:ratio<minRatio||ratio>maxRatio};
    }
    return {...r,index:i,row:i,x:trackLeft,trackTop,baseline,currentBar:geometry(r.current),forecastBar:geometry(r.forecast)};
  });
  const remain=d.totalBudget!=null&&d.totalCurrent!=null?d.totalBudget-d.totalCurrent:null;
  const forecastRemain=d.totalBudget!=null&&d.totalForecast!=null?d.totalBudget-d.totalForecast:null;
  return {data:d,style:s,rows,maxRatio,minRatio,scaling,trackLeft,trackWidth,rowHeight,barHeight,xRatio,height:s.barTop+Math.max(1,rows.length)*rowHeight+12,remaining:remain,forecastRemaining:forecastRemain};
}
function cardSvg(input,style={},options={}) {
  const m=model(input,style,options),{style:s,data:d,rows,height:H}=m,c=colors(s),uid='kf'+(++seq);
  const currentOnly=options.currentOnly===true,labelMode=options.labelMode||'current';
  const consumption=d.balance?.kind==='cumulative_expense'&&!currentOnly;
  const font=FONTS[clamp(Math.round(s.fontIndex),0,FONTS.length-1)],nf=NFONTS[clamp(Math.round(s.numberFontIndex),0,NFONTS.length-1)];
  const txt=(x,y,text,size,weight=400,fill='#fff',anchor='start',extra='')=>`<text x="${round(x)}" y="${round(y)}" font-size="${round(size)}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" ${extra}>${esc(text)}</text>`;
  const r=s.radius,br=s.bottomRadius;
  let svg=`<svg xmlns="http://www.w3.org/2000/svg" class="kf-budget-svg" viewBox="0 0 363 ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="항목별 사용률. 카테고리별 색상에서 진한 바는 현재 소비, 같은 색의 반투명 바와 점선은 기간 말 예상 총소비." style="display:block;width:100%;height:auto;font-family:${esc(font)};letter-spacing:${s.letterSpacing}px"><title>현재·미래 예측을 같은 0 기준점에서 겹칩니다. 합산 막대가 아닙니다.</title><defs><linearGradient id="${uid}-fade" x1="0" y1="0" x2="0" y2="1"><stop offset="85%" stop-color="#fff" stop-opacity="0"/><stop offset="100%" stop-color="#fff" stop-opacity="${s.fadeBottom}"/></linearGradient></defs>`;
  const shape=`M ${r} .5 H ${363-r} Q 362.5 .5 362.5 ${r} V ${H-br} Q 362.5 ${H-.5} ${363-br} ${H-.5} H ${br} Q .5 ${H-.5} .5 ${H-br} V ${r} Q .5 .5 ${r} .5 Z`;
  svg+=`<path class="card-surface" d="${shape}" fill="${c.bg}"/><path d="${shape}" fill="url(#${uid}-fade)"/>`;
  const warn=consumption?(d.source.startsWith('synthetic')?'합성 예시':'종료일 예측'):m.remaining==null?'확인 필요':m.remaining<0?'초과했어요':d.totalBudget>0&&m.remaining/d.totalBudget<.3?'주의해요':'좋아요!';
  const warnColor=m.remaining!=null&&m.remaining<0?c.pink:warn==='주의해요'?c.yellow:c.mint;
  svg+=txt(s.padX,s.titleY,consumption?(d.meta.headline||'기간 말 예상 소비'):(d.meta.period_start?'이번 예산 남은 금액':'이번 달 남은 예산'),s.titleSize,s.titleWeight);
  svg+=txt(363-s.padX,s.statusY,warn,s.statusSize,500,warnColor,'end');
  if(d.meta.period_start)svg+=txt(s.padX,s.titleY+19,d.meta.period_range,10,400,'#fff','start','class="budget-period" opacity=".9"');
  const amount=consumption?d.totalForecast:m.remaining,number=money(amount),amountSize=Math.min(s.amountSize,(317/Math.max(number.length*.58,1)));
  svg+=txt(s.padX,s.amountY,number,amountSize,s.amountWeight,'#fff','start',`class="remaining-number" data-value="${amount??''}" style="font-family:${esc(nf)};letter-spacing:${s.amountSpacing}px"`);
  const subtitle=consumption?`${d.meta.period_label||'기간 말 누적'} · 예산 ${money(d.totalBudget)} 대비 ${pct(d.totalBudget>0&&d.totalForecast!=null?d.totalForecast/d.totalBudget*100:null)}`:`총 예산 ${money(d.totalBudget)} 중 ${money(d.totalCurrent)} 사용`;
  svg+=txt(s.padX,s.subtitleY,subtitle,Math.min(s.subtitleSize,318/Math.max(subtitle.length*.7,1)),400,'#fff','start',`opacity="${s.mutedAlpha}"`);
  const pw=363-s.padX*2,py=s.progressY,ph=s.progressH,progress=d.totalBudget>0&&d.totalCurrent!=null?clamp(d.totalCurrent/d.totalBudget,0,1):0;
  svg+=`<rect class="progress-track" x="${s.padX}" y="${py}" width="${pw}" height="${ph}" rx="${ph/2}" fill="${c.track}"/>`;
  const future=d.totalBudget>0&&d.totalForecast!=null?clamp(d.totalForecast/d.totalBudget,0,1):0;
  if(!currentOnly)svg+=`<rect class="progress-forecast" x="${s.padX}" y="${py}" width="${pw*future}" height="${ph}" rx="${ph/2}" fill="${c.mint}" fill-opacity="0.4" data-value="${d.totalForecast??''}" data-ratio="${future}"/>`;
  svg+=`<rect class="progress-current" x="${s.padX}" y="${py}" width="${pw*progress}" height="${ph}" rx="${ph/2}" fill="${c.mint}" fill-opacity="1" data-value="${d.totalCurrent??''}" data-ratio="${progress}"/>`;
  if(!currentOnly&&d.totalBudget>0&&d.totalForecast!=null)svg+=`<line class="progress-forecast-cap" x1="${s.padX+pw*future}" x2="${s.padX+pw*future}" y1="${py-1}" y2="${py+ph+1}" stroke="${c.mint}" stroke-width="1.5" stroke-dasharray="2 2"/>`;
  const totalLabel=(value)=>money(value)+' ('+pct(d.totalBudget>0&&value!=null?value/d.totalBudget*100:null)+')';
  svg+=txt(s.padX,py+ph+13,'현재 '+totalLabel(d.totalCurrent),8.5);
  if(!currentOnly)svg+=txt(363-s.padX,py+ph+13,'예상 '+totalLabel(d.totalForecast),8.5,400,'#fff','end');
  svg+=txt(s.padX,s.headingY,'항목별 사용률',s.headingSize,500);
  const step=m.maxRatio-m.minRatio<=1.4?.2:(m.maxRatio-m.minRatio)/4;
  const ticks=[m.minRatio,m.maxRatio,1];
  for(let v=m.minRatio+step;v<m.maxRatio-.001;v+=step)if(Math.abs(v-1)>step*.4)ticks.push(v);
  for(const v of [...new Set(ticks.map(round))].sort((a,b)=>a-b))svg+=txt(m.xRatio(v),s.barTop-12,pct(v*100),9,400,'#fff','middle','class="usage-tick"');
  for(const r of rows){
    const bw=m.trackWidth,by=r.trackTop,bh=m.barHeight,rad=bh/2,cid=uid+'-'+r.index,color=categoryColors[r.index%categoryColors.length];
    const v=labelMode==='forecast'&&!currentOnly?r.forecast:r.current;
    const ratio=v==null||r.budget<=0||r.budget==null?null:v/r.budget*100;
    const label=r.budget===0?(v>0?'무예산':'—'):pct(ratio);
    const tip=`${r.fullLabel}\n현재 ${money(r.current)}${r.currentBar?' ('+pct(r.currentBar.percent)+')':''}\n기간 말 예측 ${money(r.forecast)}${r.forecastBar?' ('+pct(r.forecastBar.percent)+')':''}\n예산 ${money(r.budget)}${(r.currentBar?.clipped||r.forecastBar?.clipped)&&m.scaling==='reference'?'\n길이는 0~100% 범위로 제한합니다. 원래 값은 수치로 표시합니다.':''}`;
    svg+=`<g class="kf-bar" tabindex="0" role="button" data-id="${esc(r.id)}" aria-label="${esc(tip)}"><title>${esc(tip)}</title><rect x="${s.padX}" y="${by-8}" width="${363-s.padX*2}" height="${m.rowHeight}" fill="transparent"/><defs><clipPath id="${cid}"><rect x="${r.x}" y="${by}" width="${bw}" height="${bh}" rx="${rad}"/></clipPath></defs>`;
    svg+=`<rect class="budget-track" x="${r.x}" y="${by}" width="${bw}" height="${bh}" rx="${rad}" fill="${c.track}" fill-opacity=".18"/>`;
    const draw=(g,cls,alpha)=>{
      if(!g)return '';
      return `<rect class="${cls}" data-value="${g.value}" data-ratio="${g.ratio}" data-clipped="${g.clipped}" x="${g.x}" y="${g.y}" width="${g.width}" height="${bh}" rx="${Math.min(rad,g.width/2)}" fill="${color}" fill-opacity="${alpha}" clip-path="url(#${cid})"/>`;
    };
    if(!currentOnly)svg+=draw(r.forecastBar,'forecast-bar',.4);
    svg+=draw(r.currentBar,'current-bar',1);
    if(!currentOnly&&r.forecastBar){
      svg+=`<line class="forecast-cap" x1="${r.forecastBar.endpoint}" x2="${r.forecastBar.endpoint}" y1="${by+2}" y2="${by+bh-2}" stroke="${color}" stroke-width="1.6" stroke-dasharray="2 2"/>`;
    }
    if(m.minRatio<0)svg+=`<line class="zero-line" x1="${r.baseline}" x2="${r.baseline}" y1="${by-3}" y2="${by+bh+3}" stroke="#fff" stroke-width="1"/>`;
    svg+=txt(363-s.padX,by+bh/2+4,label,Math.min(s.labelSize,36/Math.max(label.length*.55,1)),s.labelWeight,'#fff','end',`class="bar-value" style="font-family:${esc(nf)}"`);
    const short=r.label.length>7?r.label.slice(0,6)+'…':r.label;
    svg+=txt(s.padX,by+bh/2+4,short,Math.min(s.categorySize,76/Math.max(short.length,1)),400,'#fff','start',`class="bar-label" opacity=".96"`);
    svg+='</g>';
  }
  if(rows.length)svg+=`<line class="budget-limit" x1="${m.xRatio(1)}" x2="${m.xRatio(1)}" y1="${s.barTop-4}" y2="${rows.at(-1).trackTop+m.barHeight+4}" stroke="#fff" stroke-width="1" stroke-dasharray="3 3" pointer-events="none"><title>예산 100%</title></line>`;
  if(!rows.length)svg+=txt(181.5,s.barTop+16,'봉투별 수치가 없습니다.',13,400,'#fff','middle');
  svg+='</svg>';return svg;
}
function mount(root,input,options={}) {
  if(!root||typeof root.innerHTML!=='string')throw new TypeError('HTML 요소가 필요합니다.');
  let payload=normalize(input),style=options.style||global.KEYFIN_STYLE||DEFAULT_STYLE;
  const render=()=>{
    root.innerHTML=cardSvg(payload,style,options);root.__keyfinModel=model(payload,style,options);
    const disclose=e=>{let g=e.target.closest('.kf-bar');if(g&&options.onSelect){const row=payload.categories.find(r=>r.id===g.dataset.id);options.onSelect(row);}};
    root.onclick=disclose;root.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();disclose(e);}};
  };render();
  return {update(next){payload=normalize(next);render();return payload;},setOptions(next){Object.assign(options,next);render();},getData(){return structuredClone(payload);},destroy(){root.innerHTML='';root.onclick=null;root.onkeydown=null;}};
}
const api={categoryColors,DEFAULT_STYLE,FONTS,NFONTS,colors,normalize,model,cardSvg,mount,state,fmt,money,pct,KIND,budgetPeriod,day,validDate,version:'2.0.0'};
if(typeof module!=='undefined'&&module.exports)module.exports=api;global.KeyFinChart=api;
})(typeof window!=='undefined'?window:globalThis);
