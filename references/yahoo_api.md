# Yahoo Fantasy API 参考 & 踩坑记录

## API 端点

### 基础端点
| 功能 | 端点 | 说明 |
|------|------|------|
| 联赛信息 | `league/{league_key}/metadata` | 联赛名、赛季、队伍数 |
| 排名 | `league/{league_key}/standings` | W-L-T、win_pct、playoff_seed |
| 队伍详情 | `league/{league_key}/teams` | 经理、头像、team_logos |
| 选秀 | `league/{league_key}/draftresults` | 全部选秀记录 |
| 交易 | `league/{league_key}/transactions` | add/drop/trade |

### Scoreboard 端点
| 功能 | 端点 | 关键字段 |
|------|------|---------|
| 每周对阵 | `league/{league_key}/scoreboard;week={n}` | `matchups` → `teams` → `team_stats` |
| 比分判定 | 同上 | `stat_winners` → `{cat: {winner: team_key, tied: '0'}}` |
| 胜负 | 同上 | `winner_team_key` |

### 球员端点
| 功能 | 端点 | 说明 |
|------|------|------|
| 球员统计 | `players;player_keys={keys}/stats` | 最多25个key一批 |
| 队伍阵容 | `team/{team_key}/roster;week={n}` | 当周活跃球员 |

## Stat ID 映射（11-Cat）

| Stat ID | 名称 | 代码 | 类型 | 说明 |
|:---:|------|:---:|:---:|------|
| 5 | 投篮命中率 | FG% | 比率 | 越高越好 |
| 8 | 罚球命中率 | FT% | 比率 | 越高越好 |
| 10 | 三分命中 | 3PM | 累计 | 越多越好 |
| 12 | 得分 | PTS | 累计 | 越多越好 |
| 13 | 助攻 | AST | 累计 | 越多越好 |
| 15 | 篮板 | REB | 累计 | 越多越好 |
| 16 | 抢断 | STL | 累计 | 越多越好 |
| 17 | 盖帽 | BLK | 累计 | 越多越好 |
| 18 | 失误 | TO | 累计 | **越低越好** |
| 19 | 前场篮板 | OREB | 累计 | 越多越好 |
| 20 | 助攻失误比 | A/TO | 比率 | 越高越好 |

**注意**：`player_stats` 里 stat_id=19 存为 `GP` key，stat_id=20 存为 `TW` key（yahoo_fantasy_api 的映射问题）。生成报告时需要转换。

## Scoreboard 数据结构

```json
{
  "weekly_scoreboard": {
    "1": [
      {
        "team1": "YCCC Team",
        "team1_key": "466.l.15393.t.3",
        "team2": "Laheman's Legendary Team",
        "team2_key": "466.l.15393.t.10",
        "team1_cat_wins": 5,
        "team2_cat_wins": 6,
        "ties": 0,
        "score": "5-6-0",
        "winner_team_key": "466.l.15393.t.10",
        "is_playoffs": "0",
        "team1_stats": {"FG%": ".511", "FT%": ".823", ...},
        "team2_stats": {"FG%": ".510", "FT%": ".737", ...},
        "stat_winners": {
          "FG%": {"winner": "466.l.15393.t.10", "tied": "0"},
          "FT%": {"winner": "466.l.15393.t.10", "tied": "0"},
          ...
        }
      }
    ]
  }
}
```

**关键**：`stat_winners` 的 key 是 `FG%`/`FT%` 等显示名（不是 `s5`/`s8`），`winner` 是完整的 team_key。

## NBA.com API

### 球员匹配
```python
from nba_api.stats.static import players as nba_players
# 用全名匹配 Yahoo 球员到 NBA person_id
all_nba = nba_players.get_players()
# 匹配率: 322/358（其余为退役或G-League球员）
```

### 球员头像
```
https://cdn.nba.com/headshots/nba/latest/260x190/{person_id}.png
```

### 赛季场均数据
```python
from nba_api.stats.endpoints import leaguedashplayerstats
stats = leaguedashplayerstats.LeagueDashPlayerStats(
    season='2024-25',
    per_mode_detailed='PerGame'
)
```

## 踩坑记录

### 1. Yahoo OAuth Token 1小时过期
Yahoo OAuth Access Token 有效期约 1 小时。长时间拉取需要中间重新授权。

### 2. `cats` vs `stat_winners`
Scoreboard 返回的 `cats` 字段在某些联赛配置下为空，**必须用 `stat_winners`** 判断每个 category 的胜负。

### 3. STAT_MAP 必须包含 19 和 20
初始版本只映射了 stat_id 5-18（9项），遗漏了 19(OREB) 和 20(A/TO)。必须在 `fetch_scoreboard_final.py` 的 STAT_MAP 中包含全部 11 项。

### 4. add/drop 操作计数
一次 add/drop 在 transactions 里产生 **2 条记录**（dst + src）。按 `tx_id` 去重后才是实际操作次数。

### 5. player_stats 的 key 名
`yahoo_fantasy_api` 返回的 `player_stats` 里：
- stat_id=19 的 key 是 `GP`（不是 OREB）
- stat_id=20 的 key 是 `TW`（不是 A/TO）
生成报告时需要映射：`PS_KEY_MAP = {'OREB': 'GP', 'A/TO': 'TW'}`

### 6. 经理名隐私
Yahoo 隐私设置会把经理名显示为 `-- hidden --`。需要 `MANAGER_OVERRIDES` 手动覆盖。

### 7. 赛季开始日期
24-25 赛季开始日期为 **2025-10-27**（不是 10-20）。交易时间戳匹配当周时用：
```python
SEASON_START = datetime(2025, 10, 27)
week_start = SEASON_START + timedelta(weeks=week_num - 1)
week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
```

### 8. upset 对象 vs match 对象
`classic_upsets` 里的 `winner_team_key` / `loser_team_key` 可能为空。判断胜负方必须用 **scoreboard match 对象自身的 `winner_team_key`**。

### 9. 球队头像 vs 经理头像
- `manager_avatars`: 经理个人头像（Yahoo 账号头像）
- `team_logos`: 球队自定义头像（经理设置的队徽）
报告中统一使用 `team_logos`。

### 10. 球员 Rank 算法
旧版只用 PTS 排名，导致 Gobert 等蓝领球员被低估。改为 **11-cat Z-Score**：
```python
# 对每项统计计算 Z-Score
z = (player_value - league_mean) / league_stddev
# TO 反向：z_to = -z_to
# 过滤：赛季 PTS > 100
# 综合 Z = sum(11项 Z-Score)
```
Z-Score Top 3: Jokić(19.36) > Dončić(15.01) > Jalen Johnson(14.46)

### 11. scroll-snap 整页滚动
颁奖报告和经典战役使用 CSS `scroll-snap-type: y mandatory/proximity`，滚轮滚一下跳一个奖项/战役。
