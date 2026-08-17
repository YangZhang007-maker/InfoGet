import type { PlatformCategory, TagDef, IndustryDef } from "../types";

export const API_BASE = "http://localhost:6688";

/** 54 个平台按 7 大分类组织 */
export const PLATFORM_CATEGORIES: PlatformCategory[] = [
  {
    key: "video",
    label: "视频/直播",
    icon: "🎬",
    platforms: [
      { id: "bilibili", name: "哔哩哔哩", description: "热门榜" },
      { id: "acfun", name: "AcFun", description: "排行榜" },
      { id: "douyin", name: "抖音", description: "热点榜" },
      { id: "kuaishou", name: "快手", description: "热点榜" },
      { id: "coolapk", name: "酷安", description: "热榜" },
    ],
  },
  {
    key: "social",
    label: "社交媒体",
    icon: "💬",
    platforms: [
      { id: "weibo", name: "微博", description: "热搜榜" },
      { id: "zhihu", name: "知乎", description: "热榜" },
      { id: "zhihu-daily", name: "知乎日报", description: "推荐榜" },
      { id: "tieba", name: "百度贴吧", description: "热议榜" },
      { id: "douban-group", name: "豆瓣讨论小组", description: "讨论精选" },
      { id: "v2ex", name: "V2EX", description: "主题榜" },
      { id: "ngabbs", name: "NGA", description: "热帖" },
      { id: "hupu", name: "虎扑", description: "步行街热帖" },
    ],
  },
  {
    key: "news",
    label: "新闻资讯",
    icon: "📰",
    platforms: [
      { id: "baidu", name: "百度", description: "热搜榜" },
      { id: "thepaper", name: "澎湃新闻", description: "热榜" },
      { id: "toutiao", name: "今日头条", description: "热榜" },
      { id: "36kr", name: "36氪", description: "热榜" },
      { id: "qq-news", name: "腾讯新闻", description: "热点榜" },
      { id: "sina", name: "新浪网", description: "热榜" },
      { id: "sina-news", name: "新浪新闻", description: "热点榜" },
      { id: "netease-news", name: "网易新闻", description: "热点榜" },
      { id: "huxiu", name: "虎嗅", description: "24小时" },
      { id: "ifanr", name: "爱范儿", description: "快讯" },
    ],
  },
  {
    key: "tech",
    label: "科技/技术",
    icon: "💻",
    platforms: [
      { id: "ithome", name: "IT之家", description: "热榜" },
      { id: "ithome-xijiayi", name: "IT之家「喜加一」", description: "最新动态" },
      { id: "sspai", name: "少数派", description: "热榜" },
      { id: "csdn", name: "CSDN", description: "排行榜" },
      { id: "juejin", name: "稀土掘金", description: "热榜" },
      { id: "51cto", name: "51CTO", description: "推荐榜" },
      { id: "nodeseek", name: "NodeSeek", description: "最新动态" },
      { id: "hellogithub", name: "HelloGitHub", description: "Trending" },
    ],
  },
  {
    key: "game",
    label: "游戏/ACG",
    icon: "🎮",
    platforms: [
      { id: "genshin", name: "原神", description: "最新消息" },
      { id: "miyoushe", name: "米游社", description: "最新消息" },
      { id: "honkai", name: "崩坏3", description: "最新动态" },
      { id: "starrail", name: "崩坏：星穹铁道", description: "最新动态" },
      { id: "lol", name: "英雄联盟", description: "更新公告" },
    ],
  },
  {
    key: "reading",
    label: "阅读/文化",
    icon: "📚",
    platforms: [
      { id: "jianshu", name: "简书", description: "热门推荐" },
      { id: "guokr", name: "果壳", description: "热门文章" },
      { id: "weread", name: "微信读书", description: "飙升榜" },
      { id: "douban-movie", name: "豆瓣电影", description: "新片榜" },
    ],
  },
  {
    key: "tool",
    label: "工具/其他",
    icon: "🔧",
    platforms: [
      { id: "52pojie", name: "吾爱破解", description: "榜单" },
      { id: "hostloc", name: "全球主机交流", description: "榜单" },
      { id: "weatheralarm", name: "中央气象台", description: "全国气象预警" },
      { id: "earthquake", name: "中国地震台", description: "地震速报" },
      { id: "history", name: "历史上的今天", description: "月-日" },
    ],
  },
];

/** 15 种标签 → 平台映射 */
export const TAGS: TagDef[] = [
  {
    name: "科技",
    platforms: ["ithome", "36kr", "sspai", "csdn", "juejin", "51cto"],
  },
  {
    name: "互联网",
    platforms: ["sina-news", "netease-news", "qq-news"],
  },
  {
    name: "游戏",
    platforms: ["genshin", "miyoushe", "lol", "bilibili", "hupu"],
  },
  {
    name: "娱乐",
    platforms: ["weibo", "douban-group", "douban-movie"],
  },
  {
    name: "社会",
    platforms: ["sina-news", "netease-news", "qq-news"],
  },
  {
    name: "财经",
    platforms: ["36kr", "huxiu"],
  },
  {
    name: "汽车",
    platforms: [],
  },
  {
    name: "体育",
    platforms: ["hupu"],
  },
  {
    name: "教育",
    platforms: ["zhihu", "bilibili"],
  },
  {
    name: "健康",
    platforms: ["zhihu"],
  },
  {
    name: "国际",
    platforms: ["sina-news", "netease-news", "qq-news"],
  },
  {
    name: "房产",
    platforms: [],
  },
  {
    name: "数码",
    platforms: ["ithome", "coolapk", "sspai"],
  },
  {
    name: "时尚",
    platforms: [],
  },
  {
    name: "美食",
    platforms: [],
  },
];

