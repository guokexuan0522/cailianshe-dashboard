# -*- coding: utf-8 -*-
"""v8.2 HTML patch 第三批：自选股 + 投研池 分类筛选（第9点）"""
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
# 8. 自选股区：加「来源分类」下拉（财联社栏目 + 人工录入）
# ============================================================
rep("""<div class="fold-bar" id="favSyncBar">
<button class="fold-btn" id="favLinkBtn" type="button" title="作用：自选股保存在每台设备的浏览器本地（按网址隔离），换设备/换浏览器默认互不相通。点此按钮会把你的全部自选股（含各自选价与人工录入股）编码进当前网址，复制后发到任何设备，对方直接打开该链接即完整恢复你的自选清单。">🔗 复制同步链接</button>""",
"""<div class="fold-bar" id="favSyncBar">
<select class="fold-sel" id="favColSel" onchange="renderFavs()" title="按文章来源分类筛选自选股（财联社栏目或人工录入）"><option value="">全部来源</option></select>
<button class="fold-btn" id="favLinkBtn" type="button" title="作用：自选股保存在每台设备的浏览器本地（按网址隔离），换设备/换浏览器默认互不相通。点此按钮会把你的全部自选股（含各自选价与人工录入股）编码进当前网址，复制后发到任何设备，对方直接打开该链接即完整恢复你的自选清单。">🔗 复制同步链接</button>""",
    tag='自选股区加来源分类下拉')

# ============================================================
# 9. 投研池区：加「来源分类」下拉
# ============================================================
rep("""<div class="legend" id="poolLegend"></div>
<div class="stocks-grid" id="poolBox"></div></section>""",
"""<div class="legend" id="poolLegend"></div>
<div class="fold-bar" style="margin-bottom:10px">
<select class="fold-sel" id="poolColSel" onchange="renderPool()" title="按财联社文章来源栏目筛选投研池股票"><option value="">全部栏目</option></select>
<span class="fold-info">在池时长按交易日计算（21个交易日移出）· 筛选只影响本区卡片展示，不影响统计与图表</span>
</div>
<div class="stocks-grid" id="poolBox"></div></section>""",
    tag='投研池区加来源分类下拉')

# ============================================================
# 10. renderPool / renderFavs 应用筛选 + 选项动态填充
# ============================================================
rep("""function renderPool(){
document.getElementById('poolBox').innerHTML=W.length?applyOrder(autoSort(W),'pool').map(function(w){return cardHtml(w,false);}).join(''):'<div class="fav-empty">投研池暂无标的，等待采集注入（每日 15:35 / 0:30）。</div>';
setCnt('poolCntT',W.length);
refreshOrdReset();
}
function renderFavs(){
var arr=favList();
setCnt('favCntT',arr.length);
arr=applyOrder(autoSort(arr),'fav');document.getElementById('favBox').innerHTML=arr.length?('<div class="stocks-grid">'+arr.map(function(w){return cardHtml(w,true);}).join('')+'</div>'):'<div class="fav-empty">暂无自选股。在入选投研池卡片中勾选「⭐ 加入自选」即可收藏（本机记忆，刷新不丢失）。</div>';
refreshOrdReset();
}""",
"""// v8.2 分类筛选选项（两个下拉共用一套财联社栏目；自选股额外提供「人工录入」）
function fillColSels(){
 var opts=COL_ORDER.map(function(c){return '<option value="'+esc(c)+'">'+esc(c)+'</option>';}).join('');
 var ps=document.getElementById('poolColSel');
 if(ps){var pv=ps.value;ps.innerHTML='<option value="">全部栏目（'+COL_ORDER.length+'）</option>'+opts;if(COL_ORDER.indexOf(pv)>=0||pv==='')ps.value=pv;}
 var fs=document.getElementById('favColSel');
 if(fs){var fv=fs.value;fs.innerHTML='<option value="">全部来源</option>'+opts+'<option value="__manual__">🧑 人工录入</option>';if(fv)fs.value=fv;}
}
function renderPool(){
 var cv=(document.getElementById('poolColSel')||{}).value||'';
 var list=cv?W.filter(function(w){return colOf(w)===cv;}):W;
 document.getElementById('poolBox').innerHTML=list.length?applyOrder(autoSort(list),'pool').map(function(w){return cardHtml(w,false);}).join(''):'<div class="fav-empty">'+(cv?('当前栏目筛选（'+esc(cv)+'）下暂无在池标的。'):'投研池暂无标的，等待采集注入（每日 15:35 / 0:30）。')+'</div>';
 setCnt('poolCntT',W.length);
 refreshOrdReset();
}
function renderFavs(){
var arr=favList();
setCnt('favCntT',arr.length);
var cv=(document.getElementById('favColSel')||{}).value||'';
if(cv==='__manual__')arr=arr.filter(function(w){return !!w.manual;});
else if(cv)arr=arr.filter(function(w){return !w.manual&&colOf(w)===cv;});
arr=applyOrder(autoSort(arr),'fav');document.getElementById('favBox').innerHTML=arr.length?('<div class="stocks-grid">'+arr.map(function(w){return cardHtml(w,true);}).join('')+'</div>'):'<div class="fav-empty">'+(cv?('当前来源筛选下暂无自选股。'):'暂无自选股。在入选投研池卡片中勾选「⭐ 加入自选」即可收藏（本机记忆，刷新不丢失）。')+'</div>';
refreshOrdReset();
}""",
    tag='renderPool/renderFavs 分类筛选')

# ============================================================
# 11. renderStatic 里调用 fillColSels（页面初始化时填充选项）
# ============================================================
rep("""function renderStatic(){
// 栏目图例（入选投研池 / 上涨概率）""",
"""function renderStatic(){
fillColSels();
// 栏目图例（入选投研池 / 上涨概率）""",
    tag='renderStatic 填充筛选项')

open(P, 'w', encoding='utf-8').write(html)
print()
print('完成 %d 处替换，长度 %d → %d' % (n_ok, orig_len, len(html)))
