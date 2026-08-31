import { useEffect, useRef, useState } from "react";

const API_BACKEND = "http://localhost:5001";
const PRESETS = ["Claude Code 和智能代理", "新能源汽车行业动态", "AI 绘画入门", "健康饮食与运动", "量化交易实践"];

interface Blogger {
  name: string; fans_text: string; sign: string; avatar: string; profile_url: string;
  sample_video: string; sample_url: string; reason: string;
}
interface Platform { name: string; link: string; reason: string; }
interface SourceInput { kind: "blogger" | "platform"; name: string; url: string; reason: string; scope: string; }
interface ContentItem {
  title: string; url: string; hot?: string; desc?: string; summary?: string;
  relevance?: number; match_type?: string; source_name?: string;
}
interface SourceResult {
  source_url: string; source_name: string; matched_platform: string | null;
  is_known: boolean; items: ContentItem[]; error: string | null;
}
interface Batch {
  batch: number; kind: "blogger" | "platform"; status: "completed" | "failed";
  sources: SourceInput[]; interests: string[]; results: SourceResult[]; error: string | null;
}
interface DiscoveryResult {
  discovery_id: string; query: string; keywords: string[];
  recommendation: { bloggers: Blogger[]; platforms: Platform[] };
  source_inputs: SourceInput[]; batches: Batch[];
  summary: {
    recommended_bloggers: number; recommended_platforms: number;
    sources_processed: number; total_items: number; failed_batches: number;
  };
  warnings: string[];
}

type ReportIntent = "learning" | "industry" | "decision";
type ReportPreset = "compact" | "standard" | "detailed" | "custom";
type ReportPhase = "idle" | "cleaning" | "semantic" | "organizing";

interface ReportOverview {
  topic_summary: string;
  covered_directions: string[];
  reading_order: string;
  missing_directions: string[];
}
interface ReportSourceAnnotation {
  source_id: string;
  kind: "blogger" | "platform";
  name: string;
  role_label: string;
  relation_summary: string;
  matched_keywords: string[];
  url: string;
}
interface ReportItem {
  item_id: string; title: string; url: string; source_name: string; source_key: string;
  content_type: string; stage: string; relation_summary: string; tags: string[];
  matched_keywords: string[]; relevance_score: number; hot: string;
  quality_score: number; heat_score: number;
}
interface ReportStage { name: string; items: ReportItem[]; }
interface DiscoveryReport {
  schema_version: number; title: string; query: string; keywords: string[];
  intent: ReportIntent; structure_name: string; stage_order: string[];
  overview: ReportOverview;
  recommended_sources: { bloggers: ReportSourceAnnotation[]; platforms: ReportSourceAnnotation[] };
  stages: ReportStage[]; warnings: string[];
}
interface ReportResponse {
  report_id: string; discovery_id: string; requested_amount: number; returned_amount: number;
  generation_mode: "codex" | "fallback"; degraded_reason: string | null;
  report: DiscoveryReport; markdown: string;
}

const REPORT_AMOUNTS: Record<Exclude<ReportPreset, "custom">, number> = {
  compact: 5,
  standard: 10,
  detailed: 20,
};

async function getError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function clampAmount(value: number): number {
  return Math.min(30, Math.max(1, Number.isFinite(value) ? Math.round(value) : 10));
}

