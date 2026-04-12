#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充拉取：W-L-T 战绩、每周对阵、选秀、交易
"""
import json, os, sys, time, requests
from requests.auth import HTTPBasicAuth

CLIENT_ID     = "dj0yJmk9d2F3a3RXSDN1YW9hJmQ9WVdrOVNERnJUVWd3WTJNbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWE3"
CLIENT_SECRET = "28553ef85ef1d0804d44406fa1b43fe2590f837d"
LEAGUE_ID     = "15393"
TOKEN_FILE    = os.path.join(os.path.dirname(__file__), "yahoo_token.json")
BASE_URL      = "https://fantasysports.yahooapis.com/fantasy/v2"
LEAGUE_KEY    = f"nba.l.{LEAGUE_ID}"

STAT_MAP = {
    "5":  "FG%",
    "8":  "FT%",
    "10": "3PM",
    "12": "PTS",
    "13": "AST",
    "15": "REB",
    "16": "STL",
    "17": "BLK",
    "18": "TO",
    "19": "GP",
    "20": "TW",   # Total Wins (H2H)
}

def get_token():
    with open(TOKEN_FILE) as f:
        t = json.load(f)
    if t.get("refresh_token"):
        r = requests.post(
            "https://api.login.yahoo.com/oauth2/get_token",
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={"grant_type": "refresh_token", "redirect_uri": "oob",
                  "refresh_token": t["refresh_token"]},
        )
        if r.ok:
            new_t = r.json()
            new_t.setdefault("refresh_token", t["refresh_token"])
            with open(TOKEN_FILE, "w") as f:
                json.dump(new_t, f, indent=2)
            return new_t["access_token"]
    return t.get("access_token", "")

def yapi(token, path, retries=2):
    url = f"{BASE_URL}{path}?format=json"
    for i in range(retries):
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.ok:
            return r.json()
        if r.status_code == 401:
            print("[WARN] Token 过期，无法继续")
            return None
        print(f"[WARN] {r.status_code} {path} (retry {i+1})")
        time.sleep(1)
    return None

def parse_team_meta(meta_list):
    info = {}
    for x in meta_list:
        if isinstance(x, dict):
            info.update(x)
    name = info.get("name", "?")
    mgr_list = info.get("managers", [{}])
    mgr = mgr_list[0].get("manager", {}).get("nickname", "?") if mgr_list else "?"
    team_id = info.get("team_id", "?")
    team_key = info.get("team_key", "?")
    moves = info.get("number_of_moves", 0)
    trades = info.get("number_of_trades", 0)
    return {"name": name, "manager": mgr, "team_id": team_id,
            "team_key": team_key, "moves": moves, "trades": trades}

def main():
    token = get_token()
    output = {}

    # ── 1. 用 teams/standings 拿 W-L-T ─────────────────────────────────────
    print("[*] 拉取队伍战绩 (teams/standings) ...")
    resp = yapi(token, f"/league/{LEAGUE_KEY}/teams/standings")
    teams_wlt = {}
    if resp:
        league_arr = resp.get("fantasy_content", {}).get("league", [{}, {}])
        teams_raw = league_arr[1].get("teams", {}) if len(league_arr) > 1 else {}
        count = int(teams_raw.get("count", 0))
        print(f"    共 {count} 支队伍")
        for i in range(count):
            t_data = teams_raw.get(str(i), {}).get("team", [[], {}])
            meta = parse_team_meta(t_data[0] if t_data else [])
            st = {}
            if len(t_data) > 1:
                ts = t_data[1].get("team_standings", {})
                ot = ts.get("outcome_totals", {})
                st = {
                    "wins":   ot.get("wins", "?"),
                    "losses": ot.get("losses", "?"),
                    "ties":   ot.get("ties", "?"),
                    "win_pct": ot.get("percentage", "?"),
                    "rank":   ts.get("rank", "?"),
                    "playoff_seed": ts.get("playoff_seed", "?"),
                }
            entry = {**meta, **st}
            teams_wlt[meta["team_id"]] = entry
            line = (f"  #{st.get('rank','?'):>2} {meta['name']} ({meta['manager']})  "
                    f"W{st.get('wins','?')}-L{st.get('losses','?')}-T{st.get('ties','?')}  "
                    f"Moves:{meta['moves']} Trades:{meta['trades']}")
            print(line.encode('gbk', errors='replace').decode('gbk'))
    output["teams_wlt"] = teams_wlt

    # ── 2. 每周 scoreboard ─────────────────────────────────────────────────
    print("\n[*] 拉取每周 scoreboard ...")
    all_weekly = {}
    for week in range(1, 25):
        resp = yapi(token, f"/league/{LEAGUE_KEY}/scoreboard;week={week}")
        if not resp:
            print(f"    Week {week:2d}: 跳过（请求失败）")
            continue
        league_arr = resp.get("fantasy_content", {}).get("league", [{}, {}])
        if len(league_arr) < 2:
            print(f"    Week {week:2d}: 无数据")
            break
        sb = league_arr[1].get("scoreboard", {})
        matchups_raw = sb.get("matchups", {})
        count = int(matchups_raw.get("count", 0))
        if count == 0:
            print(f"    Week {week:2d}: 0 场 (赛季结束)")
            break

        week_matchups = []
        for j in range(count):
            m = matchups_raw.get(str(j), {}).get("matchup", {})
            teams_in_m = m.get("teams", {})
            pair = []
            for k in range(2):
                t_data = teams_in_m.get(str(k), {}).get("team", [[], {}])
                meta = parse_team_meta(t_data[0] if t_data else [])
                stats_raw = t_data[1].get("team_stats", {}).get("stats", []) if len(t_data) > 1 else []
                stats = {}
                for s in stats_raw:
                    sid = s.get("stat", {}).get("stat_id", "")
                    val = s.get("stat", {}).get("value", "")
                    if sid in STAT_MAP:
                        stats[STAT_MAP[sid]] = val
                pts = t_data[1].get("team_points", {}).get("total", "") if len(t_data) > 1 else ""
                pair.append({
                    "team_id": meta["team_id"],
                    "name": meta["name"],
                    "manager": meta["manager"],
                    "stats": stats,
                    "points": pts,
                })
            status = m.get("status", "")
            winner_id = m.get("winner_team_key", "").split(".")[-1] if m.get("winner_team_key") else ""
            week_matchups.append({
                "status": status,
                "winner_team_id": winner_id,
                "teams": pair,
            })

        all_weekly[str(week)] = week_matchups
        print(f"    Week {week:2d}: {count} 场 [OK]")
        time.sleep(0.3)

    output["weekly_matchups"] = all_weekly

    # ── 3. 赛季统计汇总（各队 stats） ──────────────────────────────────────
    print("\n[*] 拉取各队赛季统计 ...")
    resp = yapi(token, f"/league/{LEAGUE_KEY}/teams/stats")
    team_stats_out = {}
    if resp:
        league_arr = resp.get("fantasy_content", {}).get("league", [{}, {}])
        teams_raw = league_arr[1].get("teams", {}) if len(league_arr) > 1 else {}
        count = int(teams_raw.get("count", 0))
        for i in range(count):
            t_data = teams_raw.get(str(i), {}).get("team", [[], {}])
            meta = parse_team_meta(t_data[0] if t_data else [])
            stats_raw = t_data[1].get("team_stats", {}).get("stats", []) if len(t_data) > 1 else []
            stats = {}
            for s in stats_raw:
                sid = s.get("stat", {}).get("stat_id", "")
                val = s.get("stat", {}).get("value", "")
                if sid in STAT_MAP:
                    stats[STAT_MAP[sid]] = val
            team_stats_out[meta["team_id"]] = {"name": meta["name"], "manager": meta["manager"], "stats": stats}
    output["team_season_stats"] = team_stats_out

    # ── 4. 合并并保存 ──────────────────────────────────────────────────────
    base = os.path.join(os.path.dirname(__file__), "yahoo_raw_data.json")
    if os.path.exists(base):
        with open(base, encoding="utf-8") as f:
            existing = json.load(f)
        existing.update(output)
        output = existing

    out_path = os.path.join(os.path.dirname(__file__), "yahoo_full_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[OK] 完整数据已保存: {out_path}")

if __name__ == "__main__":
    main()
    print("[OK] 全部完成！")
