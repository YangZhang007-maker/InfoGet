import { useCallback, useEffect, useRef, useState } from "react";

import HotList from "../../frontend/src/components/HotList";
import { fetchHotList, formatHot, searchAllPlatforms } from "../../frontend/src/services/api";
import {
  getAllPlatformIds,
  PLATFORM_CATEGORIES,
  PLATFORM_NAME_MAP,
} from "../../frontend/src/services/data";
import type { HotItem, HotListResponse } from "../../frontend/src/types";
import "./daily-info.css";

const BACKEND_API = "http://localhost:5001";
const TOP_PANEL_KEY = "daily-info-top20-open";

interface SearchResult {
  item: HotItem;
  platformId: string;
  platformName: string;
}

interface DailyTopItem {
  id: string | number;
  title: string;
  url: string;
  hot: number | null;
  platform_id: string;
  platform_name: string;
}

interface DailyTopResponse {
  date: string;
  generated_at: string;
  cached: boolean;
  source_count: number;
  failed_sources: string[];
  items: DailyTopItem[];
}

export default function DailyInfo() {
  const [selectedPlatform, setSelectedPlatform] = useState("weibo");
  const [hotList, setHotList] = useState<HotListResponse | null>(null);
  const [hotLoading, setHotLoading] = useState(true);
  const [hotError, setHotError] = useState("");
  const platformRequest = useRef(0);

  const [keyword, setKeyword] = useState("");
  const [activeKeyword, setActiveKeyword] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const searchRequest = useRef(0);

  const [topPanelOpen, setTopPanelOpen] = useState(() => {
    return window.localStorage.getItem(TOP_PANEL_KEY) !== "false";
  });
  const [topData, setTopData] = useState<DailyTopResponse | null>(null);
  const [topLoading, setTopLoading] = useState(true);
  const [topError, setTopError] = useState("");
  const topRequest = useRef(0);

  const loadPlatform = useCallback(async (platformId: string) => {
    const requestId = ++platformRequest.current;
    setSelectedPlatform(platformId);
    setActiveKeyword("");
    setSearchError("");
    setHotError("");
    setHotLoading(true);
    try {
      const response = await fetchHotList(platformId);
      if (requestId === platformRequest.current) setHotList(response);
    } catch {
      if (requestId === platformRequest.current) {
        setHotList(null);
        setHotError("该平台热榜暂时无法访问，请稍后重试。");
      }
    } finally {
      if (requestId === platformRequest.current) setHotLoading(false);
    }
  }, []);

  const loadTop20 = useCallback(async (refresh = false) => {
    const requestId = ++topRequest.current;
    setTopLoading(true);
    setTopError("");
    try {
      const response = await fetch(
        `${BACKEND_API}/api/daily-info/top20${refresh ? "?refresh=true" : ""}`,
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(payload?.detail || `HTTP ${response.status}`);
      }
      const payload = await response.json() as DailyTopResponse;
      if (requestId === topRequest.current) setTopData(payload);
    } catch (error) {
      if (requestId === topRequest.current) {
        setTopError(error instanceof Error ? error.message : "Top20 加载失败");
      }
    } finally {
      if (requestId === topRequest.current) setTopLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlatform("weibo");
    void loadTop20();
    const timer = window.setInterval(() => void loadTop20(), 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [loadPlatform, loadTop20]);

  useEffect(() => {
    window.localStorage.setItem(TOP_PANEL_KEY, String(topPanelOpen));
  }, [topPanelOpen]);

  const handleSearch = async () => {
    const cleaned = keyword.trim();
    if (!cleaned) return;
    const requestId = ++searchRequest.current;
    setActiveKeyword(cleaned);
    setSearching(true);
    setSearchError("");
    setSearchResults([]);
    try {
      const results = await searchAllPlatforms(cleaned, getAllPlatformIds(), 30);
      if (requestId === searchRequest.current) setSearchResults(results);
    } catch {
      if (requestId === searchRequest.current) {
        setSearchError("跨平台搜索失败，请确认热榜 API 正在运行。");
      }
    } finally {
      if (requestId === searchRequest.current) setSearching(false);
    }
  };

  const clearSearch = () => {
    searchRequest.current += 1;
    setKeyword("");
    setActiveKeyword("");
    setSearchResults([]);
    setSearchError("");
    setSearching(false);
  };

  return (
    <div className={`daily-info-shell ${topPanelOpen ? "" : "top-collapsed"}`}>
      <aside className="daily-info-sidebar">
        <form
          className="daily-info-search"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSearch();
          }}
        >
          <label htmlFor="daily-info-keyword">舆情搜索</label>
          <div>
            <input
              id="daily-info-keyword"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="输入热点关键词"
              maxLength={100}
            />
            {keyword && (
              <button type="button" className="daily-info-clear" onClick={clearSearch} title="清空搜索">
                ×
              </button>
            )}
          </div>
          <button type="submit" disabled={searching || !keyword.trim()}>
            {searching ? "检索中..." : "搜索全平台"}
          </button>
        </form>

        <div className="daily-info-platform-heading">
          <h2>热榜平台</h2>
          <span>{getAllPlatformIds().length}</span>
        </div>
        <nav className="daily-info-platforms" aria-label="热榜平台">
          {PLATFORM_CATEGORIES.map((category) => (
            <section key={category.key}>
              <header><span>{category.icon}</span>{category.label}</header>
              {category.platforms.map((platform) => (
                <button
                  key={platform.id}
                  type="button"
                  className={selectedPlatform === platform.id && !activeKeyword ? "active" : ""}
                  onClick={() => void loadPlatform(platform.id)}
                  title={`${platform.name} - ${platform.description}`}
                >
                  <span>{platform.name}</span><small>{platform.description}</small>
                </button>
              ))}
            </section>
          ))}
        </nav>
      </aside>

      <main className="daily-info-content">
        {activeKeyword ? (
          <SearchResults
            keyword={activeKeyword}
            results={searchResults}
            loading={searching}
            error={searchError}
            onBack={clearSearch}
          />
        ) : (
          <>
            {hotError && <div className="daily-info-error">{hotError}</div>}
            <HotList
              platformName={hotList?.title || PLATFORM_NAME_MAP[selectedPlatform] || selectedPlatform}
              updateTime={hotList?.updateTime || new Date().toISOString()}
              items={hotList?.data || []}
              loading={hotLoading}
            />
          </>
        )}
      </main>

      <Top20Drawer
        open={topPanelOpen}
        data={topData}
        loading={topLoading}
        error={topError}
        onToggle={() => setTopPanelOpen((open) => !open)}
        onRefresh={() => void loadTop20(true)}
      />
    </div>
  );
}

function SearchResults({
  keyword,
  results,
  loading,
  error,
  onBack,
}: {
  keyword: string;
  results: SearchResult[];
  loading: boolean;
  error: string;
  onBack: () => void;
}) {
  return (
    <section className="daily-info-results">
      <header>
        <div><span>跨平台舆情</span><h2>“{keyword}”</h2></div>
        <button type="button" onClick={onBack}>返回平台热榜</button>
      </header>
      <div className="daily-info-result-meta">
        {loading ? "正在检索全部平台..." : `按热度整理出 ${results.length} 条结果`}
      </div>
      {error && <div className="daily-info-error">{error}</div>}
      {loading && <div className="daily-info-loading"><div className="spinner" />正在聚合舆情</div>}
      {!loading && !error && results.length === 0 && (
        <div className="daily-info-empty">当前热榜中没有匹配内容，可尝试更短的关键词。</div>
      )}
      {!loading && results.map((result, index) => (
        <a
          className="daily-info-result"
          href={result.item.url}
          target="_blank"
          rel="noopener noreferrer"
          key={`${result.platformId}-${result.item.id}-${index}`}
        >
          <b>{String(index + 1).padStart(2, "0")}</b>
          <div><strong>{result.item.title}</strong><span>{PLATFORM_NAME_MAP[result.platformId] || result.platformName}</span></div>
          {result.item.hot !== undefined && result.item.hot > 0 && <small>{formatHot(result.item.hot)}</small>}
        </a>
      ))}
    </section>
  );
}

function Top20Drawer({
  open,
  data,
  loading,
  error,
  onToggle,
  onRefresh,
}: {
  open: boolean;
  data: DailyTopResponse | null;
  loading: boolean;
  error: string;
  onToggle: () => void;
  onRefresh: () => void;
}) {
  return (
    <aside className={`daily-top-drawer ${open ? "open" : "closed"}`}>
      {!open ? (
        <button type="button" className="daily-top-open" onClick={onToggle} title="展开跨平台 Top20">
          <span>‹</span><b>TOP20</b>
        </button>
      ) : (
        <>
          <header className="daily-top-header">
            <div><span>每日聚合</span><h2>跨平台 TOP20</h2></div>
            <div className="daily-top-actions">
              <button type="button" onClick={onRefresh} disabled={loading} title="重新聚合今日数据">↻</button>
              <button type="button" onClick={onToggle} title="收起 Top20">›</button>
            </div>
          </header>
          {data && (
            <div className="daily-top-meta">
              <span>{data.date}</span><span>{data.source_count} 个来源</span><span>{data.cached ? "今日快照" : "刚刚更新"}</span>
            </div>
          )}
          {loading && !data && <div className="daily-top-status"><div className="spinner mini" />首次聚合可能需要片刻</div>}
          {error && <div className="daily-top-error"><p>{error}</p><button type="button" onClick={onRefresh}>重试</button></div>}
          <div className="daily-top-list">
            {data?.items.map((item, index) => (
              <a href={item.url} target="_blank" rel="noopener noreferrer" key={`${item.platform_id}-${item.id}-${index}`}>
                <b className={index < 3 ? "leading" : ""}>{index + 1}</b>
                <div><strong>{item.title}</strong><span>{item.platform_name}</span></div>
                {item.hot !== null && item.hot > 0 && <small>{formatHot(item.hot)}</small>}
              </a>
            ))}
          </div>
          {loading && data && <div className="daily-top-refreshing">正在刷新今日榜单...</div>}
        </>
      )}
    </aside>
  );
}
