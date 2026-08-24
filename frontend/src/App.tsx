import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import HotList from "./components/HotList";
import SearchBar from "./components/SearchBar";
import Top10 from "./components/Top10";
import CustomSearch from "./components/CustomSearch";
import RecommendSource from "./components/RecommendSource";
import AcademicInfo from "./components/AcademicInfo";
import type { HotItem } from "./types";
import { fetchHotList } from "./services/api";
import { PLATFORM_NAME_MAP } from "./services/data";
import "./App.css";

type ViewMode = "hotlist" | "search" | "top10" | "custom" | "academic" | "recommend";

const VIEW_MODES: ViewMode[] = ["hotlist", "search", "top10", "custom", "academic", "recommend"];

function initialViewMode(): ViewMode {
  const requested = new URLSearchParams(window.location.search).get("view") as ViewMode | null;
  return requested && VIEW_MODES.includes(requested) ? requested : "hotlist";
}

function App() {
  const [selectedPlatform, setSelectedPlatform] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [hotItems, setHotItems] = useState<HotItem[]>([]);
  const [platformName, setPlatformName] = useState("");
  const [updateTime, setUpdateTime] = useState("");
  const [loading, setLoading] = useState(false);

  const loadPlatform = useCallback(async (id: string, preserveView = false) => {
    setSelectedPlatform(id);
    if (!preserveView) setViewMode("hotlist");
    setLoading(true);
    setHotItems([]);
    try {
      const data = await fetchHotList(id);
      setHotItems(data.data || []);
      setPlatformName(data.title);
      setUpdateTime(data.updateTime);
    } catch {
      setHotItems([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadPlatform("weibo", true);
  }, [loadPlatform]);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title" onClick={() => setViewMode("hotlist")}>
          🔥 每日热榜
        </h1>
        <nav className="app-nav">
          <button
            className={`nav-btn ${viewMode === "hotlist" ? "active" : ""}`}
            onClick={() => setViewMode("hotlist")}
          >
            📊 热榜浏览
          </button>
          <button
            className={`nav-btn ${viewMode === "search" ? "active" : ""}`}
            onClick={() => setViewMode("search")}
          >
            🔍 舆情搜索
          </button>
          <button
            className={`nav-btn ${viewMode === "top10" ? "active" : ""}`}
            onClick={() => setViewMode("top10")}
          >
            🏆 跨平台TOP20
          </button>
          <button
            className={`nav-btn ${viewMode === "custom" ? "active" : ""}`}
            onClick={() => setViewMode("custom")}
          >
            🎯 自定义源
          </button>
          <button
            className={`nav-btn ${viewMode === "academic" ? "active" : ""}`}
            onClick={() => setViewMode("academic")}
          >
            📚 学术追踪
          </button>
          <button
            className={`nav-btn ${viewMode === "recommend" ? "active" : ""}`}
            onClick={() => setViewMode("recommend")}
          >
            🤝 推荐博主
          </button>
        </nav>
        <div className="header-status">
          <span className="api-badge">API: localhost:6688</span>
          {selectedPlatform && viewMode === "hotlist" && (
            <span className="current-platform">
              📱 {PLATFORM_NAME_MAP[selectedPlatform] || selectedPlatform}
            </span>
          )}
        </div>
      </header>

      <div className="app-body">
        {viewMode === "hotlist" && (
          <>
            <Sidebar selectedPlatform={selectedPlatform} onSelect={loadPlatform} />
            <main className="main-content">
              <HotList
                platformName={platformName}
                updateTime={updateTime}
                items={hotItems}
                loading={loading}
              />
            </main>
          </>
        )}

        {viewMode === "search" && (
          <main className="main-content full-width">
            <SearchBar />
          </main>
        )}

        {viewMode === "top10" && (
          <main className="main-content full-width">
            <Top10 />
          </main>
        )}

        {viewMode === "custom" && (
          <main className="main-content full-width">
            <CustomSearch />
          </main>
        )}

        {viewMode === "recommend" && (
          <main className="main-content full-width">
            <RecommendSource />
          </main>
        )}

        {viewMode === "academic" && (
          <main className="main-content full-width academic-width">
            <AcademicInfo />
          </main>
        )}
      </div>
    </div>
  );
}

export default App;
