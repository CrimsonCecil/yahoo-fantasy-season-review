#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Fantasy NBA 赛季回顾汇总首页 + 在三个报告中注入统一导航"""
import json, sys, os
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

d = json.load(open('yahoo_full_data.json', encoding='utf-8'))

wlt = d.get('teams_wlt', {})
team_logos = d.get('team_logos', {})
playoff_placements = {}

# 简单推导冠亚季军
weekly_sb = d.get('weekly_scoreboard', {})
if weekly_sb.get('21') and weekly_sb.get('22') and weekly_sb.get('23'):
    qf_w = set()
    for m in weekly_sb['21']:
        if m.get('is_playoffs') == '1':
            qf_w.add(m['winner_team_key'])
    sf_w, sf_l = set(), set()
    for m in weekly_sb['22']:
        if m.get('is_playoffs') != '1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk != t1k else t2k
        if t1k in qf_w and t2k in qf_w:
            sf_w.add(wk); sf_l.add(lk)
    for m in weekly_sb['23']:
        if m.get('is_playoffs') != '1': continue
        wk = m['winner_team_key']
        t1k, t2k = m['team1_key'], m['team2_key']
        lk = t1k if wk != t1k else t2k
        if t1k in sf_w and t2k in sf_w:
            playoff_placements[1] = wk; playoff_placements[2] = lk
        elif t1k in sf_l and t2k in sf_l:
            playoff_placements[3] = wk; playoff_placements[4] = lk

MANAGER_OVERRIDES = {'King Crimson Cecil': 'Cecil'}

# 队伍信息
teams = []
for tid, t in wlt.items():
    name = t.get('name', '?')
    mgr = MANAGER_OVERRIDES.get(name, t.get('manager', '?'))
    tk = t.get('team_key', '')
    logo = team_logos.get(tk, '')
    teams.append({'name': name, 'manager': mgr, 'team_key': tk, 'logo': logo,
                  'rank': int(t.get('rank') or 99),
                  'W': t.get('wins', 0), 'L': t.get('losses', 0), 'T': t.get('ties', 0)})
teams.sort(key=lambda x: x['rank'])

tk_to_team = {t['team_key']: t for t in teams}

html = '''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>Fantasy NBA 24-25 — Hub</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:'Noto Sans JP','Helvetica Neue',system-ui,sans-serif;
  background:#faf9f6;color:#2d2d2d;min-height:100vh;
  display:flex;flex-direction:column;align-items:center;
}
.hero{
  text-align:center;padding:80px 20px 50px;width:100%;
  border-bottom:1px solid #e8e4de;
}
.hero h1{
  font-family:'Noto Serif JP',serif;font-size:2.8em;font-weight:400;
  color:#2d2d2d;letter-spacing:.08em;
}
.hero .sub{color:#8a8580;font-size:1em;letter-spacing:.2em;font-weight:300;margin-top:12px}
.hero .season-badge{
  display:inline-block;margin-top:24px;padding:8px 28px;
  border:1px solid #c8a45c;color:#c8a45c;font-size:.78em;letter-spacing:.25em;
}

/* 冠亚季军迷你领奖台 */
.mini-podium{
  display:flex;justify-content:center;align-items:flex-end;gap:32px;
  margin-top:40px;
}
.mini-podium-item{text-align:center}
.mini-podium-item img{width:52px;height:52px;border-radius:50%;object-fit:cover;margin-bottom:6px}
.mini-podium-item .label{font-size:.68em;color:#c8a45c;letter-spacing:.2em}
.mini-podium-item .name{font-family:'Noto Serif JP',serif;font-size:1.1em;font-weight:700}
.mini-podium-item.p1 .name{font-size:1.3em}

/* 三个报告卡片 */
.cards{
  display:flex;gap:24px;flex-wrap:wrap;justify-content:center;
  max-width:1000px;margin:48px auto;padding:0 20px;
}
.card{
  flex:1;min-width:280px;max-width:320px;
  background:#fff;border:1px solid #e8e4de;
  padding:32px 24px;text-decoration:none;color:#2d2d2d;
  transition:border-color .3s, box-shadow .3s;
  display:flex;flex-direction:column;
}
.card:hover{border-color:#c8a45c;box-shadow:0 4px 20px rgba(200,164,92,.12)}
.card-num{font-family:'Noto Serif JP',serif;font-size:3em;font-weight:700;color:#f0ede8;line-height:1}
.card-title{font-family:'Noto Serif JP',serif;font-size:1.2em;margin-top:8px;letter-spacing:.05em}
.card-desc{color:#8a8580;font-size:.82em;margin-top:12px;line-height:1.7;flex:1}
.card-link{
  margin-top:20px;font-size:.75em;color:#c8a45c;letter-spacing:.2em;
  font-weight:500;
}

/* 队伍列表 */
.team-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
  gap:12px;max-width:1000px;margin:20px auto 60px;padding:0 20px;
}
.team-item{
  display:flex;align-items:center;gap:10px;padding:10px 14px;
  background:#fff;border:1px solid #f0ede8;font-size:.82em;
}
.team-item img{width:32px;height:32px;border-radius:50%;object-fit:cover}
.team-item .rank-num{color:#b5b0a8;font-size:.75em;min-width:20px}
.team-item .team-name{font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.team-item .team-mgr{color:#8a8580;font-size:.85em}

.section-title{
  font-family:'Noto Serif JP',serif;font-size:1.1em;color:#2d2d2d;
  letter-spacing:.1em;text-align:center;margin-top:48px;
}
.section-line{width:40px;height:1px;background:#c8a45c;margin:12px auto 0}

.footer{text-align:center;color:#d0ccc4;padding:40px 20px;font-size:.72em;letter-spacing:.15em}
</style></head><body>
'''

