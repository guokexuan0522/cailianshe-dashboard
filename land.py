#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三层落地（v7.5 全自动版）：把 autopool 预核验结果落地到 index.html。

用户铁律（2026-10-21 亲定，优先于此前一切条款）：
  ① 价格 ≥280 微信豆是抓取层硬关（scan/autopool 已执行）。
  ② 摘要条数 = 股票数量硬上限（autopool 层已执行；本层再做一次安全网）。
  ③ 全网比对确认：摘要未字面点名的匿名线索进入「待全网比对」队列
     （pending_webcheck.json + 看板 webcheck 区），由 AI 自主用公开信源比对：
     匹配上→入池；匹配度高→候选池；匹配不上→放弃（宁缺毋滥）。
  ④ 笼统行业文/无一一对应特征→彻底放弃。
  ⑤ 非公告类栏目点名声股票需有明确正向催化剂才考虑（autopool 层 trend-unconfirmed）。
  ⑥ 负面消息绝对排除（negative-signal）→ 进「已放弃」审计区，绝不入池/入候选。

本脚本（云端每日自动运行，land.yml 触发）：
  - 公告类栏目且非 STAT/负面的 entry → 投研池（同时嵌入 K 线，看板自动重算真实概率）
  - STAT / trend-unconfirmed / 匿名 → 候选池 或 待全网比对队列
  - negative-signal → 已放弃（审计可见）
