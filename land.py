#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三层落地（v7.4 自动化）：把 autopool 预核验结果落地到 index.html。

读取 autopool/results/*.json（outcome=auto，含 entries）与 autopool/routed/*.json（outcome=wake），
按严格铁律分类：
  - 投研池：栏目属于「公告类」且 reason 非研报统计提及的 entry（UNIQ/ADS 明确信号）
  - 比对候选池：研报统计提及（STAT）/ 匿名指代（NONE）/ wake 路由的匿名线索
dashboard 加载时会用 kline 对入池股票重算真实概率；无 kline 的新代码走 probStatic 兜底。

幂等：autopool/landed.log 记录已落地的 batchId:code，重复运行不重复落地。
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

# 公告类栏目：条目视为 UNIQ/ADS 明确信号，可入投研池
ANNOUNCE_COLS = {"公告全知道", "公告", "盘中宝", "电报", "公告解读",
                 "公告早知道", "公告掘金", "公告全知道·夜", "公告全知道·午"}
# 研报统计提及关键词：命中则判 STAT（无个股投资信号），进候选池
STAT_KW = ["研报", "评级", "覆盖", "首度覆盖", "关注度", "新财富",
           "深度覆盖", "上调", "机构", "排行"]


def classify(entry):
    col = (entry.get("column") or "").strip()
    reason = entry.get("reason") or ""
    if any(k in reason for k in STAT_KW):
        return "candidate", "STAT"
    if col in ANNOUNCE_COLS:
        return "pool", "UNIQ"
    return "candidate", "NONE"


def load_landed():
    s = set()
    if os.path.exists(LANDED_LOG):
        for ln in open(LANDED_LOG, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                s.add(ln)
    return s


def today():
    return datetime.date.today().strftime("%Y-%m-%d")


def now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


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
        "fundamental": "（自动落地，待人工研判补充）" + (e.get("reason", "")[:60]),
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
    out = {
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
    return out


def main():
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        print("ERROR: MONITOR_DATA not found")
        return 1
    raw = m.group(1)
    d = json.loads(raw)

    wl = d.get("watchlist", [])
    if isinstance(wl, dict):
        wl = list(wl.values())
    pooled_codes = {w.get("code") for w in wl if isinstance(w, dict)}
    landed = load_landed()
    cands = d.get("candidates") or []
    cand_keys = {(c.get("name"), c.get("code"), c.get("column")) for c in cands if isinstance(c, dict)}

    new_pool, new_cand = [], []
    for F in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json")) +
                   glob.glob(os.path.join(ROUTED_DIR, "*.json"))):
        try:
            j = json.load(open(F, encoding="utf-8"))
        except Exception:
            continue
        aid = str(j.get("aid"))
        # results 的 entries
        for e in j.get("entries", []):
            code = e.get("code")
            name = e.get("name")
            if not code or not name:
                continue
            key = aid + ":" + code
            if key in landed or code in pooled_codes:
                continue
            cls, lvl = classify(e)
            if cls == "pool":
                rec = build_pool_entry(e, j)
                new_pool.append(rec)
                pooled_codes.add(code)
            else:
                ck = (name, code, e.get("column"))
                if ck not in cand_keys:
                    new_cand.append(build_candidate(e, j, lvl, "results"))
                    cand_keys.add(ck)
        # routed：匿名线索，整篇进候选池
        if j.get("outcome") == "wake" and j.get("column"):
            title = j.get("title", "")
            ck = ("", "", j.get("column"))
            if ck not in cand_keys:
                new_cand.append({
                    "name": "", "code": "", "q": None, "exch": [],
                    "sector": "", "column": j.get("column"),
                    "dateIn": today(), "pub": j.get("pub") or today(),
                    "beans": j.get("beans"), "level": "NONE",
                    "reason": title, "source": "routed",
                })
                cand_keys.add(ck)

    changed = False
    if new_pool:
        wl.extend(new_pool)
        d["watchlist"] = wl
        changed = True
    if new_cand:
        cands.extend(new_cand)
        d["candidates"] = cands
        changed = True
    if changed:
        base = d.get("lastUpdated", "").split("（")[0].strip()
        d["lastUpdated"] = base + "（" + now_ts() + " 自动落地 " + str(len(new_pool)) + " 只入投研池 / " + str(len(new_cand)) + " 条进比对候选池）"
        new_raw = json.dumps(d, ensure_ascii=False, indent=1)
        html = html[:m.start(1)] + new_raw + html[m.end(1):]
        open(HTML, "w", encoding="utf-8").write(html)
        with open(LANDED_LOG, "a", encoding="utf-8") as f:
            for rec in new_pool:
                f.write(rec["batchId"] + ":" + rec["code"] + "\n")
        print("OK landed %d -> 投研池, %d -> 比对候选池" % (len(new_pool), len(new_cand)))
        for r in new_pool:
            print("  [投研池] %s %s (%s)" % (r["name"], r["code"], r["column"]))
        for c in new_cand:
            print("  [候选] %s%s (%s/%s)" % (c["name"] or "匿名", c["code"], c["column"], c["level"]))
    else:
        print("OK nothing new to land (all pre-verified results already consumed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