export default function CombinedDiscovery() {
  const [query, setQuery] = useState("");
  const [maxBloggers, setMaxBloggers] = useState(6);
  const [batchSize, setBatchSize] = useState(3);
  const [maxPerSource, setMaxPerSource] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [activeResultView, setActiveResultView] = useState<"discovery" | "report">("discovery");
  const [reportPreset, setReportPreset] = useState<ReportPreset>("standard");
  const [customAmount, setCustomAmount] = useState(10);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [reportResult, setReportResult] = useState<ReportResponse | null>(null);
  const [reportPhase, setReportPhase] = useState<ReportPhase>("idle");
  const reportTimers = useRef<number[]>([]);
  const reportRequestVersion = useRef(0);

  useEffect(() => () => {
    reportTimers.current.forEach((timer) => window.clearTimeout(timer));
  }, []);

  const clearReportTimers = () => {
    reportTimers.current.forEach((timer) => window.clearTimeout(timer));
    reportTimers.current = [];
  };

  const run = async (preset?: string) => {
    if (reportLoading) return;
    const value = (preset ?? query).trim();
    if (!value) {
      setError("请输入你感兴趣的内容");
      return;
    }
    if (preset) setQuery(preset);
    reportRequestVersion.current += 1;
    clearReportTimers();
    setLoading(true);
    setError("");
    setResult(null);
    setReportResult(null);
    setReportError("");
    setReportLoading(false);
    setReportPhase("idle");
    setActiveResultView("discovery");
    try {
      const response = await fetch(`${API_BACKEND}/api/combined-discovery/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: value, max_bloggers: maxBloggers,
          batch_size: batchSize, max_per_source: maxPerSource }),
      });
      if (!response.ok) throw new Error(await getError(response));
      setResult((await response.json()) as DiscoveryResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "智能发现请求失败");
    } finally {
      setLoading(false);
    }
  };

  const generateReport = async () => {
    if (!result) return;
    const amount = reportPreset === "custom"
      ? clampAmount(customAmount)
      : REPORT_AMOUNTS[reportPreset];
    if (reportPreset === "custom") setCustomAmount(amount);
    const requestVersion = ++reportRequestVersion.current;
    clearReportTimers();
    setReportLoading(true);
    setReportError("");
    setReportPhase("cleaning");
    reportTimers.current = [
      window.setTimeout(() => setReportPhase("semantic"), 450),
      window.setTimeout(() => setReportPhase("organizing"), 1300),
    ];
    try {
      const response = await fetch(`${API_BACKEND}/api/combined-discovery/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ discovery_id: result.discovery_id, amount }),
      });
      if (!response.ok) throw new Error(await getError(response));
      const report = (await response.json()) as ReportResponse;
      if (
        reportRequestVersion.current !== requestVersion
        || report.discovery_id !== result.discovery_id
      ) return;
      setReportResult(report);
      setActiveResultView("report");
    } catch (caught) {
      if (reportRequestVersion.current !== requestVersion) return;
      setReportError(caught instanceof Error ? caught.message : "展示报告生成失败");
    } finally {
      if (reportRequestVersion.current === requestVersion) {
        clearReportTimers();
        setReportLoading(false);
        setReportPhase("idle");
      }
    }
  };

  return (
    <section className="combined-section">
      <header className="combined-heading">
        <div><h2>兴趣智能发现</h2><p>从兴趣描述发现优质博主和平台，并自动检索相关热点内容</p></div>
        <span>推荐 + 自定义源</span>
      </header>

      <div className="combined-presets">
        {PRESETS.map((preset) => <button type="button" key={preset} onClick={() => run(preset)} disabled={loading || reportLoading}>{preset}</button>)}
      </div>

      <div className="combined-query">
        <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={3} disabled={loading || reportLoading}
          onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); run(); } }}
          placeholder="输入一个兴趣点、问题或希望持续关注的领域" />
        <button type="button" onClick={() => run()} disabled={loading || reportLoading}>{loading ? "发现中..." : "开始智能发现"}</button>
      </div>

      <div className="combined-options">
        <label>推荐博主数<input type="number" min="1" max="8" value={maxBloggers} disabled={loading || reportLoading} onChange={(event) => setMaxBloggers(Number(event.target.value))} /></label>
        <label>平台批次大小<input type="number" min="1" max="5" value={batchSize} disabled={loading || reportLoading} onChange={(event) => setBatchSize(Number(event.target.value))} /></label>
        <label>每个来源结果<input type="number" min="1" max="20" value={maxPerSource} disabled={loading || reportLoading} onChange={(event) => setMaxPerSource(Number(event.target.value))} /></label>
      </div>

      {loading && <DiscoveryProgress />}
      {error && <div className="combined-error">{error}</div>}
      {result && <>
        <ReportToolbar
          preset={reportPreset}
          customAmount={customAmount}
          loading={reportLoading}
          onPreset={setReportPreset}
          onCustomAmount={setCustomAmount}
          onGenerate={generateReport}
        />
        {reportLoading && <ReportProgress phase={reportPhase} />}
        {reportError && <div className="combined-error combined-report-error">{reportError}</div>}
        <div className="combined-result-tabs" role="tablist" aria-label="智能发现结果视图">
          <button type="button" role="tab" aria-selected={activeResultView === "discovery"}
            className={activeResultView === "discovery" ? "active" : ""}
            onClick={() => setActiveResultView("discovery")}>发现结果</button>
          <button type="button" role="tab" aria-selected={activeResultView === "report"}
            className={activeResultView === "report" ? "active" : ""}
            disabled={!reportResult} onClick={() => setActiveResultView("report")}>展示报告</button>
        </div>
        {activeResultView === "discovery"
          ? <DiscoveryOutput result={result} />
          : reportResult && <ReportDashboard response={reportResult} />}
      </>}
    </section>
  );
}

