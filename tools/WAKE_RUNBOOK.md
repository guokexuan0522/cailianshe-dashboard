# 财联社看板·第三层唤醒核验入池流水线 RUNBOOK

> 版本：v1.2（2026-10-23）｜适用：每天 00:30 / 12:45 / 16:00 / 23:45 四个唤醒时点
> 定位：唤醒会话的自包含执行手册。每次唤醒按本手册跑完整闭环，**幂等可重入**——已核验过的文章按 aid 自动跳过，重复唤醒不会重复入池。
> v1.1 变更：第二层云端自动入池引擎已上线（2026-10-20），§0 架构图、铁律第 9 条、§2 步骤 3（消费自动入池结果）、§5（二期上线说明）同步更新。
> v1.2 变更：新增「附：仓库自包含应急路径」完整方案（wake_bootstrap.py tarball 自举 + 路径映射 + api_push.py 令牌回退 + 双沙箱边界），根治唤醒任务跑在未配置裸沙箱连续 5 次阻断的问题；执行环境无 `/root/.codebuddy/monitor-mcp/` 时**直接按附录 A-D 执行**，§1 表格视作主沙箱参考。

---

## 0. 架构总览（三层流水线）

```
第一层  云端文章发现（GitHub Actions articles.yml，每30分钟）
        → 扫11个VIP栏目，过280豆门槛的新文章自动写入 云端仓库 pending/ 队列
第二层  云端安全自动入池【已上线 2026-10-20】（autopool.yml 每小时 :15/:45 运行）
        → pending/ 工单确定性预核验：公开点名字面匹配（新浪全量A股名单）+ 三重防护
          （板块分布校验 / 短名·通用词防护 / 统计提及防护），零模型推断
        → 产出 autopool/results/（可自动入池）与 autopool/routed/（转唤醒）
第三层  本地唤醒核验入池（本手册，每天4个时点）
        → 拉取云端 pending/ → 消费第二层 results/routed → 按 aid 跳过已核验
        → 逐篇公开信源取证 → 入池升版 → API推送 → Pages自动更新
```

**铁律（入池资格，2026-10-20 起生效，v6.0 用户授权修订版）**：
1. 入池标的必须满足以下之一：①文章公开摘要/公开转载**字面点名**该公司；②有可**逐字引用**的公开信源证据（公告原文、权威媒体标题/正文与摘要逐字对应）。
2. **严禁**由模型依据自身知识或推断补名。摘要没提的公司，检索不到公开出处，一律不入池。
3. 公开内容提到了几只就验证几只、入池几只；已删除的标的不回流。
4. **所有栏目统一 ≥280 微信豆**才入队核验（含金牌纪要库，取代原普通 280/金牌 380 双轨制）；低于 280 的文章一律不抓取、不比对、不入池（云端扫描层已过滤）。
5. 数据窗口：只处理 2026-10-11 及以后的文章。
6. 单文件看板不新建文件（脚本除外）；人工会话实质性修订必须升版。
7. **比对候选池（v6.0 新增）**：比对未成功的股票暂不入投研池，写入 MONITOR_DATA `candidates` 数组（字段同 watchlist 精简版：name/code/q/column/batchId/dateIn/pub/beans/reason/tags），标识「推断·待正文确认」；比对成功确认后移入 watchlist 并从 candidates 删除该条；入候选池第 10 个交易日仍未确认的，第 11 个交易日从看板彻底删除（candidates/图表/统计全部剔除）。
8. **交易日历（v6.0 新增）**：在池时长/10 日统计/21 日移出/候选池清退一律按交易日计算；2026 年国务院官方放假安排（含调休上班日）已内置页面 CAL_HOLIDAYS/CAL_MAKEUP，2027 年按法定假日预估，官方安排发布后必须校准。
9. **第二层自动入池结果消费（v6.1 新增）**：autopool/results/<aid>.json 为云端确定性预核验产物（带 evidence 点名原句 + 板块校验明细 + 行情/K线/分时/期次档案），唤醒层复核 evidence 与 skipped 后落地母版；routed/<aid>.json 必须走完整公开信源取证。第二层只预核验、不落地，母版唯一权威不变。

---

## 1. 环境与凭证

