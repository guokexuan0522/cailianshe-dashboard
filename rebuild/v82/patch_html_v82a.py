# -*- coding: utf-8 -*-
"""v8.2 HTML/JS 层 patch：栏目补齐 / 核验列 / 复盘计数 / 自选同步重写 / 同步链接说明 / 全网比对重构 / 分类筛选"""
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
# 1. COLUMNS 补齐 盘中宝 / 九点特供 / 研选•行业数据（第 4/5 点根因修复）
# ============================================================
rep("""var COLUMNS={
 '公告全知道':{name:'公告全知道',icon:'📢',color:'#7fd3ff',bg:'#10283a',bd:'#1d4e6b',bar:'#4fc3f7'},
 '财联社早知道':{name:'财联社早知道',icon:'☀',color:'#f5c86e',bg:'#2e2410',bd:'#6b5510',bar:'#f0b43c'},
 '狙击龙虎榜':{name:'狙击龙虎榜',icon:'🎯',color:'#f4737f',bg:'#33161a',bd:'#6e2230',bar:'#f4505e'},
 '风口研报·洞察':{name:'风口研报·洞察',icon:'🔭',color:'#c9a6f5',bg:'#241b38',bd:'#4a3a6b',bar:'#a78bfa'},
 '金牌纪要库':{name:'金牌纪要库',icon:'🏅',color:'#ffd700',bg:'linear-gradient(135deg,#4a3a00,#6b5510 55%,#4a3a00)',bd:'#b38728',bar:'#ffd700'},
 '掘金行业龙头':{name:'掘金行业龙头',icon:'🌟',color:'#f8b3d4',bg:'#331a2a',bd:'#6b2a4a',bar:'#f472b6'}
};
var COL_ORDER=['公告全知道','财联社早知道','狙击龙虎榜','风口研报·洞察','金牌纪要库'];""",
"""var COLUMNS={
 '公告全知道':{name:'公告全知道',icon:'📢',color:'#7fd3ff',bg:'#10283a',bd:'#1d4e6b',bar:'#4fc3f7'},
 '财联社早知道':{name:'财联社早知道',icon:'☀',color:'#f5c86e',bg:'#2e2410',bd:'#6b5510',bar:'#f0b43c'},
 '狙击龙虎榜':{name:'狙击龙虎榜',icon:'🎯',color:'#f4737f',bg:'#33161a',bd:'#6e2230',bar:'#f4505e'},
 '盘中宝':{name:'盘中宝',icon:'⚡',color:'#7ee0a0',bg:'#0e2b1e',bd:'#1d5b3a',bar:'#4ade80'},
 '九点特供':{name:'九点特供',icon:'🕘',color:'#8fd0ff',bg:'#10233a',bd:'#1d4a6b',bar:'#60a5fa'},
 '风口研报·洞察':{name:'风口研报·洞察',icon:'🔭',color:'#c9a6f5',bg:'#241b38',bd:'#4a3a6b',bar:'#a78bfa'},
 '金牌纪要库':{name:'金牌纪要库',icon:'🏅',color:'#ffd700',bg:'linear-gradient(135deg,#4a3a00,#6b5510 55%,#4a3a00)',bd:'#b38728',bar:'#ffd700'},
 '研选•行业数据':{name:'研选•行业数据',icon:'📊',color:'#f0a6d4',bg:'#331a2a',bd:'#6b2a4a',bar:'#f472b6'},
 '掘金行业龙头':{name:'掘金行业龙头',icon:'🌟',color:'#f8b3d4',bg:'#331a2a',bd:'#6b2a4a',bar:'#f472b6'}
};
// v8.2：栏目清单与财联社实际发布栏目对齐（原缺失 盘中宝/九点特供/研选•行业数据，导致入池股票被错标为「公告全知道」）
var COL_ORDER=['公告全知道','财联社早知道','狙击龙虎榜','盘中宝','九点特供','风口研报·洞察','金牌纪要库','研选•行业数据'];""",
    tag='COLUMNS+COL_ORDER 补 3 栏目')

