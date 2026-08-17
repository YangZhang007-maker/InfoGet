/** 单条热搜 */
export interface HotItem {
  id: number | string;
  title: string;
  cover?: string;
  author?: string;
  desc?: string;
  hot: number | undefined;
  timestamp: number | undefined;
  url: string;
  mobileUrl: string;
}

/** 单个热榜 API 响应 */
export interface HotListResponse {
  code: number;
  name: string;
  title: string;
  type: string;
  description?: string;
  params?: Record<string, string | object>;
  total: number;
  link?: string;
  updateTime: string;
  fromCache: boolean;
  data: HotItem[];
}

/** 路由信息（来自 /all） */
export interface RouteInfo {
  name: string;
  path: string;
  message?: string;
}

/** 所有路由响应 */
export interface AllRoutesResponse {
  code: number;
  count: number;
  routes: RouteInfo[];
}

/** 平台分类 */
export interface PlatformCategory {
  key: string;
  label: string;
  icon: string;
  platforms: { id: string; name: string; description: string }[];
}

/** 标签定义 */
export interface TagDef {
  name: string;
  platforms: string[];
}

/** 行业定义 */
export interface IndustryDef {
  name: string;
  platforms: string[];
  description: string;
}