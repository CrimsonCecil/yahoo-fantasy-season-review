#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正确解析 scoreboard 结构，拉取 23 周对阵 + 季后赛"""
import json, sys, time, requests
sys.stdout.reconfigure(encoding='utf-8')

with open("yahoo_token.json") as f: t=json.load(f)
TOKEN=t["access_token"]
H={"Authorization":f"Bearer {TOKEN}"}
BASE="https://fantasysports.yahooapis.com/fantasy/v2"
LK="466.l.15393"

STAT_MAP={"5":"FG%","8":"FT%","10":"3PM","12":"PTS","13":"AST","15":"REB","16":"STL","17":"BLK","18":"TO","19":"OREB","20":"A/TO"}

def get_sb(week):
    for attempt in range(5):
        try:
            r=requests.get(f"{BASE}/league/{LK}/scoreboard;week={week}?format=json",headers=H,timeout=30)
            return r.json() if r.ok else None
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            print(f"    [RETRY {attempt+1}/5] Week {week}: {type(e).__name__}")
            time.sleep(3 + attempt * 2)
    return None

def parse_team_name(t_arr):
    info={}
    for x in (t_arr if isinstance(t_arr,list) else []):
        if isinstance(x,dict): info.update(x)
    mgrs=info.get("managers",[])
    mgr=mgrs[0].get("manager",{}).get("nickname","?") if mgrs else "?"
    return info.get("team_key","?"), info.get("name","?"), mgr

# 加载现有数据
with open("yahoo_full_data.json",encoding="utf-8") as f: data=json.load(f)

all_weeks=data.get("weekly_scoreboard",{})
already=set(all_weeks.keys())
if already:
    print(f"  (已有 Week {', '.join(sorted(already, key=int))} 数据，跳过)\n")
print("[*] 拉取 23 周 Scoreboard...\n")

for week in range(1,24):
    resp=get_sb(week)
    if not resp: print(f"  Week {week:2d}: FAIL"); continue
    
    la=resp.get("fantasy_content",{}).get("league",[{},{}])
    if len(la)<2: print(f"  Week {week:2d}: no data"); continue
    
    sb=la[1].get("scoreboard",{})
    # matchups 在 sb["0"]["matchups"] 里
    inner=sb.get("0",{})
    matchups_raw=inner.get("matchups",{})
    
    count=int(matchups_raw.get("count",0))
    if count==0:
        print(f"  Week {week:2d}: 0 matchups")
        continue
    
    week_data=[]
    for j in range(count):
        m=matchups_raw.get(str(j),{}).get("matchup",{})
        
        wk=m.get("week","?")
        status=m.get("status","?")
        is_pf=str(m.get("is_playoffs","0"))
        is_con=str(m.get("is_consolation","0"))
        winner_key=m.get("winner_team_key","")
        is_tied=m.get("is_tied",0)
        
        # stat_winners
        stat_winners={}
        for sw in m.get("stat_winners",[]):
            si=sw.get("stat_winner",{})
            sid=si.get("stat_id","")
            wtk=si.get("winner_team_key","")
            is_t=si.get("is_tied","0")
            label=STAT_MAP.get(sid,f"s{sid}")
            stat_winners[label]={"winner":wtk,"tied":str(is_t)}
        
        # teams
        teams_data=m.get("0",{}).get("teams",{})
        pair=[]
        for k in range(2):
            td=teams_data.get(str(k),{}).get("team",[[],{}])
            tk,name,mgr=parse_team_name(td[0] if td else [])
            
            # stats
            stats={}
            if len(td)>1:
                ts=td[1].get("team_stats",{}).get("stats",[])
                for s in ts:
                    sid=s.get("stat",{}).get("stat_id","")
                    val=s.get("stat",{}).get("value","")
                    label=STAT_MAP.get(sid,"")
                    if label: stats[label]=val
            
            pair.append({"team_key":tk,"name":name,"manager":mgr,"stats":stats})
        
        # count cat wins
        t1k,t2k=pair[0]["team_key"],pair[1]["team_key"]
        w1,w2,ties=0,0,0
        for cat,info in stat_winners.items():
            if cat not in STAT_MAP.values(): continue
            if info["tied"]=="1": ties+=1
            elif info["winner"]==t1k: w1+=1
            elif info["winner"]==t2k: w2+=1
        
        week_data.append({
            "week":int(wk),
            "status":status,
            "is_playoffs":is_pf,
            "is_consolation":is_con,
            "winner_team_key":winner_key,
            "is_tied":is_tied,
            "team1":pair[0]["name"],"team1_key":t1k,"team1_mgr":pair[0]["manager"],
            "team1_stats":pair[0]["stats"],"team1_cat_wins":w1,
            "team2":pair[1]["name"],"team2_key":t2k,"team2_mgr":pair[1]["manager"],
            "team2_stats":pair[1]["stats"],"team2_cat_wins":w2,
            "ties":ties,"score":f"{w1}-{w2}-{ties}",
            "stat_winners":stat_winners,
        })
    
    all_weeks[str(week)]=week_data
    pf_flag=any(m["is_playoffs"]=="1" for m in week_data)
    con_flag=any(m["is_consolation"]=="1" for m in week_data)
    tag=""
    if pf_flag: tag+=" [PLAYOFF]"
    if con_flag: tag+=" [CONSOLATION]"
    
    brief=[]
    for mu in week_data[:4]:
        brief.append(f"{mu['team1_mgr'][:6]} {mu['score']} {mu['team2_mgr'][:6]}")
    extra=f" +{len(week_data)-4}" if len(week_data)>4 else ""
    print(f"  Week {week:2d}: {count} 场{tag} | {' | '.join(brief)}{extra}")
    time.sleep(0.35)

