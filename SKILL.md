---
name: yahoo-fantasy-season-review
description: 从 Yahoo Fantasy Basketball 拉取联赛完整赛季数据并生成数据总览、颁奖典礼报告和经典战役报告。此技能整合了数据拉取和赛季回顾两大流程：先通过 Yahoo API 获取联赛战绩、每周对阵、选秀记录、交易记录、球员统计等全量数据，再通过 NBA.com API 补充球员头像和官方场均数据，最后生成 4 份 HTML 报告（汇总首页、数据总览、颁奖典礼、经典战役）。
triggers:
  - "yahoo fantasy 赛季回顾"
  - "拉取fantasy数据并生成报告"
  - "fantasy赛季总结"
  - "fantasy season review"
  - "yahoo fantasy recap"
  - "帮我回顾这赛季的fantasy"
---

# Yahoo Fantasy 赛季回顾

## 概述

一站式完成 Yahoo Fantasy NBA 数据拉取 + 赛季回顾报告生成。

**输入**: Yahoo OAuth 授权 + 联赛 ID
**输出**: 4 份 HTML 报告（可互相跳转）

## 文件结构

```
scripts/
├── 01_oauth_setup.py              # Yahoo OAuth 授权 + 选秀/交易基础数据
├── 02_fetch_standings.py          # 16队 W-L-T 战绩 + 赛季统计（11-cat）
├── 03_fetch_players.py            # 球员赛季统计（批量 player_key 查询）
├── 04_fetch_scoreboard.py         # 23周 Scoreboard + stat_winners + 季后赛
├── 05_fetch_nba_data.py           # NBA.com 球员头像 + 官方赛季场均数据
├── 06_fetch_rosters.py            # 16队×23周 每周阵容名单
├── 07_gen_overview.py             # 数据总览 HTML（6大板块）
├── 08_gen_review.py               # 颁奖典礼 HTML（12个奖项）
├── 09_gen_classic_battles.py      # 经典战役 HTML（以下克上 Top5）
└── 10_gen_index.py                # 汇总首页 HTML（互相跳转）

references/
└── yahoo_api.md                   # Yahoo API 参考 + 踩坑记录
```

## 执行流程

### 阶段一：数据拉取（步骤 1-6）

```
01 OAuth授权 → 02 战绩统计 → 03 球员数据 → 04 每周对阵 → 05 NBA头像场均 → 06 每周阵容
```

每步输出追加到 `yahoo_full_data.json`，最终包含：

| 数据 | 字段 | 说明 |
|------|------|------|
| 队伍战绩 | `teams_wlt` | 16队 W-L-T、胜率、排名、操作次数 |
| 赛季统计 | `team_season_stats` | 11-cat: FG%/FT%/3PM/PTS/OREB/REB/AST/STL/BLK/TO/A/TO |
| 选秀记录 | `draft_picks_raw` | 192个选秀（16队×12轮） |
| 交易记录 | `transactions` | Add/Drop/Trade 全部操作 |
| 球员统计 | `player_stats` | 358名球员赛季数据 |
| 每周对阵 | `weekly_scoreboard` | 23周完整 Scoreboard + stat_winners 胜负判定 |
| 每周排名 | `weekly_standings` | 23周排名变化 |
| NBA数据 | `player_nba_map` | NBA.com person_id、头像URL、官方赛季场均 |
| 每周阵容 | `weekly_rosters` | 16队×23周活跃球员名单 |
| 阵容Rank | `weekly_roster_rank` | 每周每队阵容均Rank值 |

### 阶段二：报告生成（步骤 7-10）

```
07 数据总览 → 08 颁奖报告 → 09 经典战役 → 10 汇总首页
```

输出 4 个 HTML 文件，用本地 HTTP 服务器预览：
```bash
python -m http.server 7788 --bind 127.0.0.1
# 浏览器打开 http://127.0.0.1:7788/index.html
```

## 报告内容

### 📊 数据总览 (`fantasy_data_overview.html`)

| 板块 | 内容 |
|------|------|
| 战绩 & 统计 | 16队排名、W-L-T、11项赛季统计、每列Top3高亮 |
| 每周对阵结果 | 23周完整对阵、11-cat详细比分、stat_winners颜色标记 |
| 经理每周胜负变化 | W/L/T + 比分 + 对手，悬停显示详情 |
| 每周排名变化 | 升降箭头 + 名次颜色（1-4绿/5-8黄/9+红） |
| 季后赛对决 | 总决赛/季军赛/排位赛分开显示 |
| 选秀记录 | 球员头像 + Rank + 11项场均 + Top100分级高亮 |
| 交易 & Waiver | 经理间转会卡片 + 多维重磅分析 + 操作日期 |

### 🏆 颁奖典礼 (`fantasy_season_review.html`)

**12 个奖项**（日式极简风格）：

| # | 奖项 | 评选依据 |
|:--:|------|---------|
| 1 | 🏆 最佳总教练 | 综合排名 + 胜率 + 季后赛成绩 |
| 2 | 📅 最佳常规赛教练 | 常规赛（W1-20）周胜利次数 + 最佳单周比分 |
| 3 | 🔥 最长连胜教练 | 赛季最长连续周胜利（支持并列并排显示） |
| 4 | 🎯 选秀之王 | 选秀球员平均 Rank（11-cat Z-Score 综合排名）越小越好 |
| 5 | 🎰 捡漏之王 | 自由市场签入球员的累计价值 |
| 6 | 🤝 转会大师 | 经理间交易的净价值提升（详列转入/转出球员+头像+Rank） |
| 7 | 🚀 逆袭王 | 前后半赛季排名提升幅度 |
| 8 | 📊 最稳阵容 | 每周比分标准差最低 |
| 9 | 👑 统计之王 | 赛季统计称霸最多类别（支持并列） |
| 10 | 🤕 最惨教练 | 险负次数（差≤2比分）+ 被对手累计赢比分 |
| 11 | 🦀 摆烂之王 | 最终排名垫底（趣味颁发） |
| 12 | 🦾 铁人教练 | 赛季操作次数最多（支持并列并排显示） |

