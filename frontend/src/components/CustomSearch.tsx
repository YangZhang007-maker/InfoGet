import { useState } from "react";
import { resolveUrl } from "../services/data";

const API_BACKEND = "http://localhost:5001";
const PRESET_INTERESTS = [
  "科技", "AI", "金融", "财经", "游戏", "汽车", "新能源", "医疗", "健康",
  "教育", "房产", "娱乐", "体育", "数码", "时尚", "美食", "旅游", "国际",
];

type Mode = "filter" | "crawler";
type OutputView = "results" | "json" | "code" | "plan";

interface HotItemResp {
  title: string; hot: string; url: string; summary: string; relevance: number; match_type: string;
}
interface SourceResult {
  source_url: string; source_name: string; matched_platform: string | null;
  is_known: boolean; items: HotItemResp[]; error: string | null;
}
interface SearchResponse { results: SourceResult[]; total_items: number; }
interface CrawlerArticle {
  title: string; published_at: string | null; summary: string; url: string;
  hot: number | null; hot_label: string; matched_keywords: string[]; hot_score: number;
}
interface CrawlerAnalysis {
  analysis_id: string; source_url: string; warnings: string[];
  plan: Record<string, unknown>; generated_code: string; generated_file: string; plan_file: string;
}
interface CrawlerResult {
  source_url: string; articles: CrawlerArticle[]; warnings: string[];
  json_file: string; status: string;
}

const PIPELINE = ["robots.txt", "访问检查", "DOM 分析", "代码生成", "内容抓取", "JSON 保存"];

function formatHot(hot: string): string {
  const num = Number.parseInt(hot, 10);
  if (Number.isNaN(num) || num === 0) return hot;
  if (num >= 100000000) return `${(num / 100000000).toFixed(1)}亿`;
  if (num >= 10000) return `${(num / 10000).toFixed(0)}万`;
  return hot;
}