# Hero
html += '''
<div class="hero">
<h1>Fantasy NBA 24-25</h1>
<p class="sub">SEASON HUB</p>
<div class="season-badge">LEAGUE 15393 &middot; 16 TEAMS &middot; 11-CAT H2H</div>
'''

# Mini podium
html += '<div class="mini-podium">'
for place, cls in [(2, 'p2'), (1, 'p1'), (3, 'p3')]:
    tk = playoff_placements.get(place, '')
    t = tk_to_team.get(tk, {})
    label = {1: 'CHAMPION', 2: 'RUNNER-UP', 3: 'THIRD'}[place]
    logo = t.get('logo', '')
    img = f'<img src="{logo}" onerror="this.style.display=\'none\'">' if logo else ''
    html += f'<div class="mini-podium-item {cls}">'
    html += img
    html += f'<div class="label">{label}</div>'
    html += f'<div class="name">{t.get("manager", "?")}</div>'
    html += '</div>'
html += '</div></div>'

# Three report cards
html += '<div class="cards">'

cards = [
    ('01', 'Season Review', '12 项赛季奖项颁奖典礼。最佳总教练、选秀之王、转会大师等全面评选。',
     'fantasy_season_review.html', 'VIEW AWARDS →'),
    ('02', 'Data Overview', '16 队完整数据总览。战绩、每周对阵、排名变化、选秀、交易一目了然。',
     'fantasy_data_overview.html', 'VIEW DATA →'),
    ('03', 'Classic Battles', '赛季 5 大以下克上经典战役。双方阵容对比、操作分析、翻盘叙事。',
     'classic_battles.html', 'VIEW BATTLES →'),
]

for num, title, desc, link, label in cards:
    html += f'''<a class="card" href="{link}">
    <div class="card-num">{num}</div>
    <div class="card-title">{title}</div>
    <div class="card-desc">{desc}</div>
    <div class="card-link">{label}</div>
    </a>'''

html += '</div>'

# Team grid
html += '<div class="section-title">ALL TEAMS</div>'
html += '<div class="section-line"></div>'
html += '<div class="team-grid">'
for t in teams:
    logo = t.get('logo', '')
    img = f'<img src="{logo}" onerror="this.style.display=\'none\'">' if logo else ''
    html += f'<div class="team-item">'
    html += f'<span class="rank-num">#{t["rank"]}</span>'
    html += img
    html += f'<span class="team-name">{t["name"]}</span>'
    html += f'<span class="team-mgr">{t["manager"]}</span>'
    html += '</div>'
html += '</div>'

# Footer
html += f'''
<div class="footer">
GENERATED {datetime.now().strftime("%Y.%m.%d")} &middot; FANTASY BASKETBALL REVIEW SKILL
</div>
</body></html>'''

out = os.path.join(os.path.dirname(__file__), 'index.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"[OK] {out}")