function DiscoveryProgress() {
  return <div className="combined-progress">
    <span className="done">1</span><strong>推荐博主与平台</strong><i />
    <span className="active">2</span><strong>分批检索信息源</strong><i />
    <span>3</span><strong>聚合内容</strong>
  </div>;
}

function ReportToolbar({ preset, customAmount, loading, onPreset, onCustomAmount, onGenerate }: {
  preset: ReportPreset; customAmount: number; loading: boolean;
  onPreset: (preset: ReportPreset) => void; onCustomAmount: (amount: number) => void;
  onGenerate: () => void;
}) {
  const options: Array<{ id: ReportPreset; label: string }> = [
    { id: "compact", label: "精简 5" },
    { id: "standard", label: "标准 10" },
    { id: "detailed", label: "详细 20" },
    { id: "custom", label: "自定义" },
  ];
  return <div className="combined-report-toolbar">
    <div>
      <strong>展示报告</strong>
      <span>选择精选内容的信息量</span>
    </div>
    <div className="combined-report-amount" role="group" aria-label="报告信息量">
      {options.map((option) => <button type="button" key={option.id}
        className={preset === option.id ? "active" : ""}
        onClick={() => onPreset(option.id)} disabled={loading}>{option.label}</button>)}
    </div>
    {preset === "custom" && <label className="combined-report-custom">
      <span>条数</span>
      <input type="number" min="1" max="30" value={customAmount}
        onChange={(event) => onCustomAmount(Number(event.target.value))}
        onBlur={() => onCustomAmount(clampAmount(customAmount))} disabled={loading} />
    </label>}
    <button type="button" className="combined-report-generate" onClick={onGenerate} disabled={loading}>
      {loading ? "生成中..." : "生成展示报告"}
    </button>
  </div>;
}

function ReportProgress({ phase }: { phase: ReportPhase }) {
  const phases: Array<{ id: ReportPhase; label: string }> = [
    { id: "cleaning", label: "清洗结果" },
    { id: "semantic", label: "语义分析" },
    { id: "organizing", label: "组织报告" },
  ];
  const current = Math.max(0, phases.findIndex((item) => item.id === phase));
  return <div className="combined-report-progress" aria-live="polite">
    {phases.map((item, index) => <div key={item.id} className={index < current ? "done" : index === current ? "active" : ""}>
      <span>{index + 1}</span><strong>{item.label}</strong>
    </div>)}
  </div>;
}

