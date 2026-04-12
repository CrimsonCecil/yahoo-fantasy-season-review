#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拉取所有球员赛季统计 + 名字"""
import json, os, sys, time, requests
from requests.auth import HTTPBasicAuth

sys.stdout.reconfigure(encoding='utf-8')

CLIENT_ID     = "dj0yJmk9d2F3a3RXSDN1YW9hJmQ9WVdrOVNERnJUVWd3WTJNbWNHbzlNQT09JnM5Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWE3"
CLIENT_SECRET = "28553ef85ef1d0804d44406fa1b43fe2590f837d"
TOKEN_FILE    = os.path.join(os.path.dirname(__file__), "yahoo_token.json")
BASE_URL      = "https://fantasysports.yahooapis.com/fantasy/v2"

STAT_MAP = {
    "5":"FG%","8":"FT%","10":"3PM","12":"PTS","13":"AST",
    "15":"REB","16":"STL","17":"BLK","18":"TO","19":"GP","20":"TW",
}

def get_token():
    with open(TOKEN_FILE) as f:
        t = json.load(f)
    if t.get("refresh_token"):
        r = requests.post(
            "https://api.login.yahoo.com/oauth2/get_token",
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            data={"grant_type":"refresh_token","redirect_uri":"oob",
                  "refresh_token":t["refresh_token"]},
        )
        if r.ok:
            new_t = r.json()
            new_t.setdefault("refresh_token", t["refresh_token"])
            with open(TOKEN_FILE,"w") as f: json.dump(new_t,f,indent=2)
            return new_t["access_token"]
    return t.get("access_token","")

def yapi(token, path):
    url = f"{BASE_URL}{path}?format=json"
    for i in range(3):
        r = requests.get(url, headers={"Authorization":f"Bearer {token}"})
        if r.ok: return r.json()
        if r.status_code == 401: return None
        time.sleep(1.5)
    return None

def fetch_players_batch(token, keys):
    keys_str = ",".join(keys)
    resp = yapi(token, f"/players;player_keys={keys_str}/stats;type=season_2024")
    if not resp:
        # fallback: try without season param
        resp = yapi(token, f"/players;player_keys={keys_str}/stats;type=season")
    if not resp:
        return {}
    players_raw = resp.get("fantasy_content",{}).get("players",{})
    count = int(players_raw.get("count", 0))
    result = {}
    for i in range(count):
        pd = players_raw.get(str(i),{}).get("player",[[], {}])
        pm = {}
        for x in (pd[0] if pd else []):
            if isinstance(x, dict): pm.update(x)
        stats_raw = pd[1].get("player_stats",{}).get("stats",[]) if len(pd)>1 else []
        stats = {}
        for s in stats_raw:
            sid = s.get("stat",{}).get("stat_id","")
            val = s.get("stat",{}).get("value","")
            if sid in STAT_MAP: stats[STAT_MAP[sid]] = val
        pk = pm.get("player_key","")
        if pk:
            eligible = pm.get("eligible_positions",[])
            pos = [p.get("position","") for p in eligible if isinstance(p,dict)] if isinstance(eligible,list) else []
            result[pk] = {
                "name":       pm.get("full_name", pm.get("name",{}).get("full","?")),
                "player_id":  pm.get("player_id",""),
                "positions":  pos,
                "status":     pm.get("status",""),
                "stats":      stats,
            }
    return result

def main():
    token = get_token()
    full_path = os.path.join(os.path.dirname(__file__), "yahoo_full_data.json")
    with open(full_path, encoding="utf-8") as f:
        data = json.load(f)

    # 收集所有 player keys
    picks = data.get("draft_picks_raw", [])
    txs   = data.get("transactions", [])

    all_keys = set()
    for p in picks:
        if p.get("player_key"): all_keys.add(p["player_key"])
    for tx in txs:
        for pl in tx.get("players", []):
            if pl.get("player_key"): all_keys.add(pl["player_key"])

    all_keys = list(all_keys)
    print(f"[*] 共 {len(all_keys)} 名球员，分批拉取统计...")

    all_player_stats = {}
    batch_size = 25
    for i in range(0, len(all_keys), batch_size):
        batch = all_keys[i:i+batch_size]
        result = fetch_players_batch(token, batch)
        all_player_stats.update(result)
        print(f"    批次 {i//batch_size+1}/{(len(all_keys)-1)//batch_size+1}: 拿到 {len(result)} 名 (累计 {len(all_player_stats)})")
        time.sleep(0.4)

    data["player_stats"] = all_player_stats
    print(f"\n[OK] 球员统计拿到 {len(all_player_stats)} 名")

    # 打印几个示例
    for pk, info in list(all_player_stats.items())[:3]:
        print(f"  {info['name']}: {info['stats']}")

    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"[OK] 已保存到 {full_path}")

if __name__ == "__main__":
    main()
