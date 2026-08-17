import { useState, useCallback } from "react";
import type { HotItem } from "../types";
import { getTopN, formatHot } from "../services/api";
import { PLATFORM_CATEGORIES, PLATFORM_NAME_MAP, getAllPlatformIds } from "../services/data";

type Top10Mode = "all" | "social" | "tech" | "news";

const MODE_OPTIONS: { key: Top10Mode; label: string; icon: string }[] = [
  { key: "all", label: "全网", icon: "🌐" },
  { key: "social", label: "社交媒体", icon: "💬" },
  { key: "tech", label: "科技", icon: "💻" },
  { key: "news", label: "新闻", icon: "📰" },
];

function getPlatformIdsForMode(mode: Top10Mode): string[] {
  if (mode === "all") return getAllPlatformIds();
  const cat = PLATFORM_CATEGORIES.find(
    (c) =>
      (mode === "social" && c.key === "social") ||
      (mode === "tech" && (c.key === "tech" || c.key === "game")) ||
      (mode === "news" && c.key === "news")
  );
  if (!cat) return getAllPlatformIds();
  return cat.platforms.map((p) => p.id);
}

export default function Top10() {
  const [mode, setMode] = useState<Top10Mode>("all");
  const [items, setItems] = useState<
    { item: HotItem; platformId: string; platformName: string }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const loadTopN = useCallback(async (m: Top10Mode) => {
    setMode(m);
    setLoading(true);
    setLoaded(true);
    const ids = getPlatformIdsForMode(m);
    const res = await getTopN(ids, 20);
    setItems(res);
    setLoading(false);
  }, []);

  return (
    <div className="top10-section">
      <div className="top10-header">
        <h3>🏆 跨平台热点</h3>
        <div className="top10-tabs">
          {MODE_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              className={`top10-tab ${mode === opt.key ? "active" : ""}`}
              onClick={() => loadTopN(opt.key)}
            >
              {opt.icon} {opt.label}
            </button>
          ))}
        </div>
      </div>

      {!loaded && (
        <div className="top10-placeholder" onClick={() => loadTopN("all")}>
          <span>点击查看跨平台热点 TOP 20</span>
        </div>
      )}

      {loading && (
        <div className="top10-loading">
          <div className="spinner mini" />
          <span>聚合中...</span>
        </div>
      )}

      {loaded && !loading && (
        <div className="top10-list">
          {items.slice(0, 20).map((entry, idx) => (
            <a
              key={`${entry.platformId}-${entry.item.id}`}
              href={entry.item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="top10-item"
            >
              <span className={`top10-rank rank-${idx < 3 ? "top" : "normal"}`}>
                {idx + 1}
              </span>
              <div className="top10-content">
                <span className="top10-title">{entry.item.title}</span>
                <div className="top10-meta">
                  <span className="top10-platform">
                    📱 {PLATFORM_NAME_MAP[entry.platformId] || entry.platformName}
                  </span>
                  {entry.item.hot !== undefined && entry.item.hot > 0 && (
                    <span className="top10-hot">🔥 {formatHot(entry.item.hot)}</span>
                  )}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
