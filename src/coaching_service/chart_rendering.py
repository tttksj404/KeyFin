"""Render the pinned KeyFin template without generated code or remote dependencies."""

import hashlib
import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel

from coaching_service.chart_contract import ChartResult
from coaching_service.errors import ServiceError

_PRESENTATION = r"""
<style>
h1,.intro,.helper,.result-note,.flow-range,.bottom-note,.day-detail,.source{
 word-break:keep-all;overflow-wrap:break-word}
.chart-brief{font-size:14px;line-height:1.8;word-break:keep-all;margin:16px 0}
.chart-date{white-space:nowrap}
.chart-quality{margin:16px 0;padding:14px 18px;border:1px solid #e6e1f3;
 border-radius:12px;background:#faf9fd;font-size:12px;line-height:1.8;word-break:keep-all;
 overflow-wrap:break-word}
.chart-quality p{margin:0;font-weight:600}.chart-quality ul{margin:6px 0 0;padding-left:18px}
/* 좁은 카드에서도 원 단위 금액을 축약하거나 통화 단위만 다음 줄로 보내지 않는다. */
.asset-value{font-size:clamp(20px,6vw,30px);white-space:nowrap}
@media(max-width:360px){h1{font-size:21px}}
</style><script>
(()=>{
 const brief=document.createElement('p');brief.id='chart-explanation';brief.className='chart-brief';
 brief.setAttribute('aria-label','차트 해설');document.querySelector('#as-of').after(brief);
 const quality=document.createElement('section');quality.id='chart-quality';
 quality.className='chart-quality';quality.setAttribute('aria-label','계산에 사용한 자료');
 brief.after(quality);
 function showQuality(d){
  quality.replaceChildren();
  const notices=d.meta.quality?.notices||[
   '이 저장 결과에는 자료 점검 요약이 없습니다. 새 요청으로 다시 계산해 주세요.'];
  quality.hidden=!notices.length;
  if(!notices.length)return;
  const title=document.createElement('p');title.textContent='계산에 사용한 자료';quality.append(title);
  const list=document.createElement('ul');
  for(const text of notices){const item=document.createElement('li');item.textContent=text;list.append(item);}
  quality.append(list);
 }
 function explain(text){
  brief.replaceChildren();
  for(const part of text.split(/(\d{4}-\d{2}-\d{2})/)){
   if(/^\d{4}-\d{2}-\d{2}$/.test(part)){
    const span=document.createElement('span');span.className='chart-date';span.textContent=part;
    brief.append(span);
   }else brief.append(document.createTextNode(part));
  }
 }
 function observedLabel(text){
  return text.replaceAll('예산 기간 예상 소비','예산 기간 기록 소비')
   .replaceAll('기간 말 예상 총소비','기간 총소비').replaceAll('기간 말 예측','기간 총소비')
   .replaceAll('기간 말 예상','기간 총소비').replaceAll('종료일 예측','종료일 기록')
   .replaceAll('예상 사용률','기록 기준 사용률').replace(/^예상 /,'기간 총소비 ');
 }
 function selected(){
  if(window.PREVIEW_DATA.meta.status==='observed_period_complete'){
   const node=document.querySelector('#selection');node.textContent=observedLabel(node.textContent);
  }
 }
 function spaceTicks(){
  const ticks=[...document.querySelectorAll('#budget .usage-tick')],kept=[];
  const priority=node=>node.textContent==='100%'?0:node.textContent==='0%'?1:2;
  ticks.sort((a,b)=>priority(a)-priority(b));
  for(const node of ticks){
   node.style.visibility='visible';node.removeAttribute('aria-hidden');
   const box=node.getBBox();
   if(kept.some(other=>box.x<other.x+other.width+3&&box.x+box.width+3>other.x)){
    node.style.visibility='hidden';node.setAttribute('aria-hidden','true');
   }else kept.push(box);
  }
 }
 function update(){
  brief.hidden=!document.querySelector('#error').classList.contains('hidden');
  quality.hidden=brief.hidden;
  if(brief.hidden)return;
  const d=window.PREVIEW_DATA;explain(d.answer);spaceTicks();showQuality(d);
  if(d.meta.observation_start){
   const short=value=>value.slice(5).replace('-','/');
   document.querySelector('#actual-range').textContent=
    '입력 기록 '+short(d.meta.observation_start)+' ~ '+short(d.meta.as_of);
  }
  if(d.unallocatedCurrent>0){
   const row=document.createElement('tr');row.id='unallocated-row';
   const terminal=d.meta.status==='observed_period_complete'?KeyFinChart.fmt(d.unallocatedCurrent):'—';
   const values=['미분류 (전체에 포함)','—',KeyFinChart.fmt(d.unallocatedCurrent),
    terminal,'—','항목별 막대에서 제외'];
   for(const value of values){
    const cell=document.createElement('td');cell.textContent=value;row.append(cell);
   }
   document.querySelector('#total').prepend(row);
  }
  const over=d.categories.filter(r=>r.forecast!=null&&r.budget!=null&&r.forecast>r.budget);
  if(over.length)document.querySelector('#result-note').textContent=over.map(
   r=>r.label+': '+KeyFinChart.money(r.forecast-r.budget)+' 초과 예상').join(' · ');
  if(d.meta.status==='observed_period_complete'){
   document.title='KeyFin · 예산 기간별 소비 기록';
   document.querySelector('h1').textContent='내 예산 시작일에 맞춘 소비 기록';
   document.querySelectorAll('#budget text,#budget title,.small-label,.table-section th').forEach(
    node=>{node.textContent=observedLabel(node.textContent);});
   document.querySelectorAll('#budget [aria-label]').forEach(
    node=>node.setAttribute('aria-label',observedLabel(node.getAttribute('aria-label'))));
   document.querySelector('#budget svg title').textContent=
    '관측 소비와 기간 총소비는 같은 값입니다. 합산 막대가 아닙니다.';
   document.querySelector('#budget-legend span:last-child').textContent='기간 동안 기록된 총금액';
   document.querySelector('.preview .helper').textContent=
    '기간이 종료되어 두 막대는 같은 관측 금액입니다. '+
    '막대 오른쪽 숫자는 기록 기준 사용률 · 흰 점선은 예산 100%';
   document.querySelector('.table-section h2').textContent='카테고리별 소비 기록';
   document.querySelector('.bottom-note').lastChild.textContent=
    '현재 소비와 기간 총소비는 모두 위 예산 기간에 속한 관측 금액입니다.';
   document.querySelector('#forecast-range').textContent='추가 예측 없음 · 관측 기간 종료';
   document.querySelector('#flow svg').setAttribute('aria-label',
    d.meta.period_range+' 누적 소비 관측 기록');
   document.querySelector('#daily svg').setAttribute('aria-label',
    d.meta.period_range+' 일별 소비 관측 기록과 카테고리 구성');
   const remain=d.totalBudget==null?null:d.totalBudget-d.totalCurrent;
   document.querySelector('#flow-range').textContent=
    '기간 예산 '+KeyFinChart.money(d.totalBudget)+' · '+d.meta.horizon_end+' 종료 기록 · '+
    (remain==null?'남은 예산 정보 없음':KeyFinChart.money(Math.abs(remain))+(remain<0?' 초과':' 남음'));
   if(over.length)document.querySelector('#result-note').textContent=over.map(
    r=>r.label+': '+KeyFinChart.money(r.forecast-r.budget)+' 초과').join(' · ');
  }
  if(d.totalBudget==null&&d.categories.some(row=>row.budget!=null)){
   document.querySelectorAll('#budget text').forEach(node=>{
    node.textContent=node.textContent.replace('예산 정보 없음 대비 —','전체 예산 확인 필요');
   });
   const range=document.querySelector('#flow-range');
   range.textContent=range.textContent.replace('기간 예산 정보 없음',
    '일부 항목만 예산 입력 · 전체 합계 확인 필요');
  }
 }
 document.querySelector('#budget').addEventListener('click',selected);
 document.querySelector('#budget').addEventListener('keydown',selected);
 document.querySelector('#case').addEventListener('change',update);update();
 document.fonts.ready.then(spaceTicks);
})();
</script>
"""


