# -*- coding: utf-8 -*-
"""v8.4 数据层补录：裁决云端合并带来的 2 篇新文章（承接“继续核验其余标的”指令的延伸）

背景：v8.3 推送前与 origin/main 的 11 个云端自动提交合并，云端流水带来 2 篇本地未裁决的新文章：
  ① 2510680【风口专家会议】物理AI能否催生“聪明”的机器人？（2026-10-21 16:01 · 1280 豆）
     autopool 路由 wake/generic-name-risk（仅命中通用词“机器人”），工单 related_stock 为空
  ② 2511096【风口研报·记者传真】近期该小金属价格再次涨至历史高位附近（2026-10-21 16:52 · 280 豆）
     autopool 已按 skip-oos 跳过（栏目不在 COLUMN_MAP）

人工复核（均取财联社原文页核实公开部分）：
  ① 原文页公开部分仅会议推广信息；4 条摘要为会议议程式概念阐述，无一个点名个股、无官方板块分布
     → 4 条全部放弃（铁律④笼统行业文；栏目「风口专家会议」不在看板 8 栏目监控范围）
  ② 原文页公开摘要仅 1 条：“这个小金属……及相关上市公司动态”——金属种类未点名、
     “相关上市公司”为复数泛指，工单 related_stock 主板 2 只但公开信息无法定位到具体标的
     → 放弃（铁律③④宁缺毋滥；栏目「风口研报·记者传真」不在看板 8 栏目监控范围）

本脚本：batches 补 2 期（5 条放弃 items 全挂接）+ abandoned 36→41 +
webcheck_decisions.jsonl 补 5 条 abandon 记录 + 版本 8.4 + 注入 index.html。
不涉及在池标的变动（35 只不变）、行情不变、review 不变、baseP 不变。
"""
import json, os, re, sys

ROOT = '/workspace/cailianshe-dashboard'
HTML = os.path.join(ROOT, 'index.html')
DECISIONS = os.path.join(ROOT, 'autopool', 'webcheck_decisions.jsonl')
V84_TIME = '2026-10-21 19:30'

# ---------- 读母版 ----------
h = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.3', d['version']
assert len(d['watchlist']) == 35 and len(d['batches']) == 17 and len(d['abandoned']) == 36

T680 = [
    '①何为物理AI？能否推动“聪明”的机器人诞生？',
    '②物理AI所需数据种类及国内数据采集、研发相关企业业务介绍；',
    '③机器人大脑所需配套硬件数量、价值量趋势分析；',
    '④人形机器人量产节点及国内产业链进展情况分析。',
]
R680 = [
    '会议议程设问（“何为物理AI”），纯概念阐述，未出现任何公司名称/股票代码，无锚点；且栏目「风口专家会议」为专家会议观看权益产品（议程式摘要），不在看板 8 栏目监控范围，按铁律④笼统行业文彻底放弃',
    '“国内数据采集、研发相关企业”为泛指，未点名任何主体、无唯一锚点；工单 related_stock 为空、无官方板块分布，且栏目「风口专家会议」不在看板 8 栏目监控范围，按铁律④彻底放弃',
    '配套硬件数量与价值量趋势为行业总量分析，无个股锚点；栏目不在看板监控范围，宁缺毋滥',
    '产业链进展为行业动态综述，无个股锚点；栏目不在看板监控范围，宁缺毋滥',
]

# ---------- ① batches 补 2 期 ----------
b680 = {
    'id': 'b2510680', 'period': '2026-10-21', 'pub': '2026-10-21 16:01',
    'beans': 1280, 'tier': 'webcheck', 'column': '风口专家会议', 'companies': 0,
    'title': '【风口专家会议】物理AI能否催生“聪明”的机器人？特邀行业专家全面解读物理AI对机器人产业的推动作用',
    'article': {
        'title': '【风口专家会议】物理AI能否催生“聪明”的机器人？特邀行业专家全面解读物理AI对机器人产业的推动作用',
        'meta': '原创 · 财联社VIP · 2026-10-21 16:01 · 1280 微信豆',
        'foreword': '栏目：风口专家会议。本文为财联社VIP收费文章（专家会议观看权益产品），此处仅呈现公开可见的摘要部分（正文付费锁定）。豆数经文章页核实。',
        'teasers': T680,
    },
    'items': [{
        'title': '摘要%s→（匿名线索·会议议程）· 无锚点放弃' % ['①', '②', '③', '④'][i],
        'tags': [], 'verified': False, 'tier': 'webcheck',
        'content': '摘要%s→放弃。%s。autopool 路由 generic-name-risk（仅命中通用词“机器人”），与人工复核一致。' % (['①', '②', '③', '④'][i], R680[i]),
        'stock': '', 'scode': '', 'aid': '2510680', 'bulletNo': i + 1,
    } for i in range(4)],
    'note': ('本篇栏目「风口专家会议」不在看板 8 栏目监控范围（公告全知道/财联社早知道/狙击龙虎榜/盘中宝/九点特供/'
             '风口研报·洞察/金牌纪要库/研选•行业数据）；原文页公开部分仅会议推广信息，4 条摘要均为会议议程式概念阐述，'
             '无一个点名个股、工单 related_stock 为空、无官方板块分布，按铁律④笼统行业文彻底放弃，4 条全部留痕备查。'),
}