幂等：autopool/landed.log 防重复落地；webcheck/abandoned 按 (aid,code/name) 去重。
"""
import json
import os
import re
import glob
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, "index.html")
RESULTS_DIR = os.path.join(ROOT, "autopool", "results")
ROUTED_DIR = os.path.join(ROOT, "autopool", "routed")
LANDED_LOG = os.path.join(ROOT, "autopool", "landed.log")
WEBCHECK_PATH = os.path.join(ROOT, "autopool", "pending_webcheck.json")

ANNOUNCE_COLS = {'公告全知道', '公告', '盘中宝', '电报', '公告解读',
                 '公告早知道', '公告掘金'}
STAT_KW = ['研报', '评级', '覆盖', '首度覆盖', '关注度', '新财富',
           '深度覆盖', '上调', '机构', '排行']
NEGATIVE_KW = ['衰落', '盈利能力下降', '业绩下滑', '出现亏损', '亏损', '减持', '违规',
               '处罚', '退市', '爆雷', '暴跌', '萎缩', '走下坡', '景气度下行',
               '需求萎缩', '价格下跌', '产能过剩', '评级下调', '目标价下调']


def teaser_count(snippet):
    return len([s for s in re.split(r'(?=[\u2460-\u2465])', snippet or '') if s.strip()])


def today():
    return datetime.date.today().strftime("%Y-%m-%d")


def now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def load_landed():
    s = set()
    if os.path.exists(LANDED_LOG):
        for ln in open(LANDED_LOG, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                s.add(ln)
    return s


def build_pool_entry(e, j):
    d = today()
    return {
        "name": e["name"],
        "code": e["code"],
        "q": e.get("q"),
        "exch": e.get("exch") or [],
        "margin": bool(e.get("margin")),
        "sector": e.get("sector") or "",
        "reason": e.get("reason", ""),
        "fundamental": "（自动落地）" + (e.get("reason", "")[:70]),
        "outlook": "",
        "dateIn": e.get("dateIn") or d,
        "pub": e.get("pub") or d,
        "beans": e.get("beans"),
        "tier": "auto",
        "priceIn": float(e.get("priceNow") or e.get("priceIn") or 0),
        "priceNow": float(e.get("priceNow") or e.get("priceIn") or 0),
        "gainSince": 0.0,
        "verifyTag": e.get("verifyTag") or "摘要确认",
        "verify": True,
        "tech": "",
        "forecast": "—",
        "prob": None,
        "probStatic": 55,
        "conf": e.get("conf") or "low",
        "pct": 0.0,
        "price": float(e.get("priceNow") or e.get("priceIn") or 0),
        "column": e.get("column"),
        "batchId": e.get("batchId") or ("b" + d),
        "verifyBasis": "UNIQ",
    }


def build_candidate(e, j, level, source):
    return {
        "name": e.get("name", ""),
        "code": e.get("code", ""),
        "q": e.get("q"),
        "exch": e.get("exch") or [],
        "sector": e.get("sector") or "",
        "column": e.get("column") or j.get("column"),
        "dateIn": e.get("dateIn") or today(),
        "pub": e.get("pub") or j.get("pub") or today(),
        "beans": e.get("beans"),
        "level": level,
        "reason": e.get("reason") or j.get("title", ""),
        "source": source,
    }


def split_bullets(snippet):
    return [s.strip() for s in re.split(r'(?=[\u2460-\u2465])', snippet or "") if s.strip()]


def main():
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        print("ERROR: MONITOR_DATA not found")
        return 1
    d = json.loads(m.group(1))

    wl = d.get("watchlist", [])
    if isinstance(wl, dict):
        wl = list(wl.values())
    pooled_codes = {w.get("code") for w in wl if isinstance(w, dict)}
    landed = load_landed()
    cands = d.get("candidates") or []
    cand_keys = {(c.get("name"), c.get("code"), c.get("column")) for c in cands if isinstance(c, dict)}
    abandoned = d.get("abandoned") or []
    aband_keys = {(a.get("aid"), a.get("code") or a.get("name")) for a in abandoned if isinstance(a, dict)}
    webcheck = d.get("webcheck") or []
    wc_keys = {(w.get("aid"), w.get("bullet", "")[:20]) for w in webcheck if isinstance(w, dict)}

    new_pool, new_cand, new_aband, new_wc = [], [], [], []

    for F in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")) +
                    glob.glob(os.path.join(ROUTED_DIR, "*.json"))):
        try:
            j = json.load(open(F, encoding="utf-8"))
        except Exception:
            continue
        aid = str(j.get("aid"))
        snippet = j.get("snippet") or j.get("evidence") or ""
        t_cap = teaser_count(snippet)

        # ---- results：entries 逐条按铁律分类 ----
        pool_from_this = 0
        for e in j.get("entries", []):
            code = e.get("code")
            name = e.get("name")
            if not code or not name:
                continue
            if aid + ":" + code in landed or code in pooled_codes:
                continue
            reason = (e.get("reason") or "") + " " + (e.get("ev") or "")
            col = (e.get("column") or "").strip()
            # 铁律⑥：负面绝对排除
            if any(k in reason for k in NEGATIVE_KW):
                if (aid, code) not in aband_keys:
                    new_aband.append({"aid": aid, "name": name, "code": code,
                                      "column": col, "dateIn": today(),
                                      "reason": "负面信号（铁律⑥：绝不逆向选择）：" + reason[:80]})
                    aband_keys.add((aid, code))
                continue
            # 公告类 + 非 STAT → 投研池（受摘要条数硬上限约束）
            is_stat = any(k in reason for k in STAT_KW)
            if (col in ANNOUNCE_COLS) and not is_stat:
                if t_cap and pool_from_this >= t_cap:
                    # 铁律②安全网：本篇入池已达摘要条数上限，多余的降级候选
                    ck = (name, code, col)
                    if ck not in cand_keys:
                        new_cand.append(build_candidate(e, j, "OVER-CAP", "results"))
                        cand_keys.add(ck)
                    continue
                rec = build_pool_entry(e, j)
                new_pool.append(rec)
                pooled_codes.add(code)
                pool_from_this += 1
                # 嵌入 K 线/行情 → 看板自动重算真实概率
                st = (j.get("stocks") or {}).get(e.get("q"))
                if st and st.get("kline"):
                    d.setdefault("stocks", {})[e.get("q")] = st
            else:
                ck = (name, code, col)
                if ck not in cand_keys:
                    lvl = "STAT" if is_stat else "TREND"
                    new_cand.append(build_candidate(e, j, lvl, "results"))
                    cand_keys.add(ck)

        # ---- routed（wake）：匿名线索 → 待全网比对队列 ----
        if j.get("outcome") == "wake" and j.get("column"):
            bullets = split_bullets(snippet)
            for b in bullets:
                key = (aid, b[:20])
                if key in wc_keys:
                    continue
                new_wc.append({
                    "aid": aid, "column": j.get("column"),
                    "title": j.get("title", ""), "pub": j.get("pub") or today(),
                    "dateIn": today(), "beans": j.get("beans"),
                    "bullet": b, "status": "pending",
                })
                wc_keys.add(key)
            if not bullets:
                key = (aid, "")
                if key not in wc_keys:
                    new_wc.append({
                        "aid": aid, "column": j.get("column"),
                        "title": j.get("title", ""), "pub": j.get("pub") or today(),
                        "dateIn": today(), "beans": j.get("beans"),
                        "bullet": j.get("title", ""), "status": "pending",
                    })
                    wc_keys.add(key)

        # ---- results 中被跳过的 generic-name-risk / label-chain-risk 进全网比对队列 ----
        # 注意：skip 分两类处置——
        #   进队列（需公开信源取证补名）：generic-name-risk（短名/通用词）、
        #     label-chain-risk（概念标签串，公司名只是标签之一）
        #   不进队列（证据已充分否定，直接留痕即可）：negative-signal（铁律⑥）、
        #     statistical-mention（统计口径提及）、trend-unconfirmed（无正向催化剂）
        for s in j.get("skipped", []):
            if s.get("kind") in ("generic-name-risk", "label-chain-risk") and s.get("name"):
                key = (aid, s.get("ev", s.get("name", ""))[:20])
                if key in wc_keys:
                    continue
                new_wc.append({
                    "aid": aid, "column": j.get("column"),
                    "title": j.get("title", ""), "pub": j.get("pub") or today(),
                    "dateIn": today(), "beans": j.get("beans"),
                    "bullet": (s.get("ev") or s.get("name") or "")[:120],
                    "status": "pending",
                })
                wc_keys.add(key)

    changed = False
    if new_pool:
        wl.extend(new_pool)
        d["watchlist"] = wl
        changed = True
    if new_cand:
        cands.extend(new_cand)
        d["candidates"] = cands
        changed = True
    if new_aband:
        abandoned.extend(new_aband)
        d["abandoned"] = abandoned
        changed = True
    if new_wc:
        webcheck.extend(new_wc)
        d["webcheck"] = webcheck
        changed = True
    if changed:
        base = d.get("lastUpdated", "").split("（")[0].strip()
        d["lastUpdated"] = base + "（" + now_ts() + " 自动落地 " + str(len(new_pool)) + " 只入投研池 / " + \
            str(len(new_cand)) + " 条进比对候选池 / " + str(len(new_wc)) + " 条待全网比对 / " + \
            str(len(new_aband)) + " 条负面放弃）"
        new_raw = json.dumps(d, ensure_ascii=False, indent=1)
        html = html[:m.start(1)] + new_raw + html[m.end(1):]
        open(HTML, "w", encoding="utf-8").write(html)
        with open(LANDED_LOG, "a", encoding="utf-8") as f:
            for rec in new_pool:
                f.write(rec["batchId"] + ":" + rec["code"] + "\n")
        # 待全网比对队列落盘（供 AI 会话消费 + 审计）
        json.dump(webcheck, open(WEBCHECK_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("OK 落地：投研池+%d，候选池+%d，待全网比对+%d，负面放弃+%d" % (
            len(new_pool), len(new_cand), len(new_wc), len(new_aband)))
        for r in new_pool:
            print("  [投研池] %s %s (%s)" % (r["name"], r["code"], r["column"]))
        for c in new_cand:
            print("  [候选] %s%s (%s/%s)" % (c["name"] or "匿名", c["code"], c["column"], c["level"]))
        for a in new_aband:
            print("  [放弃] %s %s (%s)" % (a["name"], a["code"], a["column"]))
        for w in new_wc:
            print("  [待比对] %s | %s" % (w["column"], w["bullet"][:50]))
    else:
        print("OK nothing new to land")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
