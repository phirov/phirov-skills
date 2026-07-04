---
name: pdf-edu-processor
description: >-
  PDF 教辅材料后处理工具。当用户需要处理含有页眉（教师信息/标语/logo）、
  水印、需要页码重编号、目录美化和导航增强的教学 PDF 时使用此 skill。
  支持：去除页眉文字和图片、去除对角线水印、目录页与内容页页码偏移重编号、
  目录点号对齐、添加书签和目录跳转链接。
---

# PDF 教辅材料后处理

> **v0.1.0** | 2026-07-04 | 首次发布

对教辅类 PDF 进行一系列后处理：清理页眉水印、重编号页码、美化目录、添加导航。

## 适用场景

- 教学讲义 PDF 需要去除教师署名和机构 logo
- PDF 含有半透明对角线水印需要清除
- 目录页码与实际页码需要同步偏移
- 目录页点号需要两端对齐
- 需要添加书签和目录跳转链接以便导航

## 使用方法

### 步骤 1：理解需求

从用户输入中提取以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| `input_pdf` | 输入 PDF 路径或 URL | `/workspace/doc.pdf` 或 `https://...` |
| `header_texts` | 要删除的页眉文字列表 | `["@建宇老师", "方法学得牛，剑指双一流"]` |
| `page_offset` | 页码偏移量（旧页码 - offset = 新页码） | `7`（页码 8→1, 9→2...） |
| `toc_page_index` | 目录页 PDF 索引（0-based） | `0` |
| `toc_as_roman` | 目录页页码是否改为罗马数字 | `true` |
| `chapters` | 章节定义：`[[编号, 标题, 新页码, PDF索引, 标题结束x坐标], ...]` | 见脚本中的示例格式 |
| `remove_watermark` | 是否去除水印 | `true` |

### 步骤 2：调用处理脚本

使用 `scripts/process.py` 作为参考模板，根据具体需求定制参数。

脚本依赖 PyMuPDF (`fitz`)，已在环境中预装。

### 步骤 3：验证结果

处理完成后自动检查：
- 页眉文字是否清除
- 水印命令是否残留
- 目录页和内容页页码是否正确
- 书签和目录跳转链接数量

## 核心技术要点

### 页眉删除
使用 `page.add_redact_annot()` + `page.apply_redactions()` 彻底删除文本和图片。

### 水印删除
水印通常是 `<</Type/Pagination/Subtype/Watermark>>` 标记的 Form XObject。
使用正则匹配 `/Artifact<</Type/Pagination/Subtype/Watermark>>BDC ... /Fm1 Do Q EMC`
并通过 `doc.update_stream()` 从内容流中移除。

### 页码重编号
1. 定位原始页码文本块（通常在页面底部，y > 780）
2. 用 `add_redact_annot` 移除旧页码
3. 用 `insert_text()` 插入新页码，使用 Times-Roman 字体
4. TOC 页码引用同步更新

### 目录美化
1. 用 redact 清除旧的 dots+页码区域
2. 用 `fitz.get_text_length()` 精确计算每个字符宽度
3. 根据可用空间计算需要的 dots 数量
4. 分别插入 dots 和页码，确保页码右端对齐

### 导航增强
- 书签：`doc.set_toc([[level, title, page], ...])`
- TOC 链接：`page.insert_link({"kind": fitz.LINK_GOTO, "from": rect, "page": idx})`

## 文件保存

处理后的文件覆盖回原路径（或用户指定路径），避免产生中间版本冗余。
