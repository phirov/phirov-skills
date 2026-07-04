# Changelog

## [0.2.0] - 2026-07-04

### 修复
- **目录页码错位**：修复 `overlay=False` 导致白块在底层、旧页码始终可见的问题
- **标题被截断**：修复 `add_redact_annot` 切断 Quark 生成 PDF 中与点号同文本对象的标题末字
- **水印残留**：修复水印正则仅匹配 `/Fm1 Do`，遗漏 Artifact BDC 块和内联 FT22 文字水印
- **处理顺序**：水印删除移至页眉删除之前，避免 `apply_redactions()` 改写内容流导致正则失效

### 新增
- `get_toc_lines_data()` 函数：通过 `get_text("dict")` 动态提取目录页 dots span 坐标，无需手动配置 x 坐标和 `TOC_Y_POSITIONS`
- 双模式水印删除：Artifact BDC 块 + 内联 FT22 文字水印
- `skip_indices` 参数：支持跳过指定页面（封面、空白页）的页眉删除
- `content_start_index` 参数：灵活指定内容页起始 PDF 索引

### 改进
- `rebuild_toc` 核心重写：`overlay=True` 白块覆盖 + `insert_y = y0 + 15` 精确定位
- `CHAPTERS` 简化：从 5 元组 `[编号, 标题, 新页码, PDF索引, x坐标]` 减为 4 元组 `[编号, 标题, 新页码, PDF索引]`
- `verify` 增强：水印检测使用 `/FT22\s` 精确匹配，排除 `/FT224` 等正文字体误报
- 全量注释：每个函数添加工作原理说明

## [0.1.0] - 2026-07-04

### 首次发布

- 页眉删除：支持文字匹配 + 右上角图片识别
- 水印删除：正则匹配移除 Form XObject Watermark Artifact
- 页码重编号：TOC 页码 → 罗马数字，内容页统一偏移
- 目录美化：精确 dots 计算实现两端对齐
- 导航增强：一级章节书签 + 目录跳转链接
- 自动验证：处理完成后检查页眉/水印/页码/书签/链接
