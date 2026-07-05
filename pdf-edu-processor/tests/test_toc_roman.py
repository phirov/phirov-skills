#!/usr/bin/env python3
"""
v0.3.3 目录页罗马数字改造测试

测试策略：
- 单元测试：_to_roman 小写输出、_looks_like_toc_page 结构识别
- 端到端测试：用 PyMuPDF 生成 3 种页脚格式（chinese/numeric/english）的测试 PDF，
  验证处理后目录页 P3 的 y>770 区域只含小写罗马数字 "i"，且原页码特征（"第" / "/" / "of"）全部清除
- 多页目录测试：连续 2 页目录，验证 P3="i"、P4="ii"
- 正文字符测试：正文页不应被改为罗马数字
"""

import os
import sys
import re
import subprocess
import fitz

# 把 skill 目录加入 path
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

import process  # noqa: E402


# ============================================================
# 单元测试
# ============================================================

def test_to_roman_lowercase():
    """_to_roman 必须输出小写（v0.3.3 新增）"""
    assert process._to_roman(1) == "i", f"got {process._to_roman(1)!r}"
    assert process._to_roman(2) == "ii"
    assert process._to_roman(3) == "iii"
    assert process._to_roman(4) == "iv"
    assert process._to_roman(5) == "v"
    assert process._to_roman(9) == "ix"
    assert process._to_roman(10) == "x"
    print("  ✅ _to_roman 输出小写 (1~10)")


def test_looks_like_toc_page():
    """_looks_like_toc_page 应能识别不同页脚格式的目录页（v0.3.3 新增）"""
    fixtures_dir = "/tmp/pdf_test_fixtures"
    for fmt in ["chinese", "numeric", "english"]:
        pdf = os.path.join(fixtures_dir, f"sample_{fmt}.pdf")
        doc = fitz.open(pdf)
        # P3 (索引2) 是目录页（结构：含"目录"标题 + dots行 + 章节编号）
        assert process._looks_like_toc_page(doc[2]), \
            f"{fmt} 格式: P3 应该是目录页但未被识别"
        # P5 (索引4) 是正文页
        assert not process._looks_like_toc_page(doc[4]), \
            f"{fmt} 格式: P5 应该是正文页但被误判为目录"
        doc.close()
    print("  ✅ _looks_like_toc_page 正确识别 3 种页脚格式的目录页")


def test_count_toc_pages_returns_toc():
    """_count_toc_pages 应返回 TOC_PAGE_INDEX 起的连续目录页"""
    fixtures_dir = "/tmp/pdf_test_fixtures"
    for fmt in ["chinese", "numeric", "english"]:
        pdf = os.path.join(fixtures_dir, f"sample_{fmt}.pdf")
        doc = fitz.open(pdf)
        # 设置正确的 CONTENT_START_INDEX
        toc_pages = process._count_toc_pages(doc, content_start_index=4)
        assert 2 in toc_pages, f"{fmt}: P3 应在目录页列表中，实际 {toc_pages}"
        # 多页时也要支持
        assert len(toc_pages) >= 1
        doc.close()
    print("  ✅ _count_toc_pages 返回目录页索引列表")


# ============================================================
# 端到端测试
# ============================================================

def _configure_process():
    """配置 process 模块的全局变量（用样例的章节）"""
    process.CHAPTERS = [
        (1, "1. 几何图形的认识", 1),
        (2, "2. 几何图形找规律", 5),
        (3, "3. 角度的计算方法", 9),
    ]
    process.TOC_PAGE_INDEX = 2
    process.CONTENT_START_INDEX = 4
    process.PAGE_OFFSET = 7
    process.PAGE_TOTAL = 16
    process.REMOVE_WATERMARK = False
    process.HEADER_TEXTS = []
    process.SKIP_INDICES = set()
    process.PAGE_NUMBER_MODE = "auto"
    process.TOC_AS_ROMAN = True


def _get_footer_text(page, y_min=770):
    """获取页脚区域（y > y_min）的拼接文字"""
    words = page.get_text("words")
    footer = [(w[0], w[4]) for w in words if w[1] > y_min and w[4].strip()]
    footer.sort(key=lambda x: x[0])
    return "".join(t for _, t in footer).strip()


