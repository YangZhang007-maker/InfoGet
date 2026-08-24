import { useState } from "react";
import { resolveUrl } from "../services/data";

const API_BACKEND = "http://localhost:5001";

const PRESET_INTERESTS = [
  "科技", "AI", "金融", "财经", "游戏", "汽车",
  "新能源", "医疗", "健康", "教育", "房产", "娱乐",
  "体育", "数码", "时尚", "美食", "旅游", "国际",
];

interface SourceResult {
  source_url: string;
  source_name: string;
  matched_platform: string | null;
  is_known: boolean;
  items: HotItemResp[];
  error: string | null;
}

interface HotItemResp {
  title: string;
  hot: string;
  url: string;
  desc: string;
  rank: number;
  source_name: string;
  summary: string;
  relevance: number;
  match_type: string;
}

interface SearchResponse {
  results: SourceResult[];
  total_sources: number;
  total_items: number;
}

function formatHot(hot: string): string {
  const num = parseInt(hot, 10);
  if (isNaN(num) || num === 0) return hot;
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}亿`;
  if (num >= 10000) return `${(num / 10000).toFixed(0)}万`;
  return hot;
}

export default function CustomSearch() {
  const [urlInput, setUrlInput] = useState("");
  const [customInterest, setCustomInterest] = useState("");
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [results, setResults] = useState<SourceResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const toggleInterest = (tag: string) => {
    setSelectedInterests((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const addCustomInterest = () => {
    const val = customInterest.trim();
    if (val && !selectedInterests.includes(val)) {
      setSelectedInterests([...selectedInterests, val]);
      setCustomInterest("");
    }
  };

  const handleSearch = async () => {
    const urls = urlInput
      .split(/[\n,，]+/)
      .map((u) => resolveUrl(u.trim()))
      .filter(Boolean);

    if (!urls.length) {
      setError("请输入至少一个信息源网站 URL");
      return;
    }
    if (!selectedInterests.length) {
      setError("请选择或输入至少一个兴趣方向");
      return;
    }

    setLoading(true);
    setSearched(true);
    setError("");
    setResults([]);

    try {
      const resp = await fetch(`${API_BACKEND}/api/custom-search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls, interests: selectedInterests }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }

      const data: SearchResponse = await resp.json();
      setResults(data.results);
    } catch (e: any) {
      setError(e.message || "请求失败，请确保后端服务已启动 (port 5001)");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="custom-search">
      <h2>🎯 自定义信息源</h2>
      <p className="custom-desc">
        输入你关注的网站 URL，选择感兴趣的方向，自动筛选/提取热点信息
      </p>

      {/* URL 输入区 */}
      <div className="cs-input-section">
        <label className="cs-label">信息源网站 URL</label>
        <textarea
          className="cs-url-input"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          placeholder={
            "输入网站 URL 或中文名（换行或逗号分隔）\n例如：\n微博\n知乎\nB站\nhttps://news.163.com\n网易新闻"
          }
          rows={4}
        />
      </div>

      {/* 兴趣方向选择区 */}
      <div className="cs-input-section">
        <label className="cs-label">感兴趣的方向（可多选）</label>
        <div className="cs-interest-tags">
          {PRESET_INTERESTS.map((tag) => (
            <button
              key={tag}
              className={`cs-tag ${selectedInterests.includes(tag) ? "active" : ""}`}
              onClick={() => toggleInterest(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
        <div className="cs-custom-interest">
          <input
            type="text"
            value={customInterest}
            onChange={(e) => setCustomInterest(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCustomInterest()}
            placeholder="自定义方向，回车添加..."
          />
          <button onClick={addCustomInterest}>+ 添加</button>
        </div>
        {selectedInterests.length > 0 && (
          <div className="cs-selected-interests">
            已选：
            {selectedInterests.map((t) => (
              <span key={t} className="cs-selected-tag">
                {t}
                <button onClick={() => toggleInterest(t)}>×</button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 搜索按钮 */}
      <button
        className="cs-search-btn"
        onClick={handleSearch}
        disabled={loading}
      >
        {loading ? "⏳ 搜索中..." : "🔍 开始搜索"}
      </button>

      {error && <div className="cs-error">⚠️ {error}</div>}

      {/* 搜索结果 */}
      {searched && !loading && !error && results.length === 0 && (
        <div className="cs-no-results">未找到相关热点信息</div>
      )}

      {results.map((source, idx) => {
        const allFallback = source.items.length > 0 && source.items.every(
          (i) => i.match_type === "llm_fallback" || i.match_type === "llm_extracted" || i.match_type === "section_search_api" || i.match_type === "section_search_web"
        );
        const isSectionSearch = source.items.length > 0 && source.items.some(
          (i) => i.match_type === "section_search_api" || i.match_type === "section_search_web"
        );

        return (
        <div key={idx} className="cs-source-result">
          <div className="cs-source-header">
            <span className="cs-source-name">
              {source.is_known ? "✅" : "🤖"} {source.source_name}
            </span>
            <span className="cs-source-badge">
              {source.is_known && !allFallback
                ? `已知平台 · ${source.matched_platform}`
                : source.is_known && isSectionSearch
                ? `板块搜索 · ${source.matched_platform}`
                : source.is_known && allFallback
                ? `已知平台 · LLM补充 · ${source.matched_platform}`
                : "LLM 智能提取"}
            </span>
            {source.error && (
              <span className="cs-source-error">{source.error}</span>
            )}
          </div>

          {source.items.length > 0 && (
            <div className="cs-items">
              {source.items.map((item, i) => (
                <a
                  key={i}
                  href={item.url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="cs-item"
                >
                  <span className="cs-item-rank">{i + 1}</span>
                  <div className="cs-item-content">
                    <span className="cs-item-title">{item.title}</span>
                    <div className="cs-item-meta">
                      {item.hot && (
                        <span className="cs-item-hot">🔥 {formatHot(item.hot)}</span>
                      )}
                      {item.relevance > 0 && (
                        <span className="cs-item-relevance">
                          📊 相关度 {item.relevance}/10
                        </span>
                      )}
                      {item.match_type === "known_api" && (
                        <span className="cs-item-type">📡 API查询</span>
                      )}
                      {item.match_type === "llm_extracted" && (
                        <span className="cs-item-type">🤖 LLM提取</span>
                      )}
                      {item.match_type === "llm_fallback" && (
                        <span className="cs-item-type">🔄 LLM补充</span>
                      )}
                      {item.match_type === "section_search_api" && (
                        <span className="cs-item-type">🔎 板块搜索(API)</span>
                      )}
                      {item.match_type === "section_search_web" && (
                        <span className="cs-item-type">🔎 板块搜索</span>
                      )}
                    </div>
                    {item.summary && (
                      <p className="cs-item-summary">{item.summary}</p>
                    )}
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      );})}
    </div>
  );
}
