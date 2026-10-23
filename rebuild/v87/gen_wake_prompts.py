#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8.7 唤醒任务定版 prompt 生成器（供 scheduler-api.sh update 使用）。

用法：python3 gen_wake_prompts.py <任务ID> <时段>
  时段：main(00:30主核验) / noon(12:45午间) / close(16:00收盘) / night(23:45兜底)
输出该任务的完整 prompt 到 stdout（含 <GH_TOKEN> 占位符，替换后使用）。

设计要点（v8.7 自包含方案）：
  - 不依赖 /root/.codebuddy/monitor-mcp/、不依赖 git clone（沙箱均不可用）
  - 第0步 codeload tarball 自举下载仓库；一切路径相对 $REPO
  - 母版=$REPO/index.html；台账=$REPO/tools/verify_ledger.jsonl
  - 推送=api.github.com Git Data API（tools/api_push.py，GH_TOKEN 环境变量）
  - 与云端 land.py 协作：唤醒层入池即写 watchlist，land.py 按 pooled_codes 自动跳过，不双重入池
"""
import sys

COMMON_HEAD = """财联社投研看板·第三层唤醒核验任务（{slot_desc}）。铁律与自包含执行路径如下，严格遵守。

■ 第0步·环境自举（每次必做；本沙箱无 git 凭证、github.com 不可达，禁止使用 git clone）：
mkdir -p /workspace/cls-repo && cd /workspace/cls-repo
curl -sL -o repo.tgz "https://codeload.github.com/guokexuan0522/cailianshe-dashboard/tar.gz/refs/heads/main"
rm -rf cailianshe-dashboard-main && tar xzf repo.tgz
export REPO=/workspace/cls-repo/cailianshe-dashboard-main
自检：ls "$REPO/tools/" 须含 WAKE_RUNBOOK.md/api_push.py/calc_signals.py/verify_ledger.jsonl；wc -c "$REPO/index.html" 应约 2MB。失败则报告 HTTP 码/超时，不得静默跳过。

■ 执行标准：读 $REPO/tools/WAKE_RUNBOOK.md，按 §2 步骤执行；本环境无 /root/.codebuddy/monitor-mcp/，一切路径以 $REPO 为根（见 RUNBOOK v1.5 附录 B 路径映射表）。母版=$REPO/index.html，台账=$REPO/tools/verify_ledger.jsonl，采集=$REPO/refresh.py，量化=$REPO/tools/calc_signals.py，第二层产物=$REPO/autopool/results|routed/。

■ 铁律（不可违背）：
1. 只入池「公开摘要字面点名」或「可逐字引用公开信源证据」的标的；严禁依据自身知识推断补名；摘要没提的公司检索不到公开出处一律不入池。
2. 摘要条数=股票数硬上限；板块分布 related_stock 是硬约束，认出的股票市场构成必须与之吻合。
3. 幂等：按 aid 与 tools/verify_ledger.jsonl 求差集（两侧 aid 都转 int 再比较；台账 aid 一律写整数，禁止字符串），已核验跳过（勿用标题匹配）；台账不可得时报「无法计算」，不得以「无待核验工单」结报（未知≠空集）。
4. 每篇核验完立即写台账并单独推送（台账是唤醒侧独占只追加文件，防超时/并发丢进度）：追加 $REPO/tools/verify_ledger.jsonl 一行后立即执行
   cd "$REPO" && GH_TOKEN=<GH_TOKEN> python3 tools/api_push.py --base "$REPO" --files tools/verify_ledger.jsonl --rebase-retry 3 --msg "wake: 台账 aid <AID>"
   land.py 可能并发提交导致 non-fast-forward，脚本会自动按新 HEAD 重建重试（最多 3 次）；重试仍失败就继续核验下一篇，末尾统一补推，不得中断流程。
5. 入池价口径：文章发布日收盘价；盘中发布的文章按当日收盘校正（先落 priceIn 草稿值，收盘后巡检时段校正）。
6. 与云端 land.py 协作：唤醒层入池即写入 index.html watchlist，land.py 按 pooled_codes 自动跳过，不会双重入池；results 文件无需删除。
7. 无 GH_TOKEN 时：完成核验+本地落地+写台账，汇报明确「推送受阻（缺令牌）」，把待推送文件清单列清，不得伪造成功。
8. 版本字段纪律（母版规则，与云端 land.py 惯例一致）：只写数据记录（watchlist/stocks/batches/candidates/review），严禁修改 version/lastUpdated/collectTime 字段及任何 HTML/CSS/JS——定时任务无权升版，版本只在人工会话由用户驱动更新；本次变更写进 review.notes 即可。
"""

COMMON_TAIL = """
■ 推送（有 GH_TOKEN 时）：
- 台账收尾补推（逐篇推送已按铁律 4 执行，此处确保无遗漏）：
  cd "$REPO" && GH_TOKEN=<GH_TOKEN> python3 tools/api_push.py --base "$REPO" --files tools/verify_ledger.jsonl --rebase-retry 3 --msg "wake: {msg_hint} 台账收尾"
- 母版（单次推送，严禁 --rebase-retry——会覆盖 land.py 并发落地，脚本内已拦截）：
  cd "$REPO" && GH_TOKEN=<GH_TOKEN> python3 tools/api_push.py --base "$REPO" --files index.html --msg "wake: {msg_hint}"