function DiscoveryOutput({ result }: { result: DiscoveryResult }) {
  return <div className="combined-output">
    <div className="combined-summary">
      <div><strong>{result.summary.recommended_bloggers}</strong><span>推荐博主</span></div>
      <div><strong>{result.summary.recommended_platforms}</strong><span>推荐平台</span></div>
      <div><strong>{result.summary.sources_processed}</strong><span>已处理来源</span></div>
      <div><strong>{result.summary.total_items}</strong><span>内容结果</span></div>
    </div>

    <div className="combined-keywords"><span>领域关键词</span>{result.keywords.map((keyword) => <b key={keyword}>{keyword}</b>)}</div>
    {result.warnings.length > 0 && <div className="combined-warnings">{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}

    {result.recommendation.bloggers.length > 0 && <section className="combined-block">
      <h3>推荐博主</h3>
      <div className="combined-bloggers">{result.recommendation.bloggers.map((blogger) => <a key={blogger.profile_url}
        href={blogger.profile_url} target="_blank" rel="noopener noreferrer" className="combined-blogger">
        {blogger.avatar && <img src={blogger.avatar} alt="" onError={(event) => { (event.currentTarget).style.display = "none"; }} />}
        <div><strong>{blogger.name}</strong><span>{blogger.fans_text ? `${blogger.fans_text}粉` : blogger.reason}</span>
          <p>{blogger.sign || blogger.reason}</p>{blogger.sample_video && <small>{blogger.sample_video}</small>}</div>
      </a>)}</div>
    </section>}

    <section className="combined-block">
      <h3>送入自定义源的输入</h3>
      <div className="combined-source-table">{result.source_inputs.map((source) => <div key={`${source.kind}-${source.url}`}>
        <span className={`combined-kind ${source.kind}`}>{source.kind === "blogger" ? "博主" : "平台"}</span>
        <div><a href={source.url} target="_blank" rel="noopener noreferrer">{source.name}</a><small>{source.scope}</small></div>
        <p>{source.reason}</p>
      </div>)}</div>
    </section>

    <section className="combined-block">
      <h3>自定义源聚合结果</h3>
      <div className="combined-batches">{result.batches.map((batch) => <BatchOutput key={batch.batch} batch={batch} />)}</div>
    </section>
  </div>;
}

function BatchOutput({ batch }: { batch: Batch }) {
  const count = batch.results.reduce((total, source) => total + source.items.length, 0);
  return <details className={`combined-batch ${batch.status}`} open={count > 0}>
    <summary><span>批次 {batch.batch}</span><strong>{batch.kind === "blogger" ? "博主检索" : "平台检索"}</strong>
      <small>{batch.sources.map((source) => source.name).join("、")}</small><b>{batch.status === "failed" ? "失败" : `${count} 条`}</b></summary>
    {batch.error && <p className="combined-batch-error">{batch.error}</p>}
    {batch.results.map((source) => <div className="combined-source-result" key={source.source_url}>
      <header><strong>{source.source_name}</strong><span>{source.is_known ? `已知平台 · ${source.matched_platform}` : "智能提取"}</span></header>
      {source.error && <p className="combined-source-error">{source.error}</p>}
      {source.items.length === 0 && !source.error && <p className="combined-empty">没有匹配内容</p>}
      {source.items.map((item, index) => <a className="combined-item" key={`${item.url}-${index}`} href={item.url || "#"} target="_blank" rel="noopener noreferrer">
        <b>{index + 1}</b><div><strong>{item.title}</strong><p>{item.summary || item.desc}</p>
          <small>{item.hot && `热度 ${item.hot}`}{item.match_type && ` · ${item.match_type}`}</small></div>
      </a>)}
    </div>)}
  </details>;
}

function ReportDashboard({ response }: { response: ReportResponse }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const copyTimer = useRef<number | null>(null);
  useEffect(() => () => {
    if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
  }, []);

  const copyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(response.markdown);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
    copyTimer.current = window.setTimeout(() => setCopyState("idle"), 1800);
  };

  const sourceCount = new Set(
    response.report.stages.flatMap((stage) => stage.items.map((item) => item.source_key)),
  ).size;
  return <article className="combined-report-dashboard">
    <header className="combined-report-header">
      <div>
        <div className="combined-report-meta">
          <span>{response.report.structure_name}</span>
          <span>{response.generation_mode === "codex" ? "智能总结" : "基础排序"}</span>
        </div>
        <h2>{response.report.title}</h2>
        <div className="combined-report-keywords">{response.report.keywords.map((keyword) => <b key={keyword}>{keyword}</b>)}</div>
      </div>
      <div className="combined-report-actions">
        <button type="button" onClick={() => window.print()}>打印 / 保存 PDF</button>
        <button type="button" onClick={copyMarkdown}>
          {copyState === "copied" ? "已复制" : copyState === "failed" ? "复制失败" : "复制 Markdown"}
        </button>
      </div>
    </header>

    {response.generation_mode === "fallback" && <div className="combined-report-degraded">
      <strong>当前为基础排序报告</strong><span>{response.degraded_reason}</span>
    </div>}
    {response.returned_amount < response.requested_amount && <div className="combined-report-notice">
      请求 {response.requested_amount} 条，实际返回 {response.returned_amount} 条；低相关内容未用于补足数量。
    </div>}

    <div className="combined-report-metrics">
      <div><strong>{response.requested_amount}</strong><span>请求内容</span></div>
      <div><strong>{response.returned_amount}</strong><span>精选内容</span></div>
      <div><strong>{sourceCount}</strong><span>覆盖来源</span></div>
      <div><strong>{response.report.stages.length}</strong><span>覆盖阶段</span></div>
    </div>

    <section className="combined-report-overview">
      <div className="combined-report-section-title"><span>01</span><h3>报告总览</h3></div>
      <p className="combined-report-topic">{response.report.overview.topic_summary || "暂无主题概览"}</p>
      <div className="combined-report-overview-grid">
        <div><strong>覆盖方向</strong><p>{response.report.overview.covered_directions.join("、") || "暂无"}</p></div>
        <div><strong>推荐阅读顺序</strong><p>{response.report.overview.reading_order || response.report.stage_order.join(" → ")}</p></div>
        <div><strong>尚缺方向</strong><p>{response.report.overview.missing_directions.join("、") || "暂无明显缺口"}</p></div>
      </div>
    </section>

    <ReportSourceOverview report={response.report} />

    <section className="combined-report-path">
      <div className="combined-report-section-title"><span>03</span><h3>精选内容路径</h3></div>
      {response.report.stages.length === 0 && <div className="combined-report-empty">没有达到展示条件的内容。</div>}
      {response.report.stages.map((stage, index) => <ReportStageSection key={stage.name} stage={stage} index={index + 1} />)}
    </section>
  </article>;
}

