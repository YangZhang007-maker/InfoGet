import { PLATFORM_CATEGORIES } from "../services/data";

interface SidebarProps {
  selectedPlatform: string;
  onSelect: (id: string) => void;
}

export default function Sidebar({ selectedPlatform, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>🔥 热榜平台</h2>
        <span className="platform-count">54个</span>
      </div>
      <nav className="sidebar-nav">
        {PLATFORM_CATEGORIES.map((cat) => (
          <div key={cat.key} className="category-group">
            <div className="category-title">
              {cat.icon} {cat.label}
              <span className="category-count">{cat.platforms.length}</span>
            </div>
            {cat.platforms.map((p) => (
              <button
                key={p.id}
                className={`platform-btn ${selectedPlatform === p.id ? "active" : ""}`}
                onClick={() => onSelect(p.id)}
                title={p.description}
              >
                <span className="platform-name">{p.name}</span>
                <span className="platform-desc">{p.description}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}