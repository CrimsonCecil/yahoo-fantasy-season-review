#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 nba_api 匹配 Yahoo Fantasy 球员到 NBA.com 的:
1. person_id -> 头像 URL
2. 24-25 赛季真实场均数据
"""
import json, sys, time
sys.stdout.reconfigure(encoding='utf-8')

from nba_api.stats.static import players as nba_players
from nba_api.stats.endpoints import leaguedashplayerstats

# 加载 Yahoo 数据
d = json.load(open('yahoo_full_data.json', encoding='utf-8'))
player_stats = d.get('player_stats', {})

# 获取所有 NBA 球员列表
all_nba = nba_players.get_players()
print(f"NBA 球员库: {len(all_nba)} 人")

# 构建名字索引（小写全名 -> player info）
name_index = {}
for p in all_nba:
    name_index[p['full_name'].lower()] = p
    # 也加 first_last 无空格版本
    name_index[f"{p['first_name']} {p['last_name']}".lower()] = p

# 常见名字差异映射（Yahoo名 -> NBA名）
NAME_FIXES = {
    'Nic Claxton': 'Nicolas Claxton',
    'Cam Thomas': 'Cameron Thomas',
    'AJ Griffin': 'AJ Griffin',
    'Jabari Smith Jr.': 'Jabari Smith Jr.',
    'GG Jackson II': 'GG Jackson II',
    'Herb Jones': 'Herbert Jones',
    'PJ Washington': 'P.J. Washington',
    'Dereck Lively II': 'Dereck Lively II',
    'Cam Johnson': 'Cameron Johnson',
    'Jalen Johnson': 'Jalen Johnson',
    'TJ McConnell': 'T.J. McConnell',
    'Kenyon Martin Jr.': 'Kenyon Martin Jr.',
    'Marcus Morris Sr.': 'Marcus Morris Sr.',
    'Trey Murphy III': 'Trey Murphy III',
    'Jaime Jaquez Jr.': 'Jaime Jaquez Jr.',
    'Robert Williams III': 'Robert Williams III',
    'Kelly Oubre Jr.': 'Kelly Oubre Jr.',
    'Wendell Carter Jr.': 'Wendell Carter Jr.',
    'Larry Nance Jr.': 'Larry Nance Jr.',
    'Tim Hardaway Jr.': 'Tim Hardaway Jr.',
    'Gary Trent Jr.': 'Gary Trent Jr.',
    'Dennis Smith Jr.': 'Dennis Smith Jr.',
    'Luguentz Dort': 'Luguentz Dort',
}

def match_player(yahoo_name):
    """尝试匹配 Yahoo 球员名到 NBA person_id"""
    if not yahoo_name or yahoo_name == '?':
        return None
    
    # 先尝试直接匹配
    key = yahoo_name.lower().strip()
    if key in name_index:
        return name_index[key]
    
    # 尝试 NAME_FIXES
    fixed = NAME_FIXES.get(yahoo_name, yahoo_name)
    key = fixed.lower().strip()
    if key in name_index:
        return name_index[key]
    
    # 去掉后缀 Jr./Sr./II/III/IV
    import re
    clean = re.sub(r'\s+(Jr\.|Sr\.|II|III|IV|V)$', '', yahoo_name, flags=re.IGNORECASE).strip()
    key = clean.lower()
    if key in name_index:
        return name_index[key]
    
    # 模糊搜索
    results = nba_players.find_players_by_full_name(yahoo_name)
    if results and len(results) == 1:
        return results[0]
    
    # 按姓搜索
    parts = yahoo_name.split()
    if len(parts) >= 2:
        last = parts[-1]
        if last.lower() in ('jr.', 'sr.', 'ii', 'iii', 'iv'):
            last = parts[-2] if len(parts) > 2 else parts[0]
        results = nba_players.find_players_by_last_name(last)
        if results and len(results) == 1:
            return results[0]
        # 如果多个结果，找 first_name 开头匹配的
        first = parts[0].lower()
        for r in results:
            if r['first_name'].lower().startswith(first[:3]):
                return r
    
    return None

# 匹配所有球员
print("\n开始匹配球员...")
matched = 0
unmatched = []
player_nba_map = {}  # yahoo_player_key -> {nba_id, headshot_url, name}

for pk, ps in player_stats.items():
    yahoo_name = ps.get('name', '')
    nba_info = match_player(yahoo_name)
    if nba_info:
        nba_id = nba_info['id']
        headshot = f"https://cdn.nba.com/headshots/nba/latest/260x190/{nba_id}.png"
        player_nba_map[pk] = {
            'nba_id': nba_id,
            'nba_name': nba_info['full_name'],
            'headshot_url': headshot,
            'is_active': nba_info.get('is_active', False),
        }
        matched += 1
    else:
        unmatched.append(yahoo_name)

print(f"匹配成功: {matched}/{len(player_stats)}")
print(f"未匹配: {len(unmatched)}")
if unmatched[:20]:
    print(f"示例未匹配: {unmatched[:20]}")

# 拉取 24-25 赛季真实场均数据
print("\n拉取 NBA.com 24-25 赛季场均数据...")
try:
    time.sleep(1)  # rate limit
    stats_resp = leaguedashplayerstats.LeagueDashPlayerStats(
        season='2024-25',
        per_mode_detailed='PerGame',
        season_type_all_star='Regular Season'
    )
    rows = stats_resp.get_data_frames()[0]
    print(f"获取到 {len(rows)} 名球员的场均数据")
    
    # 建立 nba_id -> 场均数据 的映射
    nba_avg_stats = {}
    for _, row in rows.iterrows():
        pid = int(row['PLAYER_ID'])
        nba_avg_stats[pid] = {
            'GP': int(row['GP']),
            'MIN': round(row['MIN'], 1),
            'FG_PCT': round(row['FG_PCT'], 3) if row['FG_PCT'] else 0,
            'FT_PCT': round(row['FT_PCT'], 3) if row['FT_PCT'] else 0,
            'FG3M': round(row['FG3M'], 1),
            'PTS': round(row['PTS'], 1),
            'OREB': round(row['OREB'], 1),
            'REB': round(row['REB'], 1),
            'AST': round(row['AST'], 1),
            'STL': round(row['STL'], 1),
            'BLK': round(row['BLK'], 1),
            'TOV': round(row['TOV'], 1),
        }
        # 计算 A/TO
        if row['TOV'] > 0:
            nba_avg_stats[pid]['A_TO'] = round(row['AST'] / row['TOV'], 2)
        else:
            nba_avg_stats[pid]['A_TO'] = 0
    
    # 写入 player_nba_map
    for pk, info in player_nba_map.items():
        nba_id = info['nba_id']
        if nba_id in nba_avg_stats:
            info['per_game'] = nba_avg_stats[nba_id]
    
    has_pg = sum(1 for v in player_nba_map.values() if 'per_game' in v)
    print(f"有场均数据: {has_pg}/{matched}")

except Exception as e:
    print(f"[WARN] 拉取场均数据失败: {e}")
    import traceback
    traceback.print_exc()

# 保存到 yahoo_full_data.json
d['player_nba_map'] = player_nba_map
with open('yahoo_full_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f"\n[OK] player_nba_map 已保存到 yahoo_full_data.json")
print(f"  - {matched} 球员有头像 URL")
print(f"  - {has_pg} 球员有 NBA.com 真实场均数据")

# 验证几个关键球员
test_names = ['Shai Gilgeous-Alexander', 'LeBron James', 'Nikola Jokic', 'Victor Wembanyama']
for name in test_names:
    for pk, info in player_nba_map.items():
        if info.get('nba_name') == name:
            pg = info.get('per_game', {})
            print(f"  {name}: headshot OK, PTS={pg.get('PTS','-')}/g REB={pg.get('REB','-')}/g AST={pg.get('AST','-')}/g")
            break
