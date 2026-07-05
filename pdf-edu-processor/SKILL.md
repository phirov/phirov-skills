---
name: pdf-edu-processor
description: >-
  PDF 教辅材料后处理工具。当用户需要处理含有页眉（教师信息/标语/logo）、
  水印、需要页码重编号、目录美化和导航增强的教学 PDF 时使用此 skill。
  支持：去除页眉文字和图片、去除对角线水印、目录页与内容页页码偏移重编号、
  目录点号对齐、添加书签和目录跳转链接。
---

# PDF 教辅材料后处理

> **v0.3.3** | 2026-07-06 | 目录页页码统一改为罗马数字（与原页码格式解耦），结构特征识别替代页脚匹配

对教辅类 PDF 进行一系列后处理：清理页眉水印、重编号页码、美化目录、添加导航。

## 适用场景

- 教学讲义 PDF 需要去除教师署名和机构 logo
- PDF 含有半透明对角线水印需要清除
- 目录页码与实际页码需要同步偏移
- 目录页点号需要两端对齐
- 需要添加书签和目录跳转链接以便导航

## 使用方法

### 步骤 1：理解需求

从用户输入或 PDF 分析中提取以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `input_pdf` | 输入 PDF 路径或目录（v0.3.1） | `/workspace/我的教辅.pdf` 或 `/workspace/` |
| `output_pdf` | 输出 PDF 路径（v0.3.1：None 时自动按原名+"-整理后"生成） | `None` 或 `/workspace/output.pdf` |
| `header_texts` | 要删除的页眉文字列表 | `["@建宇老师", "方法学得牛", "剑指双一流"]` |
| `page_offset` | 页码偏移量（旧页码 - offset = 新页码） | `7`（页码 8→1, 9→2...） |
| `page_number_mode` | 页码模式：`chinese` / `numeric` / `auto`（v0.3.2 默认 auto） | `"auto"` |
| `page_total` | 总页数显式覆盖：`None` = 自动推断（v0.3.2） | `100` |
| `mode_detect_samples` | auto 模式扫描样本数（v0.3.2） | `5` |
| `toc_page_index` | 目录页 PDF 索引（0-based） | `2` |
| `toc_as_roman` | 目录页页码是否改为罗马数字 | `true` |
| `chapters` | 章节定义：`[[编号, 标题, 新页码], ...]`（v0.3.0 简化） | 见脚本中的示例格式 |
| `remove_watermark` | 是否去除水印 | `true` |
| `content_start_index` | 内容页起始 PDF 索引（0-based，跳过封面） | `4` |
| `skip_indices` | 跳过页眉删除的页面索引集合 | `{0, 1, 3}` |

> **v0.3.3 变更**：目录页页码格式与原 PDF 格式完全解耦。新增 `_looks_like_toc_page()` 结构特征识别（"目录"标题 / dots 行 / 章节编号 / 页码范围）替代原 `_match_footer_token` 页脚匹配，确保不论原页码是"第7页 共20页"、"7 / 20"、"7 of 20" 还是纯数字 "7"，目录页都能被正确识别并改写为小写罗马数字 i/ii/iii。`_to_roman()` 输出小写。`verify()` 升级为对所有目录页逐一检查。
>
> **v0.3.2 变更**：新增 `PAGE_NUMBER_MODE` 双模式支持。`auto` 模式自动扫描前 5 页页脚识别中英文格式，识别到纯数字（`"8"` / `"8/107"` / `"8 of 107"`）时自动切换为 `numeric` 模式（TiRo 字体、居中、不嵌 CJK）。多页目录支持罗马数字 `i`/`ii`/`iii`。新增 `PAGE_TOTAL` 配置项允许手动覆盖总页数。

> **v0.3.1 变更**：`input_pdf` 支持目录路径（自动取该目录下第一个 PDF），`output_pdf` 留空时自动按"原名-整理后.pdf"生成。AI Agent 无需重命名上传文件，保持原文件名即可。

