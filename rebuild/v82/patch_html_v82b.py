# -*- coding: utf-8 -*-
"""v8.2 HTML patch 第二批：全网比对与放弃审计重构（第5点）+ 分类筛选（第9点）"""
import re

P = '/workspace/cailianshe-dashboard/index.html'
html = open(P, encoding='utf-8').read()
orig_len = len(html)
n_ok = 0


def rep(old, new, cnt=1, tag=''):
    global html, n_ok
    if old not in html:
        raise SystemExit('!! 未找到锚点: ' + (tag or old[:60]))
    html = html.replace(old, new, cnt)
    n_ok += 1
    print('[ok]', tag or old[:50].replace('\n', ' '))


# ============================================================
# 6. 全网比对与放弃审计 section 重构（第 5 点）
#    - 只保留「待比对」「已放弃」两栏（已入池股票不再冗余出现）
#    - 两区均支持全部收起
#    - 超过 10 个交易日的待比对股票：连同期次备查与说明信息彻底抹除
# ============================================================
rep("""<section id="wcSection"><h2>全网比对与放弃审计 <span class="cnt" id="wcCntT">0</span> 条 <span class="sub">铁律③：摘要匿名的线索由 AI 拿公告特征比对全网公开信源 · 匹配上入池 / 匹配度高进候选池 / 匹配不上<b style="color:#f06a6a">宁缺毋滥放弃</b>（放弃全程留痕可复盘）</span></h2>
<div class="legend" id="wcLegend">
<span class="lg-all on" data-st="all" onclick="wcFilter('all',this)">全部</span>
<span class="lg-cand-exp" data-st="pending" onclick="wcFilter('pending',this)">⏳ 待比对</span>
<span class="lg-ok" data-st="pool" onclick="wcFilter('pool',this)">✅ 已确认入池</span>
<span class="lg-no" data-st="abandon" onclick="wcFilter('abandon',this)">🗑 已放弃（宁缺毋滥）</span>
</div>
<div class="stocks-grid" id="wcBox"></div>
<div id="abandBox"></div></section>""",
"""<section id="wcSection"><h2>全网比对与放弃审计 <span class="cnt" id="wcCntT">0</span> 条 <span class="sub">铁律③：摘要匿名的线索由 AI 拿公告特征比对全网公开信源 · 匹配上入池 / 匹配度高进候选池 / 匹配不上<b style="color:#f06a6a">宁缺毋滥放弃</b>（放弃全程留痕可复盘）· 已确认入池的股票不在此重复出现</span></h2>
<div class="legend" id="wcLegend">
<span class="lg-all on" data-st="all" onclick="wcFilter('all',this)">全部</span>
<span class="lg-cand-exp" data-st="pending" onclick="wcFilter('pending',this)">⏳ 待比对</span>
<span class="lg-no" data-st="abandon" onclick="wcFilter('abandon',this)">🗑 已放弃（宁缺毋滥）</span>
</div>
<div class="fold-bar" style="margin-bottom:10px">
<button class="fold-btn" onclick="expandAll('#wcBox details')">一键展开</button>
<button class="fold-btn ghost" onclick="collapseAll('#wcBox details')">全部收起</button>
<button class="fold-btn ghost" onclick="collapseAll('#abandBox details')">放弃审计区全部收起</button>
<span class="fold-info">⏳ 待比对满 10 个交易日仍未确认 → 第 11 个交易日连同期次备查与说明信息<b style="color:#f06a6a">从看板彻底抹除</b></span>
</div>
<div id="wcBox"></div>
<div id="abandBox"></div></section>""",
    tag='wcSection 重构（两栏+全部收起+超期抹除说明）')

