import { useMemo, useState } from "react";

const API_BACKEND = import.meta.env.VITE_ENHANCER_API || "http://localhost:5001";

type OutputFormat = "json" | "markdown";

interface AcademicArticle {
  title: string;
  url: string;
  authors: string[];
  published_at: string | null;
  abstract: string;
  citations: number | null;
  downloads: number | null;
  rating: number | null;
  hot_label: string;
  hot_score: number;
  source: string;
}

interface AcademicResponse {
  source_url: string;
  source_name: string;
  strategy: string;
  articles: AcademicArticle[];
  generated_code: string;
  generated_file: string;
  selector_config: Record<string, string | boolean>;
  warnings: string[];
  markdown: string;
  formatted_output: AcademicArticle[] | string;
}

const SOURCE_PRESETS = [
  { name: "arXiv", url: "https://arxiv.org/" },
  { name: "PubMed", url: "https://pubmed.ncbi.nlm.nih.gov/" },
  { name: "Google Scholar", url: "https://scholar.google.com/" },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "学术信息采集失败";
}

function formatMetric(value: number | null): string {
  if (value === null) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function strategyLabel(strategy: string): string {
  if (strategy === "official_api") return "官方 API";
  if (strategy === "official_api_alternative") return "OpenAlex API";
  return "自适应网页解析";
}

export default function AcademicInfo() {
  const [sourceUrl, setSourceUrl] = useState("https://arxiv.org/");
  const [keywordInput, setKeywordInput] = useState("transformer, LLM");
  const [timeRangeDays, setTimeRangeDays] = useState(365);
  const [minCitations, setMinCitations] = useState(10);
  const [recentDays, setRecentDays] = useState(30);
  const [maxResults, setMaxResults] = useState(20);
  const [renderJavaScript, setRenderJavaScript] = useState(false);
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("json");
  const [result, setResult] = useState<AcademicResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<"output" | "code" | "">("");

  const keywords = useMemo(
    () => keywordInput.split(/[,，;；\n]+/).map((item) => item.trim()).filter(Boolean),
    [keywordInput]
  );

  const runSearch = async () => {
    if (!sourceUrl.trim()) {
      setError("请输入学术信息来源 URL");
      return;
    }
    if (!keywords.length) {
      setError("请输入至少一个关键词");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_BACKEND}/api/academic/crawl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_url: sourceUrl.trim(),
          keywords,
          time_range_days: timeRangeDays || null,
          min_citations: minCitations || null,
          recent_days: recentDays || null,
          max_results: maxResults,
          render_javascript: renderJavaScript,
          output_format: outputFormat,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }
      setResult((await response.json()) as AcademicResponse);
    } catch (requestError: unknown) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  const copyText = async (value: string, kind: "output" | "code") => {
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    window.setTimeout(() => setCopied(""), 1400);
  };

  const formattedOutput = result
    ? outputFormat === "markdown"
      ? result.markdown
      : JSON.stringify(result.articles, null, 2)
    : "";

  return (
    <section className="academic-section">
      <div className="academic-heading">
        <div>
          <h2>学术信息追踪</h2>
          <p>API 优先采集、字段识别与热点排序</p>
        </div>
        <span className="academic-model">gpt-5.6-terra</span>
      </div>

      <div className="academic-toolbar" aria-label="学术来源快捷选择">
        {SOURCE_PRESETS.map((source) => (
          <button
            key={source.name}
            type="button"
            className={sourceUrl === source.url ? "active" : ""}
            onClick={() => setSourceUrl(source.url)}
          >
            {source.name}
          </button>
        ))}
      </div>

      <div className="academic-form">
        <div className="academic-field academic-field-wide">
          <label htmlFor="academic-url">学术来源 URL</label>
          <input
            id="academic-url"
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder="https://journal.example.com/search"
          />
        </div>

        <div className="academic-field academic-field-wide">
          <label htmlFor="academic-keywords">关键词</label>
          <input
            id="academic-keywords"
            value={keywordInput}
            onChange={(event) => setKeywordInput(event.target.value)}
            placeholder="transformer, LLM, diffusion model"
          />
          <div className="academic-keywords" aria-live="polite">
            {keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}
          </div>
        </div>

        <div className="academic-field">
          <label htmlFor="academic-range">时间范围</label>
          <select
            id="academic-range"
            value={timeRangeDays}
            onChange={(event) => setTimeRangeDays(Number(event.target.value))}
          >
            <option value={0}>不限</option>
            <option value={7}>近 7 天</option>
            <option value={30}>近 30 天</option>
            <option value={180}>近半年</option>
            <option value={365}>近一年</option>
            <option value={1095}>近三年</option>
          </select>
        </div>

        <div className="academic-field">
          <label htmlFor="academic-citations">最低引用数</label>
          <input
            id="academic-citations"
            type="number"
            min="0"
            value={minCitations}
            onChange={(event) => setMinCitations(Number(event.target.value))}
          />
        </div>

        <div className="academic-field">
          <label htmlFor="academic-recent">近期发布阈值</label>
          <div className="academic-number-unit">
            <input
              id="academic-recent"
              type="number"
              min="0"
              value={recentDays}
              onChange={(event) => setRecentDays(Number(event.target.value))}
            />
            <span>天</span>
          </div>
        </div>

        <div className="academic-field">
          <label htmlFor="academic-limit">结果数量</label>
          <input
            id="academic-limit"
            type="number"
            min="1"
            max="50"
            value={maxResults}
            onChange={(event) => setMaxResults(Number(event.target.value))}
          />
        </div>

        <div className="academic-field academic-options">
          <span className="academic-label">页面渲染</span>
          <label className="academic-toggle">
            <input
              type="checkbox"
              checked={renderJavaScript}
              onChange={(event) => setRenderJavaScript(event.target.checked)}
            />
            <span aria-hidden="true" />
            JavaScript
          </label>
        </div>

        <div className="academic-field academic-options">
          <span className="academic-label">输出格式</span>
          <div className="academic-segmented">
            <button
              type="button"
              className={outputFormat === "json" ? "active" : ""}
              onClick={() => setOutputFormat("json")}
            >
              JSON
            </button>
            <button
              type="button"
              className={outputFormat === "markdown" ? "active" : ""}
              onClick={() => setOutputFormat("markdown")}
            >
              Markdown
            </button>
          </div>
        </div>
      </div>

      <button className="academic-submit" type="button" onClick={runSearch} disabled={loading}>
        {loading ? <><span className="spinner mini" /> 正在分析与采集</> : "开始采集"}
      </button>

      {error && <div className="academic-error">{error}</div>}

      {result && (
        <div className="academic-results">
          <div className="academic-result-summary">
            <div>
              <strong>{result.source_name}</strong>
              <span>{strategyLabel(result.strategy)}</span>
            </div>
            <div className="academic-summary-metrics">
              <span><b>{result.articles.length}</b> 条结果</span>
              <span>按综合热度排序</span>
            </div>
          </div>

          {result.warnings.map((warning) => (
            <div className="academic-warning" key={warning}>{warning}</div>
          ))}

          {result.articles.length === 0 ? (
            <div className="academic-empty">没有找到符合当前筛选条件的学术内容</div>
          ) : (
            <div className="academic-paper-list">
              {result.articles.map((article, index) => (
                <article className="academic-paper" key={`${article.url}-${index}`}>
                  <div className="academic-paper-rank">{index + 1}</div>
                  <div className="academic-paper-body">
                    <a href={article.url} target="_blank" rel="noopener noreferrer">
                      {article.title}
                    </a>
                    <div className="academic-paper-meta">
                      {article.authors.length > 0 && <span>{article.authors.slice(0, 4).join(", ")}</span>}
                      {article.published_at && <time>{article.published_at.slice(0, 10)}</time>}
                      <span>引用 {formatMetric(article.citations)}</span>
                      {article.downloads !== null && <span>下载 {formatMetric(article.downloads)}</span>}
                    </div>
                    {article.abstract && <p>{article.abstract.slice(0, 420)}</p>}
                  </div>
                  <div className="academic-hot-score">
                    <strong>{article.hot_score.toFixed(1)}</strong>
                    <span>热度</span>
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="academic-output-block">
            <div className="academic-output-header">
              <strong>{outputFormat === "json" ? "JSON 输出" : "Markdown 表格"}</strong>
              <button type="button" onClick={() => copyText(formattedOutput, "output")}>
                {copied === "output" ? "已复制" : "复制"}
              </button>
            </div>
            <pre>{formattedOutput}</pre>
          </div>

          <details className="academic-code-block">
            <summary>
              <span>生成的 Python 爬虫</span>
              <code>{result.generated_file.split("/").pop()}</code>
            </summary>
            <div className="academic-code-actions">
              <button type="button" onClick={() => copyText(result.generated_code, "code")}>
                {copied === "code" ? "已复制" : "复制代码"}
              </button>
            </div>
            <pre>{result.generated_code}</pre>
          </details>

          {Object.keys(result.selector_config).length > 0 && (
            <details className="academic-selectors">
              <summary>CSS 选择器配置</summary>
              <pre>{JSON.stringify(result.selector_config, null, 2)}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
