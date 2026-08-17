import type { HotItem } from "../types";
import { formatHot } from "../services/api";

interface HotListProps {
  platformName: string;
  updateTime: string;
  items: HotItem[];
  loading: boolean;
}

export default function HotList({ platformName, updateTime, items, loading }: HotListProps) {
  if (loading) {
    return (
      <div className="hot-list-loading">
        <div className="spinner" />
        <p>正在获取热榜数据...</p>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="hot-list-empty">
        <p>👈 请从左侧选择一个平台查看热榜</p>
      </div>
    );
  }

  return (
    <div className="hot-list">
      <div className="hot-list-header">
        <h2>🔥 {platformName}</h2>
        <span className="update-time">
          更新于 {new Date(updateTime).toLocaleString("zh-CN")}
        </span>
      </div>
      <div className="hot-items">
        {items.map((item, idx) => (
          <a
            key={item.id}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hot-item"
          >
            <span className={`rank rank-${idx < 3 ? "top" : "normal"}`}>
              {idx + 1}
            </span>
            <span className="item-title">{item.title}</span>
            {item.hot !== undefined && item.hot > 0 && (
              <span className="item-hot">{formatHot(item.hot)}</span>
            )}
            <span className="item-arrow">↗</span>
          </a>
        ))}
      </div>
    </div>
  );
}