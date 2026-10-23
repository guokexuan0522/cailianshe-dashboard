#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8.7 唤醒修复·幂等台账补登

背景：v8.5/v8.6 会话裁决了三篇文章（2507832/2510857/2511471），裁决结果已落
batches/watchlist/abandoned，但 aid 未登 verify_ledger.jsonl——导致第三层唤醒
按 aid 求差集时会重复核验这三篇（幂等失效）。

本脚本按台账标准格式补登三条记录（aid 精确匹配，不用标题匹配），
同步写入主沙箱台账与仓库 tools/ 台账，保持两者一致。
"""
import io, json, os, sys

RECORDS = [
    dict(aid='2507832', col='盘中宝', date='2026-10-21 00:30', tier='night',
         items=[
             dict(clue='摘要→人形机器人量产验证期（官方归因：凡拓数创+大业股份）',
                  stock='凡拓数创', code='301313',
                  anchor='财联社官方往期回顾（2509219/2510607文章页）+10-19/10-21 VIP日报逐字载明本文点评人形机器人方向，凡拓数创10-19 20cm涨停',
                  new=False),
             dict(clue='同上（板块分布创业板1+主板1第二席位）',
                  stock='大业股份', code='603278',
                  anchor='铁律⑤⑥负面排除：10-21异动公告自述腱绳产品尚未批量生产、未产生实质性收益；毛利率2023/2024/2025分别8.25%/2.90%/6.33%盈利能力相对有限',
                  new=False),
         ],
         note='v8.5官方归因裁决：v8.0时代行业误判（新能源量产验证期）纠正为人形机器人；凡拓数创已由2507397①入池不重复；大业股份负面排除；本篇无新标的，留痕备查。v8.7补登（此前漏登aid）。'),
    dict(aid='2510857', col='盘中宝', date='2026-10-21 00:30', tier='night',
         items=[
             dict(clue='摘要①→固态电池（自研平台/实验阶段·无唯一硬锚点）',
                  stock='', code='',
                  anchor='行业经原文页确认为固态电池，但「自研平台」「多个项目进入实验阶段」无唯一硬锚点；先导智能/国轩高科无官方归因支撑且原记录板块归属写反',
                  new=False),
         ],
         note='按铁律③宁缺毋滥放弃；v8.5已将原2条错误审计记录（金盘科技串位自2510883/先导智能板块写反）合并重写为1条，留痕备查。v8.7补登（此前漏登aid）。'),
    dict(aid='2511471', col='公告全知道', date='2026-10-21 23:30', tier='night',
         items=[
             dict(clue='摘要①「1.6T AWG芯片已实现小批量出货」',
                  stock='仕佳光子', code='688313',
                  anchor='仕佳光子投资者关系记录逐字原话（全球唯二供应商），与摘要逐字互证；已由2511175③入池不重复',
                  new=False),
             dict(clue='摘要②「人形机器人刀具已形成小批量订单」',
                  stock='', code='',
                  anchor='华锐精密「获宇树科技小批量订单」与恒锋工具「中小批量订单明显增多」两家高度相似，无唯一硬锚点，放弃',
                  new=False),
             dict(clue='摘要③「2亿美元词元跨境服务订单已完成合同签署」',
                  stock='润建股份', code='002929',
                  anchor='巨潮投资者关系记录表逐字确认，10-19/20/21三连板；已由webcheck裁决入池（batchId=wc20261021）',
                  new=False),
         ],
         note='v8.6源头补抓+逐字比对裁决（与用户截图一致）：仕佳光子/润建股份入池（后者经webcheck通道）、刀具线索放弃。v8.7补登（此前漏登aid）。'),
]

LEDGERS = [
    '/root/.codebuddy/monitor-mcp/verify_ledger.jsonl',
    '/workspace/cailianshe-dashboard/tools/verify_ledger.jsonl',
]

def existing_aids(path):
    if not os.path.isfile(path):
        return set()
    s = set()
    for l in open(path, encoding='utf-8', errors='ignore'):
        if l.strip():
            try: s.add(str(json.loads(l)['aid']))
            except Exception: pass
    return s

def main():
    for path in LEDGERS:
        have = existing_aids(path)
        add = [r for r in RECORDS if str(r['aid']) not in have]
        if not add:
            print('%s：三条 aid 均已存在，跳过' % path)
            continue
        with io.open(path, 'a', encoding='utf-8') as f:
            for r in add:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        print('%s：补登 %d 条（%s）' % (path, len(add), ', '.join(str(r['aid']) for r in add)))
    return 0

if __name__ == '__main__':
    sys.exit(main())
