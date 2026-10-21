# -*- coding: utf-8 -*-
"""
财联社投研看板 · 第二层云端自动入池引擎（v6.1，2026-10-20 正式上线）
====================================================================
定位：三层流水线的第二层——在云端（GitHub Actions）对 pending/ 工单做
      **确定性**预核验，零模型推断，产出结果文件供本地唤醒（第三层）消费。

安全边界（铁律）：
  1. 只做「公开点名字面匹配」：摘要/标题中字面出现已知上市公司名。字典来源为
     新浪 A 股全量名单（hs_a 分页抓取，name→code 为事实映射，无推断），
     叠加在池股票 overlay（带 sector/column）；名单抓取失败时回退本地缓存。
  2. 板块分布校验：字面点名数不得超过工单 related_stock 声称的各板块数量，
     超出即判疑，转人工唤醒，绝不自动入池。
  3. 不补名：字面没点到的，一律不猜（转唤醒层做公开信源取证）。
  4. 低于 280 微信豆 / 窗口外 / 非监控栏目：直接跳过并留痕。
  5. 短名/通用词防护：≤3 字公司名若仅在摘要（非标题）中出现，或命中
     ref/generic_names.json 通用词黑名单（如"机器人"既是 002090 公司名
     又是高频行业词），一律不自动入池，转唤醒层人工研判。
  6. 统计提及防护：证据句命中排行/榜单/关注度等统计类标记词（狙击龙虎榜
     栏目除外——该栏目龙虎榜数据即核心信号）的，判为纯统计提及、无个股
     投资信号，不自动入池，转唤醒层研判。

产出：
  autopool/results/<aid>.json  自动入池结果（含完整条目+行情+期次档案）
  autopool/routed/<aid>.json   转唤醒层工单（附板块校验明细与转出原因）
  autopool/processed.jsonl     全量处理台账（aid 幂等，跨运行共享）
绝不直接修改 index.html（母版唯一权威，入池由本地唤醒落地）。

已知边界（均为安全方向）：
  - 名单来自新浪 hs_a 节点，覆盖沪深主板/创业板/科创板，不含北交所；
    北交所公司字面点名不命中字典 → 转唤醒层人工研判。
  - 个股停牌（零价）导致整篇行情抓取失败 → 整篇转唤醒，不部分入池。
"""
import datetime
import glob
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from refresh import http_get, fetch_quotes, fetch_minute, fetch_kline, log  # noqa: E402

PENDING_DIR = os.path.join(BASE_DIR, 'pending')
REF_DIR = os.path.join(BASE_DIR, 'ref')
OUT_DIR = os.path.join(BASE_DIR, 'autopool')
RESULTS_DIR = os.path.join(OUT_DIR, 'results')
ROUTED_DIR = os.path.join(OUT_DIR, 'routed')

# ---- 监控栏目（v6.0：五栏目，全栏目统一 ≥280 微信豆）----
COLUMN_MAP = {
    '公告全知道': '公告全知道',
    '财联社早知道': '财联社早知道',
    '狙击龙虎榜': '狙击龙虎榜',
    '风口研报': '风口研报·洞察',
    '风口研报·洞察': '风口研报·洞察',
    '金牌纪要库': '金牌纪要库',
}
WINDOW_START = '2026-10-11'
BEANS_MIN = 280

# ---- v7.5 用户铁律（2026-10-21 亲定，优先于此前一切条款）----
# ① 价格是第一道硬关：仅 ≥280 微信豆的高价值文章，180 豆信息类/普通研报直接不要。
# ② 摘要条数 = 股票数量硬上限：摘要 ①②③ 几条就是几只股票，多出的必是错误信息，绝不外延。
# ③ 全网比对确认：摘要未字面点名的，需拿公告特征与全网公开信息比对；匹配上才入池，
#    匹配度高的进候选池，匹配不上的宁缺毋滥直接放弃（不马马虎虎）。
# ④ 笼统行业文/无一一对应特征的，彻底放弃。
# ⑤ 点名声但做趋势分析的文章：需前瞻看好 + 公开信息对应 + 上涨概率研判高才入池。
# ⑥ 负面消息（行业衰落/盈利下降/减持/处罚等）绝对排除，绝不逆向选择。
ANNOUNCE_COLS = {'公告全知道', '公告', '盘中宝', '电报', '公告解读',
                 '公告早知道', '公告掘金'}