| 项 | 值 |
|---|---|
| 本地母版 | `/workspace/财联社·投研看板.html`（**唯一权威数据源**） |
| 云端仓库（本地克隆） | `/workspace/cailianshe-dashboard/` |
| 云端部署产物 | `cailianshe-dashboard/index.html`（= 母版副本，Pages 发布用） |
| 核验台账 | `/root/.codebuddy/monitor-mcp/verify_ledger.jsonl`（aid 幂等账） |
| 推送脚本 | `/root/.codebuddy/monitor-mcp/api_push.py`（GitHub Git Data API） |
| Token | `/root/.codebuddy/monitor-mcp/.gh_push_token`（600 权限，api_push.py 自动读取） |
| 采集核心 | `/workspace/cailianshe-dashboard/refresh.py`（fetch_quotes/fetch_kline/fetch_minute） |
| 第二层引擎 | `/workspace/cailianshe-dashboard/autopool.py`（云端 autopool.yml 每小时 :15/:45 驱动） |
| 第二层产物 | `cailianshe-dashboard/autopool/results/`（可自动入池）、`autopool/routed/`（转唤醒）、`autopool/processed.jsonl`（aid 幂等台账） |
| 第二层字典 | `cailianshe-dashboard/ref/`（all_names 全量名单缓存 / name_dict+pool_names 在池 overlay / generic_names 通用词黑名单） |
| 量化引擎 | `/root/.codebuddy/monitor-mcp/calc_signals.py`（`calc(kline, quote, price_in)`） |
| 线上地址 | https://guokexuan0522.github.io/cailianshe-dashboard/ |

推送命令（token 不明文，脚本内自动读文件）：
```bash
python3 /root/.codebuddy/monitor-mcp/api_push.py
```
注意：**推送前必须先把母版复制到云端仓库**（见 §5 步骤2），否则会把旧 index.html 推上去（v5.4 试跑时踩过此坑）。

---

## 2. 标准执行流程（每次唤醒照此执行）

### 步骤 1｜同步云端工单队列（5 分钟）
```bash
TOKEN=$(cat /root/.codebuddy/monitor-mcp/.gh_push_token)
# 列 pending 目录，下载本地缺失的工单 JSON 到 /workspace/cailianshe-dashboard/pending/
curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/guokexuan0522/cailianshe-dashboard/contents/pending"
# 对每个缺失文件：Accept: application/vnd.github.raw+json 下载
```
工单 JSON 关键字段：`aid`（台账匹配键）、`column`、`title`、`snippet`（公开摘要，核验主依据）、`related_stock`（板块分布，交叉校验用）、`beans`、`create_time`、`url`。

### 步骤 2｜计算待核验集合（幂等）
```bash
python3 - <<'EOF'
import json, os, glob
aids = {json.loads(l)['aid'] for l in open('/root/.codebuddy/monitor-mcp/verify_ledger.jsonl') if l.strip()}
todo = []
for f in glob.glob('/workspace/cailianshe-dashboard/pending/*.json'):
    if f.endswith('_scan_status.json'): continue
    d = json.load(open(f))
    if d.get('aid') not in aids and d.get('create_time','') >= '2026-10-11':
        todo.append(d)
print('待核验', len(todo), '篇')
EOF
```
**台账标题与 pending 标题格式不一致，必须用 aid 匹配，勿用标题匹配。**

### 步骤 3｜消费第二层自动入池结果（v6.1 新增）
```bash
ls /workspace/cailianshe-dashboard/autopool/results/   # 云端预核验通过、可自动入池
ls /workspace/cailianshe-dashboard/autopool/routed/    # 云端判定需唤醒层核验
```
对每个 `results/<aid>.json`：
1. **复核 evidence**（点名原句，如 `贵州茅台：「贵州茅台发布2026年三季报……」`）与 `boardCheck`（板块校验明细）；证据不足或与母版铁律冲突的，降级为完整核验。
2. **复核 skipped 字段**：被防护规则跳过的标的（`kind` = generic-name-risk 短名/通用词 / statistical-mention 统计提及）。若公开信源取证后认为应入池，可人工补入并在台账 note 说明理由。
3. `allInPool: true` 表示本篇点名公司均已在池——无需落地，记录后删除结果文件。
4. 直接落地：`entries` → `watchlist`（字段已齐：name/code/q/exch/column/batchId/dateIn/pub/beans/reason/priceIn/verifyTag/conf 等）；`stocks` → `zr.storage`（含 kline/minute）；`batch` → `batches`。**tech 字段为空**，需按步骤 5 用 calc_signals.py 计算补齐；`priceIn` 已按发布日收盘价口径预取，盘中发布文章需人工校正。
5. 落地即删：`rm autopool/results/<aid>.json` 并 git 提交（processed.jsonl 已记 aid，不会重复处理）。