/** 10 大行业 → 平台映射 */
export const INDUSTRIES: IndustryDef[] = [
  {
    name: "科技互联网",
    platforms: ["ithome", "36kr", "csdn", "juejin"],
    description: "IT之家、36氪、CSDN、稀土掘金",
  },
  {
    name: "游戏行业",
    platforms: ["genshin", "miyoushe", "lol", "bilibili"],
    description: "原神、米游社、英雄联盟、B站",
  },
  {
    name: "汽车行业",
    platforms: [],
    description: "汽车之家、懂车帝、易车网",
  },
  {
    name: "金融财经",
    platforms: ["36kr"],
    description: "36氪、虎嗅等",
  },
  {
    name: "数码消费",
    platforms: ["coolapk", "ithome", "sspai"],
    description: "酷安、IT之家、少数派",
  },
  {
    name: "娱乐影视",
    platforms: ["weibo", "douban-group", "douban-movie", "bilibili"],
    description: "微博、豆瓣、豆瓣电影、B站",
  },
  {
    name: "房产家居",
    platforms: [],
    description: "房产相关",
  },
  {
    name: "医疗健康",
    platforms: ["zhihu"],
    description: "知乎健康话题",
  },
  {
    name: "旅游出行",
    platforms: [],
    description: "旅游相关",
  },
  {
    name: "餐饮消费",
    platforms: [],
    description: "餐饮相关",
  },
];

/** 获取所有平台 ID 列表 */
export function getAllPlatformIds(): string[] {
  const ids: string[] = [];
  for (const cat of PLATFORM_CATEGORIES) {
    for (const p of cat.platforms) {
      ids.push(p.id);
    }
  }
  return ids;
}

/** 平台 ID → 平台名称映射 */
export const PLATFORM_NAME_MAP: Record<string, string> = {};
for (const cat of PLATFORM_CATEGORIES) {
  for (const p of cat.platforms) {
    PLATFORM_NAME_MAP[p.id] = p.name;
  }
}

/** 中文名称/别名 → URL 映射（支持用户输入中文名代替 URL） */
export const NAME_TO_URL: Record<string, string> = {
  // 视频/直播
  "b站": "https://www.bilibili.com",
  "bilibili": "https://www.bilibili.com",
  "哔哩哔哩": "https://www.bilibili.com",
  "acfun": "https://www.acfun.cn",
  "a站": "https://www.acfun.cn",
  "抖音": "https://www.douyin.com",
  "快手": "https://www.kuaishou.com",
  "酷安": "https://www.coolapk.com",
  // 社交媒体
  "微博": "https://weibo.com",
  "知乎": "https://www.zhihu.com",
  "知乎日报": "https://www.zhihu.com",
  "贴吧": "https://tieba.baidu.com",
  "百度贴吧": "https://tieba.baidu.com",
  "豆瓣": "https://www.douban.com",
  "豆瓣电影": "https://movie.douban.com",
  "v2ex": "https://www.v2ex.com",
  "nga": "https://ngabbs.com",
  "虎扑": "https://www.hupu.com",
  // 新闻资讯
  "百度": "https://www.baidu.com",
  "澎湃新闻": "https://www.thepaper.cn",
  "澎湃": "https://www.thepaper.cn",
  "今日头条": "https://www.toutiao.com",
  "头条": "https://www.toutiao.com",
  "36氪": "https://36kr.com",
  "腾讯新闻": "https://news.qq.com",
  "新浪": "https://www.sina.com.cn",
  "新浪新闻": "https://news.sina.com.cn",
  "网易新闻": "https://news.163.com",
  "网易": "https://news.163.com",
  "虎嗅": "https://www.huxiu.com",
  "爱范儿": "https://www.ifanr.com",
  // 科技/技术
  "it之家": "https://www.ithome.com",
  "ithome": "https://www.ithome.com",
  "少数派": "https://sspai.com",
  "csdn": "https://www.csdn.net",
  "掘金": "https://juejin.cn",
  "稀土掘金": "https://juejin.cn",
  "51cto": "https://www.51cto.com",
  "nodeseek": "https://www.nodeseek.com",
  "hellogithub": "https://hellogithub.com",
  // 游戏
  "原神": "https://www.bilibili.com",
  "米游社": "https://www.miyoushe.com",
  "英雄联盟": "https://lol.qq.com",
  "lol": "https://lol.qq.com",
  // 阅读/文化
  "简书": "https://www.jianshu.com",
  "果壳": "https://www.guokr.com",
  "微信读书": "https://weread.qq.com",
  // 工具/其他
  "吾爱破解": "https://www.52pojie.cn",
  "hostloc": "https://hostloc.com",
  "中央气象台": "https://weatheralarm.com",
  "中国地震台": "https://earthquake.com",
};

/** 解析用户输入：中文名 → URL */
export function resolveUrl(input: string): string {
  const trimmed = input.trim();
  // 已经是 URL
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }
  // 查中文名映射
  const lower = trimmed.toLowerCase();
  if (NAME_TO_URL[lower]) {
    return NAME_TO_URL[lower];
  }
  // 包含 . 的可能是域名，加 https:// 前缀
  if (trimmed.includes(".")) {
    return trimmed.startsWith("http") ? trimmed : "https://" + trimmed;
  }
  // 无法识别，原样返回（后端还会再尝试匹配）
  return trimmed;
}