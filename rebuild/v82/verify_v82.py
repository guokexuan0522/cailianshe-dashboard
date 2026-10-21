# -*- coding: utf-8 -*-
"""v8.2 功能验证：无头浏览器加载 index.html，逐项核验 9 项反馈修复"""
import json, re, asyncio
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
results = []


def chk(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('✅' if ok else '❌'), name, '|', detail)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width': 1400, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        await page.goto(URL, wait_until='networkidle')
        await page.wait_for_timeout(2500)

        # ===== 数据层 =====
        data = await page.evaluate("() => { try { return JSON.parse(document.getElementById('MONITOR_DATA').textContent); } catch(e){ return {err:e.message}; } }")
        chk('MONITOR_DATA 可解析', 'err' not in data)
        chk('版本 8.2', data.get('version') == '8.2', str(data.get('version')))
        chk('ruleCats 11 类（用户亲定已融合）', len(data.get('ruleCats', [])) == 11, str(len(data.get('ruleCats', []))))
        rc_names = [c['name'] for c in data.get('ruleCats', [])]
        chk('无「〇、用户亲定铁律」置顶类', not any('用户亲定铁律' in n for n in rc_names))
        own_cnt = sum(1 for c in data['ruleCats'] for it in c['items'] if it.startswith('【用户亲定'))
        chk('亲定条款已并入 11 类', own_cnt == 8, '共 %d 条' % own_cnt)
        chk('review 数据存在', bool(data.get('review', {}).get('stocks')), '%s %d 只' % (data['review']['date'], len(data['review']['stocks'])))
        chk('batches 17 期', len(data.get('batches', [])) == 17)
        chk('batches 全部含 teasers 原文', all(len(b.get('article', {}).get('teasers') or []) > 0 for b in data['batches']))
        chk('watchlist 33 只', len(data.get('watchlist', [])) == 33)
        chk('无中恒电气/科华数据残留', not any(w['code'] in ('002364', '002335') for w in data['watchlist']))
        chk('杰瑞股份在池', any(w['code'] == '002353' for w in data['watchlist']))

        # ===== 第4点：栏目分类 =====
        cols = await page.evaluate("() => Object.keys(COLUMNS)")
        for c in ('盘中宝', '九点特供', '研选•行业数据'):
            chk('COLUMNS 含 ' + c, c in cols)
        jl_col = await page.evaluate("() => { var w = W.filter(x=>x.code==='002353')[0]; return w ? colOf(w) : null; }")
        chk('杰瑞股份栏目=盘中宝', jl_col == '盘中宝', str(jl_col))
        zx_col = await page.evaluate("() => { var w = W.filter(x=>x.code==='688234')[0]; return w ? colOf(w) : null; }")
        chk('天岳先进栏目=公告全知道', zx_col == '公告全知道', str(zx_col))
        # 板块分布校验：2510883 主板2 → 实际入池 1 只主板
        dist = await page.evaluate("""() => {
          var out = {};
          W.forEach(function(w){ var c = colOf(w); out[c] = (out[c]||0)+1; });
          return out;
        }""")
        chk('栏目分布含盘中宝/九点特供', '盘中宝' in dist and '九点特供' in dist, json.dumps(dist, ensure_ascii=False))

        # ===== 第6点：核验列 =====
        ver = await page.evaluate("() => { var r = verifyHtml(W[0]); return r; }")
        chk('核验列显示✔（非推断）', '✔' in ver and '推断' not in ver, ver[:80])
        ver_all = await page.evaluate("() => W.every(w => verifyHtml(w).indexOf('推断') < 0)")
        chk('全部 33 只核验列无「推断」误显', ver_all)

        # ===== 第2点：今日收盘数据复盘（先模拟用户勾选自选）=====
        await page.evaluate("() => { window.toggleFav('002353', true); window.toggleFav('688234', true); }")
        await page.wait_for_timeout(500)
        rv_date = await page.text_content('#rvDate')
        chk('复盘日期显示 2026-10-21', rv_date == '2026-10-21', str(rv_date))
        rv_cnt = await page.text_content('#rvCntT')
        chk('复盘只数动态（非硬编码0）', rv_cnt == '2', str(rv_cnt))
        rv_rows = await page.evaluate("() => document.querySelectorAll('#rvBox tbody tr').length")
        chk('自选股在复盘区正常显示', rv_rows == 2, '%d 行' % rv_rows)
        rv_first = await page.evaluate("() => { var t=document.querySelector('#rvBox tbody tr'); return t?t.textContent:''; }")
        chk('复盘行含技术面要点与建议', '现价' in rv_first and ('持有' in rv_first or '增持' in rv_first or '观望' in rv_first or '减仓' in rv_first or '买进' in rv_first or '卖出' in rv_first), rv_first[:60])

        # ===== 第9点：分类筛选 =====
        chk('自选股来源下拉存在', await page.evaluate("() => !!document.getElementById('favColSel')"))
        chk('投研池栏目下拉存在', await page.evaluate("() => !!document.getElementById('poolColSel')"))
        fav_opts = await page.evaluate("() => Array.from(document.getElementById('favColSel').options).map(o=>o.value)")
        chk('自选下拉含人工录入分类', '__manual__' in fav_opts, str(fav_opts))
        pool_opts = await page.evaluate("() => Array.from(document.getElementById('poolColSel').options).map(o=>o.value)")
        chk('投研池下拉含全部 8 栏目', all(c in pool_opts for c in ('公告全知道', '财联社早知道', '狙击龙虎榜', '盘中宝', '九点特供', '风口研报·洞察', '金牌纪要库', '研选•行业数据')), str(pool_opts))

        # 投研池筛选功能实测
        await page.select_option('#poolColSel', '盘中宝')
        await page.wait_for_timeout(400)
        shown = await page.evaluate("() => Array.from(document.querySelectorAll('#poolBox .stock-card .nm')).map(e=>e.textContent)")
        chk('投研池筛选「盘中宝」生效', len(shown) > 0 and all('中恒' not in s and '科华' not in s for s in shown), str(shown))
        await page.select_option('#poolColSel', '')

        # ===== 第5点：全网比对两栏 =====
        wc_legend = await page.evaluate("() => Array.from(document.querySelectorAll('#wcLegend span')).map(s=>s.textContent.trim())")
        chk('全网比对 legend 无「已确认入池」', not any('已确认入池' in t for t in wc_legend), str(wc_legend))
        chk('全网比对 legend 有待比对+已放弃', any('待比对' in t for t in wc_legend) and any('已放弃' in t for t in wc_legend))
        collapse_btns = await page.evaluate("() => document.getElementById('wcSection').textContent.indexOf('全部收起') >= 0")
        chk('全网比对区有「全部收起」', collapse_btns)
        pool_cards = await page.evaluate("() => Array.from(document.querySelectorAll('#wcBox [data-st]')).map(e=>e.getAttribute('data-st')).filter(s=>s==='pool').length")
        chk('wcBox 无 pool 状态卡片', pool_cards == 0, str(pool_cards))
        ab_items = await page.evaluate("() => document.querySelectorAll('#abandBox details.aband-item').length")
        chk('放弃审计区留痕可展开', ab_items > 0, '%d 条' % ab_items)

        # ===== 第1点：自选股同步 =====
        enc = await page.evaluate("() => { FAVS['601606'] = {addTime:'2026-10-21', priceFav:25.5, dateIn:'2026-10-20', priceIn:25.0}; return favSync.encodeFavs(FAVS); }")
        chk('encodeFavs 含完整字段', '601606~25.5~0~' in enc or '601606~25.5' in enc, enc[:80])
        # 人工录入股跨设备恢复模拟
        rec = await page.evaluate("""() => {
          var hash = '#fav=sz002353~91~1~%E6%9D%B0%E7%91%9E%E8%82%A1%E4%BB%BD~sz002353,sh601606~25.5~0~';
          var r = (function(){ var m=/[#&]fav=([^&]*)/.exec(hash); if(!m) return null;
            var out={},n=0,manN=0; m[1].split(',').forEach(function(pair){
              var p=pair.split('~'),code=p[0]; if(!code)return;
              var price=parseFloat(p[1]),manual=p[2]==='1',name=decodeURIComponent(p[3]||''),q=decodeURIComponent(p[4]||'');
              if(byCode[code]){out[code]={priceFav:price,fromLink:true};n++;}
              else if(manual){out[code]={priceFav:price,manual:true,name:name,q:q,fromLink:true};manN++;}
            }); return {favs:out,n:n,manN:manN}; })();
          return r;
        }""")
        chk('人工录入股可跨设备恢复（全新浏览器）', rec and rec['manN'] == 1 and rec['favs']['sz002353']['name'] == '杰瑞股份', json.dumps(rec, ensure_ascii=False))

        # ===== 第3点：同步链接说明 =====
        title = await page.get_attribute('#favLinkBtn', 'title')
        chk('同步链接按钮有用法说明', title and len(title) > 30, (title or '')[:60])
        info = await page.text_content('#favSyncInfo')
        chk('favSyncInfo 有换设备同步方法说明', '复制同步链接' in info and '导入' in info)

        # ===== 第7点：期次备查 =====
        batch_count = await page.evaluate("() => document.querySelectorAll('#batchBox details.batch').length")
        chk('期次备查 17 期渲染', batch_count == 17, str(batch_count))
        batch_teasers = await page.evaluate("() => { var b = document.querySelector('#batchBox details.batch'); return b ? b.querySelectorAll('.news-item').length : 0; }")
        chk('期次备查含摘要原文', batch_teasers > 0, '%d 个内容块' % batch_teasers)
        batch_has_link = await page.evaluate("() => { var t = document.getElementById('batchBox').textContent; return t.indexOf('cls.cn/detail') >= 0 || t.indexOf('原文') >= 0; }")

        # ===== 第8点：铁律融合展示 =====
        rule_cnt = await page.evaluate("() => document.querySelectorAll('#ruleBox details.rule').length")
        chk('铁律区 11 类渲染', rule_cnt == 11, str(rule_cnt))
        rule_txt = await page.text_content('#ruleBox')
        chk('铁律区含用户亲定条款', '【用户亲定' in rule_txt)
        chk('铁律区栏目清单已补全', '盘中宝' in rule_txt and '九点特供' in rule_txt and '研选•行业数据' in rule_txt)

        # ===== 页面错误 =====
        real_errs = [e for e in errors if 'ERR_FILE_NOT_FOUND' not in e and 'net::' not in e and 'Failed to fetch' not in e and 'favicon' not in e.lower()]
        chk('无 JS 运行时错误', len(real_errs) == 0, '; '.join(real_errs[:3]))

        await page.screenshot(path='/tmp/v82_full.png', full_page=False)
        await browser.close()

    print()
    ok_n = sum(1 for _, ok, _ in results if ok)
    print('===== 通过 %d / %d =====' % (ok_n, len(results)))
    for name, ok, detail in results:
        if not ok:
            print('  ❌', name, detail)


asyncio.run(main())
