#!/usr/bin/env python3
"""
生成 3 种页脚格式的样例 PDF 用于测试 pdf-edu-processor 目录页罗马数字改造。

样例：
  - chinese: 目录页脚 "第7页 共20页"，正文 "第8页 共20页"
  - numeric: 目录页脚 "7 / 20"，正文 "8 / 20"
  - english: 目录页脚 "7 of 20"，正文 "8 of 20"
"""

import os
import sys
import fitz

CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
PAGE_W, PAGE_H = fitz.paper_size("a4")
FOOTER_Y = PAGE_H - 30  # PDF 坐标系从底部算，底部 30pt 留页脚


def make_pdf(out_path, footer_format):
    """生成测试 PDF（用 PyMuPDF 直接写，绕过 reportlab 的 OTC 限制）"""
    doc = fitz.open()

    # 注册 CJK 字体
    if footer_format == "chinese":
        try:
            doc.insert_font(fontname="noto-cjk", fontfile=CJK_FONT)
            font_name = "noto-cjk"
        except Exception:
            font_name = "helv"
    else:
        font_name = "helv"

    # P1: 封面
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_text((PAGE_W / 2 - 100, PAGE_H / 2), f"测试 PDF - {footer_format}",
                     fontname=font_name, fontsize=20, color=(0, 0, 0))

    # P2: 空白
    doc.new_page(width=PAGE_W, height=PAGE_H)

    # P3: 目录
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_text((PAGE_W / 2 - 30, PAGE_H - 60), "目录",
                     fontname=font_name, fontsize=18, color=(0, 0, 0))
    chapters = [
        ("1. 几何图形的认识", 1),
        ("2. 几何图形找规律", 5),
        ("3. 角度的计算方法", 9),
    ]
    y = PAGE_H - 110
    for title, p in chapters:
        page.insert_text((50, y), title, fontname=font_name, fontsize=12, color=(0, 0, 0))
        page.insert_text((PAGE_W - 80, y), f"{p}", fontname="helv", fontsize=12, color=(0, 0, 0))
        y -= 25

    # 目录页页脚
    if footer_format == "chinese":
        footer = "第7页 共20页"
    elif footer_format == "numeric":
        footer = "7 / 20"
    elif footer_format == "english":
        footer = "7 of 20"
    page.insert_text((PAGE_W / 2 - 30, FOOTER_Y), footer,
                     fontname=font_name, fontsize=10, color=(0, 0, 0))

    # P4: 空白
    doc.new_page(width=PAGE_W, height=PAGE_H)

    # P5~P20: 正文 16 页（原页码 8~23，偏移 7 后为新页 1~16）
    for orig_page in range(8, 24):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_text((50, PAGE_H - 50), f"正文第{orig_page}页",
                         fontname=font_name, fontsize=14, color=(0, 0, 0))
        if footer_format == "chinese":
            footer = f"第{orig_page}页 共20页"
            page.insert_text((PAGE_W / 2 - 30, FOOTER_Y), footer,
                             fontname=font_name, fontsize=10, color=(0, 0, 0))
        elif footer_format == "numeric":
            footer = f"{orig_page} / 20"
            page.insert_text((PAGE_W / 2 - 20, FOOTER_Y), footer,
                             fontname="helv", fontsize=10, color=(0, 0, 0))
        elif footer_format == "english":
            footer = f"{orig_page} of 20"
            page.insert_text((PAGE_W / 2 - 30, FOOTER_Y), footer,
                             fontname="helv", fontsize=10, color=(0, 0, 0))

    doc.save(out_path)
    doc.close()
    print(f"  已生成: {out_path}")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pdf_test_fixtures"
    os.makedirs(out_dir, exist_ok=True)
    for fmt in ["chinese", "numeric", "english"]:
        out = os.path.join(out_dir, f"sample_{fmt}.pdf")
        make_pdf(out, fmt)
    print(f"\n所有测试样例已生成到 {out_dir}/")
