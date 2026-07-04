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

# 是否删除水印（Form XObject Watermark）
REMOVE_WATERMARK = True

# 文件保存路径（None 表示覆盖原文件）
OUTPUT_PDF = None  # 设为路径字符串可另存，如 "/workspace/output.pdf"

# 章节定义：[编号, 标题, 新页码, PDF索引, 标题右端x坐标]
# 新页码 = 原始页码 - PAGE_OFFSET
# PDF索引 = 新页码 + 1（因为 PDF 第1页=索引0 是目录，第2页=索引1 是空白）
CHAPTERS = [
    # 示例 — 请根据实际 PDF 替换
    # (1, "1 一元一次方程的解法", 8 - PAGE_OFFSET, (8 - PAGE_OFFSET) + 1, 193),
]

# 目录页每行的 y 坐标范围 (y0, y1)
TOC_Y_POSITIONS = [
    # 示例
    # (131, 150), (158, 177), ...
]

# ============================================================
# 处理逻辑
# ============================================================


def remove_headers(doc):
    """删除每页中的页眉文字和右上角图片"""
    for i in range(doc.page_count):
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
    """删除内容流中的 Watermark Artifact (Fm1)"""
    pattern = re.compile(
        r'/Artifact<</Type/Pagination/Subtype/Watermark>>BDC\s+q.*?/Fm1\s+Do\s+Q\s+EMC',
        re.DOTALL,
    )
    removed = 0
    for i in range(doc.page_count):
        page = doc[i]
        for xref in page.get_contents():
            stream_text = doc.xref_stream(xref).decode("latin-1", errors="replace")
            new_text = stream_text
            while True:
                m = pattern.search(new_text)
                if not m:
                    break
                removed += 1
                new_text = new_text[: m.start()] + new_text[m.end():]
            if new_text != stream_text:
                doc.update_stream(xref, new_text.encode("latin-1", errors="replace"))
    print(f"[2/5] 水印已删除 ({removed} 处)")


def renumber_pages(doc):
    """重编号目录页和内容页页码"""
    DOT_W = fitz.get_text_length(".", "TiRo", 9.0)
    DIGIT_W = fitz.get_text_length("0", "TiRo", 9.0)

    # 目录页
    page0 = doc[TOC_PAGE_INDEX]
    words0 = page0.get_text("words")
    for w in words0:
        if w[1] > 780 and w[4].strip().isdigit():
            page0.add_redact_annot(fitz.Rect(w[0] - 5, w[1] - 2, w[2] + 5, w[3] + 2))
            break
    page0.apply_redactions()
    if TOC_AS_ROMAN:
        page0.insert_text(fitz.Point(294, 797), "i", fontname="TiRo", fontsize=9.0, color=(0, 0, 0))

    # 内容页
    for i in range(2, doc.page_count):
        page = doc[i]
        words = page.get_text("words")
        for w in words:
            text = w[4].strip()
            if w[1] > 780 and text.isdigit():
                new_str = str(int(text) - PAGE_OFFSET)
                nw = len(new_str) * DIGIT_W
                cx = (w[0] + w[2]) / 2
                page.add_redact_annot(fitz.Rect(cx - nw / 2 - 5, w[1] - 2, cx + nw / 2 + 5, w[3] + 2))
                page.apply_redactions()
                page.insert_text(
                    fitz.Point(cx - nw / 2, w[3] - 2),
                    new_str,
                    fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
                )
                break
    print("[3/5] 页码已重编号")