NEGATIVE_KW = ['衰落', '盈利能力下降', '业绩下滑', '出现亏损', '亏损', '减持', '违规',
               '处罚', '退市', '爆雷', '暴跌', '萎缩', '走下坡', '景气度下行',
               '需求萎缩', '价格下跌', '产能过剩', '评级下调', '目标价下调']
POSITIVE_KW = ['看好', '增长', '提升', '订单', '扩产', '突破', '龙头', '景气', '预增',
               '涨停', '中标', '签约', '获批', '投产', '交付', '创新高', '紧缺',
               '涨价', '复苏', '改善', '放量', '超预期', '翻倍', '倍增']


def teaser_count(snippet):
    """摘要条数（①②③…分段数）——股票数量的硬上限。"""
    return len([s for s in re.split(r'(?=[\u2460-\u2465])', snippet or '') if s.strip()])


def ev_is_negative(ev):
    return any(k in (ev or '') for k in NEGATIVE_KW)


def ev_is_positive_catalyst(ev):
    return any(k in (ev or '') for k in POSITIVE_KW)

# ---- v6.2：真实分类注册表（ref/columns.json 由采集层动态登记，看板分类自主增减）----
COLUMNS_REG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ref', 'columns.json')

def _load_real_columns():
    try:
        return set(json.load(open(COLUMNS_REG_PATH, encoding='utf-8')).keys())
    except Exception:
        return set()

REAL_COLUMNS = _load_real_columns() | {
    '公告全知道', '财联社早知道', '狙击龙虎榜', '风口研报·洞察', '金牌纪要库'}

# ---- 板块归类（按证券代码前缀）----
def board_of(code):
    if code.startswith('60'):
        return '主板'
    if code.startswith('00'):
        return '主板'
    if code.startswith('30'):
        return '创业板'
    if code.startswith('688'):
        return '科创板'
    if code.startswith('8') or code.startswith('4'):
        return '北交所'
    return '其他'

def exch_of(code):
    if code.startswith('sh') or code.startswith('60'):
        return ['sh']
    if code.startswith('688'):
        return ['sh', 'kc']
    if code.startswith('sz') or code.startswith('00'):
        return ['sz']
    if code.startswith('30'):
        return ['sz', 'cy']
    if code.startswith('8') or code.startswith('4'):
        return ['bj']
    return []

def q_of(code):
    c = code.lstrip('sh').lstrip('sz')
    if code.startswith('60') or code.startswith('688'):
        return 'sh' + c
    return 'sz' + c


# ---- A 股全量名单（新浪 hs_a 分页）----
SINA_NODE_URL = ('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
                 'Market_Center.getHQNodeData?node=hs_a&num=100&page=%d')
ALL_NAMES_CACHE = os.path.join(REF_DIR, 'all_names.json')
# 上市首日临时标识（N/C）、除权除息标识（XD/XR/DR）、风险警示（*）与退市整理（退）不作为匹配名
NAME_BAD_PREFIX = ('*', 'N', 'C', 'XD', 'XR', 'DR', '退')
# 通用词黑名单：既是上市公司名又是高频行业/通用词，字面出现不足以证明点名该公司
# （文件不存在时为空集；在 main() 中初始化以避免前向引用）
GENERIC_NAMES = set()


def name_is_risky(name, in_title):
    """短名/通用词风险判定：≤3 字且未上标题，或命中通用词黑名单 → 不自动入池"""
    if name in GENERIC_NAMES:
        return True
    if len(name) <= 3 and not in_title:
        return True
    return False


# 统计提及标记词：证据句含这些词说明该公司出现在排行/榜单/统计口径中，
# 属于纯统计提及而非个股投资信号（对齐第三层唤醒核验判据）。
STAT_MARKERS = ('前五名', '前三名', '前十大', '前二十', '前三十', '排行', '排行榜',
                '榜单', '关注度', '依次', '涨幅居前', '跌幅居前', '领涨', '领跌',
                '净买入', '净卖出', '换手率', '上榜')