data["weekly_scoreboard"]=all_weeks

# 季后赛 / 安慰赛 分离
pf={wk:[m for m in ms if m["is_playoffs"]=="1" and m["is_consolation"]!="1"] for wk,ms in all_weeks.items()}
pf={k:v for k,v in pf.items() if v}
con={wk:[m for m in ms if m["is_consolation"]=="1"] for wk,ms in all_weeks.items()}
con={k:v for k,v in con.items() if v}
data["playoff_matchups"]=pf
data["consolation_matchups"]=con

# 每周排名
print("\n[*] 计算每周排名...")
cum={}
weekly_standings={}
for wk in sorted(all_weeks.keys(),key=int):
    for mu in all_weeks[wk]:
        for nm,kk,wf,lf in [("team1","team1_key","team1_cat_wins","team2_cat_wins"),
                              ("team2","team2_key","team2_cat_wins","team1_cat_wins")]:
            tk=mu[kk]
            if tk not in cum: cum[tk]={"name":mu[nm],"mgr":mu[nm.replace("team","team")+"_mgr"],"w":0,"l":0,"t":0}
            cum[tk]["w"]+=mu[wf]; cum[tk]["l"]+=mu[lf]; cum[tk]["t"]+=mu["ties"]
    
    ranking=[]
    for tk,c in cum.items():
        total=c["w"]+c["l"]+c["t"]
        pct=c["w"]/total if total>0 else 0
        ranking.append({"key":tk,"name":c["name"],"mgr":c["mgr"],"w":c["w"],"l":c["l"],"t":c["t"],"pct":round(pct,4)})
    ranking.sort(key=lambda x: x["pct"],reverse=True)
    for i,r in enumerate(ranking): r["rank"]=i+1
    weekly_standings[wk]=ranking

data["weekly_standings"]=weekly_standings

# 打印最终排名
if weekly_standings:
    last=max(weekly_standings.keys(),key=int)
    print(f"\n  Week {last} 最终排名:")
    for s in weekly_standings[last]:
        print(f"    #{s['rank']:>2} {s['name']:<30} ({s['mgr']:<12}) {s['w']}-{s['l']}-{s['t']} ({s['pct']:.3f})")

# 季后赛
if pf:
    print(f"\n  季后赛 (Week {', '.join(pf.keys())}):")
    for wk,ms in sorted(pf.items(),key=lambda x:int(x[0])):
        for mu in ms:
            w="*" if mu["winner_team_key"]==mu["team1_key"] else " "
            l="*" if mu["winner_team_key"]==mu["team2_key"] else " "
            print(f"    Week {wk}: {w}{mu['team1']:<26} {mu['score']:>7} {l}{mu['team2']}")

with open("yahoo_full_data.json","w",encoding="utf-8") as f:
    json.dump(data,f,indent=2,ensure_ascii=False,default=str)

print(f"\n[OK] 全部完成! {len(all_weeks)} 周, {sum(len(v) for v in pf.values())} 场季后赛, {sum(len(v) for v in con.values())} 场安慰赛")