# ============================================================
# 7. renderWebcheck 重写：pool 状态不再展示；待比对超期自动抹除；放弃审计区可折叠
# ============================================================
old_wc = html[html.index("function wcCardHtml(x){"):html.index("function renderStatic(){")]
new_wc = """function wcCardHtml(x){
 // v8.2：全网比对区只呈现「待比对」与「已放弃」两类；已确认入池（pool）不再冗余出现。
 // 待比对满 10 个交易日未确认 → 第 11 个交易日起连同其期次备查与说明信息从看板彻底抹除（铁律⑤-4）。
 var td=tdIndex(x);
 var expired=td>=10;
 var st=x.status==='abandon'?'abandon':'pending';
 var m={pool:{c:'ok',t:'✅ 已确认入池'},abandon:{c:'no',t:'🗑 已放弃（宁缺毋滥）'},pending:{c:'wait',t:'⏳ 待比对'}}[st]||{c:'wait',t:'⏳ 待比对'};
 if(expired)return '';   // 超期项：彻底抹除，不留卡片
 return '<details class="stock-card wc-card" data-st="'+esc(st)+'" data-aid="'+esc(x.aid)+'"><summary>'+
 '<div class="head"><span class="nm">'+esc(x.column)+'</span><span class="wc-badge '+m.c+'">'+m.t+'</span></div>'+
 '<div class="blk t1"><b class="lbl">'+esc(x.dateIn)+' 入队 · 第 '+td+' 个交易日 · 来源文章 '+esc(x.aid)+' · '+esc(x.beans)+' 微信豆</b>'+esc(x.title)+'</div></summary>'+
 '<div class="blk"><b class="lbl">摘要线索</b>'+esc(x.bullet)+'</div>'+
 '<div class="blk"><b class="lbl">全网比对结论</b>'+esc(x.verdict||'')+
 (x.resolvedTo?'<div class="wc-resolved">→ 确认标的：'+esc(x.resolvedTo)+'</div>':'')+
 '</div>'+
 (td>=8&&st==='pending'?'<div class="cand-expiry">⚠ 待比对已 '+td+' 个交易日，满 10 个交易日仍未确认将连同期次备查与说明信息彻底抹除</div>':'')+
 '</details>';
}
function renderWebcheck(){
 var box=document.getElementById('wcBox');if(!box)return;
 var arr=(D.webcheck||[]).slice();
 // v8.2：过滤规则——① 不展示已确认入池（pool）条目；② 待比对超期（≥10 个交易日）的条目连同
 // 期次备查与说明信息彻底抹除（先从内存数据中删除，保证图表/统计/计数同步剔除）。
 var before=arr.length;
 arr=arr.filter(function(x){return x.status!=='pool';});
 var expired=arr.filter(function(x){return x.status==='pending'&&tdIndex(x)>=10;});
 if(expired.length){
  var expCodes={},expAids={};
  expired.forEach(function(x){if(x.code)expCodes[x.code]=1;if(x.aid)expAids[x.aid]=1;});
  arr=arr.filter(function(x){return !(x.status==='pending'&&tdIndex(x)>=10);});
  D.webcheck=(D.webcheck||[]).filter(function(x){return !(x.status==='pool'||(x.status==='pending'&&tdIndex(x)>=10));});
  // 期次备查与说明信息：抹除超期股票标识，不留残迹
  (D.batches||[]).forEach(function(b){
   (b.items||[]).forEach(function(it){
    if(it.scode&&expCodes[it.scode]){it.stock='';it.scode='';it.purged=true;}
   });
  });
 }
 setCnt('wcCntT',arr.length);
 var ord={pending:0,abandon:1};
 arr.sort(function(a,b){var dd=(ord[a.status]||3)-(ord[b.status]||3);return dd||(a.dateIn<b.dateIn?1:-1);});
 var show=WC_FILTER==='all'?arr:arr.filter(function(x){return x.status===WC_FILTER;});
 box.innerHTML=show.length?show.map(wcCardHtml).join(''):'<div class="fav-empty">当前过滤条件下无比对记录。</div>';
 if(expired.length){
  var eb=document.createElement('div');
  eb.className='fav-empty';eb.style.marginTop='8px';
  eb.innerHTML='🗑 本次已按铁律彻底抹除 <b style="color:#f06a6a">'+expired.length+'</b> 条满 10 个交易日仍未确认的待比对线索（期次备查与说明信息同步清除）。';
  box.appendChild(eb);
 }
 var ab=document.getElementById('abandBox');
 if(ab){
  var aa=(D.abandoned||[]).slice().sort(function(a,b){return a.dateIn<b.dateIn?1:-1;});
  ab.innerHTML=aa.length?'<div class="aband-title">🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（共 '+aa.length+' 条）</div>'+aa.map(function(x){
  return '<details class="aband-item"><summary><b>'+esc(x.match||x.name)+'</b>'+(x.code?' · '+esc(x.code):'')+'<span class="aband-aid">'+(x.column?esc(x.column)+' · ':'')+'文章 '+esc(x.aid)+' · '+esc(x.dateIn)+'</span></summary><div class="aband-reason">放弃原因：'+esc(x.reason)+'</div></details>';
  }).join(''):'<div class="fav-empty">已放弃审计区暂无记录。匹配不上或笼统无锚点的线索将在此全程留痕，供事后复盘筛选质量。</div>';
 }
}
"""
html = html.replace(old_wc, new_wc, 1)
n_ok += 1
print('[ok] renderWebcheck 重写（pool 不展示 + 超期彻底抹除 + 放弃审计区可折叠）')

open(P, 'w', encoding='utf-8').write(html)
print()
print('完成 %d 处替换，长度 %d → %d' % (n_ok, orig_len, len(html)))
