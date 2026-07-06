# Changelog

## [0.3.4] - 2026-07-06

### 新增
- **`PAGE_NUMBER_FORMAT` 配置项**：替代 v0.3.2 的 `PAGE_NUMBER_MODE`，明确表达"输出格式"语义
  - **`compact`**（默认）：紧凑数字 `1/56`，使用 TiRo 字体，**不嵌入 CJK 字体**，文件体积最小
  - **`plain`**：纯数字 `1`，最简洁格式
  - **`chinese`**：中文页码 `第1页 共56页`，嵌入 NotoSansCJK 字体，文件体积显著增大
  - **`auto`**：自动扫描前 5 页页脚推断最匹配格式
- **`_write_compact_page()` / `_write_plain_page()` 函数**：拆分 v0.3.2 的 `_write_numeric_page()`，支持不同输出格式
- **`_get_effective_format()` 函数**：字段优先级解析（`PAGE_NUMBER_FORMAT` 优先于 `PAGE_NUMBER_MODE`）
- **`tests/test_v034.py`**：v0.3.4 升级测试套件，5 个单元测试 + 2 个端到端测试

### 改进
- **目录页标题异常格式兼容**（用户实际场景）：`verify()` 兼容章节编号的多种分隔符
  - 支持 `"1."` (点号) / `"9 "` (空格) / `"9\n"` (换行) 等格式
  - 解决 Quark/Word 生成 PDF 中标题与编号用空格分隔导致的误报
- **`PAGE_NUMBER_MODE` 标记为 deprecated**：保留旧字段名供向后兼容，v0.4.0 移除
- **TOC 页码改用 overlay 白块**（bug 修复）：原 `apply_redactions()` 会改写内容流导致 dots span 重复（12 行变 24 行），改为 `draw_rect(overlay=True)` 物理覆盖
- **页脚匹配回退**（bug 修复）：正文文本泄漏到页脚区域时（如"于局部之和"），正则匹配失败后回退取页脚最右侧纯数字
- **页脚重写仅清除居中区域**（bug 修复）：`_write_*_page()` 中 `add_redact_annot` 限定 x>200，保留页面左/右边缘正文内容
- **`_TOC_LINES_DATA` 全局缓存**（bug 修复）：`rebuild_toc()` 提取的 dots 坐标缓存供 `add_navigation()` 复用，避免重新提取时把新 dots 也识别为旧 dots
- **目录页页眉安全清理**：在 TOC 重建后用 `draw_rect` 覆盖，避免目录页与正文页眉统一删除时破坏 dots span

### 文件体积影响
- 三种数字格式（compact / plain）文件体积几乎不变（仅 TiRo 字体）
- chinese 模式因嵌入 NotoSansCJK（~12 MB），文件体积增大 3~6 倍
- 60 页测试 PDF 实测：compact ≈ 2.6 MB，chinese ≈ 16 MB

### 向后兼容
- 默认行为变更：从 v0.3.3 的 `auto→chinese`（中文）变为 v0.3.4 的 `compact`（紧凑数字）
- 显式设置 `PAGE_NUMBER_MODE="chinese"` 可锁定旧的中文页码行为
- `PAGE_NUMBER_MODE` 字段仍可使用，新字段 `PAGE_NUMBER_FORMAT` 优先

## [0.3.3] - 2026-07-06

### 新增
- **`_looks_like_toc_page()` 函数**：结构特征识别目录页（与页码格式解耦）
  - 4 个特征：含"目录"标题 / 含 dots 行 / 含章节编号 / 含行末页码范围
  - 满足任意 2 个即判定为目录页
  - 容错 PyMuPDF 对 CJK 字体的解码异常（"目录"→"··"、"......"→"······"）
- **测试套件**：
  - `tests/make_fixtures.py`：用 PyMuPDF 直接生成 3 种页脚格式（chinese/numeric/english）的测试样例 PDF
  - `tests/test_toc_roman.py`：单元测试 + 端到端测试，7 个测试用例覆盖全部改造点

### 改进
- **目录页页码格式与原 PDF 完全解耦**：
  - 原实现 `_count_toc_pages()` 仅在目录页能匹配到 "第N页" 页脚时才识别，导致原页码格式是纯数字（如 "8"）、"8/100"、"8 of 100" 的目录页被漏判
  - 新实现基于结构特征识别，不论原页码格式如何，目录页一律改写为小写罗马数字 i/ii/iii
- **`_to_roman()` 改为小写输出**（学术/排版惯例），更符合目录页使用习惯
- **`verify()` 升级为多页目录逐一检查**：每张目录页单独校验，并对比期望罗马数字（v0.3.2 仅检查第一张）
- **`renumber_pages()` 重构**：
  - 步骤清晰化：扫描所有目录页 → 批量 redact 旧页码 → 写入新罗马数字
  - `TOC_AS_ROMAN=True` 优先级最高，与 `_RESOLVED_MODE` 解耦
  - chinese + 非 roman 模式：保持原中文页码（不变）
  - numeric + 非 roman 模式：当作内容页处理（v0.3.2 行为）

### 修复
- **数字/英文格式的目录页不被改写为罗马数字**（v0.3.2 引入）：`_match_footer_token` 优先匹配中文页脚，纯数字 / "of M" 格式下 `_count_toc_pages` 返回空列表，TOC_AS_ROMAN 失效

### 向后兼容
- 默认 `TOC_AS_ROMAN=True` 行为保持不变
- 中文模式 PDF（v0.3.1 行为）的处理结果与 v0.3.2 完全一致
- 新增的 `_looks_like_toc_page` 不影响现有 chinese 模式 PDF 的处理流程

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
