# -*- coding: utf-8 -*-
"""v8.2 修正：全网比对区去重——待比对走 wcBox，已放弃走 abandBox，不重复展示"""
P = '/workspace/cailianshe-dashboard/index.html'
html = open(P, encoding='utf-8').read()
n_ok = 0


def rep(old, new, cnt=1, tag=''):
    global html, n_ok
    if old not in html:
        raise SystemExit('!! 未找到锚点: ' + (tag or old[:60]))
    html = html.replace(old, new, cnt)
    n_ok += 1
    print('[ok]', tag or old[:50].replace('\n', ' '))


# wcFilter：abandon 筛选时隐藏 wcBox，pending 筛选时隐藏 abandBox
rep("""window.wcFilter=function(st,el){
WC_FILTER=st||'all';
document.querySelectorAll('#wcLegend span').forEach(function(s){s.classList.toggle('on',s.getAttribute('data-st')===WC_FILTER);});
if(typeof window.renderWebcheck==='function')window.renderWebcheck();
};""",
"""window.wcFilter=function(st,el){
WC_FILTER=st||'all';
document.querySelectorAll('#wcLegend span').forEach(function(s){s.classList.toggle('on',s.getAttribute('data-st')===WC_FILTER);});
var wb=document.getElementById('wcBox'),ab=document.getElementById('abandBox');
// v8.2：两栏分工——wcBox 只放「待比对」，abandBox 只放「已放弃」，筛选按栏位开关
if(wb)wb.style.display=(WC_FILTER==='abandon')?'none':'';
if(ab)ab.style.display=(WC_FILTER==='pending')?'none':'';
if(typeof window.renderWebcheck==='function')window.renderWebcheck();
};""",
    tag='wcFilter 栏位开关')

# renderWebcheck：arr 只保留 pending；计数 = pending + abandoned
rep("""function renderWebcheck(){
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
 box.innerHTML=show.length?show.map(wcCardHtml).join(''):'<div class="fav-empty">当前过滤条件下无比对记录。</div>';""",
"""function renderWebcheck(){
 var box=document.getElementById('wcBox');if(!box)return;
 // v8.2 两栏分工：① wcBox 只放「待比对」（webcheck·pending）；② abandBox 只放「已放弃」
 // （abandoned 审计区，含放弃原因全文）。已确认入池（pool）不再冗余出现。
 var arr=(D.webcheck||[]).filter(function(x){return x.status==='pending';});
 var abN=(D.abandoned||[]).length;
 // 待比对超期（≥10 个交易日）→ 连同期次备查与说明信息彻底抹除
 var expired=arr.filter(function(x){return tdIndex(x)>=10;});
 if(expired.length){
  var expCodes={};
  expired.forEach(function(x){if(x.code)expCodes[x.code]=1;});
  arr=arr.filter(function(x){return tdIndex(x)<10;});
  D.webcheck=(D.webcheck||[]).filter(function(x){return !(x.status==='pending'&&tdIndex(x)>=10);});
  (D.batches||[]).forEach(function(b){
   (b.items||[]).forEach(function(it){
    if(it.scode&&expCodes[it.scode]){it.stock='';it.scode='';it.purged=true;}
   });
  });
 }
 setCnt('wcCntT',arr.length+abN);
 arr.sort(function(a,b){return a.dateIn<b.dateIn?1:-1;});
 var show=WC_FILTER==='abandon'?[]:arr;
 box.innerHTML=show.length?show.map(wcCardHtml).join(''):(WC_FILTER==='abandon'?'':'<div class="fav-empty">当前没有待比对线索。摘要匿名且唯一锚点经全网比对未确认的股票会暂存于此，满 10 个交易日仍未确认将彻底抹除。</div>');""",
    tag='renderWebcheck 两栏分工去重')

# abandBox 渲染时尊重筛选开关
rep(""" var ab=document.getElementById('abandBox');
 if(ab){
  var aa=(D.abandoned||[]).slice().sort(function(a,b){return a.dateIn<b.dateIn?1:-1;});
  ab.innerHTML=aa.length?'<div class="aband-title">🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（共 '+aa.length+' 条）</div>'+aa.map(function(x){
  return '<details class="aband-item"><summary><b>'+esc(x.match||x.name)+'</b>'+(x.code?' · '+esc(x.code):'')+'<span class="aband-aid">'+(x.column?esc(x.column)+' · ':'')+'文章 '+esc(x.aid)+' · '+esc(x.dateIn)+'</span></summary><div class="aband-reason">放弃原因：'+esc(x.reason)+'</div></details>';
  }).join(''):'<div class="fav-empty">已放弃审计区暂无记录。匹配不上或笼统无锚点的线索将在此全程留痕，供事后复盘筛选质量。</div>';
 }
}""",
""" var ab=document.getElementById('abandBox');
 if(ab){
  if(WC_FILTER==='pending'){ab.innerHTML='';}
  else{
  var aa=(D.abandoned||[]).slice().sort(function(a,b){return a.dateIn<b.dateIn?1:-1;});
  ab.innerHTML=aa.length?'<div class="aband-title">🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（共 '+aa.length+' 条）</div>'+aa.map(function(x){
  return '<details class="aband-item"><summary><b>'+esc(x.match||x.name)+'</b>'+(x.code?' · '+esc(x.code):'')+'<span class="aband-aid">'+(x.column?esc(x.column)+' · ':'')+'文章 '+esc(x.aid)+' · '+esc(x.dateIn)+'</span></summary><div class="aband-reason">放弃原因：'+esc(x.reason)+'</div></details>';
  }).join(''):'<div class="fav-empty">已放弃审计区暂无记录。匹配不上或笼统无锚点的线索将在此全程留痕，供事后复盘筛选质量。</div>';
  }
 }
}""",
    tag='abandBox 筛选开关')

open(P, 'w', encoding='utf-8').write(html)
print()
print('完成 %d 处替换' % n_ok)
