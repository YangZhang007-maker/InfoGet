# B站自定义兴趣热点搜索 — 技术设计文档

## 概述

用户输入任意兴趣方向（如"AI"、"金融"、"人工智能教程"、"claude code使用方式"），系统通过多层降级搜索策略，从 B站（bilibili.com）获取该方向的热点/热门内容，返回带有效链接的结构化结果。

---

## 整体架构

```
用户输入: URL + 兴趣方向
    │
    ▼
┌─────────────┐     POST /api/custom-search     ┌──────────────────┐
│  React 前端  │ ──────────────────────────────→ │  FastAPI 后端     │
│  :5173       │                                 │  :5001            │
│  CustomSearch│ ←────────────────────────────── │  server.py        │
│  .tsx        │     JSON 响应                    │  custom_source.py │
└─────────────┘                                  └──────────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────────┐
                                                  │  DailyHotApi      │
                                                  │  :6688 (Node.js)  │
                                                  │  54平台热榜API     │
                                                  └──────────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────────┐
                                                  │  B站官方 API      │
                                                  │  api.bilibili.com │
                                                  └──────────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────────┐
                                                  │  Codex API        │
                                                  │  (LLM 语义分析)    │
                                                  └──────────────────┘
```

---

## 搜索流程：5 层降级策略

### Layer 0：域名识别

- **技术**：`urllib.parse.urlparse` 提取域名 → 与 `PLATFORM_DOMAIN_MAP` 匹配
- **PLATFORM_DOMAIN_MAP** 维护 54 个平台的域名映射
- B站：`bilibili.com`, `b23.tv` → 匹配为已知平台 `bilibili`

---

### Layer 1：热榜 API 关键词匹配

**函数**：`search_known_platform()`

**技术方法**：
- 调用 DailyHotApi `/bilibili` 端点获取当前热榜 TOP 20
- 用 `INTEREST_RELATED_KEYWORDS` 扩展词表做**标题只匹配**（避免描述中的免责声明误命中）
- 扩展词表示例：`"AI"` → `["人工智能", "大模型", "deepseek", "chatgpt", ...]`

**耗时**：< 1 秒

**适用场景**：热门兴趣方向（如"游戏"→热榜含原神/绝区零标题时直接命中）

**关键技术决策**：
- 只用标题匹配，不用描述（避免"请勿相信由人工智能生成"等免责声明误命中）
- 2字母关键词如 `"ai"` 从扩展词表移除（会误匹配 `laidback` 等单词）

---

### Layer 2：热榜数据 + LLM 语义分析

**函数**：`search_known_platform_with_llm()`

**技术方法**：
- Layer 1 无结果时触发
- 将热榜 TOP 50 的标题 + 描述发送给 Codex Responses API
- Prompt：`"从以下热榜中筛选出与「{兴趣}」真正相关的内容"`
- LLM 返回结构化 JSON：`[{index, title, reason}]`
- 回填完整条目信息（链接、热度值等）
- 对 LLM 结果再用 `filter_items_by_interest()` 做标题过滤（防止"用AI工具制作"被判为"AI主题"）

**耗时**：3-5 秒

**API 配置**：
- 模型：`gpt-5.6-terra`
- Endpoint：`/v1/responses`
- Max output tokens：2000

---

### Layer 3：平台板块搜索（4 级降级）

**函数**：`search_platform_section()`

#### 3-1 分区/频道 API（`search_platform_zone_api`）★ 最可靠

**技术方法**：
- `INTEREST_RELATED_KEYWORDS` 中 39 个关键词 → 16 个 B站分区 ID（rid）映射
- 使用 `requests.Session()` 先访问 B站首页获取 Cookie，再调用分区 API
- API：`api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all`
- 模糊匹配：按关键词长度降序，优先匹配长关键词

**分区映射表**：

| 分区 | rid | 覆盖关键词 |
|------|-----|-----------|
| 科技/数码 | 188 | AI、编程、芯片、手机、大模型、机器学习… |
| 汽车 | 223 | 汽车、新能源、电动车、无人驾驶 |
| 游戏 | 4 | 游戏、手游、电竞、主机游戏 |
| 娱乐 | 5 | 娱乐、明星、八卦、综艺 |
| 影视 | 181 | 电影、大片、影评 |
| 动画 | 1 | 动漫、二次元、番剧 |
| 知识 | 36 | 教育、学习、考研、读书 |
| 医疗 | 177 | 医疗、健康、医药、养生 |
| 美食 | 211 | 美食、探店、小吃、做饭 |
| 体育 | 234 | 体育、足球、篮球、健身 |
| 时尚 | 155 | 时尚、穿搭、美妆、护肤 |
| 生活 | 160 | 生活、日常、vlog |
| 音乐 | 3 | 音乐、歌曲、翻唱 |
| 动物 | 217 | 宠物、猫、狗、萌宠 |
| 舞蹈 | 129 | 舞蹈、街舞 |
| 鬼畜 | 119 | 鬼畜、搞笑 |

**耗时**：< 1 秒

#### 3-2 B站搜索 API（`search_bilibili_search_api`）

**技术方法**：
- 分区未命中时触发
- API：`api.bilibili.com/x/web-interface/search/type?keyword={keyword}&search_type=video&order=click`
- 需要 Session Cookie 和 URL 编码的中文关键词
- 解析返回的 `<em>` 标签，提取标题、播放量、BV号

**耗时**：< 1 秒

#### 3-3 热门榜 + LLM 匹配（`search_bilibili_popular_fallback`）

