#!/usr/bin/env python3
"""
Yahoo Fantasy Basketball 数据拉取脚本
League ID: 15393, Season: 2023-24
"""
import json
import os
import sys

# OAuth credentials
CLIENT_ID = "dj0yJmk9d2F3a3RXSDN1YW9hJmQ9WVdrOVNERnJUVWd3WTJNbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWE3"
CLIENT_SECRET = "28553ef85ef1d0804d44406fa1b43fe2590f837d"
LEAGUE_ID = "15393"
SEASON = 2024  # 2023-24 赛季在 Yahoo 里标记为 2024

OAUTH_FILE = os.path.join(os.path.dirname(__file__), "yahoo_oauth.json")

def get_oauth():
    """获取或刷新 OAuth token，首次运行会打开浏览器授权"""
    from yahoo_oauth import OAuth2
    
    # 写入 credentials 文件
    if not os.path.exists(OAUTH_FILE):
        creds = {
            "consumer_key": CLIENT_ID,
            "consumer_secret": CLIENT_SECRET
        }
        with open(OAUTH_FILE, "w") as f:
            json.dump(creds, f)
    
    sc = OAuth2(None, None, from_file=OAUTH_FILE)
    if not sc.token_is_valid():
        sc.refresh_access_token()
    return sc


def fetch_league_data():
    import yahoo_fantasy_api as yfa
    
    print("[*] 正在进行 OAuth 授权...")
    sc = get_oauth()
    print("[OK] 授权成功！\n")
    
    # 获取 game 对象（nba）
    gm = yfa.Game(sc, 'nba')
    
    # 获取联赛
    print(f"[*] 拉取 League {LEAGUE_ID} 数据...")
    lg = gm.to_league(f"nba.l.{LEAGUE_ID}")
    
    # 联赛基本信息
    settings = lg.settings()
    print(f"\n=== 联赛基本信息 ===")
    print(json.dumps(settings, indent=2, ensure_ascii=False))
    
    # 所有队伍
    print(f"\n=== 队伍列表 ===")
    teams = lg.teams()
    for team in teams:
        print(f"  [{team.get('team_id', '?')}] {team.get('name', '?')} - 经理: {team.get('managers', [{}])[0].get('manager', {}).get('nickname', '?')}")
    
    # 赛季战绩
    print(f"\n=== 赛季战绩 ===")
    standings = lg.standings()
    for i, team in enumerate(standings, 1):
        print(f"  #{i} {team.get('name', '?')}: {team.get('outcome_totals', {})}")
    
    # 保存原始数据
    raw_data = {
        "settings": settings,
        "teams": teams,
        "standings": standings,
    }
    
    # 拉取每周数据
    print(f"\n=== 拉取每周战绩 ===")
    weekly_data = {}
    current_week = lg.current_week()
    print(f"当前周次: {current_week}")
    
    for week in range(1, current_week + 1):
        try:
            matchups = lg.matchups(week=week)
            weekly_data[week] = matchups
            print(f"  Week {week}: {len(matchups.get('fantasy_content', {}).get('league', [{}])[1].get('scoreboard', {}).get('matchups', {}).get('count', 0))} 场对决")
        except Exception as e:
            print(f"  Week {week}: 获取失败 - {e}")
    
    raw_data["weekly_matchups"] = weekly_data
    
    # 保存到文件
    output_path = os.path.join(os.path.dirname(__file__), "yahoo_raw_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[OK] 原始数据已保存到: {output_path}")
    
    return raw_data


if __name__ == "__main__":
    try:
        data = fetch_league_data()
        print("\n[OK] 数据拉取完成！")
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