b1096 = {
    'id': 'b2511096', 'period': '2026-10-21', 'pub': '2026-10-21 16:52',
    'beans': 280, 'tier': 'webcheck', 'column': '风口研报·记者传真', 'companies': 0,
    'title': '【风口研报·记者传真】近期该小金属价格再次涨至历史高位附近，记者多方采访业内人士探寻后期价格趋势',
    'article': {
        'title': '【风口研报·记者传真】近期该小金属价格再次涨至历史高位附近，记者多方采访业内人士探寻后期价格趋势',
        'meta': '原创 · 财联社VIP · 2026-10-21 16:52 · 280 微信豆',
        'foreword': '栏目：风口研报·记者传真。本文为财联社VIP收费文章，此处仅呈现公开可见的摘要部分（正文付费锁定）。豆数经文章页核实。',
        'teasers': ['这个小金属供给端持续收紧、需求端结构性扩张，近期价格再次涨至历史高位附近，记者多方采访业内人士探寻后期价格趋势及相关上市公司动态。'],
    },
    'items': [{
        'title': '摘要①→（匿名线索·复数泛指）· 无锚点放弃',
        'tags': [], 'verified': False, 'tier': 'webcheck',
        'content': ('摘要①→放弃。公开摘要仅称“该小金属……及相关上市公司动态”：金属种类未点名、“相关上市公司”为复数泛指，'
                    '无唯一锚点锁定单一主体；工单 related_stock 主板 2 只但公开信息无法定位到具体标的；'
                    '且栏目「风口研报·记者传真」不在看板 8 栏目监控范围（autopool 2026-10-21 17:15:58 已按 skip-oos 跳过），'
                    '按铁律③④宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2511096', 'bulletNo': 1,
    }],
    'note': ('本篇栏目「风口研报·记者传真」不在看板 8 栏目监控范围（autopool 已按 skip-oos 跳过）；公开摘要 1 条为复数泛指，'
             '“该小金属”公开文本未点名金属种类、“相关上市公司动态”为多家泛指，工单 related_stock 主板 2 只但无法定位到具体标的，'
             '按铁律③④宁缺毋滥放弃，留痕备查。'),
}
d['batches'].extend([b680, b1096])
d['batches'].sort(key=lambda x: (x.get('period') or '', x.get('pub') or ''))
print('batches: %d → %d 期' % (17, len(d['batches'])))

# ---------- ② abandoned 36→41 ----------
new_ab = []
for i in range(4):
    new_ab.append({
        'aid': '2510680', 'name': '（匿名线索·会议议程）', 'code': '',
        'match': T680[i], 'column': '风口专家会议', 'dateIn': '2026-10-21',
        'reason': R680[i],
    })
new_ab.append({
    'aid': '2511096', 'name': '（匿名线索·复数泛指）', 'code': '',
    'match': '这个小金属供给端持续收紧、需求端结构性扩张……及相关上市公司动态',
    'column': '风口研报·记者传真', 'dateIn': '2026-10-21',
    'reason': ('栏目不在看板监控范围（autopool 已 skip-oos）+摘要复数泛指：“该小金属”公开文本未点名种类，'
               '“相关上市公司动态”为多家泛指，无唯一锚点锁定单一主体，按铁律③④宁缺毋滥'),
})
d['abandoned'].extend(new_ab)
print('abandoned: 36 → %d 条' % len(d['abandoned']))

# ---------- ③ 版本 / 时间戳 / 历史 ----------
d['version'] = '8.4'
d['lastUpdated'] = ('2026-10-21（v8.4：合并云端自动流水后新增 2 篇文章裁决——2510680 风口专家会议·物理AI 4 条议程摘要、'
                    '2511096 风口研报·记者传真·小金属 1 条泛指摘要，共 5 条均无唯一锚点且栏目不在看板 8 栏目监控范围，'
                    '全部放弃并挂接期次备查留痕；在池 35 只不变）')
d['history'].append({
    'version': '8.4', 'time': V84_TIME,
    'note': ('合并 origin/main 11 个云端自动提交（scan/autopool/land，15:48~19:02）后，对流水带来的 2 篇本地未裁决文章逐条复核'
             '（均取财联社原文页核实公开部分）：①2510680【风口专家会议】物理AI能否催生“聪明”的机器人？（1280 豆）——'
             '原文页公开部分仅会议推广信息，4 条摘要为会议议程式概念阐述，无一个点名个股、工单 related_stock 为空、无官方板块分布，'
             '且栏目「风口专家会议」不在看板 8 栏目监控范围，4 条全部放弃（铁律④笼统行业文）；autopool 路由 generic-name-risk 与人工复核一致；'
             '②2511096【风口研报·记者传真】小金属价格历史高位（280 豆）——公开摘要仅称“该小金属……及相关上市公司动态”，'
             '金属种类未点名、复数泛指无唯一锚点，工单 related_stock 主板 2 只但无法定位到具体标的，且栏目「风口研报·记者传真」'
             '不在看板 8 栏目监控范围（autopool 已按 skip-oos 跳过），放弃（铁律③④宁缺毋滥）。'
             'batches 17→19 期、abandoned 36→41 条，全部挂接留痕；在池 35 只、行情、review、baseP 均不变。'
             '合并冲突仅 index.html 一处，保留本地 v8.3 母版（云端版为 v8.1 数据回退：34 只含已实证剔除的科华数据/中恒电气、无期次备查、时效落后）。'),
})

# ---------- ④ 注入 index.html ----------
blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in blob
h2 = re.sub(r'(<script id="MONITOR_DATA" type="application/json">).*?(</script>)',
            lambda mm: mm.group(1) + blob + mm.group(2), h, count=1, flags=re.S)
assert h2 != h and 'MONITOR_DATA' in h2
open(HTML, 'w', encoding='utf-8').write(h2)
print('注入完成：index.html %d bytes' % len(h2.encode('utf-8')))

# ---------- ⑤ webcheck_decisions.jsonl 补 5 条 abandon ----------
rows = []
for i in range(4):
    rows.append({
        'aid': '2510680', 'match': T680[i], 'action': 'abandon',
        'name': '（匿名线索·会议议程）', 'code': '', 'column': '风口专家会议',
        'reason': R680[i] + '（v8.4 裁决）',
    })
rows.append({
    'aid': '2511096', 'match': '这个小金属供给端持续收紧、需求端结构性扩张……及相关上市公司动态',
    'action': 'abandon', 'name': '（匿名线索·复数泛指）', 'code': '',
    'column': '风口研报·记者传真',
    'reason': ('栏目不在看板监控范围（autopool 已 skip-oos）+摘要复数泛指：“该小金属”公开文本未点名种类，'
               '“相关上市公司动态”为多家泛指，无唯一锚点锁定单一主体，按铁律③④宁缺毋滥（v8.4 裁决）'),
})
with open(DECISIONS, 'a', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('webcheck_decisions.jsonl: +%d 条 abandon 记录' % len(rows))

# ---------- 自检 ----------
d2 = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>',
                          open(HTML, encoding='utf-8').read(), re.S).group(1))
assert d2['version'] == '8.4' and len(d2['batches']) == 19 and len(d2['abandoned']) == 41
assert len(d2['watchlist']) == 35 and len(d2['stocks']) == 35
for b in d2['batches']:
    assert len(b['items']) == len(b['article']['teasers']), b['id']
teas_nos = sum(len(b['article']['teasers']) for b in d2['batches'])
item_nos = sum(len(b['items']) for b in d2['batches'])
print('自检通过：%d 期 / 摘要 %d 条 = 裁决 %d 条 / abandoned %d / watchlist %d'
      % (len(d2['batches']), teas_nos, item_nos, len(d2['abandoned']), len(d2['watchlist'])))
