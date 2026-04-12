#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成完整的 Fantasy NBA 数据总览 HTML - 修复版
修复：
1. 比分使用 stat_winners 的 11-cat（含 GP, A/TO）
2. 新增"经理每周胜负变化"页签
3. 决赛 vs 季军赛分开显示
4. 正确推导冠亚季军排名
"""
import json, sys, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('yahoo_full_data.json', encoding='utf-8'))

# ── 球员头像 ──
player_nba_map = d.get('player_nba_map', {})

def player_avatar_url(player_key):
    """获取球员 NBA.com 头像 URL"""
    nba = player_nba_map.get(player_key, {})
    url = nba.get('headshot_url', '')
    if url:
        return url
    # fallback to Yahoo
    ps = d.get('player_stats', {}).get(player_key, {})
    pid = ps.get('player_id', '')
    if pid:
        return f"https://s.yimg.com/xe/i/us/sp/v/nba_cutout/players_l/full/headshots/{pid}.png"
    return ''

def player_img_html(player_key, size=22):
    """生成球员小头像 HTML"""
    url = player_avatar_url(player_key)
    if url:
        return f'<img src="{url}" onerror="this.style.display=\'none\'" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:4px">'
    return ''

# ── 球员多维排名系统 ──
def build_player_rankings(player_stats):
    """构建球员排名：11-cat Z-Score 综合排名 + 各单项排名"""
    import statistics
    
    ZSCORE_CATS = {
        'FG%': ('FG%', False), 'FT%': ('FT%', False), '3PM': ('3PM', False),
        'PTS': ('PTS', False), 'OREB': ('GP', False), 'REB': ('REB', False),
        'AST': ('AST', False), 'STL': ('STL', False), 'BLK': ('BLK', False),
        'TO': ('TO', True), 'A/TO': ('TW', False),
    }
    
    # 过滤有效球员
    valid_pks = []
    for pk, ps in player_stats.items():
        try:
            if float(ps.get('stats',{}).get('PTS',0)) > 100: valid_pks.append(pk)
        except: pass
    if not valid_pks: valid_pks = list(player_stats.keys())
    
    # 收集数值 + 计算 Z-Score
    cat_values = {cat: [] for cat in ZSCORE_CATS}
    player_vals = {}
    for pk in valid_pks:
        pst = player_stats[pk].get('stats', {})
        vals = {}
        for cat, (key, _) in ZSCORE_CATS.items():
            try: v = float(pst.get(key, 0))
            except: v = 0.0
            vals[cat] = v
            cat_values[cat].append(v)
        player_vals[pk] = vals
    
    cat_stats_z = {}
    for cat in ZSCORE_CATS:
        values = cat_values[cat]
        mean = statistics.mean(values) if len(values) >= 2 else 0
        stdev = statistics.stdev(values) if len(values) >= 2 else 1
        if stdev == 0: stdev = 1
        cat_stats_z[cat] = (mean, stdev)
    
    player_zscores = {}
    for pk in valid_pks:
        vals = player_vals[pk]
        total_z = 0
        for cat, (_, reverse) in ZSCORE_CATS.items():
            mean, stdev = cat_stats_z[cat]
            z = (vals[cat] - mean) / stdev
            if reverse: z = -z
            total_z += z
        player_zscores[pk] = total_z
    for pk in player_stats:
        if pk not in player_zscores: player_zscores[pk] = -99
    
    sorted_p = sorted(player_zscores.items(), key=lambda x: x[1], reverse=True)
    rank_pts = {pk: i+1 for i, (pk, _) in enumerate(sorted_p)}
    
    # 各单项排名（保持不变）
    cat_ranks = {}
    for cat, (key, lower_better) in ZSCORE_CATS.items():
        scored = []
        for pk, ps in player_stats.items():
            pst = ps.get('stats', {})
            try: val = float(pst.get(key, 0))
            except: val = 0
            if val == 0 and cat not in ('TO',): continue
            scored.append((pk, val))
        scored.sort(key=lambda x: x[1], reverse=not lower_better)
        cat_ranks[cat] = {pk: i+1 for i, (pk, _) in enumerate(scored)}
    
    return rank_pts, cat_ranks

def get_multidim_tags(pk, rank_pts, cat_ranks):
    """获取球员在多少个类别中排名 Top30"""
    top30_cats = []
    for cat, ranks in cat_ranks.items():
        if ranks.get(pk, 999) <= 30:
            top30_cats.append(cat)
    return top30_cats

def get_draft_round(pk, draft_data):
    """获取球员被选秀的轮次"""
    for p in draft_data:
        if p.get('player_key') == pk:
            return p.get('round', 99)
    return 99

def analyze_blockbuster(pk, pname, rank_pts, cat_ranks, draft_data, player_stats):
    """
    多维重磅交易分析
    返回 (level, reasons[])
    level: 3=超级重磅, 2=重磅, 1=值得关注, 0=普通
    """
    rank = rank_pts.get(pk, 999)
    draft_rd = get_draft_round(pk, draft_data)
    top30_cats = get_multidim_tags(pk, rank_pts, cat_ranks)
    
    # BLK/STL 稀缺性
    blk_rank = cat_ranks.get('BLK', {}).get(pk, 999)
    stl_rank = cat_ranks.get('STL', {}).get(pk, 999)
    
    level = 0
    reasons = []
    
    # 超级重磅 🔥🔥🔥
    if rank <= 20:
        level = max(level, 3)
        reasons.append(f'Rank #{rank} 超级球星')
    elif rank <= 50 and draft_rd <= 2:
        level = max(level, 3)
        reasons.append(f'Rank #{rank} + 第{draft_rd}轮选秀核心')
    
    # 重磅 🔥🔥
    if rank <= 50 and level < 3:
        level = max(level, 2)
        reasons.append(f'Rank #{rank} 联盟精英')
    if draft_rd <= 3 and rank <= 100 and level < 2:
        level = max(level, 2)
        reasons.append(f'第{draft_rd}轮选秀 + Rank #{rank}')
    if len(top30_cats) >= 3 and level < 2:
        level = max(level, 2)
        reasons.append(f'{len(top30_cats)}项Top30多面手 ({", ".join(top30_cats[:4])})')
    
    # 值得关注 🔥
    if rank <= 100 and level < 1:
        level = max(level, 1)
        reasons.append(f'Rank #{rank} Top100球员')
    if draft_rd <= 5 and level < 1:
        level = max(level, 1)
        reasons.append(f'第{draft_rd}轮选秀资产')
    if (blk_rank <= 20 or stl_rank <= 20) and level < 1:
        level = max(level, 1)
        cats_scarce = []
        if blk_rank <= 20: cats_scarce.append(f'BLK #{blk_rank}')
        if stl_rank <= 20: cats_scarce.append(f'STL #{stl_rank}')
        reasons.append(f'稀缺角色 ({", ".join(cats_scarce)})')
    
    return level, reasons

wlt = d.get('teams_wlt', {})
stats = d.get('team_season_stats', {})
draft = d.get('draft_picks_raw', [])
txs = d.get('transactions', [])
player_stats = d.get('player_stats', {})
weekly_sb = d.get('weekly_scoreboard', {})
weekly_st = d.get('weekly_standings', {})

# 构建球员多维排名
rank_pts, cat_ranks = build_player_rankings(player_stats)

# 经理名修正 (Yahoo 隐藏了部分经理名)
MANAGER_OVERRIDES = {
    'King Crimson Cecil': 'Cecil',
}

# 排序队伍
rows = []
for tid, t in wlt.items():
    s = stats.get(tid, {}).get('stats', {})
    team_name = t.get('name', '?')
    mgr = MANAGER_OVERRIDES.get(team_name, t.get('manager', '?'))
    rows.append({
        'rank': int(t.get('rank') or 99),
        'team': team_name,
        'manager': mgr,
        'team_key': t.get('team_key', ''),
        'W': t.get('wins', '?'), 'L': t.get('losses', '?'), 'T': t.get('ties', '?'),
        'pct': t.get('win_pct', '?'),
        'playoff': t.get('playoff_seed', '-'),
        'moves': t.get('moves', 0), 'trades': t.get('trades', 0),
        'FGpct': s.get('FG%', '-'), 'FTpct': s.get('FT%', '-'),
        '3PM': s.get('3PM', '-'), 'PTS': s.get('PTS', '-'),
        'OREB': s.get('GP', '-'),  # stat_id=19 is OREB
        'REB': s.get('REB', '-'), 'AST': s.get('AST', '-'),
        'STL': s.get('STL', '-'), 'BLK': s.get('BLK', '-'), 'TO': s.get('TO', '-'),
        'ATO': s.get('TW', '-'),  # stat_id=20 is A/TO
    })
rows.sort(key=lambda x: x['rank'])

tk_to_name = {}
tk_to_row = {}
for tid, t in wlt.items():
    tk = t.get('team_key', '')
    tk_to_name[tk] = t.get('name', '?')
for r in rows:
    tk_to_row[r['team_key']] = r

# ── 推导季后赛排名 ──
def derive_playoff_placements():
    """从 W21-23 对阵推导 1-8 名"""
    if not weekly_sb.get('21') or not weekly_sb.get('22') or not weekly_sb.get('23'):
        return []
    
    # QF (W21): 8 强
    qf_winners, qf_losers = [], []
    for m in weekly_sb['21']:
        if m.get('is_playoffs') != '1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk != t1k else t2k
        qf_winners.append(wk)
        qf_losers.append(lk)
    
    # SF (W22): 半决赛 = QF 胜者之间；安慰赛 = QF 败者之间
    sf_winners, sf_losers = [], []
    con_w22_winners, con_w22_losers = [], []
    for m in weekly_sb['22']:
        if m.get('is_playoffs') != '1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk != t1k else t2k
        if t1k in qf_winners and t2k in qf_winners:
            sf_winners.append(wk)
            sf_losers.append(lk)
        else:
            con_w22_winners.append(wk)
            con_w22_losers.append(lk)
    
    # Finals (W23)
    placements = {}
    for m in weekly_sb['23']:
        if m.get('is_playoffs') != '1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk != t1k else t2k
        
        if t1k in sf_winners and t2k in sf_winners:
            # 冠军赛
            placements[1] = wk
            placements[2] = lk
        elif t1k in sf_losers and t2k in sf_losers:
            # 季军赛
            placements[3] = wk
            placements[4] = lk
        elif t1k in con_w22_winners and t2k in con_w22_winners:
            # 5-6 名
            placements[5] = wk
            placements[6] = lk
        elif t1k in con_w22_losers and t2k in con_w22_losers:
            # 7-8 名
            placements[7] = wk
            placements[8] = lk
        else:
            # fallback: 5-6 or 7-8
            if 5 not in placements:
                placements[5] = wk
                placements[6] = lk
            else:
                placements[7] = wk
                placements[8] = lk
    
    result = []
    for place in sorted(placements.keys()):
        tk = placements[place]
        result.append((place, tk, tk_to_name.get(tk, '?')))
    return result

playoff_placements = derive_playoff_placements()

# 11-cat 列表 (OREB 在 REB 前面)
ALL_CATS = ['FG%', 'FT%', '3PM', 'PTS', 'OREB', 'REB', 'AST', 'STL', 'BLK', 'TO', 'A/TO']
CAT_LABELS = {'FG%':'FG%','FT%':'FT%','3PM':'3PM','PTS':'PTS','REB':'REB','OREB':'OREB',
              'AST':'AST','STL':'STL','BLK':'BLK','TO':'TO','A/TO':'A/TO',
              's19':'OREB','s20':'A/TO'}

# ── HTML 构建 ──
html = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fantasy NBA 赛季数据总览</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f6fa;color:#2d3436;margin:0;padding:20px;line-height:1.6}
h1{color:#2d3436;text-align:center;font-size:1.8em;margin-bottom:4px}
h2{color:#e17055;border-bottom:2px solid #ddd;padding-bottom:6px;margin-top:36px}
h3{color:#0984e3;margin:14px 0 6px}
h4{color:#636e72;margin:12px 0 4px}
table{border-collapse:collapse;width:100%;margin-bottom:16px;font-size:.82em}
th{background:#dfe6e9;color:#2d3436;padding:7px 10px;text-align:center;white-space:nowrap;position:sticky;top:0;font-weight:600;border-bottom:2px solid #b2bec3}
td{padding:5px 8px;border-bottom:1px solid #e8e8e8;text-align:center;white-space:nowrap}
tr:hover td{background:#f0f0f5}
.tn{text-align:left;font-weight:600;color:#2d3436;max-width:200px;overflow:hidden;text-overflow:ellipsis}
.sec{background:#fff;border-radius:8px;padding:16px 20px;margin-bottom:24px;overflow-x:auto;box-shadow:0 1px 4px rgba(0,0,0,.08)}
details summary{cursor:pointer;color:#e17055;font-weight:bold;padding:6px 0;font-size:.95em}
details[open] summary{margin-bottom:8px}
.w{color:#00b894;font-weight:600}.l{color:#d63031;font-weight:600}.t-col{color:#636e72}
.pf-win{color:#00b894;font-weight:bold}.pf-lose{color:#b2bec3}
.rank-up{color:#00b894;font-size:.7em}.rank-down{color:#d63031;font-size:.7em}
.cat-w{background:#e8f8f5;color:#00b894}.cat-l{background:#fdf2f2;color:#d63031}.cat-t{background:#faf5e4;color:#636e72}
.score-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:.9em}
.sb-win{background:#e8f8f5;color:#00b894}.sb-lose{background:#fdf2f2;color:#d63031}.sb-tie{background:#faf5e4;color:#636e72}
.subtitle{text-align:center;color:#888;margin-bottom:20px}
.nav{text-align:center;margin:16px 0;position:sticky;top:0;background:#f5f6fa;z-index:10;padding:10px 0}
.nav a{color:#e17055;text-decoration:none;margin:0 8px;padding:6px 12px;border:1px solid #ddd;border-radius:6px;font-size:.82em;background:#fff}
.nav a:hover{background:#ffeaa7;border-color:#e17055}
.medal1{color:#fdcb6e;font-size:1.2em;font-weight:bold}.medal2{color:#b2bec3;font-size:1.1em;font-weight:bold}.medal3{color:#e17055;font-size:1.1em;font-weight:bold}
.wl-w{color:#00b894;font-weight:bold}.wl-l{color:#d63031}.wl-t{color:#636e72}
.top3{background:#fff9e6;font-weight:bold}
.sub-table th{background:#f0f0f5;color:#636e72;font-size:.8em}
.sub-table td{font-size:.8em}
</style></head><body>
<h1>&#127936; Fantasy NBA 赛季数据总览</h1>
<p class="subtitle">League 15393 &middot; Yahoo Fantasy Basketball &middot; 16 支队 &middot; 11-Cat H2H</p>
<div class="nav">
<a href="index.html" style="color:#c8a45c;font-weight:500">&#127968; HUB</a>
<a href="fantasy_season_review.html">&#127942; Season Review</a>
<a href="classic_battles.html">&#9876; Classic Battles</a>
<span style="color:#ddd">|</span>
<a href="#standings">&#128202; 战绩</a>
<a href="#weekly">&#128197; 每周对阵</a>
<a href="#wl-tracker">&#128200; 经理胜负变化</a>
<a href="#rankings">&#128200; 排名变化</a>
<a href="#playoffs">&#127942; 季后赛</a>
<a href="#draft">&#127919; 选秀</a>
<a href="#transactions">&#128260; 交易</a>
</div>
'''

# ═══════════════════════════════════════════════════════════════
# 1. 战绩 & 统计 (含 OREB, A/TO) - 每列 Top3 高亮
# ═══════════════════════════════════════════════════════════════

# 计算每个统计列的 top-3 值 (用于高亮)
stat_cols = ['FGpct','FTpct','3PM','PTS','OREB','REB','AST','STL','BLK','TO','ATO']
# 大部分越高越好，TO 越低越好
lower_better = {'TO'}
col_top3 = {}
for col in stat_cols:
    vals = []
    for r in rows:
        try:
            vals.append(float(r[col]))
        except (ValueError, TypeError):
            vals.append(None)
    valid = [v for v in vals if v is not None]
    if not valid:
        col_top3[col] = set()
        continue
    if col in lower_better:
        valid.sort()
    else:
        valid.sort(reverse=True)
    top3_vals = valid[:3]
    threshold = top3_vals[-1] if top3_vals else None
    if threshold is not None:
        if col in lower_better:
            col_top3[col] = {v for v in valid if v <= threshold}
        else:
            col_top3[col] = {v for v in valid if v >= threshold}
    else:
        col_top3[col] = set()

def is_top3(col, val_str):
    try:
        v = float(val_str)
        return v in col_top3.get(col, set())
    except (ValueError, TypeError):
        return False

def td_val(col, val_str):
    if is_top3(col, val_str):
        return f'<td class="top3">{val_str} &#9733;</td>'
    return f'<td>{val_str}</td>'

html += '<h2 id="standings">&#128202; 一、队伍战绩 &amp; 赛季统计</h2><div class="sec"><table><tr>'
html += '<th>#</th><th>队伍</th><th>经理</th><th>W</th><th>L</th><th>T</th><th>Win%</th><th>Moves</th><th>Trades</th>'
html += '<th>FG%</th><th>FT%</th><th>3PM</th><th>PTS</th><th>OREB</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TO</th><th>A/TO</th></tr>'
for r in rows:
    html += f'<tr><td>{r["rank"]}</td><td class="tn">{r["team"]}</td><td>{r["manager"]}</td>'
    html += f'<td class="w">{r["W"]}</td><td class="l">{r["L"]}</td><td>{r["T"]}</td><td>{r["pct"]}</td>'
    html += f'<td>{r["moves"]}</td><td>{r["trades"]}</td>'
    html += td_val('FGpct', r['FGpct']) + td_val('FTpct', r['FTpct']) + td_val('3PM', r['3PM'])
    html += td_val('PTS', r['PTS']) + td_val('OREB', r['OREB']) + td_val('REB', r['REB']) + td_val('AST', r['AST'])
    html += td_val('STL', r['STL']) + td_val('BLK', r['BLK']) + td_val('TO', r['TO'])
    html += td_val('ATO', r['ATO'])
    html += '</tr>'
html += '</table></div>'

# ═══════════════════════════════════════════════════════════════
# 2. 每周对阵结果 (11-cat)
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="weekly">&#128197; 二、每周对阵结果</h2><div class="sec">'

def cat_winner_cls(sw, cat, t1k):
    """根据 stat_winners 判断某 category 对 team1 来说是 win/loss/tie
    sw 是 stat_winners dict，cat 是 ALL_CATS 里的 key (如 OREB)
    stat_winners 里可能存为 s19/s20"""
    # 尝试多个可能的 key
    reverse_map = {'OREB': 's19', 'A/TO': 's20'}
    sw_entry = sw.get(cat) or sw.get(reverse_map.get(cat, '')) or {}
    if not isinstance(sw_entry, dict):
        return 'cat-t'
    if sw_entry.get('tied') == '1' or sw_entry.get('tied') == 1:
        return 'cat-t'
    winner = sw_entry.get('winner', '')
    if not winner:
        return 'cat-t'
    if winner == t1k:
        return 'cat-w'
    return 'cat-l'

for wk in sorted(weekly_sb.keys(), key=int):
    matchups = weekly_sb[wk]
    is_pf = any(m.get('is_playoffs') == '1' for m in matchups)
    tag = ' &#127942; 季后赛' if is_pf else ''
    open_attr = ' open' if int(wk) >= 21 else ''
    html += f'<details{open_attr}><summary>Week {wk}{tag} ({len(matchups)} 场)</summary>'
    html += '<table><tr><th>队伍A</th><th>比分</th><th>队伍B</th>'
    for c in ALL_CATS:
        html += f'<th>{CAT_LABELS[c]}</th>'
    html += '</tr>'
    
    for m in matchups:
        t1 = m.get('team1', '?')
        t2 = m.get('team2', '?')
        score = m.get('score', '?')
        w1 = m.get('team1_cat_wins', 0)
        w2 = m.get('team2_cat_wins', 0)
        sw = m.get('stat_winners', {})
        t1k = m.get('team1_key', '')
        
        t1_cls = 'pf-win' if w1 > w2 else ('pf-lose' if w1 < w2 else '')
        t2_cls = 'pf-win' if w2 > w1 else ('pf-lose' if w2 < w1 else '')
        score_cls = 'sb-win' if w1 > w2 else ('sb-lose' if w1 < w2 else 'sb-tie')
        
        is_you = False
        row_cls = ''
        
        html += f'<tr{row_cls}><td class="tn {t1_cls}">{t1}</td>'
        html += f'<td><span class="score-badge {score_cls}">{score}</span></td>'
        html += f'<td class="tn {t2_cls}">{t2}</td>'
        
        t1s = m.get('team1_stats', {})
        t2s = m.get('team2_stats', {})
        for c in ALL_CATS:
            cls = cat_winner_cls(sw, c, t1k)
            v1 = t1s.get(c, t1s.get(CAT_LABELS.get(c, c), ''))
            v2 = t2s.get(c, t2s.get(CAT_LABELS.get(c, c), ''))
            display = f'{v1}/{v2}' if v1 and v2 else ('-' if not v1 and not v2 else f'{v1 or "?"}/{v2 or "?"}')
            html += f'<td class="{cls}" style="font-size:.72em">{display}</td>'
        html += '</tr>'
    html += '</table></details>'

html += '</div>'

# ═══════════════════════════════════════════════════════════════
# 2.5. 经理每周胜负变化 (新增)
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="wl-tracker">&#128200; 二-b、经理每周胜负变化</h2><div class="sec">'

# Build per-manager per-week W/L record
manager_weekly_wl = {}  # team_key -> [{week, opponent, w, l, t, score, result}]
weeks_sorted = sorted(weekly_sb.keys(), key=int)

for wk in weeks_sorted:
    for m in weekly_sb[wk]:
        w1 = m.get('team1_cat_wins', 0)
        w2 = m.get('team2_cat_wins', 0)
        ties = m.get('ties', 0)
        t1k = m.get('team1_key', '')
        t2k = m.get('team2_key', '')
        
        if t1k not in manager_weekly_wl:
            manager_weekly_wl[t1k] = {}
        if t2k not in manager_weekly_wl:
            manager_weekly_wl[t2k] = {}
        
        result1 = 'W' if w1 > w2 else ('L' if w1 < w2 else 'T')
        result2 = 'W' if w2 > w1 else ('L' if w2 < w1 else 'T')
        
        manager_weekly_wl[t1k][wk] = {
            'opponent': m.get('team2', '?'), 'w': w1, 'l': w2, 't': ties,
            'score': m.get('score', '?'), 'result': result1
        }
        manager_weekly_wl[t2k][wk] = {
            'opponent': m.get('team1', '?'), 'w': w2, 'l': w1, 't': ties,
            'score': f"{w2}-{w1}-{ties}", 'result': result2
        }

# 表格: 行=经理，列=周
html += '<div style="overflow-x:auto"><table><tr><th>队伍</th><th>经理</th>'
for wk in weeks_sorted:
    is_pf = int(wk) >= 21
    style = ' style="color:#FFD700"' if is_pf else ''
    html += f'<th{style}>W{wk}</th>'
html += '<th>总W</th><th>总L</th><th>总T</th></tr>'

for r in rows:
    tk = r['team_key']
    cls = ''
    html += f'<tr{cls}><td class="tn">{r["team"]}</td><td>{r["manager"]}</td>'
    
    total_w, total_l, total_t = 0, 0, 0
    for wk in weeks_sorted:
        wl = manager_weekly_wl.get(tk, {}).get(wk)
        if not wl:
            html += '<td>-</td>'
            continue
        
        res = wl['result']
        score = wl['score']
        opp = wl['opponent'][:8]
        
        if res == 'W':
            cell_cls = 'wl-w'
            total_w += 1
        elif res == 'L':
            cell_cls = 'wl-l'
            total_l += 1
        else:
            cell_cls = 'wl-t'
            total_t += 1
        
        html += f'<td class="{cell_cls}" title="{opp}: {wl["w"]}-{wl["l"]}-{wl["t"]}" style="font-size:.75em;cursor:help">{res}<br><span style="font-size:.7em;color:#888">{score}</span></td>'
    
    html += f'<td class="w">{total_w}</td><td class="l">{total_l}</td><td>{total_t}</td></tr>'

html += '</table></div></div>'

# ═══════════════════════════════════════════════════════════════
# 3. 排名变化
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="rankings">&#128200; 三、每周排名变化</h2><div class="sec">'

all_teams_keys = []
if weekly_st:
    first_wk = min(weekly_st.keys(), key=int)
    all_teams_keys = [s['key'] for s in weekly_st[first_wk]]

tk_name_st = {}
for wk_data in weekly_st.values():
    for s in wk_data:
        tk_name_st[s.get('key', '')] = s.get('name', '?')

html += '<div style="overflow-x:auto"><table><tr><th>队伍</th>'
for wk in weeks_sorted:
    is_pf = int(wk) >= 21
    style = ' style="color:#FFD700"' if is_pf else ''
    html += f'<th{style}>W{wk}</th>'
html += '</tr>'

for tk in all_teams_keys:
    name = tk_name_st.get(tk, '?')
    html += f'<tr><td class="tn">{name}</td>'
    
    prev_rank = None
    for wk in weeks_sorted:
        rank = None
        for s in weekly_st.get(wk, []):
            if s.get('key') == tk:
                rank = s['rank']
                break
        
        if rank is None:
            html += '<td>-</td>'
        else:
            if rank <= 3: color = '#FFD700'
            elif rank <= 8: color = '#7fff7f'
            elif rank <= 12: color = '#e0e0e0'
            else: color = '#ff8888'
            
            arrow = ''
            if prev_rank is not None:
                diff = prev_rank - rank
                if diff > 0: arrow = f' <span class="rank-up">&#9650;{diff}</span>'
                elif diff < 0: arrow = f' <span class="rank-down">&#9660;{-diff}</span>'
            
            html += f'<td style="color:{color};font-weight:{"bold" if rank<=3 else "normal"}">{rank}{arrow}</td>'
        prev_rank = rank
    html += '</tr>'

html += '</table></div></div>'

# ═══════════════════════════════════════════════════════════════
# 4. 季后赛对决 (决赛 vs 季军赛分开)
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="playoffs">&#127942; 四、季后赛对决</h2><div class="sec">'

def render_matchup_table(matchups, title=''):
    """渲染一组对阵的表格"""
    h = ''
    if title:
        h += f'<h4>{title}</h4>'
    h += '<table><tr><th style="width:28%">队伍A</th><th>比分</th><th style="width:28%">队伍B</th>'
    for c in ALL_CATS:
        h += f'<th>{CAT_LABELS[c]}</th>'
    h += '</tr>'
    
    for m in matchups:
        t1 = m.get('team1', '?')
        t2 = m.get('team2', '?')
        score = m.get('score', '?')
        w1 = m.get('team1_cat_wins', 0)
        w2 = m.get('team2_cat_wins', 0)
        sw = m.get('stat_winners', {})
        t1k = m.get('team1_key', '')
        
        t1_cls = 'pf-win' if w1 > w2 else 'pf-lose'
        t2_cls = 'pf-win' if w2 > w1 else 'pf-lose'
        winner_icon = ' &#10004;' if w1 > w2 else ''
        loser_icon = ' &#10004;' if w2 > w1 else ''
        score_cls = 'sb-win' if w1 > w2 else 'sb-lose'
        
        is_you = False
        row_cls = ''
        
        h += f'<tr{row_cls}><td class="tn {t1_cls}">{t1}{winner_icon}</td>'
        h += f'<td><span class="score-badge {score_cls}">{score}</span></td>'
        h += f'<td class="tn {t2_cls}">{t2}{loser_icon}</td>'
        
        t1s = m.get('team1_stats', {})
        t2s = m.get('team2_stats', {})
        for c in ALL_CATS:
            cls = cat_winner_cls(sw, c, t1k)
            v1 = t1s.get(c, t1s.get(CAT_LABELS.get(c, c), ''))
            v2 = t2s.get(c, t2s.get(CAT_LABELS.get(c, c), ''))
            display = f'{v1}/{v2}' if v1 and v2 else '-'
            h += f'<td class="{cls}" style="font-size:.72em">{display}</td>'
        h += '</tr>'
    h += '</table>'
    return h

# W21: 8 强
if weekly_sb.get('21'):
    pf21 = [m for m in weekly_sb['21'] if m.get('is_playoffs') == '1']
    html += render_matchup_table(pf21, '&#127917; 第一轮 8强 (Week 21)')

# W22: 半决赛 + 5-8名争夺
if weekly_sb.get('22'):
    pf22 = [m for m in weekly_sb['22'] if m.get('is_playoffs') == '1']
    # 区分半决赛和安慰赛
    qf_winners = set()
    for m in weekly_sb.get('21', []):
        if m.get('is_playoffs') == '1':
            qf_winners.add(m['winner_team_key'])
    
    sf22 = [m for m in pf22 if m['team1_key'] in qf_winners and m['team2_key'] in qf_winners]
    con22 = [m for m in pf22 if m not in sf22]
    
    html += render_matchup_table(sf22, '&#127917; 半决赛 (Week 22)')
    if con22:
        html += render_matchup_table(con22, '&#127917; 5-8名争夺 (Week 22)')

# W23: 决赛 + 季军赛 + 5-8名
if weekly_sb.get('23'):
    pf23 = [m for m in weekly_sb['23'] if m.get('is_playoffs') == '1']
    
    sf_winners = set()
    sf_losers = set()
    for m in weekly_sb.get('22', []):
        if m.get('is_playoffs') == '1':
            wk = m['winner_team_key']
            t1k, t2k = m['team1_key'], m['team2_key']
            lk = t1k if wk != t1k else t2k
            if t1k in qf_winners and t2k in qf_winners:
                sf_winners.add(wk)
                sf_losers.add(lk)
    
    finals = [m for m in pf23 if m['team1_key'] in sf_winners and m['team2_key'] in sf_winners]
    third_place = [m for m in pf23 if m['team1_key'] in sf_losers and m['team2_key'] in sf_losers]
    others = [m for m in pf23 if m not in finals and m not in third_place]
    
    html += render_matchup_table(finals, '&#127942;&#127942;&#127942; 总决赛 - 冠亚军争夺 (Week 23)')
    if third_place:
        html += render_matchup_table(third_place, '&#129353; 季军赛 - 3/4名争夺 (Week 23)')
    if others:
        html += render_matchup_table(others, '5-8名排位赛 (Week 23)')

# 最终排名
html += '<h3>&#127942; 季后赛最终排名</h3><table><tr><th>名次</th><th>队伍</th><th>经理</th></tr>'
medals = {1: '&#129351; 冠军', 2: '&#129352; 亚军', 3: '&#129353; 季军', 4: '第4名', 5: '第5名', 6: '第6名', 7: '第7名', 8: '第8名'}
medal_cls = {1: 'medal1', 2: 'medal2', 3: 'medal3'}

for place, tk, name in playoff_placements:
    mgr = ''
    for tid, t in wlt.items():
        if t.get('team_key') == tk:
            mgr = MANAGER_OVERRIDES.get(t.get('name', ''), t.get('manager', '?'))
            break
    row_cls = ''
    m_cls = medal_cls.get(place, '')
    m_label = medals.get(place, f'第{place}名')
    html += f'<tr{row_cls}><td class="{m_cls}">{m_label}</td><td class="tn">{name}</td><td>{mgr}</td></tr>'

html += '</table></div>'

# ═══════════════════════════════════════════════════════════════
# 5. 选秀记录 (球员居中、Rank、11-cat)
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="draft">&#127919; 五、各队选秀记录</h2><div class="sec">'

draft_by_team = {}
for p in draft:
    tid = p.get('team_key', '')
    if tid not in draft_by_team:
        draft_by_team[tid] = []
    draft_by_team[tid].append(p)

DRAFT_COLS = ['FG%', 'FT%', '3PM', 'PTS', 'OREB', 'REB', 'AST', 'STL', 'BLK', 'TO', 'A/TO']
# player_stats 里的实际 key 映射
PS_KEY_MAP = {'FG%':'FG%','FT%':'FT%','3PM':'3PM','PTS':'PTS','OREB':'GP','REB':'REB',
              'AST':'AST','STL':'STL','BLK':'BLK','TO':'TO','A/TO':'TW'}

for r in rows:
    tk = r['team_key']
    picks = draft_by_team.get(tk, [])
    picks.sort(key=lambda x: (x.get('round', 0), x.get('pick', 0)))
    html += f'<details><summary>{r["team"]} ({r["manager"]}) - {len(picks)} picks</summary>'
    html += '<table class="sub-table"><tr><th>轮</th><th>顺位</th><th>球员</th><th>Rank</th>'
    for c in DRAFT_COLS:
        html += f'<th>{c}</th>'
    html += '</tr>'
    for p in picks:
        pk = p.get('player_key', '')
        ps = player_stats.get(pk, {})
        pst = ps.get('stats', {})
        name = p.get('player_name', ps.get('name', '?'))
        rank = rank_pts.get(pk, 999)
        # Top100 标记
        if rank <= 20:
            rank_display = f'<span style="color:#e17055;font-weight:bold">#{rank} &#11088;</span>'
            row_style = ' style="background:#fff5f5"'
        elif rank <= 50:
            rank_display = f'<span style="color:#e17055;font-weight:bold">#{rank}</span>'
            row_style = ' style="background:#fff9f5"'
        elif rank <= 100:
            rank_display = f'<span style="color:#fdcb6e;font-weight:bold">#{rank}</span>'
            row_style = ' style="background:#fffdf5"'
        else:
            rank_display = f'#{rank}'
            row_style = ''
        html += f'<tr{row_style}><td>{p.get("round","?")}</td><td>{p.get("pick","?")}</td>'
        html += f'<td style="text-align:center">{player_img_html(pk)}{name}</td><td>{rank_display}</td>'
        for c in DRAFT_COLS:
            real_key = PS_KEY_MAP[c]
            val = pst.get(real_key, '-')
            html += f'<td>{val}</td>'
        html += '</tr>'
    html += '</table></details>'
html += '</div>'

# ═══════════════════════════════════════════════════════════════
# 6. 交易 & Waiver（含经理间转会 trade）
# ═══════════════════════════════════════════════════════════════
html += '<h2 id="transactions">&#128260; 六、交易 &amp; Waiver 操作</h2><div class="sec">'

# 先单独展示经理间交易（trade）
trades_list = [t for t in txs if t.get('type') == 'trade']
if trades_list:
    html += '<h3>&#129309; 经理间转会</h3>'
    for trade in sorted(trades_list, key=lambda x: x.get('timestamp', ''), reverse=True):
        ts_raw = trade.get('timestamp', '')
        try:
            ts_display = datetime.fromtimestamp(int(ts_raw)).strftime('%Y-%m-%d')
        except:
            ts_display = str(ts_raw)
        
        # 按 dst_team 分组球员
        team_gets = {}  # team_name -> [(player_name, src_team, pk)]
        for p in trade.get('players', []):
            dst = p.get('dst_team', '?')
            pname = p.get('name', p.get('player_name', '?'))
            pk = p.get('player_key', '')
            if dst not in team_gets:
                team_gets[dst] = []
            team_gets[dst].append((pname, p.get('src_team', '?'), pk))
        
        teams = list(team_gets.keys())
        if len(teams) >= 2:
            t1, t2 = teams[0], teams[1]
            t1_gets = team_gets[t1]
            t2_gets = team_gets[t2]
            
            # 多维分析每个球员
            all_levels = []
            all_reasons_html = []
            for pname, _, pk in t1_gets + t2_gets:
                level, reasons = analyze_blockbuster(pk, pname, rank_pts, cat_ranks, draft, player_stats)
                all_levels.append(level)
                if reasons:
                    fire = '&#128293;' * min(level, 3)
                    all_reasons_html.append(f'{fire} {player_img_html(pk, 18)}<b>{pname}</b>: {" / ".join(reasons)}')
            
            max_level = max(all_levels, default=0)
            if max_level >= 3:
                bb_label = '&#128293;&#128293;&#128293; 超级重磅'
            elif max_level >= 2:
                bb_label = '&#128293;&#128293; 重磅'
            elif max_level >= 1:
                bb_label = '&#128293; 值得关注'
            else:
                bb_label = ''
            
            # 描述球员 (含 Rank)
            def fmt_player(pname, pk):
                r = rank_pts.get(pk, 999)
                img = player_img_html(pk, 20)
                if r <= 20: return f'{img}<span style="color:#e17055;font-weight:bold">{pname} (Rank#{r} &#11088;)</span>'
                elif r <= 50: return f'{img}<span style="color:#e17055">{pname} (Rank#{r})</span>'
                elif r <= 100: return f'{img}<span style="color:#fdcb6e">{pname} (Rank#{r})</span>'
                else: return f'{img}{pname}'
            
            t1_names = ', '.join(fmt_player(n, pk) for n, _, pk in t1_gets)
            t2_names = ', '.join(fmt_player(n, pk) for n, _, pk in t2_gets)
            
            html += f'<div style="border:1px solid #ddd;border-radius:8px;padding:12px;margin:8px 0;background:#fafafa">'
            html += f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            html += f'<span style="font-weight:bold;color:#636e72">{ts_display}</span>'
            if bb_label:
                html += f'<span style="color:#e17055;font-weight:bold">{bb_label}</span>'
            html += '</div>'
            html += f'<table style="width:100%;font-size:.85em"><tr>'
            html += f'<th style="width:45%;text-align:left">{t1} 获得</th>'
            html += f'<th style="width:10%">&#8644;</th>'
            html += f'<th style="width:45%;text-align:left">{t2} 获得</th></tr>'
            html += f'<tr><td>{t1_names}</td><td style="text-align:center;color:#636e72;font-size:1.2em">&#8644;</td><td>{t2_names}</td></tr>'
            html += '</table>'
            if all_reasons_html:
                html += '<div style="font-size:.78em;color:#636e72;margin-top:6px;border-top:1px dashed #ddd;padding-top:6px">'
                html += '<br>'.join(all_reasons_html)
                html += '</div>'
            html += '</div>'
    html += '<hr style="border:0;border-top:1px solid #ddd;margin:20px 0">'

# 按队伍分组
tx_by_team = {}
for tx in txs:
    for p in tx.get('players', []):
        dst = p.get('dst_team_key', '')
        src = p.get('src_team_key', '')
        tx_type = tx.get('type', '')
        for tk in [dst, src]:
            if tk and tk not in tx_by_team:
                tx_by_team[tk] = []
        if dst:
            role = 'TRADE-IN' if tx_type == 'trade' else 'ADD'
            tx_by_team[dst].append({**tx, '_role': role, '_player': p})
        if src and src != dst:
            role = 'TRADE-OUT' if tx_type == 'trade' else 'DROP'
            tx_by_team[src].append({**tx, '_role': role, '_player': p})

def blockbuster_reason(tx, player_stats, rank_pts, cat_ranks, draft_data):
    """多维重磅分析，返回 HTML"""
    pid = tx.get('_player', {}).get('player_key', '')
    pname = tx.get('_player', {}).get('player_name', tx.get('_player', {}).get('name', '?'))
    level, reasons = analyze_blockbuster(pid, pname, rank_pts, cat_ranks, draft_data, player_stats)
    if level == 0:
        return ''
    fire = '&#128293;' * min(level, 3)
    return f'{fire} {" / ".join(reasons)}'

for r in rows:
    tk = r['team_key']
    team_txs = tx_by_team.get(tk, [])
    adds = [t for t in team_txs if t['_role'] in ('ADD', 'TRADE-IN')]
    drops = [t for t in team_txs if t['_role'] in ('DROP', 'TRADE-OUT')]
    trade_in = [t for t in team_txs if t['_role'] == 'TRADE-IN']
    trade_out = [t for t in team_txs if t['_role'] == 'TRADE-OUT']
    summary_parts = [f'{len(adds)} adds', f'{len(drops)} drops']
    if trade_in or trade_out:
        summary_parts.append(f'{len(trade_in)} trade-in / {len(trade_out)} trade-out')
    html += f'<details><summary>{r["team"]} ({r["manager"]}) - {" / ".join(summary_parts)}</summary>'
    html += '<table class="sub-table"><tr><th>类型</th><th>球员</th><th>操作</th><th>时间</th><th>重磅原因</th></tr>'
    
    seen = set()
    for t in sorted(team_txs, key=lambda x: x.get('timestamp', ''), reverse=True):
        p = t['_player']
        pname = p.get('player_name', p.get('name', player_stats.get(p.get('player_key',''),{}).get('name','?')))
        key = f"{t.get('tx_id','')}-{pname}-{t['_role']}"
        if key in seen: continue
        seen.add(key)
        
        role = t['_role']
        if role == 'ADD':
            role_cls, role_txt = 'w', 'ADD'
        elif role == 'DROP':
            role_cls, role_txt = 'l', 'DROP'
        elif role == 'TRADE-IN':
            role_cls, role_txt = 'w', '&#129309; TRADE-IN'
        else:
            role_cls, role_txt = 'l', '&#129309; TRADE-OUT'
        
        tx_type_display = t.get('type', '?')
        
        ts_raw = t.get('timestamp', '')
        try:
            ts_display = datetime.fromtimestamp(int(ts_raw)).strftime('%Y-%m-%d')
        except:
            ts_display = str(ts_raw)
        
        bb_reason = blockbuster_reason(t, player_stats, rank_pts, cat_ranks, draft)
        bb_html = f'<span style="color:#e17055">{bb_reason}</span>' if bb_reason else ''
        
        html += f'<tr><td>{tx_type_display}</td><td style="text-align:center">{player_img_html(p.get("player_key",""), 18)}{pname}</td>'
        html += f'<td class="{role_cls}">{role_txt}</td><td style="font-size:.75em">{ts_display}</td>'
        html += f'<td style="font-size:.75em">{bb_html}</td></tr>'
    
    html += '</table></details>'

html += '</div>'

# Footer
html += '<p style="text-align:center;color:#b2bec3;margin-top:40px;font-size:.8em">Generated by Fantasy Basketball Review Skill</p>'
html += '</body></html>'

out_path = os.path.join(os.path.dirname(__file__), 'fantasy_data_overview.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[OK] {out_path}")