# ============================================================
# 2. verifyHtml 修正（第 6 点）：按 verify/verifyTag 真实状态展示
# ============================================================
rep("function verifyHtml(w){if(w.manual)return '<span class=\"vbadge man\">🧑 人工录入</span>';return w.verifyTag==='摘要确认'?'<span class=\"vbadge ok\">✔ 摘要确认</span>':'<span class=\"vbadge warn\">◐ 推断·待正文确认</span>';}",
"""function verifyHtml(w){
 if(w.manual)return '<span class="vbadge man">🧑 人工录入</span>';
 // v8.2：以 verify 布尔字段为准（三档通过标准：摘要确认 / UNIQ 唯一锚点 / WEB-UNIQ 全网比对确认），
 // 旧版只认 verifyTag==='摘要确认' 导致全部已核验标的误显「推断·待正文确认」。
 var tag=w.verifyTag||'已核验';
 if(w.verify)return '<span class="vbadge ok" title="'+esc(tag)+'｜依据：'+esc(w.verifyBasis||'—')+'">✔ '+esc(tag)+'</span>';
 if(tag.indexOf('摘要')>=0)return '<span class="vbadge ok">✔ '+esc(tag)+'</span>';
 return '<span class="vbadge warn" title="尚未通过三档核验标准，按铁律不得入投研池">◐ 推断·待正文确认</span>';
}""",
    tag='verifyHtml 核验列')

# ============================================================
# 3. renderReview：rvCntT 动态计数（第 2 点）
# ============================================================
rep("""var poolRows='';
if(rv){
document.getElementById('rvDate').textContent=rv.date;
poolRows=(rv.stocks||[]).filter(function(x){return !!byCode[x.code] && favCodes.indexOf(x.code)>=0;}).map(function(x){""",
"""var poolRows='';
if(rv){
document.getElementById('rvDate').textContent=rv.date;
poolRows=(rv.stocks||[]).filter(function(x){return !!byCode[x.code] && favCodes.indexOf(x.code)>=0;}).map(function(x){""",
    tag='renderReview 锚点保留')

rep("""document.getElementById('rvBox').innerHTML='<div class="tbl-wrap"><table><thead><tr><th class="h-stock">股票 / 代码</th><th class="h-price">入选价格</th><th class="h-price">现价</th><th class="h-price">今日涨跌</th><th class="h-price">自选以来</th><th class="h-tech">技术面要点 · 操作提示与警示</th><th class="h-adv">操盘建议</th></tr></thead><tbody>'+
poolRows+manRows+""",
"""setCnt('rvCntT',(poolRows.match(/<tr/g)||[]).length+(manRows.match(/<tr/g)||[]).length);
document.getElementById('rvBox').innerHTML='<div class="tbl-wrap"><table><thead><tr><th class="h-stock">股票 / 代码</th><th class="h-price">入选价格</th><th class="h-price">现价</th><th class="h-price">今日涨跌</th><th class="h-price">自选以来</th><th class="h-tech">技术面要点 · 操作提示与警示</th><th class="h-adv">操盘建议</th></tr></thead><tbody>'+
poolRows+manRows+""",
    tag='rvCntT 动态计数')

