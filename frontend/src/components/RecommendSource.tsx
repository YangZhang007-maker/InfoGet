import { useState } from "react";

const API_BACKEND = "http://localhost:5001";

interface Blogger {
  name: string;
  fans: number;
  fans_text: string;
  sign: string;
  avatar: string;
  profile_url: string;
  video_count: number;
  sample_video: string;
  sample_url: string;
  reason: string;
}

interface Platform {
  name: string;
  link: string;
  reason: string;
}

interface RecommendResponse {
  query: string;
  keywords: string[];
  bloggers: Blogger[];
  platforms: Platform[];
}

const PRESET_QUESTIONS = [
  "我想学习AI绘画",
  "最近有什么好看的科技新闻",
  "想了解新能源车",
  "如何入门机器学习",
  "关注健康养生",
];

export default function RecommendSource() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRecommend = async (q?: string) => {
    const text = (q ?? query).trim();
    if (!text) {
      setError("请输入你关心的问题或感兴趣的内容");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const resp = await fetch(`${API_BACKEND}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data: RecommendResponse = await resp.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "请求失败，请确保后端服务已启动 (port 5001)");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recommend-section">
      <h2>🤝 推荐博主</h2>
      <p className="recommend-desc">
        输入你关心的问题或感兴趣的内容，为你推荐相关平台和 B站优质博主
      </p>

      {/* 预设问题 */}
      <div className="rec-presets">
        {PRESET_QUESTIONS.map((q) => (
          <button
            key={q}
            className="rec-preset-btn"
            onClick={() => {
              setQuery(q);
              handleRecommend(q);
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* 输入区 */}
      <div className="rec-input-section">
        <textarea
          className="rec-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleRecommend();
            }
          }}
          placeholder="例如：我想学习AI绘画 / 想了解新能源汽车 / 如何入门机器学习..."
          rows={2}
        />
        <button
          className="rec-search-btn"
          onClick={() => handleRecommend()}
          disabled={loading}
        >
          {loading ? "⏳ 推荐中..." : "🔍 开始推荐"}
        </button>
      </div>

      {error && <div className="rec-error">⚠️ {error}</div>}

      {/* 结果 */}
      {result && (
        <div className="rec-results">
          {/* 关键词 */}
          {result.keywords.length > 0 && (
            <div className="rec-keywords">
              <span>🔑 领域关键词：</span>
              {result.keywords.map((kw, i) => (
                <span key={i} className="rec-kw-tag">{kw}</span>
              ))}
            </div>
          )}

          {/* 博主卡片 */}
          {result.bloggers.length > 0 && (
            <div className="rec-section-block">
              <h3>👤 B站推荐博主（真实数据）</h3>
              <div className="rec-blogger-grid">
                {result.bloggers.map((b, i) => (
                  <a
                    key={i}
                    href={b.profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rec-blogger-card"
                  >
                    <img
                      src={b.avatar}
                      alt={b.name}
                      className="rec-avatar"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                    <div className="rec-blogger-info">
                      <span className="rec-blogger-name">{b.name}</span>
                      <span className="rec-blogger-fans">🔥 {b.fans_text}粉</span>
                      <span className="rec-blogger-reason">{b.reason}</span>
                      {b.sign && (
                        <p className="rec-blogger-sign">{b.sign.slice(0, 60)}</p>
                      )}
                      {b.sample_video && (
                        <span className="rec-sample">📺 {b.sample_video.slice(0, 40)}</span>
                      )}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* 平台推荐 */}
          {result.platforms.length > 0 && (
            <div className="rec-section-block">
              <h3>🔗 相关平台推荐</h3>
              <div className="rec-platform-list">
                {result.platforms.map((p, i) => (
                  <a
                    key={i}
                    href={p.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rec-platform-item"
                  >
                    <span className="rec-platform-name">{p.name}</span>
                    <span className="rec-platform-reason">{p.reason}</span>
                    <span className="rec-platform-link">{p.link} ↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