# 狙击龙虎榜栏目的龙虎榜/资金数据即核心信号，不做统计提及降级
STAT_EXEMPT_COLUMNS = ('狙击龙虎榜',)


def ev_is_statistical(ev, column):
    if column in STAT_EXEMPT_COLUMNS:
        return False
    return any(mk in ev for mk in STAT_MARKERS)


def fetch_all_names():
    """抓取新浪 A 股全量名单（hs_a，每页 100，上限 80 页 ≈ 8000 只）。
    返回 {name: {code, q, exch, sector}}；抓取失败回退 ref/all_names.json 缓存。"""
    names = {}
    for page in range(1, 81):
        try:
            text, _ = http_get(SINA_NODE_URL % page, gbk=True, timeout=25)
            arr = json.loads(text)
        except Exception as e:
            log('  新浪名单第 %d 页抓取失败：%s' % (page, e))
            break
        if not arr:
            break
        for it in arr:
            code = (it.get('code') or '').strip()
            nm = (it.get('name') or '').strip()
            if len(code) != 6 or len(nm) < 3:
                continue
            if nm.startswith(NAME_BAD_PREFIX):
                continue
            names[nm] = {'code': code, 'q': q_of(code),
                         'exch': exch_of(code), 'sector': ''}
        time.sleep(0.15)
    if names:
        try:
            with open(ALL_NAMES_CACHE, 'w', encoding='utf-8') as f:
                json.dump(names, f, ensure_ascii=False)
        except Exception as e:
            log('  名单缓存写入失败：%s' % e)
        return names
    cached = load_json(ALL_NAMES_CACHE, {})
    if cached:
        log('  新浪名单抓取失败，回退本地缓存 %d 名' % len(cached))
    else:
        log('  新浪名单抓取失败且无缓存，本期全部转唤醒')
    return cached


def build_name_dict():
    """全量 A 股名单 + 在池 overlay（overlay 带 sector/column 优先）。
    overlay 中不在新浪名单的股票（停牌/新上市未收录）也保留。"""
    alln = fetch_all_names()
    overlay = load_json(os.path.join(REF_DIR, 'name_dict.json'), {})
    for nm, info in overlay.items():
        if nm in alln:
            alln[nm].update({k: v for k, v in info.items() if v})
            alln[nm]['inPool'] = True
        else:
            alln[nm] = dict(info)
            alln[nm]['inPool'] = True
    return alln


def now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def load_processed():
    done = {}
    p = os.path.join(OUT_DIR, 'processed.jsonl')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    done[r['aid']] = r.get('outcome', '')
                except Exception:
                    pass
    return done


def append_processed(aid, outcome, title):
    p = os.path.join(OUT_DIR, 'processed.jsonl')
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'aid': aid, 'outcome': outcome, 'title': title,
                            'at': now_str()}, ensure_ascii=False) + '\n')


def fetch_beans(aid):
    """cls.cn 详情页取 articlePrice（元）×10 = 微信豆；失败返回 None"""
    try:
        text, _ = http_get('https://www.cls.cn/detail/%s' % aid, timeout=20)
        m = re.search(r'"articlePrice"\s*:\s*(\d+(?:\.\d+)?)', text)
        if m:
            return int(float(m.group(1)) * 10)
    except Exception as e:
        log('  beans 抓取失败 aid=%s: %s' % (aid, e))
    return None


def to_date_str(v):
    if v is None:
        return ''
    if isinstance(v, (int, float)):
        return datetime.datetime.fromtimestamp(v).strftime('%Y-%m-%d')
    return str(v)[:10]


def split_sentences(s):
    parts = re.split(r'[。；;！!？?]', s)
    return [p.strip(' 　①②③④⑤⑥') for p in parts if len(p.strip(' 　①②③④⑤⑥')) >= 6]