# ============================================================
# 4. favSync 重写（第 1 点）：完整字段编码 + 全新浏览器恢复人工录入股 + 合并式恢复
# ============================================================
old_sync = html[html.index('window.favSync=(function(){'):html.index("return {restoreFromHash:restoreFromHash,syncHash:syncHash,bind:bind,encodeFavs:encodeFavs};\n})();") + len("return {restoreFromHash:restoreFromHash,syncHash:syncHash,bind:bind,encodeFavs:encodeFavs};\n})();")]
new_sync = """window.favSync=(function(){
// v8.2 重写（修复自选股跨浏览器不同步）：
// 根因：localStorage 按「协议+主机+端口」隔离，且旧版同步链接只编码 code:price，
//      人工录入股的 名称/市场代码/人工标记 全部丢失——全新浏览器里 byCode 找不到、
//      本地也没有 manual 存档，人工录入股跨设备必丢；恢复语义又是整体覆盖，
//      会把本机已有自选抹掉。
// 解法：
//   ① 编码完整五元组 code~自选价~人工标记~名称~市场代码，排列顺序即自选排序；
//   ② 全新浏览器/全新设备打开链接：投研池股按 byCode 补全，人工录入股凭链接内
//      完整信息直接复活（标记 needFetch，进页面后自动补取行情/K线）；
//   ③ 恢复语义 = 合并（upsert）：链接内的自选写入本机，本机独有的自选保留，
//      此后本机增删自动写回链接——「同步」而非「快照覆盖」。
function encodeFavs(favs){
 return Object.keys(favs).map(function(c){
  var f=favs[c]||{};
  var by=byCode[c]||{};
  var nm=f.name||by.name||'';
  var q=f.q||by.q||'';
  return [c,Number(f.priceFav)>0?Number(f.priceFav):'',f.manual?'1':'0',nm,q].join('~');
 }).join(',');
}
function normCode(c){return String(c||'').replace(/[^0-9A-Za-z]/g,'');}
function decodeHash(hash){
 var m=/[#&]fav=([^&]*)/.exec(hash||'');
 if(!m||!m[1])return null;
 var out={},n=0,manN=0,miss=0;
 m[1].split(',').forEach(function(pair){
  var p=pair.split('~'),code=normCode(p[0]);
  if(!code)return;
  var price=parseFloat(p[1]);
  var manual=p[2]==='1';
  var name=decodeURIComponent(p[3]||''),q=decodeURIComponent(p[4]||'');
  if(byCode[code]){
   var ex=out[code]||FAVS[code]||{};
   out[code]={addTime:ex.addTime||D.lastUpdated,priceFav:isNaN(price)?(byCode[code].priceNow||0):price,
              dateIn:byCode[code].dateIn,priceIn:byCode[code].priceIn,fromLink:true};
   n++;
  }else if(manual||(FAVS[code]&&FAVS[code].manual)){
   // 人工录入股：链接即完整档案（名称/市场代码/人工标记/自选价），无需本地存档
   var mf=FAVS[code]||{};
   out[code]={addTime:mf.addTime||D.lastUpdated,priceFav:isNaN(price)?(Number(mf.priceFav)>0?Number(mf.priceFav):0):price,
              dateIn:mf.dateIn,priceIn:mf.priceIn,manual:true,name:name||mf.name||code,q:q||mf.q||code,
              fromLink:true,needFetch:!(D.stocks[q||mf.q]&&D.stocks[q||mf.q].kline)};
   manN++;
  }else if(FAVS[code]){out[code]=FAVS[code];n++;}
  else miss++;
 });
 return (n+manN)?{favs:out,n:n,manN:manN,miss:miss}:null;
}
function syncHash(){
 try{
  var base=location.href.split('#')[0];
  var favs=encodeFavs(FAVS);
  history.replaceState(null,'',base+(favs?'#fav='+favs:''));
 }catch(e){}
}
function setInfo(t){var el=document.getElementById('favSyncInfo');if(el)el.innerHTML=t;}
function restoreFromHash(){
 var r=decodeHash(location.hash);
 if(!r)return 0;
 var added=0;
 Object.keys(r.favs).forEach(function(c){
  if(!FAVS[c])added++;
  FAVS[c]=r.favs[c];           // upsert：链接优先，本机未冲突的自选保留（合并而非覆盖）
 });
 saveLS(FAV_KEY,FAVS);
 window.favSync._last={n:r.n,manN:r.manN,miss:r.miss,added:added};
 // 人工录入股进页面后自动补取行情/K线（needFetch 标记消费一次）
 if(r.manN){
  Object.keys(FAVS).forEach(function(c){
   var f=FAVS[c];
   if(f&&f.manual&&f.q&&f.needFetch){delete f.needFetch;setTimeout(function(){try{window.refetchManual&&window.refetchManual(c);}catch(e){}},600);}
  });
 }
 return r.n+r.manN;
}
function copyLink(){
 syncHash();
 var url=location.href.split('#')[0]+'#fav='+encodeFavs(FAVS);
 var manN=Object.keys(FAVS).filter(function(c){return FAVS[c]&&FAVS[c].manual;}).length;
 function ok(){setInfo('✅ <b style="color:#7ee0a0">同步链接已复制</b>（含 '+Object.keys(FAVS).length+' 只自选及各自选价'+(manN?'，其中人工录入 '+manN+' 只':'')+'）<br>用法：把链接发到任何设备/任何浏览器，用微信、邮件、网盘随便怎么传都行——对方<b>直接打开这条链接</b>，你的自选清单（含自选价、人工录入股）就完整恢复了，不需要对方也有本页面文件。');}
 function fallback(){
  var ta=document.createElement('textarea');
  ta.value=url;ta.style.position='fixed';ta.style.opacity='0';
  document.body.appendChild(ta);ta.select();
  try{document.execCommand('copy');ok();}catch(e){prompt('浏览器禁止自动复制，请手动全选复制下方链接：',url);}
  ta.remove();
 }
 if(navigator.clipboard&&navigator.clipboard.writeText){
  navigator.clipboard.writeText(url).then(ok,fallback);
 }else fallback();
}
function exportJson(){
 if(!Object.keys(FAVS).length){setInfo('当前没有自选股，先勾选「⭐ 加入自选」再导出。');return;}
 var data={app:'cls-fav',version:D.version,exported:new Date().toISOString(),favs:FAVS,orders:ORDERS};
 var blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
 var a=document.createElement('a');
 a.href=URL.createObjectURL(blob);
 a.download='自选清单_'+(D.lastUpdated||'board').slice(0,10)+'.json';
 document.body.appendChild(a);a.click();
 setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},500);
 setInfo('✅ 已导出 '+Object.keys(FAVS).length+' 只自选清单（JSON），妥善保管，换设备时用「导入」恢复。');
}
function importJson(file){
 var r=new FileReader();
 r.onload=function(){
  try{
   var d=JSON.parse(r.result);
   var favs=d.favs||d,clean={},n=0,miss=0,manN=0;
   Object.keys(favs).forEach(function(c){
    var code=normCode(c);
    var f=favs[c]||{};
    if(f&&f.manual){clean[code]=f;manN++;}
    else if(byCode[code]){clean[code]=favs[c];n++;}
    else miss++;
   });
   if(!n&&!manN){setInfo('⚠️ 清单内没有当前投研池的自选股（可能已满21个交易日移出或代码变更）。');return;}
   FAVS=clean;
   if(d.orders)ORDERS=d.orders;
   saveLS(FAV_KEY,FAVS);saveLS(ORD_KEY,ORDERS);
   syncHash();touchUpdated();renderAll();
   setInfo('✅ 已从文件恢复 <b style="color:#7ee0a0">'+(n+manN)+'</b> 只自选（投研池 '+n+' · 人工录入 '+manN+'）'+(miss?'（'+miss+' 只已不在池，未恢复）':'')+(manN?'<br>人工录入股若显示缺数据，点卡片「🔄 补取数据」即可重新抓取':'')+'。');
  }catch(e){setInfo('⚠️ 文件解析失败：'+e.message);}
 };
 r.readAsText(file);
}
function bind(){
 var lb=document.getElementById('favLinkBtn');
 var eb=document.getElementById('favExpBtn');
 var ib=document.getElementById('favImpBtn');
 var fi=document.getElementById('favFile');
 if(lb)lb.onclick=copyLink;
 if(eb)eb.onclick=exportJson;
 if(ib&&fi)ib.onclick=function(){fi.click();};
 if(fi)fi.onchange=function(){if(fi.files&&fi.files[0])importJson(fi.files[0]);fi.value='';};
 var rf=document.getElementById('ordResetFav');
 if(rf)rf.onclick=function(){window.resetOrder('fav');};
 var rp=document.getElementById('ordResetPool');
 if(rp)rp.onclick=function(){window.resetOrder('pool');};
 var ab=document.getElementById('favAddBtn'),ai=document.getElementById('favAddInput');
 if(ab)ab.onclick=function(){window.addFavManual();};
 if(ai)ai.onkeydown=function(e){if(e.key==='Enter')window.addFavManual();};
}
return {restoreFromHash:restoreFromHash,syncHash:syncHash,bind:bind,encodeFavs:encodeFavs};
})();"""
html = html.replace(old_sync, new_sync, 1)
n_ok += 1
print('[ok] favSync 重写（完整字段编码 + 人工录入股跨设备恢复 + 合并式恢复）')

