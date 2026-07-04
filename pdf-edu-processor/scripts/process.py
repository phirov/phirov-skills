#!/usr/bin/env python3
"""
PDF 教辅材料后处理脚本
功能：页眉删除、水印删除、页码重编号、目录美化、书签、TOC链接
依赖：pip install PyMuPDF
"""

import fitz
import re
import os


# ============================================================
# 配置区域 — 根据具体需求修改以下参数
# ============================================================

# 输入文件
INPUT_PDF = "/workspace/input.pdf"

# 页眉中需要删除的文字（任意匹配即触发）
HEADER_TEXTS = ["@建宇老师", "方法学得牛", "剑指双一流"]

# 页码偏移量：content_page = original_page - PAGE_OFFSET
PAGE_OFFSET = 7

# 目录页索引（0-based）
TOC_PAGE_INDEX = 0

# 目录页自身页码是否改为罗马数字 "i"
TOC_AS_ROMAN = True

# 是否删除水印（Artifact + 内联文字水印）
REMOVE_WATERMARK = True

# 文件保存路径（None 表示覆盖原文件）
OUTPUT_PDF = None  # 设为路径字符串可另存，如 "/workspace/output.pdf"

# 章节定义：[编号, 标题, 新页码, PDF索引]
# 新页码 = 原始页码 - PAGE_OFFSET
# PDF索引 = 原始页码在PDF中的0-based索引
# 注意：不再需要手动配置 x 坐标和 TOC_Y_POSITIONS，脚本自动从 PDF 提取
CHAPTERS = [
    # 示例 — 请根据实际 PDF 替换
    # (1, "1 一元一次方程的解法", 1, 8),
]


# ============================================================
# 辅助函数
# ============================================================

