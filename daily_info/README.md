# 每日资讯模块

每日资讯将现有的平台热榜、跨平台舆情搜索和 Top20 聚合在同一个工作界面中，原有三个模块保持独立。

## 数据刷新

- `GET /api/daily-info/top20`：读取当天 Top20；当日无快照时自动聚合并持久化。
- `GET /api/daily-info/top20?refresh=true`：手动重新聚合当天数据。
- 快照目录：`$DAILY_HOT_DATA_DIR/daily_info/YYYY-MM-DD.json`。
- 日期按 `Asia/Shanghai` 计算。前端每五分钟检查一次，跨日后自动获取新快照。

聚合失败不会覆盖已有快照，写入使用临时文件和原子替换，避免服务中断产生半份 JSON。
