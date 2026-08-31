# 推荐与自定义源组合模块

`POST /api/combined-discovery/run` 接收一段兴趣描述，依次执行：

1. 复用 `recommend_source.recommender.recommend` 提取关键词、推荐 B站博主和平台。
2. 对每位带公开主页的博主，以“博主名 + 领域关键词”调用一次 `custom_search`。
3. 对推荐平台按 `batch_size` 分批调用 `custom_search`。
4. 保留每批状态、输入来源和错误，聚合返回内容结果。

博主主页当前由自定义源识别为平台来源，因此结果属于“平台级检索（以博主名优先匹配）”，不承诺只包含该主页发布的内容。

## 展示报告

智能发现完成后，响应顶层会包含 `discovery_id`。后端同时把本次结果保存为不可变快照，报告生成不会重新执行博主推荐或信息源抓取。

```json
{
  "discovery_id": "00000000-0000-4000-8000-000000000000",
  "query": "机器学习",
  "keywords": ["机器学习"]
}
```

使用快照生成报告：

```http
POST /api/combined-discovery/reports
Content-Type: application/json
```

```json
{
  "discovery_id": "00000000-0000-4000-8000-000000000000",
  "amount": 10
}
```

`amount` 支持 1–30。前端提供精简 5 条、标准 10 条、详细 20 条和自定义数量。推荐博主与平台不占用内容条数；达到相关度要求的内容不足时，实际返回条数会小于请求值，不用低相关内容补足。

系统会自动选择以下结构之一：

- 学习型：基础认知 → 方法与工具 → 实战内容 → 进阶方向
- 行业型：背景概览 → 当前热点 → 典型案例 → 趋势判断
- 决策型：基础知识 → 可选方案 → 实践建议 → 风险提醒

Codex 负责语义相关度、关系说明和标签，但只能引用后端提供的内容 ID，标题和链接由后端从快照回填。Codex 调用失败或返回格式无效时，接口仍会返回 `generation_mode: "fallback"` 的基础排序报告。

## 数据与导出

数据默认保存在：

```text
data/combined_discovery/<discovery_id>/
├── discovery.json
└── reports/<report_id>/
    ├── report.json
    └── report.md
```

相同快照、信息量和报告 Schema 版本会复用同一报告。首版不会自动清理这些文件。

前端报告看板支持浏览器“打印 / 保存 PDF”和“复制 Markdown”；PDF 由浏览器打印功能生成，不需要服务端 PDF 依赖。
