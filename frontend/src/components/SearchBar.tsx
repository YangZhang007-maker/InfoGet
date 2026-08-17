import { useState } from "react";
import type { HotItem } from "../types";
import { searchAllPlatforms, formatHot } from "../services/api";
import { getAllPlatformIds, PLATFORM_NAME_MAP } from "../services/data";

export default function SearchBar() {
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<
    { item: HotItem; platformId: string; platformName: string }[]
  >([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!keyword.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const allIds = getAllPlatformIds();
      const res = await searchAllPlatforms(keyword.trim(), allIds, 30);
      setResults(res);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="search-section">
      <div className="search-bar">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="🔍 跨平台搜索关键词（如：AI、特斯拉、地震）..."
        />
        <button onClick={handleSearch} disabled={searching || !keyword.trim()}>
          {searching ? "搜索中..." : "搜索"}
        </button>
      </div>

      {searched && (
        <div className="search-results">
          <div className="search-results-header">
            {searching ? (
              <span>⏳ 正在搜索全平台...</span>
            ) : (
              <span>
                🔍 "{keyword}" — 找到 {results.length} 条结果
              </span>
            )}
          </div>
          {!searching && results.length === 0 && (
            <p className="no-results">未找到相关热榜内容</p>
          )}
          {!searching &&
            results.slice(0, 15).map((r, idx) => (
              <a
                key={`${r.platformId}-${r.item.id}`}
                href={r.item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="search-item"
              >
                <span className="search-rank">{idx + 1}</span>
                <div className="search-item-content">
                  <span className="search-item-title">{r.item.title}</span>
                  <div className="search-item-meta">
                    <span className="search-platform">
                      📱 {PLATFORM_NAME_MAP[r.platformId] || r.platformName}
                    </span>
                    {r.item.hot !== undefined && r.item.hot > 0 && (
                      <span className="search-hot">🔥 {formatHot(r.item.hot)}</span>
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