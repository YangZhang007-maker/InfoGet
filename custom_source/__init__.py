"""
自定义源增强模块包

包含：
- custom_source.py: 自定义信息源搜索核心逻辑（域名匹配、多层降级搜索、Codex 集成）
- server.py: FastAPI 后端服务（端口 5001），供前端 CustomSearch 调用

使用方式：
    # 启动后端服务
    python3 custom_source/server.py

    # 作为包导入
    from custom_source.custom_source import custom_search, match_platform
"""
