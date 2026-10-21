#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.5 铁律文本对齐用户 2026-10-21 亲定意图 + 版本升版 + 修订历史。"""
import re
import json

HTML = '/workspace/cailianshe-dashboard/index.html'
html = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
d = json.loads(m.group(1))

# ========== 1) 新增最高优先级铁律类（置顶） ==========
top = {
    "name": "〇、用户亲定铁律（2026-10-21·最高优先级，与此冲突的旧条款一律以本类为准）",
    "icon": "👑",
    "items": [
        "① 价格是第一道硬关：只抓取 ≥280 微信豆的高价值文章；180 微信豆的一般信息类/普通研报类文章直接不要（对超短线/强势票策略无价值）。",
        "② 摘要条数 = 股票数量硬上限：摘要有 ①②③ 几条，这篇文章就只对应几只股票。三条摘要绝不能搞出四五个——多出来的必是错误信息，会误导入池与投资决策。绝不外延。",
        "③ 全网比对确认（第三道关）：摘要未点名具体上市公司的，拿摘要中的公告内容特征与全网公开信息（公告原文/研报/权威媒体）比对定位。比对上→入池；匹配度相当高但非一一精确→进候选池；匹配不上或匹配度不高→暂时放弃，宁缺毋滥，绝不马马虎虎。",
        "④ 笼统行业文/趋势文，公开信息无法对具体股票准确定位、没有一一对应股票特征的，整篇彻底放弃（宁缺毋滥）。",
        "⑤ 点明了股票名称但文章价值在趋势/价值分析的：需同时满足 前瞻性看好 + 公开信息有对应 + 上涨概率研判高 才入池；否则不入池（无近期最直接利好，入池意义不大）。",
        "⑥ 负面消息绝对排除：行业走向衰落、盈利能力下降、业绩下滑、减持、处罚、退市风险等——即使文章收费再高、点了名，也绝不收录。绝不逆向选择衰落行业/有负面消息的股票。",
        "⑦ 系统根本目的：全自动抓取→按上述铁律筛选→对入池股票持续数据追踪（涨跌/成功率），用一段时间的实盘表现检验这套筛选的可信度，作为投资参考。全程最大限度减少人工干预，用户只在云端网页查看结果与数据动态。",
    ],
}
cats = d.get('ruleCats', [])
# 去重后置顶
cats = [c for c in cats if not c.get('name', '').startswith('〇、')]
d['ruleCats'] = [top] + cats

# ========== 2) 修订冲突条款 ==========
for c in d['ruleCats']:
    name = c.get('name', '')
    items = c.get('items', [])
    if name.startswith('三、'):
        items.append("【v7.5 修订】第三道关＝全网主动比对：摘要未字面点名的，必须拿公告特征（唯一锚点：精确金额/唯一产品名/唯一资质关系/业绩数字）与全网公开信源逐字比对，比对结论（入池/候选/放弃）全程留痕可审计；严禁被动等待人工唤醒。")
        items.append("【v7.5 修订】放弃也须留痕：匹配不上或笼统无锚点的线索，进「已放弃」审计区并注明放弃原因，供事后复盘筛选质量——宁缺毋滥不等于无声丢弃。")
    if name.startswith('四、'):
        items.append("【v7.5 修订】通过标准新增第三档：③WEB-UNIQ＝摘要匿名但唯一硬锚点经全网公开信源比对确认唯一对应一家上市公司（须附比对证据）。")
        items.append("【v7.5 修订】三道数量/方向闸门（任何一条不过即淘汰）：a) 摘要条数硬上限（字面点名数不得超过摘要①②③条数）；b) 负面关键词绝对排除（铁律⑥）；c) 非公告类栏目点名声股票须有明确正向催化剂（铁律⑤，否则转候选待研判）。")
    if name.startswith('九、'):
        items.append("【v7.5 修订】第三层已全自动云端化（land.yml：autopool 完成后即刻 + 白天每20分钟兜底）：公告类点名信号自动入投研池并嵌入K线重算概率；匿名线索进「待全网比对」队列；负面信号进「已放弃」审计区。全网比对由 AI 自主执行（webcheck_decisions.jsonl 决策留痕），不再依赖人工会话唤醒。")

# ========== 3) 版本升版 + 修订历史 ==========
d['version'] = '7.5'
now = '2026-10-21 11:20'
d['lastUpdated'] = now + '（v7.5 铁律对齐用户亲定意图：价格≥280硬关/摘要条数=股票数硬上限/全网主动比对/负面绝对排除/宁缺毋滥放弃留痕；第三层落地+全网比对全自动云端化）'
note = ('v7.5 全面对齐用户 2026-10-21 亲定铁律（用户明确指出此前对铁律理解有偏差，以本次为准）：'
        '①代码层：autopool 新增三道闸门——摘要条数硬上限（修复 (?=①②③) 无方括号的历史 bug，teaser_count 一直算1）、'
        '负面关键词绝对排除（衰落/盈利下降/减持/处罚/退市等19词）、非公告栏目点名声须有正向催化剂（趋势研判门槛）；'
        'land.py 同步安全网+嵌K线（入池即重算真实概率）+待全网比对队列+已放弃审计区；'
        '②全网比对（铁律③）落地执行：AI 自主用公开信源逐条比对今日10条匿名摘要——确认3只入池'
        '（国新健康000503：天枢·三医+灵犀半年报精确对应；星网锐捷002396：39560万收购广州芯德46%公告精确对应；'
        '海正药业600267：瀚晖合资子公司批文+自有原料药资质逐字对应），6条放弃留痕（物理AI笼统行业/数据集团全链路多对一/'
        'MOM多厂商/Optimus供应商众多等，宁缺毋滥）；'
        '③流水线：land.yml（autopool后即刻+每20分钟兜底）+webcheck_resolve.py 决策消费，第三层不再依赖人工会话唤醒；'
        '④铁律文本：新增「〇、用户亲定铁律」最高优先级类（7条），修订三/四/九类冲突条款。'
        '投研池 33→37，候选池 5→8，已放弃审计 4 条。')
d.setdefault('history', []).append({"version": "7.5", "time": now, "note": note})

new_raw = json.dumps(d, ensure_ascii=False, indent=1)
html = html[:m.start(1)] + new_raw + html[m.end(1):]
open(HTML, 'w', encoding='utf-8').write(html)

# 校验
m2 = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', open(HTML, encoding='utf-8').read(), re.S)
d2 = json.loads(m2.group(1))
print('version:', d2['version'], '| ruleCats:', len(d2['ruleCats']), '| 首类:', d2['ruleCats'][0]['name'][:30], '| history 最新:', d2['history'][-1]['version'], d2['history'][-1]['time'])
print('watchlist:', len(d2['watchlist']), '| candidates:', len(d2['candidates']), '| abandoned:', len(d2['abandoned']), '| webcheck:', len(d2['webcheck']))