class RendererManifest(BaseModel):
    commit: str
    files: dict[str, str]


@lru_cache(maxsize=1)
def renderer_manifest() -> RendererManifest:
    packaged = files("coaching_service").joinpath("chart_manifest.json")
    content = (
        packaged.read_text(encoding="utf-8")
        if packaged.is_file()
        else (Path(__file__).resolve().parents[2] / "CHART_MANIFEST.json").read_text(encoding="utf-8")
    )
    return RendererManifest.model_validate_json(content)


@lru_cache(maxsize=6)
def asset(name: str) -> str:
    expected = renderer_manifest().files.get(name)
    if expected is None:
        raise ServiceError("unknown_chart_asset", 500)
    packaged = files("coaching_service").joinpath("chart_assets", name)
    content = (
        packaged.read_bytes()
        if packaged.is_file()
        else (Path(__file__).resolve().parents[2] / "vendor" / "keyfin_chart" / name).read_bytes()
    )
    if hashlib.sha256(content).hexdigest() != expected:
        raise ServiceError("chart_asset_integrity_mismatch", 500)
    return content.decode("utf-8")


def render_chart(chart: ChartResult) -> str:
    page = asset("forecast-template.html")
    for token, name in (("CSS", "demo.css"), ("CHART", "keyfin-chart.js"), ("FLOW", "keyfin-flow.js")):
        page = page.replace("/*" + token + "*/", asset(name))
    style = json.dumps(json.loads(asset("design-tokens.json")), ensure_ascii=False).replace("<", "\\u003c")
    payload = chart.model_dump_json(by_alias=True, exclude_unset=True).replace("<", "\\u003c")
    return page.replace(
        "/*DATA*/", "window.KEYFIN_STYLE=" + style + ";window.KEYFIN_CASES=[" + payload + "];"
    ).replace("</body>", _PRESENTATION + "</body>")