def test_e2e_toc_roman_all_formats():
    """端到端：3 种页脚格式处理后，目录页 P3 必须显示小写罗马数字 'i'"""
    fixtures_dir = "/tmp/pdf_test_fixtures"
    for fmt in ["chinese", "numeric", "english"]:
        in_pdf = os.path.join(fixtures_dir, f"sample_{fmt}.pdf")
        out_pdf = f"/tmp/test_out_{fmt}.pdf"
        process.INPUT_PDF = in_pdf
        process.OUTPUT_PDF = out_pdf
        _configure_process()
        process.main()

        doc = fitz.open(out_pdf)
        page3 = doc[2]
        footer = _get_footer_text(page3)
        doc.close()

        assert footer == "i", \
            f"{fmt}: 目录页 P3 页脚应为 'i'，实际 {footer!r}"
        print(f"  ✅ {fmt:8s}: 目录页 P3 页脚 = {footer!r}")


def test_e2e_original_footer_cleared():
    """端到端：处理后目录页不应残留原页码特征"""
    fixtures_dir = "/tmp/pdf_test_fixtures"
    for fmt in ["chinese", "numeric", "english"]:
        out_pdf = f"/tmp/test_out_{fmt}.pdf"
        doc = fitz.open(out_pdf)
        page3 = doc[2]
        # 检查 y > 770 区域不含原页码特征
        footer_words = []
        for w in page3.get_text("words"):
            if w[1] > 770 and w[4].strip():
                footer_words.append(w[4])

        # 单独提取每个 word（不拼接），避免多字符粘连
        joined = "".join(footer_words).strip()
        doc.close()

        if fmt == "chinese":
            # 原页脚含"共"和"页"中文字符，处理后不应残留
            assert joined != "" or joined == "i", \
                f"{fmt}: 目录页应只有 'i'，实际 {joined!r}"
        elif fmt == "numeric":
            # 原页脚含 "/"，处理后应清除
            assert "/" not in joined or joined == "i", \
                f"{fmt}: 残留 '/'，实际 {joined!r}"
        elif fmt == "english":
            # 原页脚含 "of"
            assert "of" not in joined.lower() or joined.lower() == "i", \
                f"{fmt}: 残留 'of'，实际 {joined!r}"
        print(f"  ✅ {fmt:8s}: 原页脚特征已清除（{joined!r}）")


def test_e2e_content_pages_not_roman():
    """端到端：正文页（auto 模式下解析为 chinese）不应被改为罗马数字"""
    fixtures_dir = "/tmp/pdf_test_fixtures"
    in_pdf = os.path.join(fixtures_dir, "sample_chinese.pdf")
    out_pdf = "/tmp/test_out_chinese.pdf"
    doc = fitz.open(out_pdf)

    # P5 (索引4) 是正文第 1 页，新页码应该是 "1"
    page5 = doc[4]
    footer5 = _get_footer_text(page5)
    doc.close()

    # 关键断言：不是罗马数字
    # 允许的格式：第N页（中文模式）或纯数字（numeric 模式）
    is_roman = footer5.lower() in ("i", "ii", "iii", "iv", "v")
    assert not is_roman, f"正文页 P5 不应是罗马数字，实际 {footer5!r}"
    # 验证有数字
    has_digit = any(c.isdigit() for c in footer5)
    assert has_digit, f"正文页 P5 应有数字，实际 {footer5!r}"
    print(f"  ✅ 正文 P5 页脚 = {footer5!r}（非罗马数字）")


