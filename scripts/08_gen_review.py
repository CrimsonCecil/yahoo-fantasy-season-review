#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fantasy NBA 24-25 赛季回顾报告生成器 v3
- 日式极简美工
- 教练头像 + 球员头像
- 经典以下克上战役
- 奖项改名 + 重排序
"""
import json, sys, os
from datetime import datetime
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
manager_avatars = d.get('manager_avatars', {})
team_logos = d.get('team_logos', {})
classic_upsets = d.get('classic_upsets', [])
weekly_roster_rank = d.get('weekly_roster_rank', {})

MANAGER_OVERRIDES = {'King Crimson Cecil': 'Cecil'}
PLAYER_AVATAR = "https://s.yimg.com/xe/i/us/sp/v/nba_cutout/players_l/full/headshots/{pid}.png"

# ═══════════════════════════════════════════════════════════════
# 数据预处理
# ═══════════════════════════════════════════════════════════════

import statistics

# Yahoo stat key 映射: GP=OREB, TW=A/TO
ZSCORE_CATS = {
    'FG%': {'key':'FG%', 'reverse':False},
    'FT%': {'key':'FT%', 'reverse':False},
    '3PM': {'key':'3PM', 'reverse':False},
    'PTS': {'key':'PTS', 'reverse':False},
    'OREB':{'key':'GP',  'reverse':False},
    'REB': {'key':'REB', 'reverse':False},
    'AST': {'key':'AST', 'reverse':False},
    'STL': {'key':'STL', 'reverse':False},
    'BLK': {'key':'BLK', 'reverse':False},
    'TO':  {'key':'TO',  'reverse':True},    # 低好
    'A/TO':{'key':'TW',  'reverse':False},
}

def calc_zscore_rank():
    """11-cat Z-Score 综合排名: 每项统计标准化后求和，TO取反"""
    # 过滤有效球员（赛季总得分>100，排除只打几场的）
    valid_pks = []
    for pk, ps in player_stats.items():
        try:
            if float(ps.get('stats',{}).get('PTS',0)) > 100:
                valid_pks.append(pk)
        except: pass
    if not valid_pks:
        valid_pks = list(player_stats.keys())

    # 收集每项数值
    cat_values = {cat: [] for cat in ZSCORE_CATS}
    player_vals = {}
    for pk in valid_pks:
        pst = player_stats[pk].get('stats', {})
        vals = {}
        for cat, info in ZSCORE_CATS.items():
            try: v = float(pst.get(info['key'], 0))
            except: v = 0.0
            vals[cat] = v
            cat_values[cat].append(v)
        player_vals[pk] = vals

    # 每项的 mean / stdev
    cat_stats = {}
    for cat in ZSCORE_CATS:
        values = cat_values[cat]
        mean = statistics.mean(values) if len(values) >= 2 else 0
        stdev = statistics.stdev(values) if len(values) >= 2 else 1
        if stdev == 0: stdev = 1
        cat_stats[cat] = (mean, stdev)

    # 计算总 Z-Score
    player_zscores = {}
    for pk in valid_pks:
        vals = player_vals[pk]
        total_z = 0
        for cat, info in ZSCORE_CATS.items():
            mean, stdev = cat_stats[cat]
            z = (vals[cat] - mean) / stdev
            if info['reverse']: z = -z
            total_z += z
        player_zscores[pk] = total_z

    for pk in player_stats:
        if pk not in player_zscores:
            player_zscores[pk] = -99

    # 按 Z-Score 降序排名
    sorted_p = sorted(player_zscores.items(), key=lambda x: x[1], reverse=True)
    rank_map = {pk: i+1 for i, (pk, _) in enumerate(sorted_p)}
    return rank_map, player_zscores

rank_pts, player_zscores = calc_zscore_rank()

# 验证 Top 10
print("[Z-Score] Top 10:")
for i, (pk, z) in enumerate(sorted(player_zscores.items(), key=lambda x:x[1], reverse=True)[:10], 1):
    nm = player_stats.get(pk,{}).get('name','?')
    st = player_stats.get(pk,{}).get('stats',{})
    print(f"  #{i} {nm}: Z={z:.2f} PTS={st.get('PTS','-')} REB={st.get('REB','-')} BLK={st.get('BLK','-')}")

teams = []
for tid, t in wlt.items():
    s = stats.get(tid, {}).get('stats', {})
    name = t.get('name','?')
    mgr = MANAGER_OVERRIDES.get(name, t.get('manager','?'))
    tk = t.get('team_key','')
    avatar_data = manager_avatars.get(tk, {})
    avatar_url = avatar_data.get('avatar', '')
    logo_url = team_logos.get(tk, '')
    teams.append({
        'tid': tid, 'name': name, 'manager': mgr,
        'team_key': tk, 'rank': int(t.get('rank') or 99),
        'W': int(t.get('wins') or 0), 'L': int(t.get('losses') or 0), 'T': int(t.get('ties') or 0),
        'pct': float(t.get('win_pct') or 0),
        'moves': int(t.get('moves') or 0), 'trades_count': int(t.get('trades') or 0),
        'stats': s, 'avatar': avatar_url, 'logo': logo_url,
    })
teams.sort(key=lambda x: x['rank'])
tk_to_team = {t['team_key']: t for t in teams}

draft_by_tk = defaultdict(list)
for p in draft:
    draft_by_tk[p.get('team_key','')].append(p)

adds_by_tk = defaultdict(list)
drops_by_tk = defaultdict(list)
for tx in txs:
    for p in tx.get('players', []):
        if p.get('dst_team_key'):
            adds_by_tk[p['dst_team_key']].append({**tx, '_player': p})
        if p.get('src_team_key'):
            drops_by_tk[p['src_team_key']].append({**tx, '_player': p})

manager_weekly = defaultdict(dict)
for wk in sorted(weekly_sb.keys(), key=int):
    for m in weekly_sb[wk]:
        w1, w2, ties = m.get('team1_cat_wins',0), m.get('team2_cat_wins',0), m.get('ties',0)
        t1k, t2k = m.get('team1_key',''), m.get('team2_key','')
        r1 = 'W' if w1>w2 else ('L' if w1<w2 else 'T')
        r2 = 'W' if w2>w1 else ('L' if w2<w1 else 'T')
        manager_weekly[t1k][wk] = {'result':r1,'w':w1,'l':w2,'t':ties,'opp':m.get('team2','?'),'score':m.get('score','?')}
        manager_weekly[t2k][wk] = {'result':r2,'w':w2,'l':w1,'t':ties,'opp':m.get('team1','?'),'score':f"{w2}-{w1}-{ties}"}

def derive_playoffs():
    if not weekly_sb.get('21') or not weekly_sb.get('22') or not weekly_sb.get('23'):
        return {}
    placements = {}
    qf_w = set()
    for m in weekly_sb['21']:
        if m.get('is_playoffs')=='1': qf_w.add(m['winner_team_key'])
    sf_w, sf_l = set(), set()
    for m in weekly_sb['22']:
        if m.get('is_playoffs')!='1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk!=t1k else t2k
        if t1k in qf_w and t2k in qf_w:
            sf_w.add(wk); sf_l.add(lk)
    for m in weekly_sb['23']:
        if m.get('is_playoffs')!='1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk!=t1k else t2k
        if t1k in sf_w and t2k in sf_w:
            placements[1]=wk; placements[2]=lk
        elif t1k in sf_l and t2k in sf_l:
            placements[3]=wk; placements[4]=lk
    return placements

playoff_placements = derive_playoffs()

player_nba_map = d.get('player_nba_map', {})

def get_player_avatar(player_key):
    """获取球员头像 URL（优先 NBA.com）"""
    nba = player_nba_map.get(player_key, {})
    url = nba.get('headshot_url', '')
    if url:
        return url
    ps = player_stats.get(player_key, {})
    pid = ps.get('player_id', '')
    if pid:
        return PLAYER_AVATAR.format(pid=pid)
    return ''

def player_inline_img(player_key, size=20):
    """生成内联球员头像 HTML（用于 stats/highlight 文字中）"""
    url = get_player_avatar(player_key)
    if url:
        return f'<img src="{url}" onerror="this.style.display=\'none\'" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;vertical-align:middle;margin:0 3px 0 0">'
    return ''

def team_logo_html(team, size=48):
    """用球队头像（team_logos）替代经理头像"""
    url = team.get('logo', '')
    if url:
        return f'<img src="{url}" alt="" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;flex-shrink:0">'
    return f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#e8e4de;flex-shrink:0"></div>'

# ═══════════════════════════════════════════════════════════════
# 12 个奖项评选 (改名 + 重排序)
# 顺序: 最佳总教练 → 最佳常规赛教练 → 最长连胜 → 选秀之王 → 捡漏之王 → 转会大师 → 逆袭王 → 最稳阵容 → 统计之王 → 最惨教练 → 摆烂之王 → 铁人教练
# ═══════════════════════════════════════════════════════════════
awards = []

# 1. 最佳总教练
def award_coty():
    ranked = sorted(teams, key=lambda t: (-1 if playoff_placements.get(1)==t['team_key'] else 0, t['rank']))
    w = ranked[0]; r = ranked[1]
    return {
        'id':'coty','emoji':'01','name':'最佳总教练','en':'Coach of the Year',
        'winner': w['manager'], 'winner_team': w['name'], 'winner_tk': w['team_key'],
        'runner': r['manager'], 'runner_team': r['name'], 'runner_tk': r['team_key'],
        'stats': f"#{w['rank']}  {w['W']}-{w['L']}-{w['T']}  Win% .{int(w['pct']*1000)}",
        'reason': f"赛季最终排名第{w['rank']}，以{w['W']}胜{w['L']}负的战绩问鼎联盟",
        'highlight': f"运筹帷幄，带领 {w['name']} 登顶联盟",
        'all': [(t['manager'],t['name'],f"#{t['rank']} {t['W']}-{t['L']}-{t['T']}",t['team_key']) for t in ranked[:8]],
    }
awards.append(award_coty())

# 2. 最佳常规赛教练 (紧跟最佳教练之后)
def award_regular_season():
    week_wins = defaultdict(int)
    best_week_score = {}
    for tk, weeks in manager_weekly.items():
        for wk, data in weeks.items():
            if int(wk) > 20: continue
            if data['result'] == 'W':
                week_wins[tk] += 1
            if tk not in best_week_score or data['w'] > best_week_score[tk][0]:
                best_week_score[tk] = (data['w'], wk, data['opp'])
    team_scores = []
    for t in teams:
        tk = t['team_key']
        ww = week_wins.get(tk, 0)
        bw = best_week_score.get(tk, (0,'?','?'))
        team_scores.append((t, ww, bw))
    team_scores.sort(key=lambda x: (x[1], x[2][0]), reverse=True)
    w = team_scores[0]; r = team_scores[1]
    return {
        'id':'regular_season','emoji':'02','name':'最佳常规赛教练','en':'Regular Season MVP',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"常规赛 {w[1]} 周胜利  最佳单周 {w[2][0]} 比分获胜 (W{w[2][1]})",
        'reason': f"常规赛 20 周中获得 {w[1]} 次胜利，联盟最多",
        'highlight': f"每周都是对手的噩梦",
        'all': [(x[0]['manager'],x[0]['name'],f"{x[1]}周胜 最佳{x[2][0]}比分",x[0]['team_key']) for x in team_scores[:8]],
    }
awards.append(award_regular_season())

# 3. 最长连胜教练
def award_win_streak():
    team_streaks = []
    for t in teams:
        tk = t['team_key']
        weeks_data = manager_weekly.get(tk, {})
        max_streak = 0; cur_streak = 0; streak_start = ''; streak_end = ''
        best_start = ''; best_end = ''
        for wk in sorted(weeks_data.keys(), key=int):
            if weeks_data[wk]['result'] == 'W':
                if cur_streak == 0:
                    streak_start = wk
                cur_streak += 1
                streak_end = wk
                if cur_streak > max_streak:
                    max_streak = cur_streak
                    best_start = streak_start
                    best_end = streak_end
            else:
                cur_streak = 0
        team_streaks.append((t, max_streak, best_start, best_end))
    team_streaks.sort(key=lambda x: x[1], reverse=True)
    top_val = team_streaks[0][1]
    co_winners = [(t, s, bs, be) for t, s, bs, be in team_streaks if s == top_val]
    first_non = next(((t, s, bs, be) for t, s, bs, be in team_streaks if s < top_val), team_streaks[-1])
    
    if len(co_winners) > 1:
        # 并列
        w_names = ' / '.join(cw[0]['manager'] for cw in co_winners)
        w_teams = ' / '.join(cw[0]['name'] for cw in co_winners)
        w_tks = [cw[0]['team_key'] for cw in co_winners]
        details = '  '.join(f"{cw[0]['manager']}(W{cw[2]}-{cw[3]})" for cw in co_winners)
        return {
            'id':'win_streak','emoji':'03','name':'最长连胜教练','en':'Win Streak King',
            'winner': w_names, 'winner_team': w_teams, 'winner_tk': w_tks[0],
            'co_winners': [{'manager': cw[0]['manager'], 'team': cw[0]['name'], 'tk': cw[0]['team_key'],
                           'stats': f"最长连胜 {cw[1]} 周 (Week {cw[2]}-{cw[3]})",
                           'reason': f"赛季中连续 {cw[1]} 周获胜"} for cw in co_winners],
            'runner': first_non[0]['manager'], 'runner_team': first_non[0]['name'], 'runner_tk': first_non[0]['team_key'],
            'stats': f"最长连胜 {top_val} 周  {details}",
            'reason': f"{len(co_winners)} 位教练并列最长连胜 {top_val} 周",
            'highlight': f"{top_val} 连胜，势不可挡",
            'all': [(x[0]['manager'],x[0]['name'],f"{x[1]}连胜 (W{x[2]}-{x[3]})" if x[1]>0 else "无连胜",x[0]['team_key']) for x in team_streaks[:8]],
        }
    
    w = team_streaks[0]; r = team_streaks[1]
    return {
        'id':'win_streak','emoji':'03','name':'最长连胜教练','en':'Win Streak King',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"最长连胜 {w[1]} 周 (Week {w[2]}-{w[3]})",
        'reason': f"赛季中连续 {w[1]} 周获胜，联盟最长连胜纪录",
        'highlight': f"势不可挡的 {w[1]} 连胜，谁也无法阻止",
        'all': [(x[0]['manager'],x[0]['name'],f"{x[1]}连胜 (W{x[2]}-{x[3]})" if x[1]>0 else "无连胜",x[0]['team_key']) for x in team_streaks[:8]],
    }
awards.append(award_win_streak())

# 4. 选秀之王 (按选秀球员 Z-Score Rank 总和)
def award_draft_king():
    team_draft_val = []
    for t in teams:
        picks = draft_by_tk.get(t['team_key'], [])
        total_rank = 0; count = 0; best_pick = None
        for p in picks:
            pk = p.get('player_key','')
            rk = rank_pts.get(pk, 999)
            if rk < 900:  # 只算有排名的球员
                total_rank += rk; count += 1
            if best_pick is None or rk < best_pick[3]:
                best_pick = (p.get('player_name', player_stats.get(pk,{}).get('name','?')), 0, p.get('round',0), rk, pk)
        avg_rank = total_rank / count if count > 0 else 999
        team_draft_val.append((t, avg_rank, count, best_pick))
    team_draft_val.sort(key=lambda x: x[1])  # avg rank 越小越好
    w = team_draft_val[0]; r = team_draft_val[1]; bp = w[3]
    return {
        'id':'draft_king','emoji':'02','name':'选秀之王','en':'Draft Day King',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"选秀球员均Rank {w[1]:.1f}  {w[2]}人  最佳 {player_inline_img(bp[4])}{bp[0]} (R{bp[2]} Rank#{bp[3]})",
        'reason': f"选秀球员平均 Rank {w[1]:.1f}，联盟最优",
        'highlight': f"选秀夜最大赢家，{player_inline_img(bp[4])}{bp[0]} 堪称神来之笔",
        'key_player': bp[4] if bp else '',
        'all': [(x[0]['manager'],x[0]['name'],f"均Rank {x[1]:.1f} ({x[2]}人)",x[0]['team_key']) for x in team_draft_val[:8]],
    }
awards.append(award_draft_king())

# 3. 捡漏之王 (原WW之王)
def award_waiver_king():
    team_ww = []
    for t in teams:
        tk = t['team_key']
        waiver_adds = [tx for tx in adds_by_tk.get(tk,[]) if tx.get('type') in ('add','add/drop')]
        total_val = 0; best_pickup = None
        for tx in waiver_adds:
            pk = tx['_player'].get('player_key','')
            rk = rank_pts.get(pk, 999)
            val = max(0, 300-rk); total_val += val
            pname = tx['_player'].get('player_name', tx['_player'].get('name', player_stats.get(pk,{}).get('name','?')))
            if best_pickup is None or rk < best_pickup[1]:
                best_pickup = (pname, rk, pk)
        team_ww.append((t, total_val, len(waiver_adds), best_pickup))
    team_ww.sort(key=lambda x: x[1], reverse=True)
    w = team_ww[0]; r = team_ww[1]; bp = w[3]
    bp_info = f"最佳捡漏 {player_inline_img(bp[2])}{bp[0]} (Rank#{bp[1]})" if bp else ""
    return {
        'id':'waiver_king','emoji':'04','name':'捡漏之王','en':'Waiver Wire King',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"WW总价值 {w[1]:.0f}  {w[2]}次操作  {bp_info}",
        'reason': f"从自由市场累计获得 {w[1]:.0f} 价值",
        'highlight': f"别人的弃将，{w[0]['manager']} 的宝藏",
        'key_player': bp[2] if bp else '',
        'all': [(x[0]['manager'],x[0]['name'],f"价值 {x[1]:.0f} {x[2]}次",x[0]['team_key']) for x in team_ww[:8]],
    }
awards.append(award_waiver_king())

# 4. 转会大师 (详细列出转入转出球员+Rank)
def award_trade_master():
    team_trade_val = []
    for t in teams:
        tk = t['team_key']
        ins = [tx for tx in adds_by_tk.get(tk,[]) if tx.get('type')=='trade']
        outs = [tx for tx in drops_by_tk.get(tk,[]) if tx.get('type')=='trade']
        in_val = sum(max(0, 300-rank_pts.get(tx['_player'].get('player_key',''), 999)) for tx in ins)
        out_val = sum(max(0, 300-rank_pts.get(tx['_player'].get('player_key',''), 999)) for tx in outs)
        net = in_val - out_val
        # 收集详细球员信息
        in_players = []
        for tx in ins:
            pk = tx['_player'].get('player_key','')
            pname = tx['_player'].get('player_name', tx['_player'].get('name', player_stats.get(pk,{}).get('name','?')))
            rk = rank_pts.get(pk, 999)
            in_players.append((pname, rk, pk))
        out_players = []
        for tx in outs:
            pk = tx['_player'].get('player_key','')
            pname = tx['_player'].get('player_name', tx['_player'].get('name', player_stats.get(pk,{}).get('name','?')))
            rk = rank_pts.get(pk, 999)
            out_players.append((pname, rk, pk))
        team_trade_val.append((t, net, in_players, out_players))
    team_trade_val.sort(key=lambda x: x[1], reverse=True)
    w = team_trade_val[0]; r = team_trade_val[1]
    # 构建详细描述
    in_desc = ' / '.join(f'{player_inline_img(pk)}{n} (Rank#{rk})' for n, rk, pk in w[2]) if w[2] else '无'
    out_desc = ' / '.join(f'{player_inline_img(pk)}{n} (Rank#{rk})' for n, rk, pk in w[3]) if w[3] else '无'
    stats_text = f"<div>交易净价值 +{w[1]:.0f}</div>"
    stats_text += f"<div style='margin-top:4px;font-size:.85em'>转入: {in_desc}</div>"
    stats_text += f"<div style='margin-top:2px;font-size:.85em'>转出: {out_desc}</div>"
    return {
        'id':'trade_master','emoji':'04','name':'转会大师','en':'Trade Master',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': stats_text,
        'reason': f"通过交易获得了联盟最高的净价值提升",
        'highlight': f"谈判桌上的王者，每笔交易都让阵容更强",
        'all': [(x[0]['manager'],x[0]['name'],f"净值 {x[1]:+.0f}",x[0]['team_key']) for x in team_trade_val[:8]],
    }
awards.append(award_trade_master())

# 7. 逆袭王
def award_comeback():
    team_comeback = []
    weeks = sorted(weekly_st.keys(), key=int)
    regular = [w for w in weeks if int(w) <= 20]
    first_half = regular[:len(regular)//2]; second_half = regular[len(regular)//2:]
    for t in teams:
        tk = t['team_key']
        fh_ranks = [s['rank'] for wk in first_half for s in weekly_st.get(wk,[]) if s.get('key')==tk]
        sh_ranks = [s['rank'] for wk in second_half for s in weekly_st.get(wk,[]) if s.get('key')==tk]
        fh_avg = sum(fh_ranks)/len(fh_ranks) if fh_ranks else 8
        sh_avg = sum(sh_ranks)/len(sh_ranks) if sh_ranks else 8
        improvement = fh_avg - sh_avg
        team_comeback.append((t, improvement, fh_avg, sh_avg))
    team_comeback.sort(key=lambda x: x[1], reverse=True)
    w = team_comeback[0]; r = team_comeback[1]
    return {
        'id':'comeback','emoji':'07','name':'逆袭王','en':'Comeback Kid',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"前半 avg#{w[2]:.1f} -> 后半 avg#{w[3]:.1f}  提升 {w[1]:+.1f}",
        'reason': f"从前半赛季平均第{w[2]:.1f}名逆袭到后半赛季第{w[3]:.1f}名",
        'highlight': f"前半蛰伏，后半爆发，厚积薄发",
        'all': [(x[0]['manager'],x[0]['name'],f"#{x[2]:.1f}->{x[3]:.1f} ({x[1]:+.1f})",x[0]['team_key']) for x in team_comeback[:8]],
    }
awards.append(award_comeback())

# 8. 最稳阵容
def award_consistent():
    team_cons = []
    for t in teams:
        tk = t['team_key']
        wins_per_week = [data['w'] for wk, data in manager_weekly.get(tk, {}).items() if int(wk) <= 20]
        if len(wins_per_week) < 5: team_cons.append((t, 999, 0)); continue
        avg = sum(wins_per_week)/len(wins_per_week)
        stddev = (sum((x-avg)**2 for x in wins_per_week)/(len(wins_per_week)-1))**0.5
        team_cons.append((t, stddev, avg))
    team_cons.sort(key=lambda x: x[1])
    w = team_cons[0]; r = team_cons[1]
    return {
        'id':'consistent','emoji':'08','name':'最稳阵容','en':'Mr. Consistent',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"周 cat wins 标准差 {w[1]:.2f}  周均 {w[2]:.1f}",
        'reason': f"每周表现极其稳定，标准差仅 {w[1]:.2f}",
        'highlight': f"稳如磐石，永远不会让你失望",
        'all': [(x[0]['manager'],x[0]['name'],f"sigma={x[1]:.2f} avg={x[2]:.1f}",x[0]['team_key']) for x in team_cons[:8]],
    }
awards.append(award_consistent())

# 9. 统计之王（处理并列第一：同值的都算第一）
def award_stat_king():
    cats = ['FG%','FT%','3PM','PTS','REB','AST','STL','BLK','TO']
    lower_better = {'TO'}
    cat_leaders = defaultdict(list)  # cat -> [team, ...]
    for cat in cats:
        vals = []
        for t in teams:
            try: val = float(t['stats'].get(cat, 0))
            except: val = 0
            vals.append((t, val))
        if cat in lower_better:
            best_val = min(v for _, v in vals)
        else:
            best_val = max(v for _, v in vals)
        for t, v in vals:
            if abs(v - best_val) < 1e-6:
                cat_leaders[cat].append(t)
    
    cat_wins = defaultdict(list)
    for cat, ts in cat_leaders.items():
        for t in ts:
            cat_wins[t['team_key']].append(cat + ("(并列)" if len(ts) > 1 else ""))
    
    team_cw = [(t, len(cat_wins.get(t['team_key'],[])), cat_wins.get(t['team_key'],[])) for t in teams]
    team_cw.sort(key=lambda x: x[1], reverse=True)
    top_val = team_cw[0][1]
    co_winners_list = [(t, v, c) for t, v, c in team_cw if v == top_val]
    first_non = next((t, v, c) for t, v, c in team_cw if v < top_val)
    w = team_cw[0]; r_entry = first_non
    
    result = {
        'id':'stat_king','emoji':'09','name':'统计之王','en':'Stat King',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r_entry[0]['manager'], 'runner_team': r_entry[0]['name'], 'runner_tk': r_entry[0]['team_key'],
        'stats': f"称霸 {w[1]} 项  {', '.join(w[2])}",
        'reason': f"在 {w[1]} 个统计类别中排名联盟第一",
        'highlight': f"数据全面碾压，{w[1]}项联盟第一",
        'all': [(x[0]['manager'],x[0]['name'],f"{x[1]}项 {', '.join(x[2]) if x[2] else '-'}",x[0]['team_key']) for x in team_cw[:8]],
    }
    if len(co_winners_list) > 1:
        result['co_winners'] = [{
            'manager': t['manager'], 'team': t['name'], 'tk': t['team_key'],
            'stats': f"称霸 {v} 项: {', '.join(c)}",
            'reason': f"{t['manager']} 在 {', '.join(c)} 等 {v} 项统计中排名联盟第一"
        } for t, v, c in co_winners_list]
    return result
awards.append(award_stat_king())

# 10. 最惨教练
def award_tough_luck():
    team_misery = []
    for t in teams:
        tk = t['team_key']
        close_losses = 0; total_opp_wins = 0
        for wk, data in manager_weekly.get(tk, {}).items():
            if data['result'] == 'L' and (data['l'] - data['w']) <= 2:
                close_losses += 1
            total_opp_wins += data['l']
        misery = close_losses * 10 + total_opp_wins * 0.1
        team_misery.append((t, misery, close_losses, total_opp_wins))
    team_misery.sort(key=lambda x: x[1], reverse=True)
    w = team_misery[0]; r = team_misery[1]
    return {
        'id':'tough_luck','emoji':'10','name':'最惨教练','en':'Tough Luck Coach',
        'winner': w[0]['manager'], 'winner_team': w[0]['name'], 'winner_tk': w[0]['team_key'],
        'runner': r[0]['manager'], 'runner_team': r[0]['name'], 'runner_tk': r[0]['team_key'],
        'stats': f"险负(差<=2比分) {w[2]}次  被对手赢走 {w[3]} 比分",
        'reason': f"赛季 {w[2]} 次惜败（差距≤2个比分），运气真的不好",
        'highlight': f"这赛季太不容易了，值得一个拥抱",
        'all': [(x[0]['manager'],x[0]['name'],f"险负{x[2]}次 被赢{x[3]}比分",x[0]['team_key']) for x in team_misery[:8]],
    }
awards.append(award_tough_luck())

# 11. 摆烂之王
def award_tank():
    ranked = sorted(teams, key=lambda x: x['rank'], reverse=True)
    w = ranked[0]; r = ranked[1]
    return {
        'id':'tank','emoji':'11','name':'摆烂之王','en':'Tanking Champion',
        'winner': w['manager'], 'winner_team': w['name'], 'winner_tk': w['team_key'],
        'runner': r['manager'], 'runner_team': r['name'], 'runner_tk': r['team_key'],
        'stats': f"#{w['rank']}  {w['W']}-{w['L']}-{w['T']}",
        'reason': f"以第{w['rank']}名的战绩光荣垫底",
        'highlight': f"摆烂也是一种艺术，明年选秀签位绝佳",
        'all': [(t['manager'],t['name'],f"#{t['rank']} {t['W']}-{t['L']}-{t['T']}",t['team_key']) for t in ranked[:5]],
    }
awards.append(award_tank())

# 12. 铁人教练（检查并列第一）
def award_iron_man():
    team_iron = [(t, t['moves']) for t in teams]
    team_iron.sort(key=lambda x: x[1], reverse=True)
    top_val = team_iron[0][1]
    co_winners = [(t, v) for t, v in team_iron if v == top_val]
    first_non = next((t, v) for t, v in team_iron if v < top_val)
    
    result = {
        'id':'iron_man','emoji':'12','name':'铁人教练','en':'Iron Man Coach',
        'winner': co_winners[0][0]['manager'], 'winner_team': co_winners[0][0]['name'], 'winner_tk': co_winners[0][0]['team_key'],
        'runner': first_non[0]['manager'], 'runner_team': first_non[0]['name'], 'runner_tk': first_non[0]['team_key'],
        'stats': f"赛季操作 {top_val}次",
        'reason': f"全赛季 {top_val} 次操作，联盟最勤劳",
        'highlight': f"全年无休，联盟最勤劳的经理",
        'all': [(x[0]['manager'],x[0]['name'],f"{x[1]}次操作",x[0]['team_key']) for x in team_iron[:8]],
    }
    if len(co_winners) > 1:
        result['co_winners'] = [{
            'manager': t['manager'], 'team': t['name'], 'tk': t['team_key'],
            'stats': f"赛季操作 {v}次 | 战绩 {t['W']}-{t['L']}-{t['T']} (#{t['rank']})",
            'reason': f"{t['manager']} 全赛季 {v} 次操作，排名第{t['rank']}"
        } for t, v in co_winners]
    return result
awards.append(award_iron_man())

# ═══════════════════════════════════════════════════════════════
# 生成 HTML — 日式极简风
# ═══════════════════════════════════════════════════════════════

html = '''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>Fantasy NBA 24-25 Season Review</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;700&display=swap');

*{box-sizing:border-box;margin:0;padding:0}
html{scroll-snap-type:y mandatory;scroll-behavior:smooth;overflow-y:scroll}
body{
  font-family:'Noto Sans JP','Helvetica Neue',system-ui,sans-serif;
  background:#faf9f6;color:#2d2d2d;line-height:1.7;font-weight:300;
  -webkit-font-smoothing:antialiased;
}
.snap-section{
  scroll-snap-align:start;
  min-height:100vh;
  display:flex;flex-direction:column;justify-content:center;
  padding:40px 24px;
  position:relative;
}
.snap-section .inner{max-width:860px;margin:0 auto;width:100%}

.hero{
  text-align:center;padding:80px 20px 60px;
  border-bottom:1px solid #e8e4de;
}
.hero h1{
  font-family:'Noto Serif JP',serif;font-size:2.4em;font-weight:400;
  color:#2d2d2d;letter-spacing:.08em;margin-bottom:12px;
}
.hero .sub{color:#8a8580;font-size:.95em;letter-spacing:.15em;font-weight:300}
.hero .season-line{
  display:inline-block;margin-top:20px;padding:6px 24px;
  border:1px solid #c8a45c;color:#c8a45c;font-size:.8em;letter-spacing:.2em;
}

.nav{
  display:flex;flex-wrap:wrap;justify-content:center;gap:6px;
  padding:16px 20px;position:sticky;top:0;background:rgba(250,249,246,.96);
  z-index:10;border-bottom:1px solid #e8e4de;backdrop-filter:blur(8px);
}
.nav a{
  color:#8a8580;text-decoration:none;padding:5px 12px;font-size:.75em;
  letter-spacing:.1em;transition:color .2s;font-weight:400;
}
.nav a:hover{color:#c8a45c}

.container{max-width:860px;margin:0 auto;padding:0 24px}

/* Award card — 日式极简 */
.award{
  padding-bottom:24px;
}
.award:last-child{border-bottom:none}

.award-num{
  font-family:'Noto Serif JP',serif;font-size:4em;font-weight:700;
  color:#f0ede8;line-height:1;margin-bottom:-20px;position:relative;z-index:0;
}
.award-name{
  font-family:'Noto Serif JP',serif;font-size:1.4em;font-weight:400;
  color:#2d2d2d;letter-spacing:.05em;position:relative;z-index:1;
}
.award-en{color:#b5b0a8;font-size:.75em;letter-spacing:.15em;margin-top:2px}

.winner-row{
  display:flex;align-items:center;gap:20px;margin-top:24px;
  padding:24px;background:#fff;border:1px solid #e8e4de;
}
.winner-info{flex:1}
.winner-label{font-size:.7em;color:#c8a45c;letter-spacing:.25em;text-transform:uppercase;font-weight:500}
.winner-name{font-family:'Noto Serif JP',serif;font-size:1.6em;font-weight:700;color:#2d2d2d;margin-top:4px}
.winner-team{color:#8a8580;font-size:.85em;margin-top:2px}

.stats-box{
  margin-top:16px;padding:12px 16px;background:#f5f3ef;
  font-size:.82em;color:#5a5550;font-family:'SF Mono','Consolas',monospace;letter-spacing:.03em;
}

.reason-text{color:#5a5550;font-size:.9em;margin-top:16px;line-height:1.8}
.highlight-text{
  margin-top:12px;padding-left:16px;
  border-left:2px solid #c8a45c;color:#8a7a5a;font-style:italic;font-size:.9em;
}

.runner{
  display:flex;align-items:center;gap:10px;margin-top:16px;
  padding-top:12px;border-top:1px solid #f0ede8;font-size:.82em;color:#8a8580;
}
.runner-badge{
  padding:2px 8px;border:1px solid #d0ccc4;font-size:.75em;letter-spacing:.1em;color:#b5b0a8;
}

.player-chip{
  display:inline-flex;align-items:center;gap:6px;
  padding:3px 10px 3px 3px;background:#f5f3ef;border:1px solid #e8e4de;
  border-radius:20px;font-size:.78em;margin:4px 2px;
}
.player-chip img{width:24px;height:24px;border-radius:50%;object-fit:cover}

details{margin-top:12px}
details summary{color:#b5b0a8;font-size:.75em;cursor:pointer;letter-spacing:.1em}
details table{width:100%;font-size:.78em;margin-top:8px;border-collapse:collapse}
details th{color:#c8a45c;font-weight:400;padding:4px 10px;text-align:left;border-bottom:1px solid #e8e4de;letter-spacing:.1em;font-size:.85em}
details td{padding:4px 10px;border-bottom:1px solid #f5f3ef}
details .rank-cell{width:24px;text-align:center;color:#b5b0a8}

/* Podium — 极简领奖台 */
.podium-section{
  text-align:center;margin-bottom:60px;padding:48px 20px;
  border:1px solid #e8e4de;background:#fff;
}
.podium-title{
  font-family:'Noto Serif JP',serif;font-size:1.6em;font-weight:400;
  color:#2d2d2d;letter-spacing:.1em;margin-bottom:32px;
}
.podium{display:flex;justify-content:center;align-items:flex-end;gap:24px}
.podium-item{text-align:center;padding:20px 24px}
.podium-1{order:2}
.podium-2{order:1}
.podium-3{order:3}
.podium-medal{font-size:.8em;color:#c8a45c;letter-spacing:.15em;margin-bottom:8px;font-weight:400}
.podium-name{font-family:'Noto Serif JP',serif;font-size:1.3em;font-weight:700;color:#2d2d2d}
.podium-team{color:#b5b0a8;font-size:.78em;margin-top:4px}
.podium-avatar img{width:56px;height:56px;border-radius:50%;object-fit:cover;margin-bottom:8px}

.footer{text-align:center;color:#d0ccc4;padding:48px 20px;font-size:.75em;letter-spacing:.15em}
</style></head><body>
'''

# Hero
html += '''
<div class="snap-section" style="justify-content:flex-end;padding-bottom:0">
<div class="hero">
<h1>Fantasy NBA 24-25</h1>
<p class="sub">SEASON REVIEW</p>
<div class="season-line">LEAGUE 15393 &middot; 16 TEAMS &middot; 11-CAT H2H</div>
</div>
'''

# Nav — sticky inside the hero snap section
html += '<div class="nav">'
html += '<a href="index.html" style="color:#c8a45c;font-weight:500">HUB</a>'
html += '<a href="fantasy_data_overview.html">DATA OVERVIEW</a>'
html += '<a href="classic_battles.html">CLASSIC BATTLES</a>'
html += '<span style="color:#e8e4de">|</span>'
html += '<a href="#podium">PODIUM</a>'
for a in awards:
    html += f'<a href="#{a["id"]}">{a["name"]}</a>'
html += '<a href="classic_battles.html">CLASSIC BATTLES</a>'
html += '</div></div>'  # close nav + hero snap-section

# Podium — snap section
html += '<div class="snap-section" id="podium"><div class="inner">'
html += '<div class="podium-section">'
html += '<div class="podium-title">Season Podium</div>'
html += '<div class="podium">'
for place in [1,2,3]:
    tk = playoff_placements.get(place,'')
    t = tk_to_team.get(tk,{})
    label = {1:'CHAMPION',2:'RUNNER-UP',3:'THIRD PLACE'}[place]
    cls = f'podium-{place}'
    html += f'<div class="podium-item {cls}">'
    html += f'<div class="podium-avatar">{team_logo_html(t, 56)}</div>'
    html += f'<div class="podium-medal">{label}</div>'
    html += f'<div class="podium-name">{t.get("manager","?")}</div>'
    html += f'<div class="podium-team">{t.get("name","?")}</div>'
    html += '</div>'
html += '</div>'
# 4-8
html += '<div style="margin-top:24px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap">'
for place in [4,5,6,7,8]:
    tk = playoff_placements.get(place,'')
    t = tk_to_team.get(tk,{})
    if t:
        html += f'<span style="font-size:.78em;color:#b5b0a8">{place}th {t.get("manager","?")}</span>'
html += '</div></div>'
html += '</div></div>'  # close podium-section + inner + snap-section

# Award cards — each is a snap section
for a in awards:
    w_team = tk_to_team.get(a.get('winner_tk',''), {})
    r_team = tk_to_team.get(a.get('runner_tk',''), {})
    co_winners = a.get('co_winners', [])
    
    html += f'<div class="snap-section" id="{a["id"]}"><div class="inner">'
    html += f'<div class="award">'
    html += f'<div class="award-num">{a["emoji"]}</div>'
    html += f'<div class="award-name">{a["name"]}</div>'
    html += f'<div class="award-en">{a["en"]}</div>'
    
    if co_winners and len(co_winners) > 1:
        # 并列第一：多人同时显示，每人独立 stats + reason
        html += '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:24px">'
        for cw in co_winners:
            cw_team = tk_to_team.get(cw['tk'], {})
            html += '<div style="flex:1;min-width:280px;border:1px solid #e8e4de;border-radius:8px;padding:16px">'
            html += '<div class="winner-row">'
            html += team_logo_html(cw_team, 56)
            html += '<div class="winner-info">'
            html += '<div class="winner-label">WINNER (TIED)</div>'
            html += f'<div class="winner-name">{cw["manager"]}</div>'
            html += f'<div class="winner-team">{cw["team"]}</div>'
            html += '</div></div>'
            # 每人独立的 stats 和 reason
            cw_stats = cw.get('stats', a['stats'])
            cw_reason = cw.get('reason', a['reason'])
            html += f'<div class="stats-box" style="margin-top:12px">{cw_stats}</div>'
            html += f'<div class="reason-text" style="margin-top:8px">{cw_reason}</div>'
            html += '</div>'
        html += '</div>'
        html += f'<div class="highlight-text">{a["highlight"]}</div>'
    else:
        # 单人获奖
        html += '<div class="winner-row">'
        html += team_logo_html(w_team, 56)
        html += '<div class="winner-info">'
        html += '<div class="winner-label">WINNER</div>'
        html += f'<div class="winner-name">{a["winner"]}</div>'
        html += f'<div class="winner-team">{a["winner_team"]}</div>'
        html += '</div>'
        
        # Key player avatar if exists
        key_pk = a.get('key_player', '')
        if key_pk:
            pa_url = get_player_avatar(key_pk)
            pname = player_stats.get(key_pk, {}).get('name', '?')
            if pa_url:
                html += f'<div class="player-chip"><img src="{pa_url}" onerror="this.style.display=\'none\'">{pname}</div>'
        
        html += '</div>'
    
    if not (co_winners and len(co_winners) > 1):
        html += f'<div class="stats-box">{a["stats"]}</div>'
        html += f'<div class="reason-text">{a["reason"]}</div>'
        html += f'<div class="highlight-text">{a["highlight"]}</div>'
    
    # Runner-up with avatar
    html += '<div class="runner">'
    html += team_logo_html(r_team, 28)
    html += f'<span class="runner-badge">RUNNER-UP</span>'
    html += f'<span>{a["runner"]}</span>'
    html += f'<span style="color:#d0ccc4">({a["runner_team"]})</span>'
    html += '</div>'
    
    # Ranking details
    html += f'<details><summary>FULL RANKING ({len(a["all"])} teams)</summary>'
    html += '<table><tr><th class="rank-cell">#</th><th>Manager</th><th>Team</th><th>Data</th></tr>'
    for i, row in enumerate(a['all'], 1):
        mgr, team, detail = row[0], row[1], row[2]
        rtk = row[3] if len(row) > 3 else ''
        rt = tk_to_team.get(rtk, {})
        html += f'<tr><td class="rank-cell">{i}</td>'
        html += f'<td style="display:flex;align-items:center;gap:6px">{team_logo_html(rt, 22)} {mgr}</td>'
        html += f'<td>{team}</td><td>{detail}</td></tr>'
    html += '</table></details>'
    html += '</div>'  # close .award
    html += '</div></div>'  # close .inner + .snap-section

# Footer
html += f'''
<div class="footer">
GENERATED {datetime.now().strftime("%Y.%m.%d")} &middot; FANTASY BASKETBALL REVIEW
</div>
</body></html>
'''

out = os.path.join(os.path.dirname(__file__), 'fantasy_season_review.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[OK] {out}")
print(f"Awards: {len(awards)}")
for a in awards:
    print(f"  {a['emoji']} {a['name']}: {a['winner']} ({a['winner_team']})")
