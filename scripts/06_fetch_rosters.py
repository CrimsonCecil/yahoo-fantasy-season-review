#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拉取 16队 × 23周 的每周阵容"""
import json, sys, time
sys.stdout.reconfigure(encoding='utf-8')

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

sc = OAuth2(None, None, from_file='oauth2.json')
if not sc.token_is_valid():
    sc.refresh_access_token()

gm = yfa.Game(sc, 'nba')
lg = gm.to_league('nba.l.15393')
teams_raw = lg.teams()

full = json.load(open('yahoo_full_data.json', encoding='utf-8'))

# 已有数据则跳过
existing = full.get('weekly_rosters', {})
print(f"已有 weekly_rosters: {len(existing)} 队")

all_rosters = existing.copy()
total = len(teams_raw) * 23
done = 0

for tk, tinfo in teams_raw.items():
    tname = tinfo.get('name', '?')
    if tk not in all_rosters:
        all_rosters[tk] = {}
    
    team_obj = lg.to_team(tk)
    
    for week in range(1, 24):
        wk_str = str(week)
        if wk_str in all_rosters[tk]:
            done += 1
            continue
        
        try:
            roster = team_obj.roster(week)
            players = []
            for p in roster:
                players.append({
                    'player_id': p.get('player_id', ''),
                    'name': p.get('name', '?'),
                    'team_abbr': p.get('editorial_team_abbr', ''),
                    'position': p.get('selected_position', ''),
                    'eligible_positions': p.get('eligible_positions', []),
                })
            all_rosters[tk][wk_str] = players
            done += 1
            print(f"  [{done}/{total}] {tname} Week {week}: {len(players)} players")
        except Exception as e:
            done += 1
            print(f"  [{done}/{total}] {tname} Week {week}: ERROR - {e}")
            all_rosters[tk][wk_str] = []
        
        # Rate limit
        time.sleep(0.3)
    
    # 每队保存一次
    full['weekly_rosters'] = all_rosters
    with open('yahoo_full_data.json', 'w', encoding='utf-8') as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    print(f"  [SAVED] {tname} done")

print(f"\n[OK] 全部完成, {total} 条记录")