async function apiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export default function CustomSearch() {
  const [mode, setMode] = useState<Mode>("filter");
  const [urlInput, setUrlInput] = useState("");
  const [customInterest, setCustomInterest] = useState("");
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [results, setResults] = useState<SourceResult[]>([]);
  const [crawlerAnalysis, setCrawlerAnalysis] = useState<CrawlerAnalysis | null>(null);
  const [crawlerResult, setCrawlerResult] = useState<CrawlerResult | null>(null);
  const [outputView, setOutputView] = useState<OutputView>("results");
  const [maxPages, setMaxPages] = useState(3);
  const [maxResults, setMaxResults] = useState(30);
  const [allowJavascript, setAllowJavascript] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const toggleInterest = (tag: string) => {
    setSelectedInterests((current) =>
      current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]
    );
  };

  const addCustomInterest = () => {
    const values = customInterest.split(/[,，]+/).map((value) => value.trim()).filter(Boolean);
    if (values.length) {
      setSelectedInterests((current) => [...new Set([...current, ...values])]);
      setCustomInterest("");
    }
  };

  const validate = (): string[] | null => {
    const urls = urlInput.split(/[\n,，]+/).map((value) => resolveUrl(value.trim())).filter(Boolean);
    if (!urls.length) {
      setError("请输入信息源网站 URL");
      return null;
    }
    if (mode === "crawler" && urls.length !== 1) {
      setError("爬虫获取模式每次只能分析一个网站 URL");
      return null;
    }
    if (!selectedInterests.length) {
      setError("请至少添加一个关键词");
      return null;
    }
    return urls;
  };

  const handleFilter = async (urls: string[]) => {
    const response = await fetch(`${API_BACKEND}/api/custom-search`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls, interests: selectedInterests }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const data = (await response.json()) as SearchResponse;
    setResults(data.results);
  };

  const handleCrawler = async (sourceUrl: string) => {
    setPipelineStep(1);
    const analyzeResponse = await fetch(`${API_BACKEND}/api/custom-crawler/analyze`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: sourceUrl, keywords: selectedInterests,
        max_pages: maxPages, max_results: maxResults, allow_javascript: allowJavascript }),
    });
    if (!analyzeResponse.ok) throw new Error(await apiError(analyzeResponse));
    const analysis = (await analyzeResponse.json()) as CrawlerAnalysis;
    setCrawlerAnalysis(analysis);
    setPipelineStep(4);
    setPipelineStep(5);
    const runResponse = await fetch(`${API_BACKEND}/api/custom-crawler/run`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysis.analysis_id }),
    });
    if (!runResponse.ok) throw new Error(await apiError(runResponse));
    setCrawlerResult((await runResponse.json()) as CrawlerResult);
    setPipelineStep(6);
  };

  const handleSearch = async () => {
    const urls = validate();
    if (!urls) return;
    setLoading(true); setSearched(true); setError(""); setResults([]);
    setCrawlerAnalysis(null); setCrawlerResult(null); setPipelineStep(0); setOutputView("results");
    try {
      if (mode === "filter") await handleFilter(urls);
      else await handleCrawler(urls[0]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "请求失败，请检查后端服务");
    } finally {
      setLoading(false);
    }
  };

  const warnings = [...new Set([...(crawlerAnalysis?.warnings || []), ...(crawlerResult?.warnings || [])])];

  return (
    <section className="custom-search">
      <div className="cs-heading">
        <div><h2>自定义信息源</h2><p className="custom-desc">筛选现有热点，或分析任意公开网站并生成专用爬虫</p></div>
        <span className="cs-model">gpt-5.6-terra</span>
      </div>

      <div className="cs-mode-tabs" role="tablist" aria-label="信息获取方式">
        <button className={mode === "filter" ? "active" : ""} onClick={() => setMode("filter")}>智能筛选</button>
        <button className={mode === "crawler" ? "active" : ""} onClick={() => setMode("crawler")}>爬虫获取</button>
      </div>

      <div className="cs-form-grid">
        <div className="cs-input-section cs-field-wide">
          <label className="cs-label">信息源网站 URL</label>
          <textarea className="cs-url-input" value={urlInput} onChange={(event) => setUrlInput(event.target.value)}
            placeholder={mode === "crawler" ? "https://news.example.com" : "网站 URL 或名称，多个来源用换行分隔"}
            rows={mode === "crawler" ? 2 : 4} />
        </div>

        <div className="cs-input-section cs-field-wide">
          <label className="cs-label">关键词</label>
          <div className="cs-interest-tags">
            {PRESET_INTERESTS.map((tag) => <button key={tag} className={`cs-tag ${selectedInterests.includes(tag) ? "active" : ""}`}
              onClick={() => toggleInterest(tag)}>{tag}</button>)}
          </div>
          <div className="cs-custom-interest">
            <input type="text" value={customInterest} onChange={(event) => setCustomInterest(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && addCustomInterest()} placeholder="输入关键词，逗号分隔" />
            <button onClick={addCustomInterest}>添加</button>
          </div>
          {selectedInterests.length > 0 && <div className="cs-selected-interests">
            {selectedInterests.map((tag) => <span key={tag} className="cs-selected-tag">{tag}
              <button aria-label={`移除 ${tag}`} onClick={() => toggleInterest(tag)}>×</button></span>)}
          </div>}
        </div>

        {mode === "crawler" && <div className="cs-crawler-options cs-field-wide">
          <label>最大页数<input type="number" min="1" max="5" value={maxPages} onChange={(event) => setMaxPages(Number(event.target.value))} /></label>
          <label>最大结果数<input type="number" min="1" max="100" value={maxResults} onChange={(event) => setMaxResults(Number(event.target.value))} /></label>
          <label className="cs-toggle"><input type="checkbox" checked={allowJavascript} onChange={(event) => setAllowJavascript(event.target.checked)} /><span />允许 Playwright 回退</label>
        </div>}
      </div>

      <button className="cs-search-btn" onClick={handleSearch} disabled={loading}>
        {loading ? (mode === "crawler" ? "分析并抓取中..." : "筛选中...") : (mode === "crawler" ? "分析网站并运行爬虫" : "开始筛选")}
      </button>

      {mode === "crawler" && (loading || pipelineStep > 0) && <div className="cs-pipeline" aria-label="爬虫执行进度">
        {PIPELINE.map((label, index) => <div key={label} className={index + 1 <= pipelineStep ? "done" : index + 1 === pipelineStep + 1 && loading ? "active" : ""}>
          <span>{index + 1 <= pipelineStep ? "✓" : index + 1}</span>{label}</div>)}
      </div>}

      {error && <div className="cs-error">{error}</div>}
      {warnings.length > 0 && <div className="cs-warnings">{warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}

      {mode === "filter" && searched && !loading && !error && results.length === 0 && <div className="cs-no-results">未找到相关热点信息</div>}
      {mode === "filter" && results.map((source) => <FilterResult key={source.source_url} source={source} />)}

      {mode === "crawler" && crawlerAnalysis && crawlerResult && <div className="cs-crawler-output">
        <div className="cs-run-summary"><strong>{crawlerResult.articles.length} 条匹配结果</strong>
          <span>JSON: {crawlerResult.json_file}</span><span>Python: {crawlerAnalysis.generated_file}</span></div>
        <div className="cs-output-tabs" role="tablist" aria-label="爬虫输出">
          {(["results", "json", "code", "plan"] as OutputView[]).map((view) => <button key={view}
            className={outputView === view ? "active" : ""} onClick={() => setOutputView(view)}>
            {{ results: "结果", json: "JSON", code: "Python", plan: "解析计划" }[view]}</button>)}
        </div>
        {outputView === "results" && <CrawlerResults articles={crawlerResult.articles} />}
        {outputView === "json" && <pre className="cs-code-view">{JSON.stringify(crawlerResult, null, 2)}</pre>}
        {outputView === "code" && <pre className="cs-code-view">{crawlerAnalysis.generated_code}</pre>}
        {outputView === "plan" && <pre className="cs-code-view">{JSON.stringify(crawlerAnalysis.plan, null, 2)}</pre>}
      </div>}
    </section>
  );
}

function FilterResult({ source }: { source: SourceResult }) {
  return <div className="cs-source-result">
    <div className="cs-source-header"><span className="cs-source-name">{source.source_name}</span>
      <span className="cs-source-badge">{source.is_known ? `已知平台 · ${source.matched_platform}` : "Codex 智能提取"}</span>
      {source.error && <span className="cs-source-error">{source.error}</span>}</div>
    <div className="cs-items">{source.items.map((item, index) => <a key={`${item.url}-${index}`} href={item.url || "#"}
      target="_blank" rel="noopener noreferrer" className="cs-item"><span className="cs-item-rank">{index + 1}</span>
      <div className="cs-item-content"><span className="cs-item-title">{item.title}</span><div className="cs-item-meta">
        {item.hot && <span className="cs-item-hot">热度 {formatHot(item.hot)}</span>}
        {item.relevance > 0 && <span className="cs-item-relevance">相关度 {item.relevance}/10</span>}
        <span className="cs-item-type">{item.match_type}</span></div>
        {item.summary && <p className="cs-item-summary">{item.summary}</p>}</div></a>)}</div>
  </div>;
}

function CrawlerResults({ articles }: { articles: CrawlerArticle[] }) {
  if (!articles.length) return <div className="cs-no-results">网站可访问，但没有找到匹配关键词的内容</div>;
  return <div className="cs-items cs-crawler-items">{articles.map((article, index) => <a key={article.url} href={article.url}
    target="_blank" rel="noopener noreferrer" className="cs-item"><span className="cs-item-rank">{index + 1}</span>
    <div className="cs-item-content"><span className="cs-item-title">{article.title}</span><div className="cs-item-meta">
      {article.published_at && <span>{article.published_at}</span>}
      {article.hot !== null && <span className="cs-item-hot">热度 {article.hot}</span>}<span>评分 {article.hot_score}</span>
      {article.matched_keywords.map((keyword) => <span className="cs-item-type" key={keyword}>{keyword}</span>)}</div>
      {article.summary && <p className="cs-item-summary">{article.summary}</p>}</div></a>)}</div>;
}
