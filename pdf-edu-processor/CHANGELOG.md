# Changelog

## [0.3.2] - 2026-07-05

### 新增
- **`PAGE_NUMBER_MODE` 配置项**：`"chinese"` / `"numeric"` / `"auto"`（默认 `auto`）
  - `chinese` 模式：处理 "第N页 共M页" 中文页脚（v0.3.1 行为）
  - `numeric` 模式：处理 "N" / "N/M" / "N of M" 纯数字页脚
  - `auto` 模式：自动扫描前 N 页页脚识别格式（向后兼容默认）
- **`PAGE_TOTAL` 配置项**：默认 `None`（自动从页脚推断），可手动指定（如 `100`），用于扫描失败兜底
- **`MODE_DETECT_SAMPLES` 配置项**：auto 模式扫描的样本页数（默认 `5`）
- **`_resolve_page_mode()` 函数**：auto 模式下扫描前 N 页页脚，识别格式
- **`_match_footer_token()` / `_match_footer_token_extended()` 函数**：4 种页脚正则匹配
  - `^第\d+页(\s*共\d+页)?$`（中文复合）
  - `^\d+\s*/\s*\d+$`（数字斜杠）
  - `^\d+\s+of\s+\d+$`（英文 of，忽略大小写）
  - `^\d+$`（纯数字）
- **`_to_roman()` 函数**：1..3999 → 罗马数字，支持多页目录 ii/iii/iv/...
- **`_count_toc_pages()` 函数**：自动识别目录页范围，连续多页依次输出罗马数字
- **`_write_chinese_page()` / `_write_numeric_page()` 函数**：拆分中文/数字页写入逻辑

### 改进
- **双模式页码**：chinese 模式保持 v0.3.1 行为；numeric 模式使用 TiRo 字体居中（不嵌 CJK，文件体积小）
- **多页目录**：numeric + `TOC_AS_ROMAN=True` 时连续输出 i/ii/iii/...
- **total 同步**：原页脚的"共XX页" / "of XX" / 分母均按 `PAGE_OFFSET` 同步偏移
- **`verify()` 多模式匹配**：兼容 4 种页脚格式的残留检测；新增"模式自检"行
- **错误提示**：`PAGE_NUMBER_MODE` 取值非法时立即抛 `ValueError`

### 向后兼容
- 默认 `auto` 模式，扫描结果为 chinese 时行为与 v0.3.1 完全一致
- 显式 `PAGE_NUMBER_MODE="chinese"` 可锁定旧行为
- 所有 v0.3.1 配置项（INPUT_PDF / OUTPUT_PDF / PAGE_OFFSET / CHAPTERS / ...）保持不变

## [0.3.1] - 2026-07-05

### 新增
- **`_resolve_paths()` 函数**：智能解析输入输出 PDF 路径
  - `INPUT_PDF` 支持单文件路径或目录路径
  - 目录路径时自动取该目录下第一个 PDF（按文件名排序）
  - `OUTPUT_PDF` 留空时自动按"原名-整理后.pdf"生成
  - 找不到文件时给出清晰的搜索目录和提示

### 改进
- **AI Agent 友好**：用户上传 PDF 后保留原名复制到 `/workspace/`，脚本自动识别，无需手动重命名为 `input.pdf`
- **向后兼容**：仍支持显式指定 `INPUT_PDF` 和 `OUTPUT_PDF` 路径

## [0.3.0] - 2026-07-05

### 新增
- **`_resolve_chapters()` 函数**：自动从 `CHAPTERS` 推导 PDF 0-based 索引，公式 `pdf_idx = CONTENT_START_INDEX + (新页码 - 1)`，避免人工配置错误
- **链接精准性校验**：`verify()` 新增逐链接目标页内容比对，确保书签和跳转链接真正指向章节标题页
- **运行时断言校验**：`_resolve_chapters()` 检查章节编号连续性、新页码单调递增；`add_navigation()` 检查推导的 PDF 索引在文档范围内

### 改进
- **`CHAPTERS` 进一步简化**：从 4 元组 `[编号, 标题, 新页码, PDF索引]` 减为 3 元组 `[编号, 标题, 新页码]`，完全消除手算 PDF 索引的出错可能
- **错误提示优化**：配置错误时立即抛出 `ValueError` 并给出具体期望值（如 "章节编号不连续: 期望 1, 实际 2"）
- **入口引导**：启动时打印前 3 个章节的"新页码 → PDF 物理页"映射，便于人工核对

### 修复
- **书签/目录链接跳错页**（v0.2.0 引入）：用户配置 `CHAPTERS` 第 4 列时极易混淆"原页码"和"PDF 物理页"。新版完全不需要这个字段，从根上消除错误源

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