**技术方法**：
- 搜索 API 也失败时触发
- API：`api.bilibili.com/x/web-interface/popular?ps=50`
- 获取全站热门 TOP 50 → 发送给 Codex：`"请找出与「{兴趣}」最相关的视频"`
- LLM 返回相关条目索引 → 回填完整信息

**耗时**：3-5 秒

#### 3-4 网页抓取（`search_platform_section_web`）

**技术方法**：
- 构造搜索页 URL（如 `search.bilibili.com/all?keyword={兴趣}`）
- `requests.get()` + BeautifulSoup 提取文本
- Codex 从文本中提取结构化结果
- **自动过滤无链接条目**（SPA 页面常见问题）

**耗时**：5-10 秒

---

### 相关性过滤层

**函数**：`filter_items_by_interest()`

在所有 Layer 3 子层的结果返回前应用：

1. **优先**：标题关键词匹配（`INTEREST_RELATED_KEYWORDS` 扩展词表）
2. **降级**：标题为 0 → 放宽到标题 + 描述（截断免责声明/赞助信息后）
3. **免责标记截断**：找到描述中最靠前的 `⛔`、`请勿`、`免责`、`赞助`、`鸣谢`、`bgm` 等标记，截断之后的内容
4. 过滤后 ≥ 1 条 → 返回；过滤后 = 0 → 继续降级

**关键技术决策**：
- 免责声明截断解决了"发烧梗"因描述含"请勿相信人工智能生成"而被误判为 AI 内容的问题
- 赞助信息截断解决了"后室里的乌鲁鲁"因赞助商"追核电竞"而被误判为游戏内容的问题

---

### Layer 4：最终保底层（智能拆词 + 多路搜索 + LLM 精选）

**触发条件**：前 4 层结果 < 3 条

**函数**：`search_bilibili_final_fallback()`

**技术方法**：

#### 4-1 智能拆词（`split_interest_keywords()`）

```
"人工智能教程" → ["人工智能", "教程", "人工智", "工智能"]
"claude code使用方式" → ["claude", "code"]
"Python机器学习入门" → ["python", "机器学习"]
```

**拆分策略**：
1. 优先匹配已知关键词（长词优先）
2. 英文按空格/标点拆分
3. 中文滑动窗口取 2-3 字片段
4. 过滤停用词（的/了/是/在…）
5. 去重，最多 4 个关键词

#### 4-2 多路搜索

每个拆分关键词 → B站搜索 API（**不做相关性过滤**）→ 合并去重（按标题）→ 10-20 条候选

#### 4-3 LLM 精选

候选 TOP 20 → Codex：
```
"请选出与「{原始关键词}」最相关的视频，返回 JSON [{index, title, reason}]"
```
→ LLM 精选 6-10 条 → 每条带相关度理由

**耗时**：5-10 秒

---

## 完整流程决策树

```
用户输入: URL="bilibili.com", interest="XXX"
    │
    ├─ 域名匹配 → bilibili（已知平台）
    │
    ├─ Layer 1: 热榜标题关键词匹配
    │   └─ 命中 ≥ 1 条？ → ✅ 返回
    │
    ├─ Layer 2: 热榜 + LLM 语义分析
    │   ├─ LLM 找到相关 → 标题过滤 → 命中？ → ✅ 返回
    │   └─ 标题过滤为 0？ → 继续
    │
    ├─ Layer 3: 板块搜索
    │   ├─ 3-1 分区 API → 相关性过滤 → 命中 ≥ 1？ → ✅ 返回
    │   ├─ 3-2 搜索 API → 相关性过滤 → 命中 ≥ 1？ → ✅ 返回
    │   ├─ 3-3 热门+LLM → 相关性过滤 → 命中 ≥ 1？ → ✅ 返回
    │   └─ 3-4 网页抓取 → 过滤无链接条目 → 命中 ≥ 1？ → ✅ 返回
    │
    └─ Layer 4: 最终保底（结果 < 3 条时触发）
        ├─ 智能拆词 → 多路搜索 → 合并去重
        └─ LLM 精选 → ✅ 返回
```

---

## 使用的技术和 API

| 技术/API | 用途 | 层级 |
|----------|------|------|
| `urllib.parse` | URL 域名提取 | Layer 0 |
| DailyHotApi `:6688/bilibili` | 获取B站热榜 TOP 20 | Layer 1-2 |
| Codex Responses API (`gpt-5.6-terra`) | 语义分析、内容筛选、相关性判断 | Layer 2-4 |
| B站 Ranking API `ranking/v2` | 分区排行（16个分区） | Layer 3-1 |
| B站 Search API `search/type` | 关键词搜索 | Layer 3-2, 4 |
| B站 Popular API `popular` | 全站热门 | Layer 3-3 |
| `requests.Session()` + Cookie | 绕过B站反爬 | Layer 3 |
| `BeautifulSoup4` | HTML 文本提取 | Layer 3-4 |
| `INTEREST_RELATED_KEYWORDS` | 23兴趣 × 扩展关键词 | 所有层 |
| 免责声明截断 | 避免模板文案误判 | 相关性过滤 |
| 滑动窗口拆词 | 中文智能分词 | Layer 4 |

---

## 前端展示

- **组件**：`frontend/src/components/CustomSearch.tsx`
- **Tab 入口**：App.tsx 第 4 个 Tab `🎯 自定义源`
- **交互**：URL 输入 + 兴趣标签选择 + 自定义输入 + 搜索结果分组展示
- **结果标记**：`📡 API查询` / `🔄 LLM补充` / `🔎 板块搜索(API)` / `🔎 板块搜索` / `🎯 智能拆词精选`