> **v0.3.0 变更**：`chapters` 简化为 3 元组 `[编号, 标题, 新页码]`，PDF 索引由脚本自动推导（`pdf_idx = CONTENT_START_INDEX + (新页码 - 1)`），彻底消除人工配置错误。

> **v0.2.0 变更**：`chapters` 不再需要手动配置 x 坐标和 `TOC_Y_POSITIONS`。脚本使用 `get_text("dict")` 自动提取目录页每行 dots span 的精确坐标。

### 步骤 2：调用处理脚本

修改 `scripts/process.py` 中的配置参数后直接运行：

```bash
python3 scripts/process.py
```

脚本依赖 PyMuPDF (`fitz`)，已在环境中预装。

### 步骤 3：验证结果

处理完成后自动检查：
- 页眉文字是否清除
- 水印命令是否残留
- 目录页和内容页页码是否正确
- 书签和目录跳转链接数量
- **v0.3.0 新增**：每个目录链接的目标页内容校验，确保精准命中章节标题

## 核心技术要点

### v0.3.0 CHAPTERS 自动推导（关键改进）

**问题**：v0.2.0 中 `CHAPTERS` 第 4 列（PDF 0-based 索引）需手算，错配后所有书签和链接都跳错页（如"原页码 8"易与"PDF 第 8 页"混淆）。

**解决方案**：
1. `CHAPTERS` 简化为 3 元组 `[编号, 标题, 新页码]`，完全消除"PDF 索引"这一易错字段
2. 新增 `_resolve_chapters()` 函数自动推导：`pdf_idx = CONTENT_START_INDEX + (新页码 - 1)`
3. 启动时打印前 3 个章节的"新页码 → PDF 物理页"映射，便于人工核对
4. 运行时断言：章节编号必须连续、新页码必须单调递增、推导的 PDF 索引必须在文档范围内
5. `verify()` 新增逐链接目标页内容比对，确保书签和跳转链接真正指向章节标题页

### v0.2.0 目录美化（关键改进）

**问题**：v0.1.0 使用 `add_redact_annot` 删除旧 dots+页码，但在 Quark 生成的 PDF 中标题和点号处于同一文本对象，redact 会切断标题末字。

**解决方案**：
1. 使用 `get_text("dict")` 自动提取每行 dots span 的精确坐标（y0, y1, x0, x1），无需手动配置
2. 用 `draw_rect(overlay=True)` 的白块覆盖旧 dots + 旧页码区域
3. `insert_text` 在 `draw_rect` 之后调用，确保新内容始终在最顶层
4. `insert_y = span_y0 + 15` 实现新页码与旧页码基线精确对齐
5. `CHAPTERS` 简化：v0.2.0 需 4 元组 `[编号, 标题, 新页码, PDF索引]`；**v0.3.0 进一步简化为 3 元组 `[编号, 标题, 新页码]`**，PDF 索引自动推导

### 页眉删除
使用 `page.add_redact_annot()` + `page.apply_redactions()` 彻底删除文本和图片。
支持 `skip_indices` 参数跳过封面等页面。

### 水印删除
**两个正则模式**，覆盖常见的教辅 PDF 水印格式：
- 模式1：Artifact Watermark BDC 块 — `/Artifact<<...Subtype/Watermark...>>BDC ... EMC`
- 模式2：内联文字水印 — `q 1 0 0 -1 0 0 cm BT /FT22 ... /GS13 gs ... ET Q`

通过 `doc.update_stream()` 从内容流中物理移除，而非视觉覆盖。

**处理顺序**：先删水印再删页眉，避免 `apply_redactions()` 改写内容流导致水印正则失效。

### 页码重编号
1. 定位原始页码文本块（通常在页面底部，y > 780）
2. 用 `add_redact_annot` 移除旧页码
3. 用 `insert_text()` 插入新页码，使用 Times-Roman 字体
4. 目录页页码改为罗马数字 "i"
5. 可通过 `content_start_index` 指定内容页起始索引

