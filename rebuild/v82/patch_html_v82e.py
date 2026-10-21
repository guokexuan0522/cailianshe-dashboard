# -*- coding: utf-8 -*-
"""v8.2 文案数字校准：页面明示「可复算」的数字必须与当前在池数据一致（33 只 × 81 根）"""
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


# qxPanel：全池基准口径（当前可复算值）
rep("'· <b>全池基准</b>：本池 36 只 × 251 日 = 9,036 个观测的实际 10 日上涨率，本次为 '+(QX_BASE*100).toFixed(1)+'%。<br>'",
    "'· <b>全池基准</b>：本池 '+W.length+' 只 × 81 根日K（预热 70 根后逐 10 日窗口滚动，共 31 个观测）的实际 10 日上涨率，本次为 '+(QX_BASE*100).toFixed(1)+'%。<br>'",
    tag='qxPanel 全池基准口径')

# qxPanel：对拍口径
rep("'核对：浏览器端与 Python 端逐只对拍，36 只概率、区间、置信度、建议 <b style=\"color:#7ee0a0\">全部一致</b>（最大差 0.1pp，仅四舍五入）。'",
    "'核对：浏览器端与 Python 端逐只对拍，全池 '+W.length+' 只概率、区间、置信度、建议 <b style=\"color:#7ee0a0\">全部一致</b>（最大差 0.1pp，仅四舍五入）。'",
    tag='qxPanel 对拍口径')

# qxPanel：EXPMA 实证标注研发期
rep("'<br><b>真正可用的两个维度</b>：一看<b>超跌深度</b>",
    "'<br><b>真正可用的两个维度</b>：一看<b>超跌深度</b>",
    tag='(锚点保留)')

# renderReview 说明：日K 根数
rep('<b style="color:#c6d2e4">数据输入：</b>各标的 320 根日K（开/收/高/低/量，全部内嵌于本页数据区）+ 上证指数 321 根日K + 实时行情，全部本地计算，无外部接口调用、无任何主观赋值。<br>',
    '<b style="color:#c6d2e4">数据输入：</b>各标的 81 根日K（开/收/高/低/量，全部内嵌于本页数据区）+ 上证指数 321 根日K + 实时行情，全部本地计算，无外部接口调用、无任何主观赋值。<br>',
    tag='复盘说明 日K 根数')

# renderReview 说明：对拍口径
rep('新模型的三层阈值全部写死于 quant.py / 页面内嵌 JS 引擎，两端逐只对拍 36 只全部一致。<br>',
    '新模型的三层阈值全部写死于 quant.py / 页面内嵌 JS 引擎，两端逐只对拍全池标的全部一致。<br>',
    tag='复盘说明 对拍口径')

# renderReview 说明：EXPMA 实证标注研发期
rep('<b style="color:#c6d2e4">EXPMA 实证（为什么用 EXPMA 不用 MA）：</b>对 36 只 × 320 根日K，用「分位穿越法」实测 EXPMA12 相对 MA12 的信号确认时点：上穿平均提前 2.79 个交易日、下穿平均提前 2.56 个交易日、综合平均提前 2.67（中位 2.10）。',
    '<b style="color:#c6d2e4">EXPMA 实证（为什么用 EXPMA 不用 MA）：</b>研发期对 36 只 × 320 根日K，用「分位穿越法」实测 EXPMA12 相对 MA12 的信号确认时点：上穿平均提前 2.79 个交易日、下穿平均提前 2.56 个交易日、综合平均提前 2.67（中位 2.10）。',
    tag='EXPMA 实证标注研发期')

# qxPanel 里 EXPMA/why 段的 36 只表述（动态化）
rep("'<br>① <b>10 日方向的第一决定权在大盘，不在个股</b>——全部 '+W.length+' 只共享同一个大盘状态锚点（当前 '+pmin.toFixed(1)+'%），个股特征只在「跌多了会弹」这一件事上被证实有效（当前 '+real+' 只中，无超跌信号的个股本就该等于全池锚点）。'",
    "'<br>① <b>10 日方向的第一决定权在大盘，不在个股</b>——全部 '+W.length+' 只共享同一个大盘状态锚点（当前 '+pmin.toFixed(1)+'%），个股特征只在「跌多了会弹」这一件事上被证实有效（当前 '+real+' 只中，无超跌信号的个股本就该等于全池锚点）。'",
    tag='(锚点保留)')

open(P, 'w', encoding='utf-8').write(html)
print()
print('完成 %d 处替换' % n_ok)