推送后汇报 commit 短哈希。母版推送若报 422 non-fast-forward，如实报告「母版推送受阻（云端并发）」，留待下轮重做，不得带重试强推。Pages 约 1-3 分钟自动更新（https://guokexuan0522.github.io/cailianshe-dashboard/）。

■ 汇报格式：①自举结果（下载字节/自检）②待核验篇数与清单③逐篇裁决（入池标的+代码+一句话逐字证据/放弃理由）④行情采集与技术评分情况⑤数据落地与推送状态（version 字段按铁律 8 未动，留待人工会话升版）⑥异常与风险。
"""

MAIN_BODY = """■ 完整闭环（00:30 主核验时段）：
① 待核验集合：pending/*.json 与 tools/verify_ledger.jsonl 按 aid 求差集（两侧 aid 都 int(str(aid)) 归一化后比较；create_time≥2026-10-11）。
② 消费 $REPO/autopool/results/<aid>.json：复核 evidence 点名原句与 boardCheck 板块校验明细；证据不足降级为完整核验；复核 skipped 防护标的（generic-name-risk/statistical-mention），确应入池的可人工补入并在台账 note 说明。allInPool=true 的直接记录跳过。
③ 逐篇核验：读 snippet 公开摘要提取线索（每条含题材标签+「这家公司」+业务特征）；用 WebSearch 公开检索取证，检索词=摘要中的独特业务短语（非泛泛公司名）；权威媒体/公告原文与摘要逐字对应才入池。
④ 每篇核验完立即追加 tools/verify_ledger.jsonl 并按铁律 4 单独推送台账（--files tools/verify_ledger.jsonl --rebase-retry 3）。
⑤ 确认标的用 $REPO/refresh.py 采集行情/K线/分时（qt.gtimg.cn 可达）；$REPO/tools/calc_signals.py 算技术评分（MA/MACD/RSI/KDJ/BOLL/BIAS/量比/20日区间；涨跌停日追加「R4涨跌停日指令降半级」）。
⑥ 写入母版 $REPO/index.html 数据表：watchlist 追加（name/code/q/exch/margin/sector/reason/fundamental/outlook/tech/priceIn/priceNow/pct/gainSince/prob/forecast/conf/verifyTag/tier/beans/gold/pub/dateIn/price/verify）；stocks[q] 写 name/price/prev/change/pct/high/low/time/minute/kline；batches 按期次追加（id 规范：b{日期}_{栏目}，栏目简写 ggzd=公告全知道/无后缀=早知道/lhb=狙击龙虎榜/dc=风口研报洞察/gold=金牌纪要库/sp=掘金行业龙头）；review.stocks+history+notes 追加（本次变更记入 notes）。**严禁修改 version/lastUpdated/collectTime 字段及任何 HTML/CSS/JS——定时任务无权升版**。写入前备份 index.html 到 $REPO/index.html.bak；序列化用 json.dumps(d, ensure_ascii=False, indent=1)，回写后必须 JSON.parse 自检 + 保证 </script> 闭合。
⑦ 推送 + 汇报。
若待核验集合为空：简要汇报「无待核验工单」+ 自举与环境自检结果，不要空跑入池流程。
"""

PATROL_BODY = """■ 轻量巡检（{slot_desc2}）：
① 自举 + 待核验清点（同主核验口径）。
② 若为空：汇报「巡检：无待核验工单」+ results 待消费清单 + 一行环境自检，即结束，不要空跑。
③ 若非空：按 RUNBOOK §2 步骤 3-7 执行完整核验入池闭环（公开信源取证→写台账→采集行情→写母版四表数据记录（不升版）→推送→汇报）。{extra}
"""

NIGHT_EXTRA = "本时段为全天兜底：须确认当日四个时段无漏核验、无未消费 results；有遗漏必须补跑完整闭环。"
CLOSE_EXTRA = "本时段行情已含当日 15:00 收盘：入池价 priceIn 按当日收盘口径落定，无需再校正；对午间入池的标的核对 priceIn 是否为当日收盘。"
NOON_EXTRA = "本时段入池的标的若为盘中发布文章，priceIn 先按最新价落草稿并在台账 note 标注「待收盘校正」，16:00 巡检时段校正。"

PROMPTS = {
    'main': COMMON_HEAD.format(slot_desc='00:30 主核验时段') + MAIN_BODY + COMMON_TAIL.format(msg_hint='v8.7 核验入池'),
    'noon': COMMON_HEAD.format(slot_desc='12:45 午间巡检时段') + PATROL_BODY.format(slot_desc2='午间巡检', extra=NOON_EXTRA) + COMMON_TAIL.format(msg_hint='v8.7 午间巡检核验'),
    'close': COMMON_HEAD.format(slot_desc='16:00 收盘后巡检时段') + PATROL_BODY.format(slot_desc2='收盘后巡检', extra=CLOSE_EXTRA) + COMMON_TAIL.format(msg_hint='v8.7 收盘巡检核验'),
    'night': COMMON_HEAD.format(slot_desc='23:45 全天兜底时段') + PATROL_BODY.format(slot_desc2='全天兜底巡检', extra=NIGHT_EXTRA) + COMMON_TAIL.format(msg_hint='v8.7 兜底巡检核验'),
}

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[2] not in PROMPTS:
        sys.stderr.write('用法: %s <任务ID> <main|noon|close|night>\n' % sys.argv[0])
        sys.exit(1)
    sys.stdout.write(PROMPTS[sys.argv[2]])