def main():
    global GENERIC_NAMES
    GENERIC_NAMES = set(load_json(os.path.join(REF_DIR, 'generic_names.json'), []))
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(ROUTED_DIR, exist_ok=True)
    os.makedirs(REF_DIR, exist_ok=True)

    name_dict = build_name_dict()
    pool_names = load_json(os.path.join(REF_DIR, 'pool_names.json'), {})
    processed = load_processed()
    log('第二层自动入池引擎启动：匹配字典 %d 名（含在池 %d） · 已处理 %d' %
        (len(name_dict), len(pool_names), len(processed)))

    stats = {'auto': 0, 'wake': 0, 'skip': 0}
    files = sorted(glob.glob(os.path.join(PENDING_DIR, '*.json')))
    files = [f for f in files if not f.endswith('_scan_status.json')]

    for fp in files:
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception as e:
            log('工单解析失败 %s: %s' % (fp, e))
            continue
        aid = d.get('aid')
        title = d.get('title', '')
        if not aid:
            continue
        if aid in processed:
            continue

        col_raw = (d.get('column') or d.get('keyword') or '').strip()
        # v6.2：真实分类（标题【】前缀）优先直通；旧父栏目名走映射回退
        column = col_raw if col_raw in REAL_COLUMNS else COLUMN_MAP.get(col_raw)
        snippet = d.get('snippet') or ''
        pub = (d.get('create_time') or d.get('savedAt') or '')[:16]
        period = to_date_str(d.get('create_time'))
        beans = d.get('beans')
        if beans is None and isinstance(d.get('price'), (int, float)):
            beans = int(d['price'] * 10)

        # ---- 门槛闸门 ----
        if not column:
            append_processed(aid, 'skip-oos', title)
            stats['skip'] += 1
            continue
        if period and period < WINDOW_START:
            append_processed(aid, 'skip-window', title)
            stats['skip'] += 1
            continue
        if beans is None:
            beans = fetch_beans(aid)
        if beans is None:
            _write_routed(aid, title, column, pub, period, snippet, d,
                          'price-unfetchable', '微信豆价格无法核实（cls.cn 详情页取价失败），按铁律不自动入池')
            append_processed(aid, 'wake', title)
            stats['wake'] += 1
            continue
        if beans < BEANS_MIN:
            append_processed(aid, 'skip-lowbeans', title)
            stats['skip'] += 1
            continue

        # ---- 公开点名字面匹配（含短名/通用词/统计提及防护）----
        text = title + '。' + snippet
        matched = []
        skipped = []
        for name, info in sorted(name_dict.items(), key=lambda kv: -len(kv[0])):
            if len(name) < 3:
                continue
            if name not in text:
                continue
            if any(name in m[0] for m in matched):
                continue
            ev = ''
            for s in split_sentences(snippet) + split_sentences(title):
                if name in s:
                    ev = s
                    break
            if name_is_risky(name, name in title):
                skipped.append({'name': name, 'code': info['code'], 'ev': ev[:60],
                                'kind': 'generic-name-risk'})
                continue
            if ev_is_statistical(ev, column):
                skipped.append({'name': name, 'code': info['code'], 'ev': ev[:60],
                                'kind': 'statistical-mention'})
                continue
            # v7.5 铁律⑥：负面消息绝对排除，绝不逆向选择
            if ev_is_negative(ev):
                skipped.append({'name': name, 'code': info['code'], 'ev': ev[:60],
                                'kind': 'negative-signal'})
                continue
            # v7.5 铁律⑤：非公告类栏目点名声的股票，需有明确正向催化剂
            # （前瞻看好 + 公开信息对应的粗判；精细趋势研判由落地层/全网比对完成）
            if column not in ANNOUNCE_COLS and not ev_is_positive_catalyst(ev):
                skipped.append({'name': name, 'code': info['code'], 'ev': ev[:60],
                                'kind': 'trend-unconfirmed'})
                continue
            matched.append((name, info, ev))
        matched.sort(key=lambda m: text.find(m[0]))

        # ---- 板块分布校验 ----
        claimed = {}
        for r in (d.get('related_stock') or []):
            mk = r.get('market') or ''
            cn = r.get('count') or 0
            if mk:
                claimed[mk] = claimed.get(mk, 0) + cn
        mb = {}
        for name, info, _ in matched:
            b = board_of(info['code'])
            mb[b] = mb.get(b, 0) + 1
        board_ok = True
        board_note = ''
        if claimed:
            over = [(k, mb.get(k, 0), v) for k, v in claimed.items() if mb.get(k, 0) > v]
            total_m = sum(mb.values())
            total_c = sum(claimed.values())
            if over:
                board_ok = False
                board_note = '字面点名超过声称分布: %s' % over
            elif total_m > total_c:
                board_ok = False
                board_note = '字面点名总数 %d 超过声称 %d' % (total_m, total_c)
            else:
                board_note = '字面点名 %d 只 ≤ 声称 %d 只（%s），其余未字面点名不予补名' % (
                    total_m, total_c, '/'.join('%s%d' % kv for kv in claimed.items()))
        else:
            board_note = '工单无 related_stock 分布信息，仅按字面点名入池'
        # v7.5 铁律②（最终优先级）：摘要条数 = 股票数量硬上限。字面点名超过摘要条数的，
        # 多出的必是错误信息（会误导入池），整篇转唤醒层逐条核实，绝不外延。
        t_n = teaser_count(snippet)
        if t_n and len(matched) > t_n:
            board_ok = False
            board_note = '字面点名 %d 只超过摘要条数 %d（铁律②：多出的为错误信息，不外延，转唤醒层逐条核实）' % (
                len(matched), t_n)

        if not matched:
            if skipped:
                kinds = '、'.join(sorted(set(s['kind'] for s in skipped)))
                _write_routed(aid, title, column, pub, period, snippet, d,
                              kinds if len(set(s['kind'] for s in skipped)) == 1 else 'no-literal-match',
                              '仅命中短名/通用词/统计提及（%s：%s），字面出现不足以证明个股投资信号，需唤醒层公开信源取证；%s'
                              % ('、'.join(s['name'] for s in skipped),
                                 '、'.join(sorted(set(s['kind'] for s in skipped))), board_note))
            else:
                _write_routed(aid, title, column, pub, period, snippet, d,
                              'no-literal-match', '公开摘要为线索式描述（未字面点名已知公司），需唤醒层公开信源取证；' + board_note)
            append_processed(aid, 'wake', title)
            stats['wake'] += 1
            continue
        if not board_ok:
            _write_routed(aid, title, column, pub, period, snippet, d,
                          'board-mismatch', board_note + '；转唤醒层核实')
            append_processed(aid, 'wake', title)
            stats['wake'] += 1
            continue

        # ---- 自动入池：抓行情 + 组装完整载荷 ----
        new_names = [(n, i, ev) for n, i, ev in matched if n not in pool_names]
        stocks_payload = {}
        entries = []
        if new_names:
            qs = [i['q'] for _, i, _ in new_names]
            try:
                quotes = fetch_quotes(qs)
            except Exception as e:
                _write_routed(aid, title, column, pub, period, snippet, d,
                              'quote-failed', '行情抓取失败（%s），转唤醒层重试' % e)
                append_processed(aid, 'wake', title)
                stats['wake'] += 1
                continue
            for name, info, ev in new_names:
                q = info['q']
                qd = quotes.get(q)
                if not qd:
                    continue
                price = qd['price']
                entry = {
                    'name': name, 'code': info['code'], 'q': q,
                    'exch': info.get('exch') or exch_of(info['code']),
                    'sector': info.get('sector') or '',
                    'column': column,
                    'batchId': 'b%s_%s' % (period.replace('-', ''), _col_suffix(column)),
                    'dateIn': period, 'pub': pub, 'beans': beans,
                    'margin': False,
                    'reason': '公开摘要字面点名：「%s」（%s）' % (name, ev or snippet[:80]),
                    'verify': '摘要确认', 'verifyTag': '摘要确认', 'conf': 'mid',
                    'priceIn': round(price, 2), 'priceNow': round(price, 2),
                    'pct': 0.0, 'gainSince': 0.0,
                    'prob': None, 'forecast': None,
                    'fundamental': None, 'outlook': None, 'tech': None,
                }
                entries.append(entry)
                st = {
                    'name': name, 'price': price, 'prev': qd['prev'],
                    'change': round(price - qd['prev'], 2), 'pct': qd['pct'],
                    'high': qd['high'], 'low': qd['low'], 'time': qd['time'],
                    'minute': [], 'kline': [],
                }
                try:
                    st['kline'] = fetch_kline(q)
                except Exception as e:
                    log('  kline 失败 %s: %s' % (q, e))
                # priceIn 口径对齐母版：文章发布日（含）之后首个交易日收盘价
                for bar in (st.get('kline') or []):
                    if str(bar[0])[:10] >= period:
                        entry['priceIn'] = round(bar[2], 2)
                        break
                try:
                    mn = fetch_minute(q)
                    if mn:
                        st['minute'] = mn
                except Exception as e:
                    log('  minute 失败 %s: %s' % (q, e))
                stocks_payload[q] = st
                time.sleep(0.3)

        # 期次档案（唤醒层落地时与主池 batches 合并，按 id 去重）
        teasers = [s for s in re.split(r'(?=[\u2460-\u2465])', snippet) if s.strip()]
        batch = {
            'id': 'b%s_%s' % (period.replace('-', ''), _col_suffix(column)),
            'period': period, 'title': title, 'pub': pub, 'beans': beans,
            'column': column, 'tier': _legacy_tier(column),
            'companies': len(matched),
            'article': {'teasers': teasers},
            'items': [{'stock': n, 'scode': i['code'], 'title': ev or title,
                       'content': '', 'tags': []} for n, i, ev in matched],
            'note': '第二层云端自动入池（公开摘要字面点名 + 板块分布校验通过）：%s%s' % (
                    '、'.join(n for n, _, _ in matched),
                    '；跳过（短名/通用词/统计提及，不入池）：%s' %
                    '、'.join(s['name'] for s in skipped) if skipped else ''),
        }
        result = {
            'aid': aid, 'outcome': 'auto', 'column': column, 'beans': beans,
            'title': title, 'pub': pub, 'period': period,
            'evidence': '；'.join('%s：「%s」' % (n, ev[:60]) for n, _, ev in matched if ev),
            'boardCheck': {'ok': True, 'claimed': claimed, 'matched': mb, 'note': board_note},
            'allInPool': bool(matched) and not new_names,
            'skipped': skipped,
            'entries': entries, 'stocks': stocks_payload, 'batch': batch,
            'processedAt': now_str(),
        }
        with open(os.path.join(RESULTS_DIR, '%s.json' % aid), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        append_processed(aid, 'auto', title)
        stats['auto'] += 1
        log('  [自动入池] aid=%s %s → %s%s' % (
            aid, column, '、'.join(n for n, _, _ in new_names) or '全部已在池',
            '（跳过 %d：%s）' % (len(skipped), '、'.join(s['name'] for s in skipped)) if skipped else ''))

    log('第二层执行完毕：自动入池 %d · 转唤醒 %d · 跳过 %d' %
        (stats['auto'], stats['wake'], stats['skip']))
    print(json.dumps({'ok': True, 'stats': stats}, ensure_ascii=False))


def _col_suffix(column):
    return {'公告全知道': '', '财联社早知道': '_499', '狙击龙虎榜': '_lhb',
            '风口研报·洞察': '_dc', '金牌纪要库': '_gold'}.get(column, '')


def _legacy_tier(column):
    return {'公告全知道': 'night', '财联社早知道': 'day', '狙击龙虎榜': 'night',
            '风口研报·洞察': 'day', '金牌纪要库': 'gold'}.get(column, 'day')


def _write_routed(aid, title, column, pub, period, snippet, d, reason, detail):
    os.makedirs(ROUTED_DIR, exist_ok=True)
    payload = {
        'aid': aid, 'outcome': 'wake', 'routeReason': reason, 'routeDetail': detail,
        'column': column, 'title': title, 'pub': pub, 'period': period,
        'snippet': snippet, 'related_stock': d.get('related_stock'),
        'beans': d.get('beans'), 'url': d.get('url'), 'processedAt': now_str(),
    }
    with open(os.path.join(ROUTED_DIR, '%s.json' % aid), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    log('  [转唤醒] aid=%s %s（%s）' % (aid, column, reason))


if __name__ == '__main__':
    main()