对每个 `routed/<aid>.json`：读 `routeReason`/`routeDetail`（no-literal-match 无字面点名 / board-mismatch 板块校验不符 / generic-name-risk 短名通用词 / statistical-mention 统计提及 / price-unfetchable 价格无法核实 / quote-failed 行情失败），按步骤 4 完整核验。

### 步骤 4｜逐篇核验（核心，铁律执行）
对每篇工单：
1. 读 `snippet` 公开摘要，提取线索（通常 3 条，每条含题材标签+"这家公司"+业务特征）。
2. **板块分布校验**：`related_stock` 如 `[{"market":"主板","count":3}]` 是硬约束——确认的标的市场构成必须与之吻合；对不上即说明认错了公司，重新检索。
3. 逐条线索用 WebSearch 公开检索取证，检索词 = 摘要中的**独特业务短语**（如"掺铒光纤""374.9亿元""70余家行业龙头"），而非泛泛的公司名。
4. 判定标准（满足其一才入池）：
   - 权威媒体/公告原文与摘要**逐字对应**（最强证据）；
   - 摘要本身**字面点名**该公司（如风口研报洞察的"宏川智慧有望迎来拐点"）。
5. 无公开出处的线索：记录 `stock:""` 不入池，**严禁推断补名**。
6. 每篇核验完立即写台账（防中断丢失）：
```json
{"aid": 2508954, "col": "公告全知道", "date": "YYYY-MM-DD HH:MM", "tier": "night|day",
 "items": [{"clue": "摘要线索", "stock": "公司名", "code": "600000", "anchor": "逐字证据原文+出处", "new": true}],
 "note": "板块分布吻合情况、排除的同名干扰项及理由"}
```

### 步骤 5｜采集行情
```python
import sys; sys.path.insert(0,'/workspace/cailianshe-dashboard')
import refresh, json
q = refresh.fetch_quotes(['sh688183', ...])[q]   # price/prev/open/pct/high/low/vol/time
kline = refresh.fetch_kline(q)   # 80根前复权日K [date,open,close,high,low,vol]
minute = refresh.fetch_minute(q) # 267点分时
```
注意：`fetch_kline` 已兼容 `qfqday`/`day` 两种返回字段；个别股票仍失败时记 `kline: []` 并在汇报中说明，不要阻塞其他股票。

### 步骤 6｜写入母版四表 + 升版
参考 `/tmp/build_v54.py`（v5.4 试跑构建脚本，可复制改造）。必改四项：
1. `watchlist` 追加（字段：name/code/q/exch/margin/sector/reason/fundamental/outlook/tech/priceIn/priceNow/pct/gainSince/prob/forecast/conf/verifyTag/tier/beans/gold/pub/dateIn/price/verify）；
2. `stocks[q]` 写入 name/price/prev/change/pct/high/low/time/minute/kline；
3. `batches` 按期次追加（id 规范：`b{日期}_{栏目}`，栏目简写 ggzd=公告全知道/无后缀=早知道/lhb=狙击龙虎榜/dc=风口研报洞察/gold=金牌纪要库/sp=掘金行业龙头）；
4. `review.stocks` 追加 + `history` 追加 + `notes` 追加 + `version` 升 minor 版（v5.4→v5.5）+ `lastUpdated/collectTime` 更新。

tech 字段由 calc_signals.py 的 advice['tags'] 拼装（含 MA/MACD/RSI/KDJ/BOLL/BIAS/量比/20日区间；涨跌停日追加"R4涨跌停日指令降半级"）。
priceIn 口径 = 文章发布日收盘价（当日收盘后发布的文章，入池价即当日收盘）。

**写入前必做**：`cp 母版 /tmp/backup.html`；序列化用 `json.dumps(d, ensure_ascii=False, indent=1)` 且先做原块轮校验（原块重序列化必须与原文一致才允许回写）。

### 步骤 7｜推送云端 + 验证 Pages
```bash
cp /workspace/财联社·投研看板.html /workspace/cailianshe-dashboard/index.html  # 必须先做！
python3 /root/.codebuddy/monitor-mcp/api_push.py
# 等 ~90 秒查 Pages 构建：GET /repos/guokexuan0522/cailianshe-dashboard/pages/builds
# 断点续传拉线上页验证（CDN 会截断大文件，需循环 curl -C - 到完整字节数）
```
线上验证标准：版本号、watchlist 条数、新标的全部就位、10-19  batches、history 最新条。