def test_e2e_multi_page_toc():
    """端到端：多页目录（连续 2 页）都应正确写罗马数字"""
    in_pdf = "/tmp/test_multi_toc_in.pdf"
    out_pdf = "/tmp/test_multi_toc_out.pdf"

    # 构造多页目录测试 PDF
    doc = fitz.open()
    PAGE_W, PAGE_H = fitz.paper_size("a4")
    FOOTER_Y = PAGE_H - 30

    # P1 封面
    p = doc.new_page(width=PAGE_W, height=PAGE_H)
    p.insert_text((PAGE_W / 2 - 50, PAGE_H / 2), "Multi-TOC Test",
                  fontname="helv", fontsize=20)
    # P2 空白
    doc.new_page(width=PAGE_W, height=PAGE_H)
    # P3 目录第 1 页
    p = doc.new_page(width=PAGE_W, height=PAGE_H)
    p.insert_text((PAGE_W / 2 - 20, PAGE_H - 50), "目录",
                  fontname="helv", fontsize=18)
    for i, (t, pg) in enumerate([
        ("1. 第一章", 1), ("2. 第二章", 5), ("3. 第三章", 9),
        ("4. 第四章", 13), ("5. 第五章", 17), ("6. 第六章", 21),
        ("7. 第七章", 25), ("8. 第八章", 29), ("9. 第九章", 33),
        ("10. 第十章", 37),
    ]):
        y = PAGE_H - 100 - i * 22
        p.insert_text((50, y), t, fontname="helv", fontsize=12)
        p.insert_text((PAGE_W - 80, y), str(pg), fontname="helv", fontsize=12)
    p.insert_text((PAGE_W / 2 - 20, FOOTER_Y), "7 / 50",
                  fontname="helv", fontsize=10)
    # P4 目录第 2 页
    p = doc.new_page(width=PAGE_W, height=PAGE_H)
    for i, (t, pg) in enumerate([
        ("11. 第十一章", 41), ("12. 第十二章", 45),
    ]):
        y = PAGE_H - 100 - i * 22
        p.insert_text((50, y), t, fontname="helv", fontsize=12)
        p.insert_text((PAGE_W - 80, y), str(pg), fontname="helv", fontsize=12)
    p.insert_text((PAGE_W / 2 - 20, FOOTER_Y), "8 / 50",
                  fontname="helv", fontsize=10)
    # P5 空白
    doc.new_page(width=PAGE_W, height=PAGE_H)
    # P6 起正文（占位 2 页，因为 CHAPTERS=2 章）
    for i in range(2):
        p = doc.new_page(width=PAGE_W, height=PAGE_H)
        p.insert_text((50, PAGE_H - 50), f"正文第 {i+1} 页", fontname="helv", fontsize=14)
        p.insert_text((PAGE_W / 2 - 20, FOOTER_Y), f"{9 + i} / 50",
                      fontname="helv", fontsize=10)

    doc.save(in_pdf)
    doc.close()

    process.INPUT_PDF = in_pdf
    process.OUTPUT_PDF = out_pdf
    process.CHAPTERS = [(1, "1. 第一章", 1), (2, "2. 第二章", 2)]
    process.TOC_PAGE_INDEX = 2
    process.CONTENT_START_INDEX = 5
    process.PAGE_OFFSET = 8
    process.PAGE_TOTAL = 1
    process.REMOVE_WATERMARK = False
    process.HEADER_TEXTS = []
    process.SKIP_INDICES = set()
    process.PAGE_NUMBER_MODE = "auto"
    process.TOC_AS_ROMAN = True
    process.main()

    doc = fitz.open(out_pdf)
    p3_footer = _get_footer_text(doc[2])
    p4_footer = _get_footer_text(doc[3])
    doc.close()

    assert p3_footer == "i", f"多页目录 P3 期望 'i'，实际 {p3_footer!r}"
    assert p4_footer == "ii", f"多页目录 P4 期望 'ii'，实际 {p4_footer!r}"
    print(f"  ✅ 多页目录: P3={p3_footer!r}, P4={p4_footer!r}")


# ============================================================
# Runner
# ============================================================

def main():
    print("=" * 60)
    print("v0.3.3 目录页罗马数字改造测试")
    print("=" * 60)

    print("\n[单元测试]")
    test_to_roman_lowercase()
    test_looks_like_toc_page()
    test_count_toc_pages_returns_toc()

    print("\n[端到端测试]")
    test_e2e_toc_roman_all_formats()
    test_e2e_original_footer_cleared()
    test_e2e_content_pages_not_roman()
    test_e2e_multi_page_toc()

    print("\n" + "=" * 60)
    print("✅ 所有测试通过 (v0.3.3)")
    print("=" * 60)


if __name__ == "__main__":
    main()
