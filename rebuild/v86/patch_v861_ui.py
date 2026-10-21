# -*- coding: utf-8 -*-
"""v8.6.1 UI 修复（用户报告三点）：

① 一键展开/全部收起按钮部分失效
   根因：expandAll/collapseAll 实现为 querySelectorAll(sel+' details')，
   内部已自动拼 ' details'；但「全网比对」与「放弃审计区」的按钮调用传的是
   '#wcBox details' / '#abandBox details' → 选择器变成 '#wcBox details details'
   （双层嵌套），选不中卡片 → 按钮无效。修复：调用处改传容器 '#wcBox'/'#abandBox'。
   （期次备查/规则铁律/更新记录传容器名本就正常，保持不变。）
   另：收起时选中容器下全部后代 details（含嵌套支栏），满足「整栏与支栏分别收起」。

② 【已放弃审计区】应整栏可收起
   修复：把 abandBox 包进 <details id="abandWrap">，summary 显示整栏标题（动态条数），
   内部 aband-item 仍为支栏 details → 整栏/支栏两级可分别收起；新增「整栏收起/展开」按钮。

③ 【自选股 · 入池以来涨幅（自选价基准）】人工股与个别在池股不显示
   根因：manualW() 硬编码 gainSince:0，且 favG() 只有「自选价 → gainSince」两级，
   人工股无自选价时直接返回 0 → 柱长恒为 0（视觉上即"显示不出来"）。
   修复：favG 三级回退（自选价 → 入池价/录入价 → gainSince）；manualW 的 priceIn
   优先取录入价、其次自选价，gainSince 按 (现价/priceIn-1) 实时计算；
   tooltip 的 priceIn.toFixed 加防御；favList 的 code 规范化（去 .SH/.SZ 后缀）提高匹配。
"""
import json, re

HTML = '/workspace/cailianshe-dashboard/index.html'
h = open(HTML, encoding='utf-8').read()
orig = h
steps = []


def rep(old, new, n=1, tag=''):
    global h
    cnt = h.count(old)
    assert cnt == n, '替换计数不符 [%s]: 期望 %d 实际 %d' % (tag, n, cnt)
    h = h.replace(old, new)
    steps.append('%s ✓' % tag)


# ---------- ① 折叠按钮选择器 ----------
rep("onclick=\"expandAll('#wcBox details')\"", "onclick=\"expandAll('#wcBox')\"", 1, '①展开按钮 wcBox')
rep("onclick=\"collapseAll('#wcBox details')\"", "onclick=\"collapseAll('#wcBox')\"", 1, '①收起按钮 wcBox')
rep("onclick=\"collapseAll('#abandBox details')\">放弃审计区全部收起</button>",
    "onclick=\"collapseAll('#abandBox')\">放弃审计区全部收起</button>"
    "<button class=\"fold-btn ghost\" onclick=\"toggleAbandWrap()\">整栏收起/展开</button>",
    1, '①收起按钮 abandBox + 新增整栏按钮')

# ---------- ② 放弃审计区整栏可收起 ----------
rep('<div id="wcBox"></div>\n<div id="abandBox"></div></section>',
    '<div id="wcBox"></div>\n<details id="abandWrap" class="aband-wrap" open>'
    '<summary id="abandSum" class="aband-title">🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘</summary>'
    '<div id="abandBox"></div></details></section>',
    1, '②abandBox 包 details 整栏')

# 整栏收起/展开函数（与 expandAll/collapseAll 同处定义）
rep("window.collapseAll=function(sel){document.querySelectorAll(sel+' details').forEach(function(d){d.open=false;});};",
    "window.collapseAll=function(sel){document.querySelectorAll(sel+' details').forEach(function(d){d.open=false;});}; "
    "// v8.6.1 放弃审计区整栏收起/展开（整栏 details 与内部支栏 details 两级独立） "
    "window.toggleAbandWrap=function(){var el=document.getElementById('abandWrap');if(!el)return;el.open=!el.open;};",
    1, '②toggleAbandWrap 函数')

# renderWebcheck：条数写进整栏 summary，内部不再重复标题
rep("ab.innerHTML=aa.length?'<div class=\"aband-title\">🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（共 '+aa.length+' 条）</div>'+aa.map(function(x){",
    "var _asum=document.getElementById('abandSum');"
    "if(_asum)_asum.innerHTML='🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（共 '+aa.length+' 条）';\n  "
    "ab.innerHTML=aa.length?aa.map(function(x){",
    1, '②整栏 summary 动态条数')

# pending 筛选视图下整栏标题提示
rep("if(WC_FILTER==='pending'){ab.innerHTML='';}",
    "if(WC_FILTER==='pending'){ab.innerHTML='';"
    "var _as2=document.getElementById('abandSum');"
    "if(_as2)_as2.innerHTML='🗑 已放弃审计区 · 宁缺毋滥 · 全程留痕可复盘（当前「待比对」视图下已隐藏，切回「全部」查看）';}",
    1, '②pending 视图整栏提示')