**球员 Rank 算法**：11-cat Z-Score 综合排名
- 对每项统计计算 Z-Score = (球员值 - 联盟平均) / 标准差
- TO 反向处理（失误越少 Z 越高）
- 赛季 PTS > 100 才参与排名（过滤小样本球员）
- 最终 Z-Score = 11 项 Z 值之和，降序排名

**特性**：
- 并列第一同时显示在 WINNER 区域，各自独立卡片含 stats + reason
- 球队头像（team_logos）显示在领奖台和奖项卡片中
- 关键球员内嵌 NBA.com 头像
- 整页滚动（scroll-snap）：滚轮滚一下跳一个奖项
- 转会大师详列转入/转出球员名 + 头像 + Rank

### ⚔️ 经典战役 (`classic_battles.html`)

基于每周阵容 Rank 分析的 **以下克上 Top 5**：

每场战役包含：
1. **对阵卡片** — 双方球队头像 + 阵容均Rank + 比分
2. **Category 标签条** — 11项胜负标记（绿=胜方赢/红=负方赢/灰=平）
3. **11项数据对比表** — 双方每项实际数值，胜方绿底/负方红底高亮
4. **翻盘分析** — 阵容对比、关键球员、比分拆解、总结
5. **双方完整阵容** — 球员头像 + 位置 + 球队 + Rank + 11项 NBA.com 官方场均
6. **当周操作时间线** — 签入(+绿)/裁掉(-红) + Rank + 11项场均

**过滤规则**：排除 5-8 名排位赛，保留总决赛/季军赛/精选常规赛
**赛事重要度标识**：总决赛金边 + 季军赛浅金 + 常规赛普通

### 🏠 汇总首页 (`index.html`)

迷你领奖台 + 3 张报告卡片（点击跳转）+ 16队列表
所有页面顶部统一导航栏，可自由跳转。

## 设计风格

**日式极简**：
- 白底 `#faf9f6`、Noto Serif JP 衬线标题
- 金色 `#c8a45c` 点缀、极简卡片无阴影
- 大量留白、左侧竖线装饰引述
- 序号用淡灰大字体

## 关键技术细节

### 11-Cat 统计
| Stat ID | 名称 | 说明 |
|:---:|------|------|
| 5 | FG% | 投篮命中率 |
| 8 | FT% | 罚球命中率 |
| 10 | 3PM | 三分命中数 |
| 12 | PTS | 得分 |
| 13 | AST | 助攻 |
| 15 | REB | 篮板 |
| 16 | STL | 抢断 |
| 17 | BLK | 盖帽 |
| 18 | TO | 失误（低者胜） |
| 19 | OREB | 前场篮板 |
| 20 | A/TO | 助攻失误比 |

### Yahoo API 注意事项
- Token 1小时过期，需重新 OAuth 授权
- `stat_winners` 字段直接给出每个 category 的赢家（team_key 格式）
- Scoreboard 每场的 `team1_stats`/`team2_stats` 含 11 项当周实际数据
- 历史赛季的 `game_key` 需要通过 `game.game_keys()` 查询
- `managers` 字段中 `image_url` 为经理头像，`team_logos` 为球队头像

### NBA.com API 注意事项
- 使用 `nba_api` 库的 `commonallplayers` 匹配 Yahoo 球员名到 NBA person_id
- 球员头像：`https://cdn.nba.com/headshots/nba/latest/260x190/{person_id}.png`
- 场均数据：`leaguedashplayerstats` 的 `PerGame` 模式

### 经理名覆盖
```python
MANAGER_OVERRIDES = {'King Crimson Cecil': 'Cecil'}
```
Yahoo 隐私设置会遮住经理名，需手动 override。

## 自定义扩展

### 增加奖项
在 `08_gen_review.py` 中按模式添加：
```python
def award_new_category():
    # 计算逻辑
    return {
        'id': 'new_cat',
        'emoji': '🌟',
        'name': '新奖项名',
        'en': 'New Award',
        'winner': ...,
        'all': [...],
    }
awards.append(award_new_category())
```

### 调整经典战役数量
在 `09_gen_classic_battles.py` 中修改 `MAX_BATTLES = 5`。

### 重磅交易维度
5 维分析（Rank/选秀轮次/多面手/稀缺角色/交易规模），阈值可在 `07_gen_overview.py` 的 `blockbuster_reason()` 函数中调整。

## 依赖

```
yahoo_oauth
yahoo_fantasy_api
nba_api
```

安装：
```bash
pip install yahoo_oauth yahoo_fantasy_api nba_api
```

## 备注

- 赛季开始日期 `SEASON_START` 在 `09_gen_classic_battles.py` 中配置（当前为 2025-10-27）
- 所有报告均为纯静态 HTML，无需后端服务器
- `yahoo_full_data.json` 是全部数据的中间存储，各生成脚本从中读取
