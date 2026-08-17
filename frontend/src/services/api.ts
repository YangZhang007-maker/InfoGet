import type { HotListResponse, HotItem } from "../types";
import { API_BASE } from "./data";

/** 获取单个平台热榜 */
export async function fetchHotList(platformId: string): Promise<HotListResponse> {
  const res = await fetch(`${API_BASE}/${platformId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  if (json.code !== 200) throw new Error("API error");
  return json as HotListResponse;
}

/** 批量获取多个平台的热榜 */
export async function fetchMultiHotLists(
  platformIds: string[],
  onProgress?: (done: number, total: number) => void
): Promise<Map<string, HotListResponse>> {
  const results = new Map<string, HotListResponse>();
  let done = 0;
  const total = platformIds.length;

  // 并发控制：每次最多 6 个请求
  const chunks: string[][] = [];
  for (let i = 0; i < platformIds.length; i += 6) {
    chunks.push(platformIds.slice(i, i + 6));
  }

  for (const chunk of chunks) {
    const promises = chunk.map(async (id) => {
      try {
        const data = await fetchHotList(id);
        results.set(id, data);
      } catch {
        // 跳过失败的平台
      }
      done++;
      onProgress?.(done, total);
    });
    await Promise.all(promises);
  }

  return results;
}

/** 跨平台关键词搜索 */
export async function searchAllPlatforms(
  keyword: string,
  platformIds: string[],
  limit: number = 10
): Promise<{ item: HotItem; platformId: string; platformName: string }[]> {
  const results = await fetchMultiHotLists(platformIds);
  const matched: { item: HotItem; platformId: string; platformName: string }[] = [];

  for (const [platformId, data] of results) {
    if (!data?.data) continue;
    const kw = keyword.toLowerCase();
    for (const item of data.data) {
      if (item.title.toLowerCase().includes(kw)) {
        matched.push({
          item,
          platformId,
          platformName: data.title,
        });
      }
    }
  }

  // 按热度排序
  matched.sort((a, b) => (b.item.hot ?? 0) - (a.item.hot ?? 0));
  return matched.slice(0, limit);
}

/** 跨平台 TOP N 聚合 */
export async function getTopN(
  platformIds: string[],
  n: number = 20
): Promise<{ item: HotItem; platformId: string; platformName: string }[]> {
  const results = await fetchMultiHotLists(platformIds);
  const allItems: { item: HotItem; platformId: string; platformName: string }[] = [];

  for (const [platformId, data] of results) {
    if (!data?.data) continue;
    for (const item of data.data) {
      allItems.push({
        item,
        platformId,
        platformName: data.title,
      });
    }
  }

  // 去重（按标题） + 排序
  const seen = new Set<string>();
  const unique: typeof allItems = [];
  for (const entry of allItems) {
    const key = entry.item.title.toLowerCase().trim();
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(entry);
    }
  }

  unique.sort((a, b) => (b.item.hot ?? 0) - (a.item.hot ?? 0));
  return unique.slice(0, n);
}

/** 格式化热度值 */
export function formatHot(hot: number | undefined): string {
  if (hot === undefined || hot === null) return "";
  if (hot >= 10000_0000) return `${(hot / 10000_0000).toFixed(1)}亿`;
  if (hot >= 10000) return `${(hot / 10000).toFixed(0)}万`;
  return hot.toLocaleString();
}