# ---------- ③ 自选股涨幅图 ----------
rep("function favG(w){var pf=Number(w.priceFav)||0;var pn=(D.stocks[w.q]||{}).price||w.priceNow||w.price||0;if(pf>0&&pn>0)return (pn/pf-1)*100;return w.gainSince;}",
    "function favG(w){var pf=Number(w.priceFav)||0;var pn=(D.stocks[w.q]||{}).price||w.priceNow||w.price||0;"
    "if(pf>0&&pn>0)return (pn/pf-1)*100;"
    "var pni=Number(w.priceIn)||0;if(pni>0&&pn>0)return (pn/pni-1)*100;"
    "return Number(w.gainSince)||0;}",
    1, '③favG 三级回退')

rep("priceIn:(Number(f.priceIn)>0?Number(f.priceIn):price),priceNow:price,pct:st.pct||0,",
    "priceIn:(Number(f.priceIn)>0?Number(f.priceIn):(Number(f.priceFav)>0?Number(f.priceFav):price)),priceNow:price,pct:st.pct||0,",
    1, '③manualW priceIn 优先录入价/自选价')

rep("outlook:'—',tech:'—',forecast:'—',conf:'mid',prob:null,gainSince:0,manual:true,priceFav:f.priceFav,verifyTag:'人工录入'};",
    "outlook:'—',tech:'—',forecast:'—',conf:'mid',prob:null,gainSince:0,manual:true,priceFav:f.priceFav,verifyTag:'人工录入'};\n"
    " if(w.priceIn>0&&price>0)w.gainSince=+((price/w.priceIn-1)*100).toFixed(2);",
    1, '③manualW gainSince 按入池价实时计算')

rep("+'<br>入选 '+w.dateIn+' @ '+w.priceIn.toFixed(2)+",
    "+'<br>入选 '+w.dateIn+' @ '+(Number(w.priceIn)||0).toFixed(2)+",
    2, '③tooltip priceIn 防御（cGain + cGainAll 两处）')

rep("var c=String(k).replace(/^(sh|sz|bj)/,'');if(byCode[c])",
    "var c=String(k).replace(/^(sh|sz|bj)/,'').replace(/\\.(SH|SZ|BJ)$/i,'');if(byCode[c])",
    1, '③favList code 规范化')

# ---------- 版本与记录 ----------
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.6'
d['version'] = '8.6.1'
d['lastUpdated'] = ('2026-10-22（v8.6.1 UI 修复：①一键展开/全部收起按钮——全网比对与放弃审计区'
                    '传参多拼 details 致失效已修正，收起时整栏与嵌套支栏一并收起；'
                    '②已放弃审计区整栏可收起（外层 details，条数动态显示）；'
                    '③自选股涨幅图——人工录入股恒显 0% 已修正（按自选价→录入价→入池价三级回退计算），'
                    '个别在池股匹配增强（代码去前缀/后缀规范化）')
d['history'].append({
    'version': '8.6.1', 'time': '2026-10-22 01:35',
    'note': ('UI 修复三处（用户报告）：①「一键展开/全部收起」按钮——expandAll/collapseAll 内部已拼 '
             '\' details\'，而全网比对/放弃审计区调用又传了 \'#wcBox details\'，导致选择器成双层嵌套选不中卡片而失效；'
             '改为传容器 id，收起时容器内全部（含嵌套）details 一并收起。'
             '②已放弃审计区整栏可收起——abandBox 包入 <details id="abandWrap">，summary 动态显示条数，'
             '与内部支栏形成两级独立折叠，并新增「整栏收起/展开」按钮。'
             '③自选股「入池以来涨幅（自选价基准）」——manualW 原硬编码 gainSince:0 且 favG 仅两级回退，'
             '致人工录入股柱长恒为 0（视觉上"显示不出来"）；改为三级回退（自选价→入池价/录入价→gainSince）'
             '并让人工股按录入价实时计算涨幅；tooltip 的 priceIn 加防御；favList 代码规范化去 .SH/.SZ 后缀提升匹配。'),
})
blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in blob
h = h[:m.start(1)] + blob + h[m.end(1):]
steps.append('版本 8.6 → 8.6.1 + history ✓')

# CSS：整栏 summary 样式（可点击 + 与内部标题区分）
if '.aband-wrap' not in h:
    CSS = ('.aband-wrap{margin-top:12px;border:1px solid var(--line,#2a3category);border-radius:10px;padding:8px 10px}'
           '.aband-wrap>summary{cursor:pointer;list-style:none;font-weight:700}\n')
    if h.count('.aband-title{') >= 1:
        h = h.replace('.aband-title{', CSS + '.aband-title{', 1)
        steps.append('②整栏 CSS（挂 .aband-title 前）✓')
    elif h.count('</style>') >= 1:
        h = h.replace('</style>', CSS + '</style>', 1)
        steps.append('②整栏 CSS（注入 style 末尾）✓')
    else:
        steps.append('②整栏 CSS 跳过（未找到锚点）⚠')
else:
    steps.append('②整栏 CSS 已存在 ✓')

assert h != orig
open(HTML, 'w', encoding='utf-8').write(h)
print('修复步骤：')
for s in steps:
    print('  ', s)
print('index.html 已更新（%d 字节）' % len(h.encode('utf-8')))
