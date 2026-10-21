#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全网比对决策消费（v7.5）：把 webcheck_decisions.jsonl（AI 全网比对结论）应用到 index.html。

每条决策：
  action=pool     → 入投研池（抓 K 线嵌入 stocks，看板自动重算真实概率）
  action=candidate → 进比对候选池
  action=abandon  → 进「已放弃」审计区（宁缺毋滥，可见可复盘）
同时把 MONITOR_DATA.webcheck / autopool/pending_webcheck.json 中对应线索标记为已处理。

幂等：landed.log 记录已入池 code；webcheck 已 done/abandoned 的不重复处理。
"""
import json
import os
import re
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, "index.html")
DECISIONS = os.path.join(ROOT, "autopool", "webcheck_decisions.jsonl")
LANDED_LOG = os.path.join(ROOT, "autopool", "landed.log")
WEBCHECK_PATH = os.path.join(ROOT, "autopool", "pending_webcheck.json")

from refresh import fetch_kline, fetch_quotes  # noqa: E402


def today():
    return datetime.date.today().strftime("%Y-%m-%d")


def load_landed():
    s = set()
    if os.path.exists(LANDED_LOG):
        for ln in open(LANDED_LOG, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                s.add(ln)
    return s


def main():
    decisions = []
    if os.path.exists(DECISIONS):
        for ln in open(DECISIONS, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                decisions.append(json.loads(ln))
    if not decisions:
        print("no decisions")
        return 0

    html = open(HTML, encoding="utf-8").read()
    m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
    d = json.loads(m.group(1))
    wl = d.get("watchlist", [])
    if isinstance(wl, dict):
        wl = list(wl.values())
    pooled = {w.get("code") for w in wl}
    landed = load_landed()
    abandoned = d.get("abandoned") or []
    aband_keys = {(a.get("aid"), a.get("code") or a.get("match")) for a in abandoned}
    webcheck = d.get("webcheck") or []

    new_pool = []
    for dec in decisions:
        aid = str(dec.get("aid"))
        action = dec.get("action")
        # 标记 webcheck 对应线索，并取回其 pub（文章发布日）作为入池日口径
        pub_date = ""
        for w in webcheck:
            if str(w.get("aid")) != aid:
                continue
            b = w.get("bullet", "")
            mk = dec.get("match") or ""
            if mk and mk not in b:
                continue
            if not pub_date:
                pub_date = str(w.get("pub") or "")[:10]
            if w.get("status") == "pending":
                w["status"] = action
                w["resolvedTo"] = dec.get("name") or ""
                w["verdict"] = dec.get("verdict") or dec.get("reason") or ""
        if not pub_date:
            pub_date = str(dec.get("pub") or "")[:10]
        if action == "pool":
            code = dec.get("code")
            q = dec.get("q")
            if not code or not q:
                continue
            if code in pooled or (aid + ":" + code) in landed:
                continue
            try:
                kl = fetch_kline(q)
            except Exception as e:
                print("kline FAIL %s: %s" % (q, e))
                continue
            try:
                qt = fetch_quotes([q]).get(q) or {}
            except Exception:
                qt = {}
            price_now = float(qt.get("price") or (kl[-1][3] if kl else 0))
            prev = float(qt.get("prev") or (kl[-2][3] if len(kl) > 1 else price_now))
            # priceIn：文章发布日（含）之后首个交易日收盘价（与 autopool/母版口径一致）
            price_in = price_now
            for bar in kl:
                if str(bar[0])[:10] >= pub_date:
                    price_in = round(bar[3], 2)
                    break
            date_in = pub_date or today()
            st = {
                "name": dec.get("name"), "price": price_now, "prev": prev,
                "change": round(price_now - prev, 2),
                "pct": qt.get("pct", 0), "high": qt.get("high"),
                "low": qt.get("low"), "time": qt.get("time"), "minute": [],
                "kline": kl,
            }
            d.setdefault("stocks", {})[q] = st
            wl.append({
                "name": dec.get("name"), "code": code, "q": q,
                "exch": dec.get("exch") or (["sh"] if q.startswith("sh") else ["sz"]),
                "margin": False, "sector": dec.get("sector") or "",
                "reason": dec.get("verdict", ""),
                "fundamental": "（全网比对确认·AI自主研判）" + dec.get("verdict", "")[:70],
                "outlook": "", "dateIn": date_in, "pub": dec.get("pub") or date_in,
                "beans": dec.get("beans"), "tier": "webcheck",
                "priceIn": price_in, "priceNow": round(price_now, 2),
                "gainSince": round((price_now / price_in - 1) * 100, 2) if price_in else 0.0,
                "verifyTag": "全网比对确认", "verify": True, "tech": "",
                "forecast": "—", "prob": None, "probStatic": 55,
                "conf": dec.get("conf") or "mid",
                "pct": st["pct"], "price": round(price_now, 2),
                "column": dec.get("column"), "batchId": "wc" + date_in.replace("-", ""),
                "verifyBasis": "WEB-UNIQ",
            })
            pooled.add(code)
            new_pool.append(dec.get("name"))
        elif action == "abandon":
            key = (aid, dec.get("code") or dec.get("match"))
            if key in aband_keys:
                continue
            abandoned.append({
                "aid": aid, "name": dec.get("name") or "（匿名线索）",
                "code": dec.get("code") or "", "match": dec.get("match") or "",
                "column": dec.get("column") or "", "dateIn": today(),
                "reason": dec.get("reason") or "",
            })
            aband_keys.add(key)
        # candidate 动作暂不在此脚本处理（land.py 已负责候选池）

    if new_pool or any(w.get("status") != "pending" for w in webcheck) or abandoned:
        d["watchlist"] = wl
        d["abandoned"] = abandoned
        d["webcheck"] = webcheck
        base = d.get("lastUpdated", "").split("（")[0].strip()
        n_ab = sum(1 for x in abandoned if x.get("dateIn") == today())
        d["lastUpdated"] = base + "（" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + \
            " 全网比对：" + str(len(new_pool)) + " 只确认入池 / 今日累计放弃 " + str(n_ab) + " 条）"
        new_raw = json.dumps(d, ensure_ascii=False, indent=1)
        html = html[:m.start(1)] + new_raw + html[m.end(1):]
        open(HTML, "w", encoding="utf-8").write(html)
        json.dump(webcheck, open(WEBCHECK_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        with open(LANDED_LOG, "a", encoding="utf-8") as f:
            for w in wl:
                if w.get("verifyBasis") == "WEB-UNIQ":
                    f.write(w.get("batchId", "") + ":" + w.get("code", "") + "\n")
        print("OK 全网比对应用：入池 %s；放弃审计 %d 条；webcheck 总数 %d（待处理 %d）" % (
            "、".join(new_pool) or "无新增",
            len(abandoned), len(webcheck),
            sum(1 for w in webcheck if w.get("status") == "pending")))
    else:
        print("OK no changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