def get_toc_lines_data(page):
    """从目录页提取 dots span 的精确坐标数据（dict 模式，无需人工配置）"""
    td = page.get_text("dict")
    lines_data = []
    for block in td["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text.startswith("."):
                    b = span["bbox"]
                    lines_data.append({
                        "y0": b[1],
                        "y1": b[3],
                        "x0": b[0],
                        "x1": b[2],
                    })
    return lines_data


# ============================================================
# 处理逻辑
# ============================================================

def remove_headers(doc, skip_indices=None):
    """删除每页的页眉文字和右上角 logo 图片（可指定保留页）"""
    if skip_indices is None:
        skip_indices = set()
    for i in range(doc.page_count):
        if i in skip_indices:
            continue
        page = doc[i]
        for b in page.get_text("blocks"):
            text = b[4].strip()
            if any(t in text for t in HEADER_TEXTS):
                page.add_redact_annot(fitz.Rect(b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3))
        for img in page.get_images(full=True):
            for r in page.get_image_rects(img):
                if r.y0 < 120 and r.x0 > 500:
                    page.add_redact_annot(fitz.Rect(r.x0 - 3, r.y0 - 3, r.x1 + 3, r.y1 + 3))
        page.apply_redactions()
    print("[1/5] 页眉已删除")


def remove_watermarks(doc):
    """删除内容流中的水印（两种格式：Artifact BDC 块 + 内联 FT22 文字水印）"""
    pattern_artifact = re.compile(
        r'/Artifact\s*<<.*?/Subtype\s*/Watermark.*?>>\s*BDC\s+.*?EMC',
        re.DOTALL,
    )
    pattern_inline = re.compile(
        r'q\s+1\s+0\s+0\s+-1\s+0\s+0\s+cm\s+BT\s+/FT22.*?/GS13\s+gs.*?ET\s+Q',
        re.DOTALL,
    )

    removed_artifact = 0
    removed_inline = 0

    for i in range(doc.page_count):
        page = doc[i]
        for xref in page.get_contents():
            stream_bytes = doc.xref_stream(xref)
            stream_text = stream_bytes.decode("latin-1", errors="replace")
            new_text = stream_text

            while True:
                m = pattern_artifact.search(new_text)
                if not m:
                    break
                removed_artifact += 1
                new_text = new_text[:m.start()] + new_text[m.end():]

            while True:
                m = pattern_inline.search(new_text)
                if not m:
                    break
                removed_inline += 1
                new_text = new_text[:m.start()] + new_text[m.end():]

            if new_text != stream_text:
                doc.update_stream(xref, new_text.encode("latin-1", errors="replace"))

    print(f"[2/5] 水印已删除 (Artifact: {removed_artifact} 处, Inline: {removed_inline} 处)")


def renumber_pages(doc, content_start_index=2):
    """重编号目录页和内容页页码"""
    DIGIT_W = fitz.get_text_length("0", "TiRo", 9.0)

    # 目录页 → 罗马数字 "i"
    page0 = doc[TOC_PAGE_INDEX]
    words0 = page0.get_text("words")
    for w in words0:
        if w[1] > 780 and w[4].strip().isdigit():
            page0.add_redact_annot(fitz.Rect(w[0] - 5, w[1] - 2, w[2] + 5, w[3] + 2))
            break
    page0.apply_redactions()
    if TOC_AS_ROMAN:
        page0.insert_text(
            fitz.Point(294, 797), "i",
            fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
        )

    # 内容页（从 content_start_index 起）
    for i in range(content_start_index, doc.page_count):
        page = doc[i]
        words = page.get_text("words")
        for w in words:
            text = w[4].strip()
            if w[1] > 780 and text.isdigit():
                old_num = int(text)
                new_num = old_num - PAGE_OFFSET
                if new_num < 1:
                    continue
                new_str = str(new_num)
                nw = len(new_str) * DIGIT_W
                cx = (w[0] + w[2]) / 2
                page.add_redact_annot(
                    fitz.Rect(cx - nw / 2 - 5, w[1] - 2, cx + nw / 2 + 5, w[3] + 2)
                )
                page.apply_redactions()
                page.insert_text(
                    fitz.Point(cx - nw / 2, w[3] - 2),
                    new_str,
                    fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
                )
                break
    print("[3/5] 页码已重编号")


def rebuild_toc(doc):
    """重建目录页 dots 和页码（overlay=True 白块覆盖 + 动态坐标提取）

    核心原理：
    1. 使用 get_text("dict") 自动提取每行 dots span 的精确坐标
    2. 用 overlay=True 的白块覆盖旧 dots + 旧页码（白块在顶层）
    3. insert_text 在白块之后调用，确保新内容在最顶层
    4. insert_y = span_y0 + 15（与旧页码基线对齐）
    """
    DOT_W = fitz.get_text_length(".", "TiRo", 14.1)
    DIGIT_W = fitz.get_text_length("0", "TiRo", 14.1)

    page0 = doc[TOC_PAGE_INDEX]
    lines_data = get_toc_lines_data(page0)

    if len(lines_data) != len(CHAPTERS):
        print(f"  ⚠ 警告: dots 行数 ({len(lines_data)}) ≠ CHAPTERS 配置数 ({len(CHAPTERS)})")

    # 步骤1: 画白块覆盖旧 dots + 旧页码（overlay=True，确保在旧内容之上）
    for line in lines_data:
        page0.draw_rect(
            fitz.Rect(line["x0"] - 2, line["y0"], 545, line["y1"]),
            fill=(1, 1, 1), color=None, overlay=True,
        )

    # 步骤2: 插入新 dots 和页码（在 draw_rect 之后调用，确保在最顶层）
    for i, line in enumerate(lines_data):
        if i >= len(CHAPTERS):
            break
        new_page = CHAPTERS[i][2]
        page_str = str(new_page)
        num_width = len(page_str) * DIGIT_W
        insert_x = line["x0"] - 2
        avail = 539 - insert_x - num_width - 1
        dots_count = max(0, int(avail / DOT_W))
        while (dots_count * DOT_W) > (avail + 1) and dots_count > 3:
            dots_count -= 1
        while (dots_count * DOT_W) < (avail - 1) and dots_count < 200:
            dots_count += 1

        # insert_y = y0 + 15（与旧页码基线精确对齐）
        insert_y = line["y0"] + 15
        page0.insert_text(
            fitz.Point(insert_x, insert_y),
            "." * dots_count,
            fontname="TiRo", fontsize=14.1, color=(0, 0, 0),
        )
        page0.insert_text(
            fitz.Point(539 - num_width - 1, insert_y),
            page_str,
            fontname="TiRo", fontsize=14.1, color=(0, 0, 0),
        )
    print(f"[4/5] 目录页已美化 ({len(lines_data)} 行)")


def add_navigation(doc):
    """添加书签和目录跳转链接（使用动态提取的行坐标）"""
    page0 = doc[TOC_PAGE_INDEX]
    lines_data = get_toc_lines_data(page0)

    # 书签
    toc_list = [[1, ch[1], ch[3] + 1] for ch in CHAPTERS]
    doc.set_toc(toc_list)

    # TOC 链接（使用实际 span 的 y 范围，自动适配）
    for i, (_, _, _, pdf_idx) in enumerate(CHAPTERS):
        if i < len(lines_data):
            line = lines_data[i]
            page0.insert_link({
                "kind": fitz.LINK_GOTO,
                "from": fitz.Rect(55, line["y0"] - 4, 545, line["y1"] + 2),
                "page": pdf_idx,
            })

    print(f"[5/5] 导航已添加 (书签 {len(toc_list)} 个, 链接 {len(CHAPTERS)} 个)")


def verify(doc):
    """验证处理结果"""
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    text_all = "".join(doc[i].get_text() for i in range(doc.page_count))

    # 页眉
    all_clean = True
    for t in HEADER_TEXTS:
        if t in text_all:
            print(f"  ⚠ 仍有页眉文字: {t}")
            all_clean = False
    if all_clean:
        print("  ✅ 页眉已清除")

    # 水印（精确匹配 /FT22 后跟空格，排除 /FT224 等正文字体）
    wm = sum(
        1
        for i in range(doc.page_count)
        for xref in doc[i].get_contents()
        if (re.search(r'/FT22\s', doc.xref_stream(xref).decode("latin-1", errors="replace"))
            or re.search(r'Watermark', doc.xref_stream(xref).decode("latin-1", errors="replace")))
    )
    print(f"  {'✅' if wm == 0 else '⚠'} 水印残留: {wm} 处")

    # 目录页页码
    page_toc = doc[TOC_PAGE_INDEX]
    for w in page_toc.get_text("words"):
        if w[1] > 780 and w[4].strip():
            print(f"  {'✅' if w[4].strip() == 'i' else '⚠'} 目录页页码: '{w[4].strip()}'")
            break

    # 抽查内容页页码
    check_indices = [4, 9, 20, 50, 80, 100]
    for idx in check_indices:
        if idx < doc.page_count:
            for w in doc[idx].get_text("words"):
                if w[1] > 780 and w[4].strip().isdigit():
                    print(f"  ✅ 第{idx + 1}页 页码: {w[4].strip()}")
                    break

    # 书签
    toc = doc.get_toc()
    print(f"  ✅ 书签: {len(toc)} 个")
    for item in toc[:3]:
        print(f"     → {item[1]} (p.{item[2]})")
    if len(toc) > 3:
        print(f"     ... 共 {len(toc)} 项")

    # 链接
    links = [l for l in doc[TOC_PAGE_INDEX].get_links() if l["kind"] == fitz.LINK_GOTO]
    print(f"  ✅ 目录链接: {len(links)} 个")


def main():
    if not CHAPTERS:
        print("请先配置 CHAPTERS 参数（章节编号、标题、新页码、PDF索引）")
        return

    doc = fitz.open(INPUT_PDF)
    print(f"处理文件: {INPUT_PDF} ({doc.page_count} 页)")

    # 注意：先删水印再删页眉，避免 redact 改写内容流导致水印正则失效
    if REMOVE_WATERMARK:
        remove_watermarks(doc)
    remove_headers(doc)
    renumber_pages(doc)
    rebuild_toc(doc)
    add_navigation(doc)

    # 保存
    output = OUTPUT_PDF or INPUT_PDF
    tmp = output + ".tmp"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, output)

    # 验证
    doc2 = fitz.open(output)
    verify(doc2)
    doc2.close()

    orig_size = os.path.getsize(INPUT_PDF)
    new_size = os.path.getsize(output)
    print(f"\n✅ 完成: {output}")
    print(f"   原始大小: {orig_size / 1024:.0f} KB → 处理后: {new_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
