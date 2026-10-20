#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财联社·投研看板 数据刷新核心（守护进程与手动触发共用）

母版铁律（最高优先级）：
  1. 唯一文件：只原地修改 /workspace/财联社·投研看板.html 内 MONITOR_DATA JSON；
     禁改 HTML 结构 / CSS / JS 与 version 字段；禁建备份文件（原子替换，不留残file）。
  2. 本模块只做【行情/分时/K线/复盘数值】的机械刷新与【文章公开信息检索】，
     不新增入池标的、不写研判结论（期次核验与复盘文字由会话内 Agent 完成）。
"""
import datetime
import fcntl
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

HTML_PATH = '/workspace/财联社·投研看板.html'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_PATH = os.path.join(BASE_DIR, 'refresh.lock')
STATUS_PATH = os.path.join(BASE_DIR, 'status.json')
LOG_PATH = os.path.join(BASE_DIR, 'daemon.log')
PENDING_DIR = os.path.join(BASE_DIR, 'pending')
SEEN_PATH = os.path.join(BASE_DIR, 'seen_articles.json')

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

SLOT_LABEL = {'close': '15:35收盘采集', 'night': '0:30夜间复核'}
SLOTS = ('close', 'night')
BEANS_MIN = 280          # 微信豆门槛（2026-10-15 用户决策）：仅采集实付≥280豆的收费文章


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass
    print(line, flush=True)


def http_get(url, gbk=False, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        final = r.geturl()
    text = raw.decode('gbk', 'ignore') if gbk else raw.decode('utf-8', 'ignore')
    return text, final


def md5_of(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_status():
    try:
        with open(STATUS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_status(patch):
    """合并式写 status.json（带独立锁，避免与守护进程心跳互相覆盖）"""
    with open(LOCK_PATH + '.status', 'a') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            st = read_status()
            st.update(patch)
            tmp = STATUS_PATH + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(st, f, ensure_ascii=False, indent=1)
            os.replace(tmp, STATUS_PATH)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ---------------------------------------------------------------- 行情抓取
def fetch_quotes(codes):
    text, _ = http_get('https://qt.gtimg.cn/q=' + ','.join(codes), gbk=True)
    quote = {}
    for line in text.strip().split(';'):
        m = re.match(r'v_(\w+)="(.*)"', line.strip())
        if not m:
            continue
        f = m.group(2).split('~')
        if len(f) < 37:
            continue
        quote[m.group(1)] = {
            'price': float(f[3] or 0), 'prev': float(f[4] or 0), 'open': float(f[5] or 0),
            'pct': float(f[32] or 0), 'high': float(f[33] or 0), 'low': float(f[34] or 0),
            'vol': int(float(f[36] or 0)), 'time': f[30] or '',
        }
    missing = [c for c in codes if c not in quote]
    if missing:
        raise RuntimeError('行情缺失: %s' % missing)
    bad = [c for c in codes if quote[c]['price'] <= 0 or quote[c]['prev'] <= 0]
    if bad:
        raise RuntimeError('行情异常（疑似停牌/零价）: %s' % bad)
    return quote


def fetch_minute(q):
    text, _ = http_get('https://ifzq.gtimg.cn/appstock/app/minute/query?code=%s' % q)
    j = json.loads(text)
    pts = j['data'][q]['data']['data']
    return [[p.split(' ')[0] + ' ', float(p.split(' ')[1])] for p in pts if ' ' in p]


def fetch_kline(q):
    text, _ = http_get(
        'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?param=%s,day,,,80,qfq' % q)
    j = json.loads(text)
    node = j['data'][q]
    day = node.get('qfqday') or node.get('day')  # 部分标的返回 day 字段（如 sh688635）
    return [[c[0], float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in day]


def quote_date(qd):
    """从 f[30] 提取行情日期 YYYY-MM-DD（兼容 20261014150003 与 2026-10-14 15:00:03）"""
    digits = re.sub(r'\D', '', qd.get('time', ''))
    if len(digits) >= 8:
        return '%s-%s-%s' % (digits[0:4], digits[4:6], digits[6:8])
    return ''


def quote_hhmm(qd):
    digits = re.sub(r'\D', '', qd.get('time', ''))
    if len(digits) >= 12:
        return digits[8:10] + ':' + digits[10:12]
    return ''


# ---------------------------------------------------------------- 主刷新
def run(job='close'):
    """执行一次刷新。job: close=15:35收盘全量 / night=0:30夜间复核。
    返回 dict: {ok, job, skipped, detail...}"""
    if job not in SLOTS:
        return {'ok': False, 'error': 'unknown job %r' % job}
    lock = open(LOCK_PATH, 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log('刷新请求被拒绝：另一刷新正在进行（%s）' % job)
        return {'ok': False, 'error': '另一刷新正在进行'}
    try:
        return _run_locked(job)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _run_locked(job):
    started = datetime.datetime.now()
    today = started.strftime('%Y-%m-%d')
    now_hm = started.strftime('%H:%M')
    log('===== 刷新开始 job=%s =====' % job)
    try:
        html = open(HTML_PATH, encoding='utf-8').read()
    except OSError as e:
        log('读取母版失败: %s' % e)
        return {'ok': False, 'error': '读取母版失败: %s' % e}
    m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        log('未找到 MONITOR_DATA 数据块')
        return {'ok': False, 'error': 'MONITOR_DATA 数据块不存在'}
    try:
        d = json.loads(m.group(1))
    except ValueError as e:
        log('MONITOR_DATA JSON 解析失败: %s' % e)
        return {'ok': False, 'error': 'JSON 解析失败: %s' % e}

    version = d.get('version')
    watchlist = d.get('watchlist') or []
    codes = [w['q'] for w in watchlist]
    if not codes:
        log('watchlist 为空，终止')
        return {'ok': False, 'error': 'watchlist 为空'}

    # ---- 抓行情 ----
    try:
        quote = fetch_quotes(codes)
    except Exception as e:
        log('行情抓取失败: %s' % e)
        write_status({'lastRunAt': started.strftime('%Y-%m-%d %H:%M:%S'), 'lastRunStatus': 'error',
                      'lastJob': job, 'lastError': '行情抓取失败: %s' % e})
        return {'ok': False, 'error': '行情抓取失败: %s' % e}
    q0 = quote[codes[0]]
    session = quote_date(q0)          # 行情数据所属交易日
    weekday = started.weekday()       # 0=周一
    log('行情时间 %s | 数据交易日 %s | 今天 %s（周%s）' % (q0['time'], session, today, '一二三四五六日'[weekday]))

    # ---- 文章公开信息检索（独立于行情，全自动，尽力而为不阻塞）----
    art = check_articles()
    art_txt = ('文章检索：发现 %d 篇新文章待核验' % art['new']) if art.get('ok') else ('文章检索失败（不阻塞）：%s' % art.get('error', '?'))
    if art.get('ok') and art.get('skipped'):
        art_txt += '，价格门槛/免费文章跳过 %d 篇（源：%s）' % (art['skipped'], art.get('source', '?'))
    if art.get('ok') and art.get('failed'):
        art_txt += '，抓取失败 %d 篇（不标记已见，下轮重试）' % art['failed']
    log(art_txt)

    # ---- 交易日判定 ----
    if job == 'close' and session != today:
        if weekday >= 5:
            log('周末休市，跳过收盘采集')
            _record_skipped(today, job, started, '周末休市', session)
            return {'ok': True, 'skipped': True, 'reason': '周末休市', 'session': session}
        log('行情数据非今日（%s），疑似假日或数据延迟，跳过' % session)
        _record_skipped(today, job, started, '非交易日或数据未更新', session)
        return {'ok': True, 'skipped': True, 'reason': '非交易日或数据未更新', 'session': session}
    if not session:
        log('无法解析行情日期，终止')
        return {'ok': False, 'error': '无法解析行情日期'}

    # ---- 抓 K 线（判定/追加日烛）----
    kline = {}
    kline_err = None
    for q in codes:
        for attempt in range(3):
            try:
                kl = fetch_kline(q)
                if kl and kl[-1][0] == session:
                    kline[q] = kl
                    break
                if job == 'night' or attempt == 2:
                    kline[q] = kl if kl else []
                    if kl and kl[-1][0] != session:
                        log('%s K线末日 %s != 行情日 %s（第%d次尝试）' % (q, kl[-1][0], session, attempt + 1))
                else:
                    time.sleep(15)
            except Exception as e:
                kline_err = str(e)
                log('%s K线抓取异常: %s' % (q, e))
                if attempt == 2:
                    kline[q] = []
    if job == 'close' and any((not kline.get(q)) or kline[q][-1][0] != session for q in codes):
        log('K线数据未就绪，本次终止（不写文件）')
        return {'ok': False, 'error': 'K线数据未就绪: %s' % (kline_err or '末烛日期不符')}

    # ---- 抓分时（仅收盘任务）----
    minute = {}
    if job == 'close':
        for q in codes:
            try:
                minute[q] = fetch_minute(q)
                log('  %s 分时 %d 点' % (q, len(minute[q])))
            except Exception as e:
                log('  %s 分时抓取失败: %s' % (q, e))
                minute[q] = []
        if any(len(minute.get(q, [])) < 200 for q in codes):
            fewest = min(len(minute.get(q, [])) for q in codes)
            log('分时点数不足（最少 %d 点 < 200），按护栏跳过（不写文件）' % fewest)
            return {'ok': True, 'skipped': True, 'session': session,
                    'reason': '盘中分时数据不足（最少 %d 点 < 200 点护栏），未写入文件；待 15:35 收盘采集自动刷新' % fewest}

    # ---- 应用更新 ----
    changed = []
    for w in watchlist:
        q = w['q']
        qd = quote[q]
        price = qd['price']
        pct = qd['pct']
        gain = round((price / w['priceIn'] - 1) * 100, 2) if w.get('priceIn') else w.get('gainSince')
        for key, val in (('priceNow', price), ('pct', pct), ('gainSince', gain), ('price', price)):
            if w.get(key) != val:
                w[key] = val
                changed.append('%s.%s' % (w.get('name', q), key))
        s = d['stocks'].get(q)
        if s is None:
            log('警告：stocks 缺少 %s，跳过行情库' % q)
            continue
        new_s = {'price': price, 'prev': qd['prev'], 'change': round(price - qd['prev'], 2),
                 'pct': pct, 'high': qd['high'], 'low': qd['low'], 'time': qd['time']}
        for k, v in new_s.items():
            if s.get(k) != v:
                s[k] = v
                changed.append('%s.%s' % (q, k))
        if minute.get(q):
            s['minute'] = minute[q]
        kl = kline.get(q) or []
        if kl and kl[-1][0] == session:
            old = s.get('kline') or []
            if old and old[-1][0] == session:
                if [float(x) for x in old[-1][1:6]] != [float(x) for x in kl[-1][1:6]]:
                    s['kline'] = kl
                    changed.append('%s.kline(末烛更新)' % q)
            else:
                s['kline'] = kl
                changed.append('%s.kline(追加%s)' % (q, session))
        elif kl:
            log('%s K线末日 %s 与行情日 %s 不符，保留原K线' % (q, kl[-1][0], session))

    # ---- 复盘数值同步（不改写文字结论）----
    rv = d.get('review') or {}
    rvmap = {x.get('name'): x for x in (rv.get('stocks') or [])}
    for w in watchlist:
        r = rvmap.get(w.get('name'))
        if not r:
            continue
        for key, val in (('price', w.get('priceNow')), ('pct', w.get('pct')), ('gainSince', w.get('gainSince'))):
            if r.get(key) != val:
                r[key] = val
                changed.append('review.%s.%s' % (w.get('name'), key))

    # ---- 头部 ----
    if job == 'close':
        hhmm = quote_hhmm(q0)
        closed = hhmm >= '15:00'
        d['lastUpdated'] = '%s %s（%s·自动）' % (today, now_hm, SLOT_LABEL['close'])
        d['collectTime'] = d['lastUpdated']
        d['quoteTime'] = '%s %s 收盘' % (session, hhmm if closed else now_hm)
        d['period'] = '%s 收盘' % session
        if rv.get('date') != session[5:]:
            rv['date'] = session[5:]           # MM-DD
    else:
        d['lastUpdated'] = '%s %s（%s·自动）' % (today, now_hm, SLOT_LABEL['night'])
        d['collectTime'] = d['lastUpdated']

    # ---- history（同日同槽去重，替换而非堆积）----
    note = '守护进程定时采集（%s·版本不变）：%d只在池标的行情同步至%s，%s；复盘数值同步。' % (
        SLOT_LABEL[job], len(watchlist), session,
        ('分时/K线已更新' if job == 'close' else '夜间复核'))
    hist = d.get('history') or []
    tag = 'auto-%s-%s' % (session, job)
    if hist and isinstance(hist[-1], dict) and hist[-1].get('note', '').startswith('守护进程定时采集') \
            and hist[-1].get('time', '').startswith(today) and job == 'night':
        hist[-1]['time'] = '%s %s' % (today, now_hm)
        hist[-1]['note'] = note
    else:
        hist.append({'version': version, 'time': '%s %s' % (today, now_hm), 'note': note})
    d['history'] = hist

    # ---- 原子回写（结构外文本逐字节保证不变）----
    prefix, suffix = html[:m.start(1)], html[m.end(1):]
    new_html = prefix + json.dumps(d, ensure_ascii=False, indent=1) + suffix
    assert new_html[:len(prefix)] == prefix, 'JSON 块之前文本被改动'
    assert new_html[len(new_html) - len(suffix):] == suffix, 'JSON 块之后文本被改动'
    tmp = HTML_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(new_html)
    os.replace(tmp, HTML_PATH)

    # ---- 校验 ----
    chk_html = open(HTML_PATH, encoding='utf-8').read()
    m2 = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', chk_html, re.S)
    chk = json.loads(m2.group(1))
    assert chk['version'] == version, 'version 被改动'
    assert len(chk['watchlist']) == len(watchlist), 'watchlist 数量被改动'
    if job == 'close':
        assert all(len(chk['stocks'][w['q']]['minute']) > 200 for w in chk['watchlist']), '分时校验失败'
        assert all(chk['stocks'][w['q']]['kline'][-1][0] == session for w in chk['watchlist']), 'K线末日校验失败'
    elapsed = (datetime.datetime.now() - started).total_seconds()
    result = {'ok': True, 'job': job, 'session': session, 'changed': len(changed),
              'md5': md5_of(HTML_PATH), 'elapsed': round(elapsed, 1), 'article': art}
    write_status({'lastRunAt': started.strftime('%Y-%m-%d %H:%M:%S'), 'lastRunStatus': 'ok',
                  'lastJob': job, 'lastError': None, 'lastResult': result,
                  'runs': _merge_runs(read_status().get('runs'), today, job, result)})
    log('刷新完成：%d 项变更 | md5 %s | 耗时 %.1fs' % (len(changed), result['md5'], elapsed))
    return result


def _merge_runs(runs, today, job, result):
    runs = dict(runs or {})
    runs['%s:%s' % (today, job)] = {'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'ok': result.get('ok')}
    # 只保留最近 30 条
    keys = sorted(runs.keys())[-30:]
    return {k: runs[k] for k in keys}


def _record_skipped(today, job, started, reason, session):
    """护栏跳过（周末/非交易日）也落 runs 记录（ok=True+reason）——
    让定时任务状态可观测：跳过是正常处理结果，不是失败（2026-10-18 修复）。"""
    write_status({'lastRunAt': started.strftime('%Y-%m-%d %H:%M:%S'),
                  'lastRunStatus': 'ok', 'lastJob': job, 'lastError': None,
                  'lastResult': {'ok': True, 'skipped': True, 'reason': reason, 'session': session},
                  'runs': _merge_runs(read_status().get('runs'), today, job, {'ok': True})})
    log('槽位 %s:%s 已记录（%s）' % (today, job, reason))


# ---------------------------------------------------------------- 文章检索（直连财联社VIP公众号，去搜狗）
FEED_PATH = os.path.join(BASE_DIR, 'feed.json')


def load_feed():
    """读取 feed.json：album=财联社VIP专辑列表固定链接（全自动主来源，无需登录）；
    biz/cookie=公众号历史消息接口授权（可选备用）。"""
    try:
        with open(FEED_PATH, encoding='utf-8') as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except (OSError, ValueError):
        d = {}
    d.setdefault('album', '')
    d.setdefault('biz', '')
    d.setdefault('cookie', '')
    return d


# ---------------------------------------------------------------- cls.cn 直抓发现源（2026-10-19 起主来源）
# 背景：微信专辑 JSON 接口自 2026-10-18 19:19 起停止更新，导致夜报文章漏抓；
# 且专辑列表未登录仅返回最新一屏，历史文章结构性缺失（10-11~10-18 窗口 136 篇从未入过库）。
# 财联社官网 cls.cn 与公众号「财联社VIP」同源发布，detail/{id} SSR 页面与签名 API 均可无登录直抓
# （价格口径：articlePrice 元 × 10 = 微信豆，与公众号 fee 字段实测一致）。
CLS_COLUMNS = {
    20015: ('盘中宝', 280),
    20021: ('风口研报', 280),
    20091: ('玩转ETF', 280),
    20026: ('电报解读', 280),
    20025: ('财联社早知道', 280),
    20023: ('数据研选', 280),
    20013: ('九点特供', 280),
    20022: ('公告全知道', 280),
    20014: ('狙击龙虎榜', 280),
    20087: ('金牌纪要库', 280),      # v6.2：全栏目统一 280 豆门槛（金牌 380 旧双轨制废除）
    20072: ('风口专家会议', 280),
}
COL_OBSERVED = []      # 本轮观测到的真实分类（含未达门槛文章，仅登记留档）
CLS_PAGES = 3          # 每栏目最多翻页数（3×20=60 篇，覆盖约 10 天，足以跨过任何断更窗口）
CLS_CAND_CAP = 400     # 单轮处理候选上限（超出部分不标记已见，下轮继续，绝静默丢弃）
DATA_WINDOW_START = '2026-10-11'   # 铁律：母版数据只从 2026-10-11 起；更早的文章标记已见但不入待核验队列
CLS_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


def _cls_flatten(k, v):
    """cls.cn 签名参数平铺（dict 按 key.upper() 排序，与服务端签名算法一致，2026-10-19 实测）。"""
    if v is None or isinstance(v, (str, int, float, bool)):
        if isinstance(v, bool):
            v = 'true' if v else 'false'
        return '%s=%s' % (k, v)
    if isinstance(v, list):
        if not v:
            return '%s[]' % k
        return '&'.join(_cls_flatten('%s[%d]' % (k, i), x) for i, x in enumerate(v))
    if isinstance(v, dict):
        return '&'.join(_cls_flatten('%s[%s]' % (k, kk), x)
                        for kk, x in sorted(v.items(), key=lambda t: t[0].upper()))
    return '%s=%s' % (k, v)


def _cls_req(url, referer='https://www.cls.cn/vip'):
    req = urllib.request.Request(url, headers={
        'User-Agent': CLS_UA, 'Referer': referer,
        'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'zh-CN,zh;q=0.9'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', 'ignore')


def cls_api(path, **params):
    """cls.cn 签名 API：sign = md5(sha1(qs).hexdigest())，qs = 参数字典排序平铺连接。"""
    params.setdefault('os', 'web')
    params.setdefault('sv', '8.7.9')
    params.setdefault('app', 'CailianpressWeb')
    qs = '&'.join([_cls_flatten(k, params[k])
                   for k in sorted(params.keys(), key=lambda x: x.upper())
                   if _cls_flatten(k, params[k])])
    sign = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
    q = dict(params)
    q['sign'] = sign
    url = 'https://www.cls.cn%s?%s' % (path, urllib.parse.urlencode(q))
    return json.loads(_cls_req(url))


def cls_article_detail(aid):
    """SSR 详情页 → articleDetail（title/brief/ctime/articlePrice/isFree）；失败返回 None。"""
    html = _cls_req('https://www.cls.cn/detail/%s' % aid, referer='https://www.cls.cn/')
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None
    nd = json.loads(m.group(1))
    pp = nd.get('props', {}).get('pageProps', {})
    return pp.get('articleDetail') or pp.get('article') or None


def _cls_articles_of(r):
    """栏目列表响应兼容提取（data 为 list 或 {articles:[]} 两种形态均实测出现过）。"""
    d = r.get('data')
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        return d.get('articles') or d.get('data') or []
    return []


def real_column(title, parent):
    """v6.2：看板分类严格以文章标题【】前缀的真实分类为准。
    父栏目 feed 混装子栏目（实测：风口研报 feed 同时含【风口研报·公司】【风口研报·洞察】
    【机构调研】等），父栏目名仅作无前缀时的回退。分类随文章自主增减，不设白名单。"""
    m = re.match(r'^\s*【([^】]{2,24})】', (title or '').strip())
    return m.group(1).strip() if m else parent


COLUMNS_REG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ref', 'columns.json')


def bump_columns_registry(cols):
    """v6.2：ref/columns.json 动态分类注册表——每轮采集把观测到的真实分类计数留档
    （含未达门槛仅登记分类的文章），看板据此自主增减分类。"""
    try:
        reg = {}
        if os.path.exists(COLUMNS_REG_PATH):
            try:
                reg = json.load(open(COLUMNS_REG_PATH, encoding='utf-8'))
            except ValueError:
                reg = {}
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        for c in cols:
            e = reg.setdefault(c, {'count': 0, 'first_seen': now})
            e['count'] = int(e.get('count', 0)) + 1
            e['last_seen'] = now
        os.makedirs(os.path.dirname(COLUMNS_REG_PATH), exist_ok=True)
        with open(COLUMNS_REG_PATH, 'w', encoding='utf-8') as f:
            json.dump(reg, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log('  分类注册表写入失败（不影响主流程）: %s' % e)


def fetch_cls_columns(pages=CLS_PAGES):
    """cls.cn 签名 API 全自动发现文章（主来源）：遍历 11 个 VIP 栏目翻页拉取最近文章。
    子栏目（大佬持仓跟踪/掘金行业龙头/机构调研/风口研报·公司·行业·洞察/季报高增长等）
    均随父栏目 feed 下发，无需单独配置（2026-10-19 实测 12 篇漏抓文章全部命中）。
    返回 (articles, ok)：ok=False 表示接口整体失败，调用方降级到专辑源。"""
    out = []
    ok_any = False
    for ctype, (name, beans_min) in CLS_COLUMNS.items():
        last_time = 0
        col_n = 0
        try:
            for _ in range(max(1, pages)):
                r = cls_api('/featured/v1/column/detail/load', last_time=last_time, type=ctype, rn=20)
                arts = _cls_articles_of(r)
                if not arts:
                    break
                ok_any = True
                for a in arts:
                    a_title = (a.get('title') or '').strip()
                    a_column = real_column(a_title, name)
                    COL_OBSERVED.append(a_column)
                    out.append({
                        'aid': a.get('id'),
                        'title': a_title,
                        'ctime': a.get('ctime') or a.get('sort_score') or 0,
                        'column': a_column,
                        'beans_min': beans_min,
                        'brief': (a.get('brief') or '').strip(),
                        'related_stock': a.get('related_stock') or [],
                    })
                    col_n += 1
                if len(arts) < 20:
                    break
                last_time = arts[-1].get('ctime') or arts[-1].get('sort_score') or 0
                time.sleep(0.4)
        except Exception as e:
            log('  cls.cn 栏目 %s(type=%s) 拉取失败: %s' % (name, ctype, e))
        if col_n:
            log('  cls.cn 栏目 %-8s 发现 %d 篇' % (name, col_n))
        time.sleep(0.3)
    return out, ok_any


def _norm_title(t):
    return re.sub(r'\s+', '', t or '')


def _lcp_len(a, b):
    """最长公共前缀长度。"""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def _title_seen(title, seen_norms):
    """跨源标题判重（2026-10-19）：微信标题与 cls.cn 标题存在同文不同截断/表述
    （实例：金牌纪要库 CXO 篇微信版截断于「订单沿临床前…」，官网版续以「海外14家CXO…」，
    40 字前缀去重会漏），故按最长公共前缀 ≥20 字判重；实测 136 篇互撞为零，阈值安全。"""
    nt = _norm_title(title)
    if not nt:
        return False
    for nk in seen_norms:
        if nk and (nt == nk or _lcp_len(nt, nk) >= 20):
            return True
    return False


def fetch_album_list(album_url):
    """经财联社VIP专辑列表 JSON 接口（f=json）全自动发现文章 (url, title, create_time, pos)；
    无需登录/无需Cookie/无反爬，是文章采集的主来源。失败返回 []。"""
    if not album_url:
        return []
    try:
        base = album_url.split('#')[0]
        headers = dict(UA)
        headers['User-Agent'] = ('Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 '
                                 '(KHTML, like Gecko) Chrome/88.0.4324.181 Mobile Safari/537.36')
        out = []
        seen_url = set()
        begin = 0
        # 循环翻页直到无新增（未登录时腾讯仅返回第一屏最新20篇，翻页会被限，靠"无新增即停"退出）
        for _ in range(60):
            page_url = base + ('&' if '?' in base else '?') + 'begin=%d&count=100&f=json' % begin
            req = urllib.request.Request(page_url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read().decode('utf-8', 'ignore'))
            resp = (j.get('getalbum_resp') or {})
            arts = resp.get('article_list') or []
            if not arts:
                break
            new_count = 0
            for a in arts:
                u = (a.get('url') or '').replace('&amp;', '&').strip()
                title = (a.get('title') or '').strip()
                if u and u not in seen_url:
                    seen_url.add(u)
                    out.append({
                        'url': u,
                        'title': title,
                        'create_time': a.get('create_time') or '',
                        'pos': a.get('pos_num') or '',
                    })
                    new_count += 1
            if new_count == 0:
                break  # 翻页未推进（未登录限制），停止
            if not resp.get('continue_flag'):
                break
            begin += len(arts)
            time.sleep(0.5)
        log('  album 列表发现文章 %d 篇' % len(out))
        return out
    except Exception as e:
        log('  album 列表获取失败: %s' % e)
        return []


def fetch_biz_list(biz, cookie):
    """经公众号历史消息接口列出最近文章 (url, title)；需 biz + 有效 cookie，失败返回 []。"""
    if not biz or not cookie:
        return []
    try:
        headers = dict(UA)
        headers['Cookie'] = cookie
        headers['Referer'] = 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=%s' % biz
        req = urllib.request.Request(
            'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=%s&f=json' % biz, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            home = json.loads(r.read().decode('utf-8', 'ignore'))
        token = home.get('appmsg_token') or ''
        if not token:
            return []
        req2 = urllib.request.Request(
            'https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz=%s&f=json&appmsg_token=%s&lang=zh_CN&count=10'
            % (biz, urllib.request.quote(token)), headers=headers)
        with urllib.request.urlopen(req2, timeout=15) as r:
            j = json.loads(r.read().decode('utf-8', 'ignore'))
        data = json.loads(j.get('general_msg_list') or '{}')
        out = []
        for item in data.get('list', []):
            ai = item.get('app_msg_ext_info') or {}
            url = (ai.get('content_url') or '').replace('&amp;', '&')
            title = ai.get('title') or ''
            if url:
                if url.startswith('/'):
                    url = 'https://mp.weixin.qq.com' + url
                out.append((url, title))
        return out
    except Exception as e:
        log('  biz 列表获取失败: %s' % e)
        return []


def extract_fee(text):
    """从公众号文章页 HTML 提取实付微信豆：页面 fee: '2800' ÷ 10 = 280 豆（1元=10微信豆）。
    非付费文章或字段缺失返回 None。"""
    m = re.search(r"fee:\s*'(\d+)'", text)
    if not m:
        return None
    return int(m.group(1)) // 10


def _article_public_part(url):
    """抓取公众号文章公开部分：标题 + 免费引语/摘要（正文前若干段，截断）+ 实付微信豆(fee)"""
    text, final = http_get(url, timeout=15)
    fee = extract_fee(text)
    title = ''
    mt = re.search(r'<meta property="og:title" content="([^"]*)"', text)
    if mt:
        title = mt.group(1)
    if not title:
        ht = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if ht:
            title = re.sub(r'<[^>]+>', '', ht.group(1)).strip()
    body = re.search(r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*</div>', text, re.S)
    seg = body.group(1) if body else text
    seg = re.sub(r'<script.*?</script>', ' ', seg, flags=re.S)
    seg = re.sub(r'<style.*?</style>', ' ', seg, flags=re.S)
    seg = re.sub(r'<[^>]+>', '\n', seg)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in seg.split('\n')]
    lines = [x for x in lines if x]
    snippet = '\n'.join(lines[:40])[:1500]
    return title.strip(), snippet, final, fee


def _fetch_article_with_retry(url, tries=3):
    """单篇文章抓取（带重试与退避，抗腾讯未登录访问的瞬时限流）。
    返回 (title, snippet, final, fee, err)：成功 err=''；彻底失败 err 描述原因。
    铁律（2026-10-16）：抓取失败绝不留白——必须返回可诊断的 err 供调用方留痕，
    且调用方不得将其标记 seen，保证下一轮自动重试，文章永不漏抓。"""
    last_err = ''
    for i in range(tries):
        try:
            text_len = 0
            title, snippet, final, fee = _article_public_part(url)
            if title:
                return title, snippet, final, fee, ''
            # title 为空：页面大概率是验证码/限流页，记录页面特征便于诊断
            last_err = '标题提取为空（第%d次尝试，页面可能为验证码或限流页）' % (i + 1)
        except Exception as e:
            last_err = '%s: %s（第%d次尝试）' % (type(e).__name__, e, i + 1)
        if i < tries - 1:
            time.sleep(3 * (i + 1))  # 3s、6s 退避，避开限流窗口
    return '', '', '', None, last_err


def check_articles():
    """全自动文章发现 + 公开部分落 pending/ 待会话内 Agent 核验。

    发现源优先级（2026-10-19 重构，防夜报漏抓再发）：
      1. cls.cn 签名 API（主来源）：11 个 VIP 栏目翻页 + SSR 详情取价，
         官网与公众号同源发布，不依赖微信专辑列表（专辑接口 10-18 起已停更）；
      2. 微信专辑列表 JSON（降级）：仅当 cls.cn 接口整体失败时启用；
      3. 公众号 biz/cookie 历史接口（兜底）。
    价格口径：cls.cn 文章 articlePrice（元）×10 = 微信豆（与公众号 fee 实测一致）；
    isFree=true 的免费推广文（周回顾/阶段回顾等）直接跳过。
    门槛：cls.cn 按栏目区分（普通 280 豆 / 金牌纪要库 380 豆）；微信源统一 280 豆。

    铁律（2026-10-16 用户最高优先级要求）：
      1. 零静默丢数据——抓取失败（SSR 无数据/超时/结构变化）一律记入 failed 并写日志，
         且【不标记 seen】，下一轮自动重试，直到成功为止；
      2. 价格字段缺失（非 isFree 却无 articlePrice）视为存疑，同样不标记 seen 重试；
      3. 只有成功取得标题且完成价格判定的文章才标记 seen。"""
    try:
        os.makedirs(PENDING_DIR, exist_ok=True)
        feed = load_feed()
        seen = {}
        if os.path.exists(SEEN_PATH):
            try:
                seen = json.load(open(SEEN_PATH, encoding='utf-8'))
            except ValueError:
                seen = {}
        seen_norms = [_norm_title(k) for k in seen if k and k.strip()]
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        saved, skipped, failed = [], [], []
        try:
            window_ts = datetime.datetime.strptime(DATA_WINDOW_START, '%Y-%m-%d').timestamp()
        except ValueError:
            window_ts = 0

        # ---------- 发现候选 ----------
        cands = []          # ('cls', meta) 或 ('wx', meta) —— 仅窗口内未见文章
        pre_window = []     # 窗口外未见文章：直接标记已见（不占处理预算、不核价）
        cls_arts, cls_ok = fetch_cls_columns()
        if cls_ok:
            for a in cls_arts:
                if not a.get('title') or _title_seen(a['title'], seen_norms):
                    continue
                ct0 = a.get('ctime') or 0
                if window_ts and ct0 and ct0 < window_ts:
                    pre_window.append(a)   # 窗口外：标记已见即可，永不入待核验队列
                    continue
                cands.append(('cls', a))
            for a in pre_window:
                seen[a['title']] = now_str
                seen_norms.append(_norm_title(a['title']))
                skipped.append({'title': a['title'], 'column': a['column'],
                                'reason': '窗口外（数据仅从%s起）' % DATA_WINDOW_START})
            if pre_window:
                log('  窗口外文章 %d 篇已标记已见（数据仅从%s起，不入待核验队列）'
                    % (len(pre_window), DATA_WINDOW_START))
        else:
            log('  cls.cn 接口整体失败，降级使用专辑列表')
            for a in fetch_album_list(feed.get('album', '')):
                if a['url'] and not _title_seen(a['title'], seen_norms):
                    cands.append(('wx', {'url': a['url'], 'title': a['title'],
                                         'create_time': a.get('create_time', ''),
                                         'pos': a.get('pos', '')}))
            if not cands:
                for (u, t) in fetch_biz_list(feed.get('biz', ''), feed.get('cookie', '')):
                    if u and not _title_seen(t, seen_norms):
                        cands.append(('wx', {'url': u, 'title': t, 'create_time': '', 'pos': ''}))
        if not cands:
            # 无窗口内候选：若本轮标记过窗口外文章，必须落盘（否则下轮重复标记）
            if pre_window:
                with open(SEEN_PATH, 'w', encoding='utf-8') as f:
                    json.dump(seen, f, ensure_ascii=False, indent=1)
                return {'ok': True, 'new': 0, 'skipped': len(pre_window), 'failed': 0,
                        'note': 'cls.cn 各栏目无窗口内新文章；窗口外文章 %d 篇已标记已见' % len(pre_window),
                        'source': 'cls.cn' if cls_ok else 'album'}
            note = ('cls.cn 各栏目无新文章（已全部收录）' if cls_ok else
                    '未配置文章源或来源无新文章：请检查 cls.cn 接口 / feed.json 的 album、biz/cookie')
            return {'ok': True, 'new': 0, 'skipped': 0, 'failed': 0, 'note': note}
        if len(cands) >= 30:
            log('  ⚠ 候选文章 %d 篇（≥30，可能存在历史积压，注意后续核验轮次安排）' % len(cands))
        if len(cands) > CLS_CAND_CAP:
            log('  ⚠ 候选 %d 篇超过单轮上限 %d，剩余 %d 篇【不标记已见】，下轮自动继续'
                % (len(cands), CLS_CAND_CAP, len(cands) - CLS_CAND_CAP))

        # ---------- 逐篇处理 ----------
        for kind, a in cands[:CLS_CAND_CAP]:
            if kind == 'cls':
                aid, title = a['aid'], a['title']
                url = 'https://www.cls.cn/detail/%s' % aid
                d, err = None, ''
                for attempt in range(3):
                    try:
                        d = cls_article_detail(aid)
                    except Exception as e:
                        err = '%s: %s（第%d次尝试）' % (type(e).__name__, e, attempt + 1)
                        d = None
                    if d:
                        break
                    if not err:
                        err = 'SSR 详情页无 __NEXT_DATA__（第%d次尝试）' % (attempt + 1)
                    time.sleep(2 * (attempt + 1))
                if not d:
                    failed.append({'title': title, 'url': url, 'error': err})
                    log('  ✗ cls.cn 详情抓取失败（不标记已见，下轮自动重试）: %s | %s' % (title[:40], err))
                    time.sleep(1)
                    continue
                if d.get('isFree'):
                    # 免费推广文（周回顾/阶段回顾）：0 豆，低于任何门槛
                    seen[title] = now_str
                    seen_norms.append(_norm_title(title))
                    skipped.append({'title': title, 'beans': 0, 'column': a['column'], 'free': True})
                    log('  免费文章跳过（isFree）: %s' % title[:40])
                    continue
                price = d.get('articlePrice')
                if price is None:
                    failed.append({'title': title, 'url': url,
                                   'error': 'articlePrice 缺失且非 isFree，疑似页面结构变化'})
                    log('  ✗ 价格字段缺失，不标记已见（下轮重试）: %s' % title[:40])
                    time.sleep(1)
                    continue
                beans = int(round(float(price) * 10))
                ct = d.get('ctime') or a.get('ctime') or 0
                ct_str = (datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M:%S')
                          if ct else '')
                if beans < a['beans_min']:
                    seen[title] = now_str
                    seen_norms.append(_norm_title(title))
                    COL_OBSERVED.append(a['column'])
                    skipped.append({'title': title, 'beans': beans, 'column': a['column'],
                                    'note': 'v6.2：未达280门槛，仅登记分类留档，不做任何抓取'})
                    log('  价格门槛跳过（%s 实付%d豆 < %d，仅登记分类）: %s'
                        % (a['column'], beans, a['beans_min'], title[:40]))
                    continue
                seen[title] = now_str
                seen_norms.append(_norm_title(title))
                item = {'keyword': a['column'], 'title': title, 'url': url,
                        'snippet': (d.get('brief') or a.get('brief') or '')[:1500],
                        'savedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'beans': beans, 'aid': aid, 'column': a['column'],
                        'create_time': ct_str,
                        'related_stock': a.get('related_stock') or [],
                        'source': 'cls.cn'}
                fn = os.path.join(PENDING_DIR, '%s.json' % re.sub(r'[\\/:*?"<>|\s]', '_', title)[:60])
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump(item, f, ensure_ascii=False, indent=1)
                saved.append(title)
                log('  ★ 新文章待核验（%s %d豆）: %s' % (a['column'], beans, title[:40]))
                time.sleep(0.5)
            else:
                # 微信降级路径（专辑/biz）：fee 从公众号页面提取
                url = a['url']
                list_title = a.get('title', '')
                title, snippet, final, fee, err = _fetch_article_with_retry(url)
                if err:
                    failed.append({'title': list_title or url, 'url': url, 'error': err})
                    log('  ✗ 文章抓取失败（不标记已见，下轮自动重试）: %s | %s' % (list_title or url, err))
                    time.sleep(1)
                    continue
                if _title_seen(title, seen_norms):
                    continue
                if fee is None:
                    failed.append({'title': title, 'url': url,
                                   'error': '实付微信豆字段提取失败（fee=None），疑似页面结构变化或限流残页'})
                    log('  ✗ 价格提取存疑，不标记已见（下轮重试）: %s' % title)
                    time.sleep(1)
                    continue
                if fee < BEANS_MIN:
                    seen[title] = now_str
                    seen_norms.append(_norm_title(title))
                    skipped.append({'title': title, 'fee': fee})
                    log('  价格门槛跳过（实付%d豆 < %d）: %s' % (fee, BEANS_MIN, title))
                    continue
                seen[title] = now_str
                seen_norms.append(_norm_title(title))
                item = {'keyword': '专辑', 'title': title, 'url': final or url, 'snippet': snippet,
                        'savedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'beans': fee}
                if a.get('create_time'):
                    item['create_time'] = a['create_time']
                if a.get('pos'):
                    item['pos'] = a['pos']
                fn = os.path.join(PENDING_DIR, '%s.json' % re.sub(r'[\\/:*?"<>|\s]', '_', title)[:60])
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump(item, f, ensure_ascii=False, indent=1)
                saved.append(title)
                time.sleep(1)
        with open(SEEN_PATH, 'w', encoding='utf-8') as f:
            json.dump(seen, f, ensure_ascii=False, indent=1)
        if COL_OBSERVED:
            bump_columns_registry(COL_OBSERVED)
        return {'ok': True, 'new': len(saved), 'skipped': len(skipped), 'failed': len(failed),
                'skippedList': skipped, 'failedList': failed, 'titles': saved,
                'source': 'cls.cn' if cls_ok else 'album'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'new': 0}


if __name__ == '__main__':
    import sys
    job = sys.argv[1] if len(sys.argv) > 1 else 'close'
    r = run(job)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r.get('ok') else 1)