function ReportSourceOverview({ report }: { report: DiscoveryReport }) {
  const sources = [...report.recommended_sources.bloggers, ...report.recommended_sources.platforms];
  return <section className="combined-report-sources">
    <div className="combined-report-section-title"><span>02</span><h3>推荐来源</h3></div>
    {sources.length === 0
      ? <p className="combined-report-empty">本次没有可展示的推荐博主或平台。</p>
      : <div className="combined-report-source-grid">{sources.map((source) => <a
        key={source.source_id} href={source.url} target="_blank" rel="noopener noreferrer"
        className="combined-report-source">
        <div><span>{source.kind === "blogger" ? "博主" : "平台"}</span><strong>{source.name}</strong></div>
        <b>{source.role_label}</b>
        <p>{source.relation_summary}</p>
        {source.matched_keywords.length > 0 && <small>{source.matched_keywords.join(" · ")}</small>}
      </a>)}</div>}
  </section>;
}

function ReportStageSection({ stage, index }: { stage: ReportStage; index: number }) {
  return <section className="combined-report-stage">
    <header><span>{String(index).padStart(2, "0")}</span><div><h4>{stage.name}</h4><small>{stage.items.length} 条精选内容</small></div></header>
    <div className="combined-report-items">{stage.items.map((item) => <article key={item.item_id} className="combined-report-item">
      <div className="combined-report-item-main">
        <div className="combined-report-item-meta"><span>{item.content_type}</span><span>{item.source_name}</span>
          {item.hot && <span>热度 {item.hot}</span>}</div>
        <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>
        <p>{item.relation_summary}</p>
        <div className="combined-report-tags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
      </div>
      <div className="combined-report-score"><strong>{item.relevance_score}</strong><span>相关度</span></div>
    </article>)}</div>
  </section>;
}