# ============================================================
# 5. 复制同步链接按钮：title 悬浮说明 + favSyncInfo 默认文案（第 3 点）
# ============================================================
rep('<button class="fold-btn" id="favLinkBtn" type="button">🔗 复制同步链接</button>',
    '<button class="fold-btn" id="favLinkBtn" type="button" title="作用：自选股保存在每台设备的浏览器本地（按网址隔离），换设备/换浏览器默认互不相通。点此按钮会把你的全部自选股（含各自选价与人工录入股）编码进当前网址，复制后发到任何设备，对方直接打开该链接即完整恢复你的自选清单。">🔗 复制同步链接</button>',
    tag='favLinkBtn title 说明')

rep('<span class="fold-info" id="favSyncInfo">默认按 10日上涨概率 ↓ · 置信度 ↓ 自动排列；长按拖拽可临时手动调整（不影响自动排序基准）· 自选股保存在本机浏览器（按网址隔离），换设备用「同步链接」或「导入清单」恢复</span>',
    '<span class="fold-info" id="favSyncInfo">自选股默认按 10日上涨概率 ↓ · 置信度 ↓ 自动排列；长按拖拽可临时手动调整。<b>换设备/换浏览器同步方法</b>：① 点「🔗 复制同步链接」——把自选清单编入网址，发到任何设备直接打开即恢复（含人工录入股）；② 点「💾 导出自选清单」下载 JSON 文件，到新设备点「📂 导入自选清单」恢复。</span>',
    tag='favSyncInfo 用法说明')

# 恢复成功提示同步更新（融合文案）
rep("if(_favRestored)setTimeout(function(){var el=document.getElementById('favSyncInfo');if(el)el.innerHTML='✅ 已从同步链接恢复 <b style=\"color:#7ee0a0\">'+_favRestored+'</b> 只自选（含各自选价）——本机记忆已同步更新，此后增删会自动写回链接';},400);",
"""if(_favRestored)setTimeout(function(){var el=document.getElementById('favSyncInfo');var L=window.favSync._last||{};if(el)el.innerHTML='✅ 已从同步链接恢复 <b style="color:#7ee0a0">'+_favRestored+'</b> 只自选（含各自选价'+(L.manN?'，人工录入 '+L.manN+' 只':'')+'）——与本机已有自选合并，此后增删会自动写回链接'+(L.miss?'（'+L.miss+' 只已不在池未恢复）':'');},400);""",
    tag='恢复成功提示合并语义')

open(P, 'w', encoding='utf-8').write(html)
print()
print('完成 %d 处替换，长度 %d → %d' % (n_ok, orig_len, len(html)))