### 导航增强
- 书签：`doc.set_toc([[level, title, page], ...])`
- TOC 链接：`page.insert_link({"kind": fitz.LINK_GOTO, "from": rect, "page": idx})`
- 链接区域自动使用 `get_toc_lines_data` 提取的实际行坐标

### v0.3.2 双模式页码（关键改进）

**问题**：v0.3.1 仅支持 "第N页 共M页" 中文格式，英文 PDF 常见 "8 of 107"、"8/107"、纯数字 "8" 等格式无法处理。

**解决方案**：
1. 新增 `PAGE_NUMBER_MODE = "chinese" | "numeric" | "auto"`，默认 `auto`（向后兼容）
2. `auto` 模式扫描前 5 页：检测 `^第\d+页` / 含 "页" 字 → chinese；检测 `^\d+$` / `^\d+/\d+$` / `^\d+\s*of\s*\d+$` → numeric
3. `numeric` 模式使用 TiRo 字体（不嵌 CJK，文件体积小），居中 (cx=297.5)
4. total 同步：原页脚 "共XX页" / 分母 / "of XX" → `new_total = old_total - PAGE_OFFSET`
5. 多页目录：numeric + `TOC_AS_ROMAN` 时，连续多页目录依次输出 i, ii, iii, ...
6. `PAGE_TOTAL` 可手动覆盖（如 `100`），用于扫描失败的兜底
7. `verify()` 多模式匹配页脚残留，避免误报

## 文件保存

处理后的文件覆盖回原路径（或用户指定路径），避免产生中间版本冗余。

## 已知限制

- 目录页旧页码文本层仍存留在 PDF 内容流中（被白块视觉覆盖），文本提取/复制可能显示旧页码。这是 PDF 文本层叠加的已知限制，不影响视觉和打印效果。
- `PAGE_TOTAL` 自动推断仅在原页脚含"共N页" / 分母 / "of N" 时生效；纯数字"N"页脚模式下 `total` 为 `None`。
- `TOC_AS_ROMAN=True` 强制要求至少能识别 1 个目录页（通过结构特征）。若 P3 完全没有"目录"标题、dots 行、章节编号和页码范围中任意两个特征，将被识别为非目录页，罗马数字不会被写入。

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.3.3 | 2026-07-06 | 目录页页码统一改为罗马数字（小写 i/ii/iii），与原页码格式解耦；结构特征识别替代页脚匹配；verify 升级为多页目录逐一检查；新增单元测试 + 端到端测试套件 |
| v0.3.2 | 2026-07-05 | 双模式页码（chinese/numeric/auto），多页目录罗马数字，PAGE_TOTAL 手动覆盖 |
| v0.3.1 | 2026-07-05 | 智能路径解析，保留上传文件原名 |
| v0.2.0 | 2026-07-04 | 修复红框切断标题问题，改用 overlay=True 白块 + 动态坐标提取；水印双模式匹配；处理顺序优化 |
| v0.1.0 | 2026-07-04 | 首次发布，基础 redact 方案 |

## 测试

`tests/` 目录提供完整的单元测试 + 端到端测试套件：

```bash
# 1. 生成测试样例 PDF（3 种页脚格式：chinese/numeric/english）
python3 tests/make_fixtures.py /tmp/pdf_test_fixtures

# 2. 运行测试
python3 tests/test_toc_roman.py
```

测试覆盖：
- `_to_roman()` 输出小写（1~10）
- `_looks_like_toc_page()` 结构特征识别（不依赖页脚格式）
- `_count_toc_pages()` 返回目录页索引列表
- 端到端：3 种页脚格式的目录页统一改为小写罗马数字 "i"
- 端到端：原页码特征（"共" / "/" / "of"）全部清除
- 端到端：正文页不被强制改为罗马数字（保留原模式）
- 端到端：多页目录（P3="i", P4="ii"）