---

## 3. 四个唤醒时点的分工建议

| 时点 | 场景 | 动作 |
|---|---|---|
| 00:30 | 夜间栏目（公告全知道/狙击龙虎榜，21-23 点发布）已入队 | 主核验时段：跑完整 §2 流程（含步骤 3 消费第二层 results/routed） |
| 12:45 | 午间档 | 轻量巡检：只跑 §2 步骤 1-2，有待核验篇目或 autopool 结果才继续 |
| 16:00 | 收盘后 | 轻量巡检 + 若 00:30 有遗漏篇目可补跑 |
| 23:45 | 全天收尾 | 兜底巡检：确保当日无漏核验、无未消费的 autopool 结果；有则补跑 |

每次唤醒结束必须向用户汇报：新核验篇数、新入池标的（名单+代码+一句话依据）、当日市场印证（涨跌幅）、版本号、线上链接状态、第二层消费情况（results 落地数 / routed 核验数）。

---

## 4. 已知坑与对策（v5.4 试跑实录 + v6.0 二期实录）

1. **推错文件**：api_push.py 推的是 `cailianshe-dashboard/index.html`，不是母版——推送前必须先 `cp` 母版过去。
2. **CDN 截断**：GitHub Pages CDN 对 1.9MB 文件会中断传输（拿到 800KB 残页），必须 `curl -C -` 循环续传至完整字节数再校验。
3. **Pages 构建偶发失败**：云端自动提交曾出现一次 build failed（同内容此前此后均 built）——失败时重推一次即可，Pages 失败不影响仓库数据。
4. **K 线字段差异**：部分标的（sh688635）返回 `day` 而非 `qfqday`，refresh.py 已修。
5. **停牌股**：三峡新材 10-20 复牌，停牌期行情为停牌价（pct=0），入池价取停牌价并在 note 说明。
6. **同名干扰项**：Seedance 2.0 首批接入有多家平台（天娱数科 CineART / 万兴科技万兴剧厂 / 德才股份奇想无限），按摘要措辞逐字锁定唯一匹配（"影视级AI视频创编平台"→CineART），排除项写入台账 note。
7. **板块分布是硬约束**：公告全知道主板1+创业1+科创1、龙虎榜主板3、早知道创业3+主板4+科创1——认出的股票市场构成必须与之吻合，这是防认错公司的关键校验。
8. **「机器人」类通用词陷阱**：002090 公司名"机器人"与高频行业词同形，风口研报摘要"……+机器人！这家公司……"中的"机器人"是题材标签不是点名——autopool 已内置通用词黑名单与 ≤3 字短名防护，命中即转唤醒，**唤醒层遇到疑似通用词务必先排除**。
9. **统计提及不算个股信号**：风口研报日报的"机构关注度排行前五名依次 A>B>C>D>E"是纯统计口径，无个股投资信号，仅记录不入池（autopool 的 statistical-mention 防护已按此判据实现；狙击龙虎榜栏目的龙虎榜/资金数据除外）。
10. **autopool 与本地推送并发**：autopool.yml 每小时 :15/:45 自动提交 autopool/ 与 ref/，本地 api_push 只推 index.html 等文件，双方改的文件不重叠；万一 push 被拒（non-fast-forward），重新基于远端 head 再推一次即可。
11. **北交所不在自动匹配范围**：新浪 hs_a 名单不含北交所股票，北交所公司字面点名不会命中字典 → 转唤醒层人工研判（安全方向）。

---

## 5. 二期已上线（第二层云端安全自动入池，2026-10-20 用户确认后开工并交付）

**边界**：只做确定性预核验，零模型推断。公开摘要/标题字面点名 + 新浪全量 A 股名单（5472 只，name→code 事实映射）+ 三重防护（板块分布校验 / 短名·通用词防护 / 统计提及防护）；"这家公司"代称类、通用词、统计提及一律转唤醒层。产出 results/ 与 routed/ 两类文件供第三层消费，**绝不直接改 index.html**。

**引擎**：`/workspace/cailianshe-dashboard/autopool.py`；工作流 `.github/workflows/autopool.yml`（每小时 :15/:45，只提交 autopool/ 与 ref/）。

