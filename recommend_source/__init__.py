"""
推荐博主模块包

功能：用户输入关心的问题或感兴趣的内容 → 推荐相关平台链接 + B站博主信息

包含：
- recommender.py: 推荐核心逻辑（LLM 关键词提取 + B站真实博主数据）
- router.py: FastAPI 路由（POST /api/recommend）
"""
