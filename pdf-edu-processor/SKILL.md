---
name: pdf-edu-processor
description: >-
  PDF 教辅材料后处理工具。当用户需要处理含有页眉（教师信息/标语/logo）、
  水印、需要页码重编号、目录美化和导航增强的教学 PDF 时使用此 skill。
  支持：去除页眉文字和图片、去除对角线水印、目录页与内容页页码偏移重编号、
  目录点号对齐、添加书签和目录跳转链接。
---

# PDF 教辅材料后处理

> **v0.2.0** | 2026-07-04 | 修复目录页码错位、动态坐标提取

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
| `input_pdf` | 输入 PDF 路径或 URL | `/workspace/doc.pdf` 或 `https://...` |
| `header_texts` | 要删除的页眉文字列表 | `["@建宇老师", "方法学得牛", "剑指双一流"]` |
| `page_offset` | 页码偏移量（旧页码 - offset = 新页码） | `7`（页码 8→1, 9→2...） |
| `toc_page_index` | 目录页 PDF 索引（0-based） | `2` |
| `toc_as_roman` | 目录页页码是否改为罗马数字 | `true` |
| `chapters` | 章节定义：`[[编号, 标题, 新页码, PDF索引], ...]` | 见脚本中的示例格式 |
| `remove_watermark` | 是否去除水印 | `true` |
| `content_start_index` | 内容页起始 PDF 索引（0-based，跳过封面） | `4` |
| `skip_indices` | 跳过页眉删除的页面索引集合 | `{0, 1, 3}` |

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

## 核心技术要点

### v0.2.0 目录美化（关键改进）

**问题**：v0.1.0 使用 `add_redact_annot` 删除旧 dots+页码，但在 Quark 生成的 PDF 中标题和点号处于同一文本对象，redact 会切断标题末字。

**解决方案**：
1. 使用 `get_text("dict")` 自动提取每行 dots span 的精确坐标（y0, y1, x0, x1），无需手动配置
2. 用 `draw_rect(overlay=True)` 的白块覆盖旧 dots + 旧页码区域
3. `insert_text` 在 `draw_rect` 之后调用，确保新内容始终在最顶层
4. `insert_y = span_y0 + 15` 实现新页码与旧页码基线精确对齐
5. `CHAPTERS` 简化：仅需 `[编号, 标题, 新页码, PDF索引]`，不再需要 x 坐标和 `TOC_Y_POSITIONS`

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

## 文件保存

处理后的文件覆盖回原路径（或用户指定路径），避免产生中间版本冗余。

## 已知限制

- 目录页旧页码文本层仍存留在 PDF 内容流中（被白块视觉覆盖），文本提取/复制可能显示旧页码。这是 PDF 文本层叠加的已知限制，不影响视觉和打印效果。
- `insert_text` 使用的 Times-Roman 字体不包含中文字符，目录标题不会通过此方法重新插入。旧标题文本不受影响。

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.2.0 | 2026-07-04 | 修复红框切断标题问题，改用 overlay=True 白块 + 动态坐标提取；水印双模式匹配；处理顺序优化 |
| v0.1.0 | 2026-07-04 | 首次发布，基础 redact 方案 |