**维护**：
- 通用词黑名单：`ref/generic_names.json`（当前仅"机器人"），发现新的同形词时追加；
- 名单缓存：`ref/all_names.json`（新浪抓取失败时回退，随每次运行自动刷新）；
- 在池 overlay：`ref/name_dict.json` + `ref/pool_names.json`，每次入池新标的后需同步更新（供 allInPool 判定与 sector/column 标注）；
- 测试方法：合成工单覆盖 auto/wake/skip 三路径 + 幂等二轮，见交付说明。



---

## 附：仓库自包含应急路径（v8.6.2 新增，根治"环境未配置"阻断）

**适用场景**：定时唤醒任务跑在未配置的裸沙箱（无 `/root/.codebuddy/monitor-mcp/`、无 `/workspace/cailianshe-dashboard/`、无 git 凭证）。这是唤醒任务自 2026-10-19 起连续 5 次阻断的根因形态，本节为根治方案。

**网络事实（沙箱内实测）**：`github.com` / `raw.githubusercontent.com` 不可达（git clone 不可用）；`codeload.github.com`（tarball 匿名下载）可达；`api.github.com`（Git Data API，需令牌写）可达；`www.cls.cn` / `qt.gtimg.cn` 等数据源可达。

### A. 第一步：自举下载仓库（替代 git clone）

```bash
python3 tools/wake_bootstrap.py            # 下载并解压到 /workspace/cls-repo/cailianshe-dashboard-main/
eval "$(python3 tools/wake_bootstrap.py | tail -1)"   # 或直接取 REPO_DIR
```

`wake_bootstrap.py` 从 `codeload.github.com` 匿名拉取 `main` 分支最新 tarball，解压即得**云端最新全量仓库**（含 index.html、tools/、pending/、autopool/、refresh.py），并自检关键依赖齐全。此后本手册所有路径均相对于 `$REPO_DIR`。

### B. 路径映射表（裸沙箱执行时一律以此为准）

| 依赖 | 裸沙箱路径（`$REPO_DIR` = 解压目录） |
|---|---|
| 本手册 | `$REPO_DIR/tools/WAKE_RUNBOOK.md` |
| 母版（唯一权威） | `$REPO_DIR/index.html`（= 云端部署产物，tarball 即云端最新态） |
| 核验台账 | `$REPO_DIR/tools/verify_ledger.jsonl` |
| 推送脚本 | `$REPO_DIR/tools/api_push.py` |
| 量化引擎 | `$REPO_DIR/tools/calc_signals.py` |
| 采集核心 | `$REPO_DIR/refresh.py` |
| 第二层引擎/产物 | `$REPO_DIR/autopool.py`、`$REPO_DIR/autopool/results/`、`$REPO_DIR/autopool/routed/` |
| pending 工单队列 | `$REPO_DIR/pending/*.json`（tarball 内即最新，等价于同步） |
| seen 状态 | `$REPO_DIR/seen/`、`$REPO_DIR/pending/_scan_status.json` |

### C. 令牌与推送

`api_push.py` 按优先级读取令牌：环境变量 `GH_TOKEN` → 脚本同目录 `.gh_push_token` → `/root/.codebuddy/monitor-mcp/.gh_push_token`。

推送命令（母版 + 台账一并回写，保证幂等账不丢）：

```bash
cd "$REPO_DIR"
GH_TOKEN=<令牌> python3 tools/api_push.py \
  --base "$REPO_DIR" \
  --files index.html,tools/verify_ledger.jsonl \
  --msg "wake: <版本号> 核验入池 <简述>"
```

**纪律**：无令牌时不得伪造"已推送"；应在汇报中明确"核验已完成、推送受阻（缺令牌）"，并把待推送内容完整留在 `$REPO_DIR` 供下次或人工会话落地——未知 ≠ 空集，不可把"推不出去"说成"无待核验"。

### D. 与主沙箱的边界

- 主沙箱（人工会话）的母版是 `/workspace/财联社·投研看板.html`，唤醒沙箱改的是 `$REPO_DIR/index.html`；两者内容应保持一致（主沙箱每次落地后推送云端）。**唤醒入池后，主沙箱下次会话应 `git pull` 同步回本地母版**，避免双写分歧。
- 唤醒沙箱每次运行都重新下载 tarball，天然获得云端最新态，无需持久化任何本地状态。
