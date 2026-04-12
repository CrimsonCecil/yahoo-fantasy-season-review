#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classic Battles v2 — 以下克上经典战役独立报告
每场包含：完整阵容列表+Rank+11项数据、当周操作、翻盘分析
"""
import json, sys, os
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('yahoo_full_data.json', encoding='utf-8'))

wlt = d.get('teams_wlt', {})
stats = d.get('team_season_stats', {})
draft = d.get('draft_picks_raw', [])
txs = d.get('transactions', [])
player_stats = d.get('player_stats', {})
weekly_sb = d.get('weekly_scoreboard', {})
weekly_st = d.get('weekly_standings', {})
team_logos = d.get('team_logos', {})
manager_avatars = d.get('manager_avatars', {})
classic_upsets = d.get('classic_upsets', [])
weekly_roster_rank = d.get('weekly_roster_rank', {})
weekly_rosters = d.get('weekly_rosters', {})
player_nba_map = d.get('player_nba_map', {})

MANAGER_OVERRIDES = {'King Crimson Cecil': 'Cecil'}

# ═══════════════════════════════════════════════════════════════
# 数据预处理
# ═══════════════════════════════════════════════════════════════

import statistics

ZSCORE_CATS = {
    'FG%': ('FG%', False), 'FT%': ('FT%', False), '3PM': ('3PM', False),
    'PTS': ('PTS', False), 'OREB': ('GP', False), 'REB': ('REB', False),
    'AST': ('AST', False), 'STL': ('STL', False), 'BLK': ('BLK', False),
    'TO': ('TO', True), 'A/TO': ('TW', False),
}

def calc_zscore_rank():
    valid_pks = []
    for pk, ps in player_stats.items():
        try:
            pts_val = ps.get('stats',{}).get('PTS', 0)
            if pts_val in ('-', '', None): continue
            if float(pts_val) > 100: valid_pks.append(pk)
        except: pass
    if not valid_pks: valid_pks = list(player_stats.keys())
    cat_values = {c: [] for c in ZSCORE_CATS}
    player_vals = {}
    for pk in valid_pks:
        pst = player_stats[pk].get('stats', {})
        vals = {}
        for cat, (key, _) in ZSCORE_CATS.items():
            try: v = float(pst.get(key, 0))
            except: v = 0.0
            vals[cat] = v; cat_values[cat].append(v)
        player_vals[pk] = vals
    cat_st = {}
    for cat in ZSCORE_CATS:
        vs = cat_values[cat]
        m = statistics.mean(vs) if len(vs)>=2 else 0
        s = statistics.stdev(vs) if len(vs)>=2 else 1
        if s == 0: s = 1
        cat_st[cat] = (m, s)
    pz = {}
    for pk in valid_pks:
        vals = player_vals[pk]
        tz = sum((-1 if ZSCORE_CATS[c][1] else 1) * (vals[c] - cat_st[c][0]) / cat_st[c][1] for c in ZSCORE_CATS)
        pz[pk] = tz
    for pk in player_stats:
        if pk not in pz: pz[pk] = -99
    sp = sorted(pz.items(), key=lambda x: x[1], reverse=True)
    return {pk: i+1 for i, (pk, _) in enumerate(sp)}

rank_pts = calc_zscore_rank()

# player_id -> player_key 映射
pid_to_pk = {}
for pk, pv in player_stats.items():
    pid = pv.get('player_id')
    if pid:
        pid_to_pk[int(pid)] = pk
        pid_to_pk[str(pid)] = pk

# 11-cat 映射: 显示名 -> player_stats 中的 key
DISPLAY_CATS = ['FG%', 'FT%', '3PM', 'PTS', 'OREB', 'REB', 'AST', 'STL', 'BLK', 'TO', 'A/TO']
PS_KEY_MAP = {'FG%':'FG%','FT%':'FT%','3PM':'3PM','PTS':'PTS','OREB':'GP','REB':'REB',
              'AST':'AST','STL':'STL','BLK':'BLK','TO':'TO','A/TO':'TW'}

teams = []
for tid, t in wlt.items():
    name = t.get('name','?')
    mgr = MANAGER_OVERRIDES.get(name, t.get('manager','?'))
    tk = t.get('team_key','')
    teams.append({
        'tid': tid, 'name': name, 'manager': mgr,
        'team_key': tk, 'rank': int(t.get('rank') or 99),
        'W': int(t.get('wins') or 0), 'L': int(t.get('losses') or 0), 'T': int(t.get('ties') or 0),
        'pct': float(t.get('win_pct') or 0),
        'moves': int(t.get('moves') or 0),
        'logo': team_logos.get(tk, ''),
        'avatar': manager_avatars.get(tk, {}).get('avatar', ''),
    })
teams.sort(key=lambda x: x['rank'])
tk_to_team = {t['team_key']: t for t in teams}
mgr_to_tk = {t['manager']: t['team_key'] for t in teams}
mgr_to_team = {t['manager']: t for t in teams}

STAT_NAMES = {
    's5':'FG%','s8':'FT%','s10':'3PM','s12':'PTS','s13':'AST',
    's15':'REB','s16':'STL','s17':'BLK','s18':'TO','s19':'OREB','s20':'A/TO'
}

def get_match_detail(week, team1_key, team2_key):
    wk_data = weekly_sb.get(str(week), [])
    for m in wk_data:
        t1k, t2k = m.get('team1_key',''), m.get('team2_key','')
        if (t1k == team1_key and t2k == team2_key) or (t1k == team2_key and t2k == team1_key):
            return {
                'team1': m.get('team1',''), 'team2': m.get('team2',''),
                'team1_key': t1k, 'team2_key': t2k,
                'winner_team_key': m.get('winner_team_key', ''),
                'team1_cat_wins': m.get('team1_cat_wins', 0),
                'team2_cat_wins': m.get('team2_cat_wins', 0),
                'ties': m.get('ties', 0),
                'stat_winners': m.get('stat_winners', {}),
                'team1_stats': m.get('team1_stats', {}),
                'team2_stats': m.get('team2_stats', {}),
            }
    return None

def get_team_week_transactions(team_key, week):
    """获取某队在某周内的操作，按 tx_id 合并 add/drop 为一次操作"""
    season_start = datetime(2025, 10, 27)  # 25-26赛季 Week 1 (Mon)
    week_start = season_start + timedelta(weeks=week-1)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    # 按 tx_id 收集
    tx_groups = defaultdict(lambda: {'adds': [], 'drops': [], 'date': None, 'type': '?'})
    
    for tx in txs:
        ts = tx.get('timestamp', '')
        try:
            dt = datetime.fromtimestamp(int(ts))
        except:
            continue
        if not (week_start <= dt <= week_end):
            continue
        
        tx_id = tx.get('tx_id', id(tx))
        tx_type = tx.get('type', '?')
        
        for p in tx.get('players', []):
            dst = p.get('dst_team_key', '')
            src = p.get('src_team_key', '')
            if dst != team_key and src != team_key:
                continue
            
            pname = p.get('name', p.get('player_name', '?'))
            pk = p.get('player_key', '')
            rk = rank_pts.get(pk, 999)
            pst = player_stats.get(pk, {}).get('stats', {})
            
            # 球员 11 项 NBA.com 真实场均数据
            nba_info = player_nba_map.get(pk, {})
            nba_pg = nba_info.get('per_game', {})
            NBA_PG_MAP2 = {
                'FG%': 'FG_PCT', 'FT%': 'FT_PCT', '3PM': 'FG3M', 'PTS': 'PTS',
                'OREB': 'OREB', 'REB': 'REB', 'AST': 'AST', 'STL': 'STL',
                'BLK': 'BLK', 'TO': 'TOV', 'A/TO': 'A_TO'
            }
            p_stats = {}
            for cat in DISPLAY_CATS:
                nba_key = NBA_PG_MAP2.get(cat)
                if nba_pg and nba_key and nba_key in nba_pg:
                    val = nba_pg[nba_key]
                    if cat in ('FG%', 'FT%'):
                        p_stats[cat] = f'.{int(val*1000):03d}' if val else '-'
                    else:
                        p_stats[cat] = str(val)
                else:
                    try:
                        gp = int(float(pst.get('GP', 0) or 0))
                    except:
                        gp = 0
                    real_key = PS_KEY_MAP[cat]
                    raw = pst.get(real_key, '-')
                    p_stats[cat] = to_per_game(raw, gp, cat)
            
            op_headshot = nba_info.get('headshot_url', '')
            info = {'player': pname, 'rank': rk, 'player_key': pk, 'stats': p_stats, 'headshot': op_headshot}
            
            if dst == team_key:
                tx_groups[tx_id]['adds'].append(info)
            if src == team_key:
                tx_groups[tx_id]['drops'].append(info)
            
            tx_groups[tx_id]['date'] = dt
            tx_groups[tx_id]['type'] = tx_type
    
    # 合并为操作列表
    results = []
    for tx_id, g in tx_groups.items():
        if g['type'] == 'trade':
            action = '转会'
        elif g['type'] == 'add/drop':
            action = '换人'
        elif g['type'] == 'add':
            action = '签入'
        elif g['type'] == 'drop':
            action = '裁掉'
        else:
            action = g['type']
        
        results.append({
            'date': g['date'],
            'type': g['type'],
            'action': action,
            'adds': g['adds'],
            'drops': g['drops'],
        })
    
    return sorted(results, key=lambda x: x['date'])

RATE_CATS = {'FG%', 'FT%', 'A/TO'}  # 这些本身就是比率/场均，不需要除 GP

def to_per_game(raw_val, gp, cat):
    """将赛季总和转为场均；FG%/FT%/A/TO 保持原值"""
    if cat in RATE_CATS:
        return raw_val
    if raw_val == '-' or raw_val == '' or gp <= 0:
        return '-'
    try:
        return f'{float(raw_val) / gp:.1f}'
    except (ValueError, TypeError):
        return raw_val

def get_roster_with_stats(team_key, week):
    """获取某队某周的阵容 + 每个球员的 Rank、头像和 11 项 NBA.com 真实场均数据"""
    rosters = weekly_rosters.get(team_key, {})
    roster = rosters.get(str(week), [])
    enriched = []
    # NBA.com 场均数据 key 映射到显示名
    NBA_PG_MAP = {
        'FG%': 'FG_PCT', 'FT%': 'FT_PCT', '3PM': 'FG3M', 'PTS': 'PTS',
        'OREB': 'OREB', 'REB': 'REB', 'AST': 'AST', 'STL': 'STL',
        'BLK': 'BLK', 'TO': 'TOV', 'A/TO': 'A_TO'
    }
    for p in roster:
        pid = p.get('player_id')
        pk = pid_to_pk.get(pid, pid_to_pk.get(str(pid), f'466.p.{pid}'))
        ps = player_stats.get(pk, {})
        pst = ps.get('stats', {})
        rk = rank_pts.get(pk, 999)
        nba_info = player_nba_map.get(pk, {})
        nba_pg = nba_info.get('per_game', {})
        headshot = nba_info.get('headshot_url', '')
        try:
            gp = int(float(pst.get('GP', 0) or 0))
        except:
            gp = 0
        row = {
            'name': p.get('name', ps.get('name', '?')),
            'position': p.get('position', '?'),
            'team_abbr': p.get('team_abbr', '?'),
            'rank': rk,
            'gp': nba_pg.get('GP', gp),
            'headshot': headshot,
            'player_key': pk,
        }
        # 优先用 NBA.com 真实场均数据
        for cat in DISPLAY_CATS:
            nba_key = NBA_PG_MAP.get(cat)
            if nba_pg and nba_key and nba_key in nba_pg:
                val = nba_pg[nba_key]
                if cat in ('FG%', 'FT%'):
                    row[cat] = f'.{int(val*1000):03d}' if val else '-'
                else:
                    row[cat] = str(val)
            else:
                # fallback 到自己算
                real_key = PS_KEY_MAP[cat]
                raw = pst.get(real_key, '-')
                row[cat] = to_per_game(raw, gp, cat)
        enriched.append(row)
    enriched.sort(key=lambda x: x['rank'])
    return enriched

# ═══════════════════════════════════════════════════════════════
# 过滤：排除5-8名排位赛
# ═══════════════════════════════════════════════════════════════
qf_winners = set()
for m in weekly_sb.get('21', []):
    if m.get('is_playoffs') == '1':
        qf_winners.add(m.get('winner_team_key', ''))

sf_winners = set()
sf_losers = set()
for m in weekly_sb.get('22', []):
    if m.get('is_playoffs') != '1': continue
    t1k, t2k = m['team1_key'], m['team2_key']
    wk = m.get('winner_team_key', '')
    lk = t1k if wk != t1k else t2k
    if t1k in qf_winners and t2k in qf_winners:
        sf_winners.add(wk)
        sf_losers.add(lk)
top4 = sf_winners | sf_losers

def is_ranking_match_5_8(upset):
    w = upset.get('week', 0)
    if w < 22: return False
    wk_tk = mgr_to_tk.get(upset['winner'], '')
    lk_tk = mgr_to_tk.get(upset['loser'], '')
    if w == 22:
        if wk_tk in qf_winners and lk_tk in qf_winners:
            return False
        return True
    if w == 23:
        if wk_tk in top4 and lk_tk in top4:
            return False
        return True
    return False

filtered_upsets = [u for u in classic_upsets if not is_ranking_match_5_8(u)]
# 只保留前 5 场
filtered_upsets = filtered_upsets[:5]
print(f"Total upsets: {len(classic_upsets)}, After filtering: {len(filtered_upsets)}")

# ═══════════════════════════════════════════════════════════════
# 生成 HTML
# ═══════════════════════════════════════════════════════════════

def team_logo_html(team, size=48):
    url = team.get('logo', '')
    if url:
        return f'<img src="{url}" alt="" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;flex-shrink:0">'
    return f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#e8e4de;flex-shrink:0"></div>'

html = '''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>Classic Battles — 以下克上</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;700&display=swap');

*{box-sizing:border-box;margin:0;padding:0}
html{scroll-snap-type:y proximity;scroll-behavior:smooth;overflow-y:scroll}
body{
  font-family:'Noto Sans JP','Helvetica Neue',system-ui,sans-serif;
  background:#faf9f6;color:#2d2d2d;line-height:1.8;font-weight:300;
  -webkit-font-smoothing:antialiased;
}
.snap-section{
  scroll-snap-align:start;
  min-height:100vh;
  display:flex;flex-direction:column;justify-content:center;
  padding:40px 24px;
}
.snap-section .inner{max-width:900px;margin:0 auto;width:100%}

.hero{
  text-align:center;padding:72px 20px 56px;
  border-bottom:1px solid #e8e4de;
}
.hero h1{
  font-family:'Noto Serif JP',serif;font-size:2em;font-weight:400;
  color:#2d2d2d;letter-spacing:.08em;margin-bottom:8px;
}
.hero .sub{color:#8a8580;font-size:.88em;letter-spacing:.2em;font-weight:300}
.hero .desc{
  color:#a09a90;font-size:.82em;max-width:520px;margin:20px auto 0;line-height:1.8;
}

.container{max-width:960px;margin:0 auto;padding:48px 24px}

.battle{
  margin-bottom:72px;padding-bottom:72px;
  border-bottom:1px solid #e8e4de;
}
.battle:last-child{border-bottom:none}

.battle-num{
  font-family:'Noto Serif JP',serif;font-size:5em;font-weight:700;
  color:#f0ede8;line-height:1;margin-bottom:-28px;position:relative;z-index:0;
}

.battle-meta{
  position:relative;z-index:1;
  display:flex;align-items:center;gap:12px;margin-bottom:4px;
}
.battle-week{font-size:.72em;color:#c8a45c;letter-spacing:.2em;font-weight:400}
.battle-badge{
  font-size:.65em;padding:2px 10px;border:1px solid #c8a45c;color:#c8a45c;
  letter-spacing:.12em;
}

/* 对阵卡片 */
.matchup{
  display:flex;align-items:center;gap:0;
  margin:24px 0;background:#fff;border:1px solid #e8e4de;overflow:hidden;
}
.matchup-team{flex:1;padding:20px;display:flex;align-items:center;gap:14px}
.matchup-team.right{flex-direction:row-reverse;text-align:right}
.matchup-info{flex:1}
.matchup-mgr{font-family:'Noto Serif JP',serif;font-size:1.15em;font-weight:700;color:#2d2d2d}
.matchup-team-name{font-size:.75em;color:#b5b0a8;margin-top:2px}
.matchup-rank{font-size:.72em;color:#8a8580;margin-top:4px;font-family:'SF Mono','Consolas',monospace}
.matchup-team.winner{background:rgba(200,164,92,.04)}
.matchup-team.loser .matchup-mgr{color:#b5b0a8}
.matchup-score{
  padding:16px 20px;font-family:'Noto Serif JP',serif;font-size:1.4em;
  font-weight:700;color:#2d2d2d;white-space:nowrap;
  border-left:1px solid #f0ede8;border-right:1px solid #f0ede8;
  background:#faf9f6;min-width:80px;text-align:center;
}

/* Category 分析条 */
.cat-bar{display:flex;gap:4px;margin:16px 0;flex-wrap:wrap}
.cat-item{padding:3px 8px;font-size:.68em;letter-spacing:.05em;border:1px solid #e8e4de}
.cat-item.won{background:#f0ede8;color:#5a5550;border-color:#d0ccc4}
.cat-item.lost{background:#fff;color:#d0ccc4;border-color:#e8e4de}
.cat-item.tied{background:#fff;color:#b5b0a8;border-color:#e8e4de;font-style:italic}

/* 阵容表格 */
.roster-section{margin:24px 0}
.roster-section h4{
  font-family:'Noto Serif JP',serif;font-size:.88em;font-weight:400;
  color:#2d2d2d;letter-spacing:.08em;margin-bottom:8px;
  display:flex;align-items:center;gap:10px;
}
.roster-label{
  font-size:.65em;padding:2px 8px;border:1px solid #e8e4de;
  color:#8a8580;letter-spacing:.1em;
}
.roster-label.winner{border-color:#c8a45c;color:#c8a45c}

.roster-table{
  width:100%;border-collapse:collapse;font-size:.72em;
  margin-bottom:16px;
}
.roster-table th{
  padding:5px 6px;text-align:center;color:#b5b0a8;font-weight:400;
  border-bottom:1px solid #e8e4de;font-size:.9em;letter-spacing:.05em;
  white-space:nowrap;
}
.roster-table th:nth-child(1){text-align:left;min-width:120px}
.roster-table td{
  padding:4px 6px;text-align:center;border-bottom:1px solid #f5f3ef;
  white-space:nowrap;
}
.roster-table td:nth-child(1){text-align:left;font-weight:400;color:#2d2d2d}
.roster-table tr.top-player td{background:rgba(200,164,92,.06)}
.rank-good{color:#c8a45c;font-weight:500}
.rank-mid{color:#8a8580}
.rank-low{color:#d0ccc4}

.roster-summary{
  font-size:.78em;color:#8a8580;padding:8px 12px;
  background:#f5f3ef;margin-top:-8px;margin-bottom:16px;
}

/* 操作时间线 */
.ops-section{margin:20px 0}
.ops-title{
  font-size:.78em;color:#8a8580;letter-spacing:.12em;margin-bottom:10px;
  font-weight:400;
}
.timeline{margin:0;padding-left:20px;border-left:2px solid #e8e4de}
.timeline-item{
  font-size:.78em;color:#5a5550;margin-bottom:8px;
  position:relative;padding-left:12px;line-height:1.6;
}
.timeline-item::before{
  content:'';position:absolute;left:-25px;top:7px;
  width:8px;height:8px;border-radius:50%;background:#e8e4de;
}
.timeline-item.highlight::before{background:#c8a45c}
.timeline-date{color:#c8a45c;font-weight:400}
.timeline-action{font-weight:400}

/* 叙事 */
.narrative{margin:24px 0}
.narrative p{
  font-size:.88em;color:#5a5550;margin-bottom:12px;line-height:1.9;
  text-align:justify;
}

/* 翻盘分析 */
.analysis{
  margin:16px 0;padding:16px 20px;
  border-left:3px solid #c8a45c;background:rgba(200,164,92,.03);
}
.analysis-title{
  font-family:'Noto Serif JP',serif;font-size:.85em;color:#c8a45c;
  letter-spacing:.1em;margin-bottom:8px;font-weight:400;
}
.analysis p{font-size:.82em;color:#5a5550;line-height:1.8;margin-bottom:6px}

.back-link{
  display:inline-block;margin-bottom:32px;
  color:#c8a45c;text-decoration:none;font-size:.82em;letter-spacing:.1em;
}
.back-link:hover{text-decoration:underline}

.footer{text-align:center;color:#d0ccc4;padding:48px 20px;font-size:.75em;letter-spacing:.15em}
.top-nav{
  display:flex;flex-wrap:wrap;justify-content:center;gap:6px;
  padding:14px 20px;position:sticky;top:0;background:rgba(250,249,246,.96);
  z-index:10;border-bottom:1px solid #e8e4de;backdrop-filter:blur(8px);
}
.top-nav a{
  color:#8a8580;text-decoration:none;padding:5px 12px;font-size:.75em;
  letter-spacing:.1em;transition:color .2s;font-weight:400;
}
.top-nav a:hover{color:#c8a45c}
</style></head><body>
<div class="top-nav">
<a href="index.html" style="color:#c8a45c;font-weight:500">HUB</a>
<a href="fantasy_season_review.html">SEASON REVIEW</a>
<a href="fantasy_data_overview.html">DATA OVERVIEW</a>
</div>
'''

# Hero
html += '''
<div class="snap-section" style="justify-content:center">
<div class="hero">
<h1>Classic Battles</h1>
<p class="sub">以下克上 · 经典战役</p>
<p class="desc">
基于每周出场阵容的球员赛季 Rank 加权计算阵容实力值。<br>
当阵容实力更低的队伍赢得比赛，即为以下克上。<br>
以下收录本赛季最精彩的逆袭之战。
</p>
</div>
</div>
'''

for i, u in enumerate(filtered_upsets, 1):
    w_mgr = u['winner']
    l_mgr = u['loser']
    w_tk = mgr_to_tk.get(w_mgr, '')
    l_tk = mgr_to_tk.get(l_mgr, '')
    w_team = mgr_to_team.get(w_mgr, {})
    l_team = mgr_to_team.get(l_mgr, {})
    week = u['week']
    score = u['score']
    
    # Badge
    epic = u.get('epic_score', 0)
    badge = 'LEGENDARY' if epic >= 100 else ('EPIC' if epic >= 60 else 'NOTABLE')
    
    # Week label & importance level
    importance = 'normal'  # normal / high / critical
    importance_label = ''
    if u.get('is_playoff'):
        if week == 23:
            if w_tk in sf_winners and l_tk in sf_winners:
                wk_label = "WEEK 23 · FINALS"
                importance = 'critical'
                importance_label = '总决赛'
            else:
                wk_label = "WEEK 23 · 3RD PLACE"
                importance = 'high'
                importance_label = '季军赛'
        elif week == 22:
            wk_label = "WEEK 22 · SEMIS"
            importance = 'high'
            importance_label = '半决赛'
        else:
            wk_label = f"WEEK {week} · PLAYOFFS"
            importance = 'high'
            importance_label = '季后赛'
    else:
        wk_label = f"WEEK {week} · REGULAR SEASON"
        importance_label = '常规赛'
    
    # Phase
    if week <= 5: phase = "赛季初期"
    elif week <= 10: phase = "赛季前半段"
    elif week <= 15: phase = "赛季中段"
    elif week <= 20: phase = "常规赛尾声"
    elif week == 21: phase = "季后赛四分之一决赛"
    elif week == 22: phase = "季后赛半决赛"
    else:
        if w_tk in sf_winners and l_tk in sf_winners: phase = "总决赛"
        elif w_tk in sf_losers and l_tk in sf_losers: phase = "季军赛"
        else: phase = "季后赛第三轮"
    
    # Rosters
    w_roster = get_roster_with_stats(w_tk, week)
    l_roster = get_roster_with_stats(l_tk, week)
    
    # Avg rank
    w_avg = u.get('winner_avg_rank', 0)
    l_avg = u.get('loser_avg_rank', 0)
    rank_diff = abs(w_avg - l_avg)
    
    # Match detail
    match = get_match_detail(week, w_tk, l_tk)
    
    # Week transactions
    w_ops = get_team_week_transactions(w_tk, week)
    l_ops = get_team_week_transactions(l_tk, week)
    
    # === HTML ===
    # 根据重要度增加不同样式
    if importance == 'critical':
        border_style = 'border:2px solid #c8a45c;background:rgba(200,164,92,.03)'
    elif importance == 'high':
        border_style = 'border:1px solid #c8a45c;background:rgba(200,164,92,.015)'
    else:
        border_style = ''
    
    html += f'<div class="snap-section"><div class="inner">'
    html += f'<div class="battle" style="{border_style}">'
    html += f'<div class="battle-num">{i:02d}</div>'
    html += f'<div class="battle-meta">'
    html += f'<span class="battle-week">{wk_label}</span>'
    html += f'<span class="battle-badge">{badge}</span>'
    if importance_label:
        imp_color = '#c8a45c' if importance == 'critical' else ('#a09070' if importance == 'high' else '#b5b0a8')
        imp_bg = 'rgba(200,164,92,.1)' if importance == 'critical' else ('rgba(160,144,112,.08)' if importance == 'high' else 'transparent')
        html += f'<span style="font-size:.65em;padding:2px 10px;border:1px solid {imp_color};color:{imp_color};background:{imp_bg};letter-spacing:.12em;font-weight:500">{importance_label}</span>'
    html += f'</div>'
    
    # 对阵卡片
    html += '<div class="matchup">'
    html += f'<div class="matchup-team winner">'
    html += team_logo_html(w_team, 48)
    html += f'<div class="matchup-info">'
    html += f'<div class="matchup-mgr">{w_mgr}</div>'
    html += f'<div class="matchup-team-name">{w_team.get("name","?")}</div>'
    html += f'<div class="matchup-rank">阵容均Rank {w_avg:.0f}</div>'
    html += '</div></div>'
    html += f'<div class="matchup-score">{score}</div>'
    html += f'<div class="matchup-team loser right">'
    html += team_logo_html(l_team, 48)
    html += f'<div class="matchup-info">'
    html += f'<div class="matchup-mgr">{l_mgr}</div>'
    html += f'<div class="matchup-team-name">{l_team.get("name","?")}</div>'
    html += f'<div class="matchup-rank">阵容均Rank {l_avg:.0f}</div>'
    html += '</div></div>'
    html += '</div>'
    
    # Category 详情条
    won_cats = []
    lost_cats = []
    tied_cats = []
    if match and match.get('stat_winners'):
        sw = match['stat_winners']
        match_winner_key = match.get('winner_team_key', '')
        html += '<div class="cat-bar">'
        for cname in ['FG%','FT%','3PM','PTS','OREB','REB','AST','STL','BLK','TO','A/TO']:
            info = sw.get(cname, {})
            sw_winner = info.get('winner', '')
            sw_tied = str(info.get('tied', '0'))
            if sw_tied == '1':
                cls = 'tied'
                tied_cats.append(cname)
            elif sw_winner == match_winner_key:
                # winner of this cat == match winner == upset winner
                cls = 'won'
                won_cats.append(cname)
            else:
                cls = 'lost'
                lost_cats.append(cname)
            html += f'<span class="cat-item {cls}">{cname}</span>'
        html += '</div>'
    
    # ═══ 0. 11项数据对比表 ═══
    if match:
        t1k = match.get('team1_key','')
        t2k = match.get('team2_key','')
        t1_stats = match.get('team1_stats', {})
        t2_stats = match.get('team2_stats', {})
        match_winner_key = match.get('winner_team_key', '')
        
        # 用 match 自身的 winner_team_key 直接判断
        if match_winner_key == t1k:
            w_stats_row, l_stats_row = t1_stats, t2_stats
            w_key_match, l_key_match = t1k, t2k
        elif match_winner_key == t2k:
            w_stats_row, l_stats_row = t2_stats, t1_stats
            w_key_match, l_key_match = t2k, t1k
        else:
            # fallback: 用经理名匹配队名
            w_stats_row, l_stats_row = t1_stats, t2_stats
            w_key_match, l_key_match = t1k, t2k
        
        CAT_ORDER = ['FG%','FT%','3PM','PTS','OREB','REB','AST','STL','BLK','TO','A/TO']
        stat_winners = match.get('stat_winners', {})
        
        html += '<div style="margin:20px 0">'
        html += '<table style="width:100%;border-collapse:collapse;font-size:.85em;text-align:center">'
        # 表头
        html += '<tr style="border-bottom:2px solid #d5d0c8">'
        html += '<th style="text-align:left;padding:10px 12px;font-weight:600;color:#5a5550;width:130px">教练</th>'
        for cat in CAT_ORDER:
            html += f'<th style="padding:10px 6px;color:#7a7570;font-weight:600;font-size:.9em">{cat}</th>'
        html += '</tr>'
        
        # Winner row
        html += '<tr style="border-bottom:1px solid #e8e4de">'
        html += f'<td style="text-align:left;padding:10px 12px;font-weight:700;color:#2d6a3f;font-size:.95em">{w_mgr} <span style="font-size:.7em;color:#8a8580">胜</span></td>'
        for cat in CAT_ORDER:
            w_val = w_stats_row.get(cat, '-')
            sw = stat_winners.get(cat, {})
            sw_winner = sw.get('winner', '')
            sw_tied = str(sw.get('tied', '0'))
            
            if sw_tied == '1':
                cell_style = 'color:#a09070;font-weight:700'
            elif sw_winner == w_key_match:
                cell_style = 'color:#1a7a3a;font-weight:800;background:#e8f5e9'
            else:
                cell_style = 'color:#aaa'
            html += f'<td style="padding:10px 6px;{cell_style}">{w_val}</td>'
        html += '</tr>'
        
        # Loser row
        html += '<tr>'
        html += f'<td style="text-align:left;padding:10px 12px;font-weight:700;color:#a63d2b;font-size:.95em">{l_mgr} <span style="font-size:.7em;color:#8a8580">负</span></td>'
        for cat in CAT_ORDER:
            l_val = l_stats_row.get(cat, '-')
            sw = stat_winners.get(cat, {})
            sw_winner = sw.get('winner', '')
            sw_tied = str(sw.get('tied', '0'))
            
            if sw_tied == '1':
                cell_style = 'color:#a09070;font-weight:700'
            elif sw_winner == l_key_match:
                cell_style = 'color:#c0392b;font-weight:800;background:#fdecea'
            else:
                cell_style = 'color:#aaa'
            html += f'<td style="padding:10px 6px;{cell_style}">{l_val}</td>'
        html += '</tr>'
        
        html += '</table>'
        html += '</div>'
    
    # ═══ 1. 翻盘分析（放在最前面） ═══
    html += '<div class="analysis">'
    html += '<div class="analysis-title">翻盘分析</div>'
    
    # 阵容分析
    w_top3 = w_roster[:3] if w_roster else []
    l_top3 = l_roster[:3] if l_roster else []
    
    html += f'<p><strong>阵容对比：</strong>'
    html += f'{l_mgr} 阵容均Rank {l_avg:.0f}，拥有'
    if l_top3:
        html += '、'.join(f'{r["name"]}(#{r["rank"]})' for r in l_top3)
    html += f'等核心球员，纸面实力领先 {rank_diff:.0f} 个Rank。'
    html += f'而 {w_mgr} 阵容均Rank {w_avg:.0f}，核心是'
    if w_top3:
        html += '、'.join(f'{r["name"]}(#{r["rank"]})' for r in w_top3)
    html += '，整体星味不如对手。</p>'
    
    # 比分分析
    if won_cats and lost_cats:
        html += f'<p><strong>比分拆解：</strong>'
        html += f'{w_mgr} 在 {", ".join(won_cats)} 共 {len(won_cats)} 项上取胜'
        html += f'，{l_mgr} 赢下 {", ".join(lost_cats)} 共 {len(lost_cats)} 项'
        if tied_cats:
            html += f'，{", ".join(tied_cats)} {len(tied_cats)} 项战平'
        html += f'。最终 {w_mgr} 以 {score} 赢得比赛。</p>'
    
    # 操作影响分析
    key_w_adds = []
    for op in w_ops:
        for a in op.get('adds', []):
            if a['rank'] <= 150:
                key_w_adds.append((op['date'], a))
    if key_w_adds:
        html += f'<p><strong>关键操作：</strong>'
        for dt, a in key_w_adds[-3:]:
            html += f'{dt.strftime("%m/%d")} 签入 {a["player"]}(Rank#{a["rank"]})、'
        html = html.rstrip('、')
        html += f'。这些操作为 {w_mgr} 的翻盘提供了重要助力。</p>'
    
    # 总结
    margin = len(won_cats) - len(lost_cats) if won_cats and lost_cats else 0
    if u.get('is_playoff'):
        if phase == "总决赛":
            html += f'<p><strong>总结：</strong>总决赛中，{w_mgr} 用均Rank {w_avg:.0f} 的阵容击败均Rank {l_avg:.0f} 的 {l_mgr}，完成本赛季最伟大的以下克上。阵容深度和配置优势弥补了星味不足。</p>'
        elif phase == "季军赛":
            html += f'<p><strong>总结：</strong>季军争夺战，{w_mgr} 以 {score} 力克 {l_mgr}，用更低Rank的阵容完成逆袭，夺得联盟第三。</p>'
        else:
            html += f'<p><strong>总结：</strong>{phase}中，{w_mgr} 以 {score} 爆冷淘汰 {l_mgr}，阵容差距 {rank_diff:.0f} 位的以下克上。</p>'
    else:
        if margin <= 2:
            html += f'<p><strong>总结：</strong>比分咬到最后一刻，{w_mgr} 以 {score} 险胜。阵容Rank差 {rank_diff:.0f} 位，每个比分项都生死攸关的一战。</p>'
        else:
            html += f'<p><strong>总结：</strong>{w_mgr} 以 {score} 赢下比赛。虽然阵容纸面不如对手 {rank_diff:.0f} 位，但在关键项目上全面开花，展现了出色的阵容搭配。</p>'
    
    html += '</div>'
    
    # ═══ 2. 双方阵容列表 ═══
    def render_roster_table(roster, mgr, is_winner):
        label_cls = "winner" if is_winner else ""
        label_txt = "胜方" if is_winner else "负方"
        count = len(roster)
        avg_rk = sum(r['rank'] for r in roster) / count if count else 0
        top3 = roster[:3]
        
        h = f'<div class="roster-section">'
        h += f'<h4>{mgr} 阵容 <span class="roster-label {label_cls}">{label_txt}</span> <span style="font-size:.7em;color:#b5b0a8;font-weight:normal;margin-left:8px">NBA.com 赛季场均数据</span></h4>'
        h += '<table class="roster-table">'
        h += '<tr><th></th><th>球员</th><th>位置</th><th>球队</th><th>Rank</th><th>GP</th>'
        for cat in DISPLAY_CATS:
            h += f'<th>{cat}</th>'
        h += '</tr>'
        
        for j, r in enumerate(roster):
            tr_cls = ' class="top-player"' if j < 3 else ''
            rk = r['rank']
            if rk <= 50:
                rk_cls = 'rank-good'
            elif rk <= 150:
                rk_cls = 'rank-mid'
            else:
                rk_cls = 'rank-low'
            
            # 球员头像
            hs_url = r.get('headshot', '')
            hs_html = f'<img src="{hs_url}" alt="" style="width:28px;height:20px;border-radius:3px;object-fit:cover;vertical-align:middle" onerror="this.style.display=\'none\'">' if hs_url else ''
            
            h += f'<tr{tr_cls}>'
            h += f'<td style="width:32px;padding:2px 4px">{hs_html}</td>'
            h += f'<td>{r["name"]}</td>'
            h += f'<td>{r["position"]}</td>'
            h += f'<td>{r["team_abbr"]}</td>'
            h += f'<td class="{rk_cls}">#{rk}</td>'
            h += f'<td>{r.get("gp", "-")}</td>'
            for cat in DISPLAY_CATS:
                val = r.get(cat, '-')
                h += f'<td>{val}</td>'
            h += '</tr>'
        
        h += '</table>'
        h += f'<div class="roster-summary">'
        h += f'{count}人出战 · 阵容均Rank {avg_rk:.0f}'
        if top3:
            h += f' · 核心: {", ".join(r["name"] + "(#" + str(r["rank"]) + ")" for r in top3)}'
        h += '</div></div>'
        return h
    
    html += render_roster_table(w_roster, w_mgr, True)
    html += render_roster_table(l_roster, l_mgr, False)
    
    # ═══ 2. 当周操作时间线 ═══
    has_ops = bool(w_ops) or bool(l_ops)
    html += '<div class="ops-section">'
    html += '<div class="ops-title">当周操作 <span style="font-size:.7em;color:#b5b0a8;font-weight:normal;margin-left:6px">球员赛季场均数据</span></div>'
    
    def render_ops(ops, mgr_name):
        h = ''
        if not ops:
            h += f'<p style="font-size:.78em;color:#b5b0a8;font-style:italic">{mgr_name} 本周无操作</p>'
            return h
        h += f'<p style="font-size:.78em;color:#5a5550;margin-bottom:6px"><strong>{mgr_name}</strong> — {len(ops)} 次操作</p>'
        for op in ops:
            date_str = op['date'].strftime('%m/%d')
            h += f'<div style="margin:10px 0;padding:10px 14px;border-left:3px solid #e8e4de;background:#faf9f6">'
            h += f'<div style="font-size:.78em;margin-bottom:6px">'
            h += f'<span class="timeline-date">{date_str}</span> '
            h += f'<span style="color:#5a5550;font-weight:400">{op["action"]}</span>'
            h += '</div>'
            
            # 签入球员 + 头像 + 11项数据
            if op['adds']:
                for a in op['adds']:
                    rk_cls = 'rank-good' if a['rank'] <= 50 else ('rank-mid' if a['rank'] <= 150 else 'rank-low')
                    hs = a.get('headshot', '')
                    hs_img = f'<img src="{hs}" style="width:22px;height:16px;border-radius:2px;object-fit:cover;vertical-align:middle;margin-right:4px" onerror="this.style.display=\'none\'">' if hs else ''
                    h += f'<div style="font-size:.8em;color:#2d6a3f;font-weight:500;margin:6px 0 2px">'
                    h += f'+ {hs_img}{a["player"]} <span class="{rk_cls}">(Rank#{a["rank"]})</span>'
                    h += '</div>'
                    # 11项数据
                    stats_parts = []
                    for cat in DISPLAY_CATS:
                        val = a['stats'].get(cat, '-')
                        if val != '-' and val != '':
                            stats_parts.append(f'<span style="color:#5a5550;font-weight:500">{cat}</span>:<span style="color:#2d6a3f">{val}</span>')
                    if stats_parts:
                        h += f'<div style="font-size:.72em;color:#5a5550;margin:3px 0 6px 14px;padding:6px 10px;background:#f0f7f2;border:1px solid #c8ddc8;border-radius:4px;line-height:1.8">'
                        h += ' · '.join(stats_parts)
                        h += '</div>'
            
            # 裁掉球员 + 头像 + 11项数据
            if op['drops']:
                for d_info in op['drops']:
                    rk_cls = 'rank-good' if d_info['rank'] <= 50 else ('rank-mid' if d_info['rank'] <= 150 else 'rank-low')
                    hs = d_info.get('headshot', '')
                    hs_img = f'<img src="{hs}" style="width:22px;height:16px;border-radius:2px;object-fit:cover;vertical-align:middle;margin-right:4px;opacity:.6" onerror="this.style.display=\'none\'">' if hs else ''
                    h += f'<div style="font-size:.8em;color:#a63d2b;font-weight:500;margin:6px 0 2px">'
                    h += f'- {hs_img}{d_info["player"]} <span class="{rk_cls}">(Rank#{d_info["rank"]})</span>'
                    h += '</div>'
                    stats_parts = []
                    for cat in DISPLAY_CATS:
                        val = d_info['stats'].get(cat, '-')
                        if val != '-' and val != '':
                            stats_parts.append(f'<span style="color:#5a5550;font-weight:500">{cat}</span>:<span style="color:#a63d2b">{val}</span>')
                    if stats_parts:
                        h += f'<div style="font-size:.72em;color:#5a5550;margin:3px 0 6px 14px;padding:6px 10px;background:#fdf2f0;border:1px solid #e0c4c0;border-radius:4px;line-height:1.8">'
                        h += ' · '.join(stats_parts)
                        h += '</div>'
            
            h += '</div>'
        return h
    
    if not has_ops:
        html += '<p style="font-size:.78em;color:#b5b0a8;font-style:italic">双方本周均无操作</p>'
    else:
        html += render_ops(w_ops, w_mgr)
        html += render_ops(l_ops, l_mgr)
    
    html += '</div>'
    html += '</div>'  # close .battle
    html += '</div></div>'  # close .inner + .snap-section

# Footer
html += f'''
<div class="footer">
GENERATED {datetime.now().strftime("%Y.%m.%d")} &middot; CLASSIC BATTLES
</div>
</body></html>
'''

out = os.path.join(os.path.dirname(__file__), 'classic_battles.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[OK] {out}")
print(f"Battles: {len(filtered_upsets)} (filtered from {len(classic_upsets)})")
for i, u in enumerate(filtered_upsets, 1):
    tag = "PLAYOFF" if u.get('is_playoff') else "REG"
    print(f"  {i}. W{u['week']} [{tag}] {u['winner']}(Rank{u['winner_avg_rank']:.0f}) {u['score']} {u['loser']}(Rank{u['loser_avg_rank']:.0f})")