def rebuild_toc(doc):
    """重建目录页 dots 和页码"""
    DOT_W = fitz.get_text_length(".", "TiRo", 14.1)
    DIGIT_W = fitz.get_text_length("0", "TiRo", 14.1)

    page0 = doc[TOC_PAGE_INDEX]

    for i, (_, _, new_page, _, title_end_x) in enumerate(CHAPTERS):
        y0, y1 = TOC_Y_POSITIONS[i]
        page0.add_redact_annot(fitz.Rect(title_end_x + 2, y0 - 3, 545, y1 + 3))
    page0.apply_redactions()

    for i, (_, _, new_page, _, title_end_x) in enumerate(CHAPTERS):
        y0, y1 = TOC_Y_POSITIONS[i]
        page_str = str(new_page)
        num_width = len(page_str) * DIGIT_W
        avail = 539 - title_end_x - num_width - 1
        dots_count = max(0, int(avail / DOT_W))
        while (dots_count * DOT_W) > (avail + 1) and dots_count > 5:
            dots_count -= 1
        while (dots_count * DOT_W) < (avail - 1) and dots_count < 200:
            dots_count += 1

        insert_y = y0 + (y1 - y0) * 0.35
        page0.insert_text(
            fitz.Point(title_end_x, insert_y),
            "." * dots_count,
            fontname="TiRo", fontsize=14.1, color=(0, 0, 0),
        )
        page0.insert_text(
            fitz.Point(539 - num_width - 1, insert_y),
            page_str,
            fontname="TiRo", fontsize=14.1, color=(0, 0, 0),
        )
    print("[4/5] 目录页已美化")


def add_navigation(doc):
    """添加书签和目录跳转链接"""
    page0 = doc[TOC_PAGE_INDEX]

    # 书签
    toc_list = [[1, ch[1], ch[3] + 1] for ch in CHAPTERS]
    doc.set_toc(toc_list)

    # TOC 链接
    for i, (_, _, _, pdf_idx, _) in enumerate(CHAPTERS):
        y0, y1 = TOC_Y_POSITIONS[i]
        page0.insert_link({
            "kind": fitz.LINK_GOTO,
            "from": fitz.Rect(55, y0 - 4, 545, y1 + 2),
            "page": pdf_idx,
        })

    print(f"[5/5] 导航已添加 (书签 {len(toc_list)} 个, 链接 {len(CHAPTERS)} 个)")


def verify(doc):
    """验证处理结果"""
    print("\n=== 验证 ===")
    text_all = "".join(doc[i].get_text() for i in range(doc.page_count))

    # 页眉
    for t in HEADER_TEXTS:
        if t in text_all:
            print(f"  ⚠ 仍有页眉文字: {t}")
    else:
        print("  ✅ 页眉已清除")

    # 水印
    wm = sum(
        1
        for i in range(doc.page_count)
        for xref in doc[i].get_contents()
        if "/Fm1 Do" in doc.xref_stream(xref).decode("latin-1", errors="replace")
    )
    print(f"  {'✅' if wm == 0 else '⚠'} 水印残留: {wm}")

    # 页码
    page0 = doc[TOC_PAGE_INDEX]
    for w in page0.get_text("words"):
        if w[1] > 780 and w[4].strip():
            print(f"  ✅ TOC 页码: '{w[4].strip()}'")
            break
    for idx in [2, 5, 9]:
        if idx < doc.page_count:
            for w in doc[idx].get_text("words"):
                if w[1] > 780 and w[4].strip().isdigit():
                    print(f"  ✅ 第{idx + 1}页页码: {w[4].strip()}")
                    break

    # 书签
    print(f"  ✅ 书签: {len(doc.get_toc())} 个")

    # 链接
    links = [l for l in doc[TOC_PAGE_INDEX].get_links() if l["kind"] == fitz.LINK_GOTO]
    print(f"  ✅ 目录链接: {len(links)} 个")


def main():
    if not CHAPTERS:
        print("请先配置 CHAPTERS 和 TOC_Y_POSITIONS 参数")
        return

    doc = fitz.open(INPUT_PDF)
    print(f"处理文件: {INPUT_PDF} ({doc.page_count} 页)")

    remove_headers(doc)
    if REMOVE_WATERMARK:
        remove_watermarks(doc)
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
    print(f"\n完成: {output}")


if __name__ == "__main__":
    main()
