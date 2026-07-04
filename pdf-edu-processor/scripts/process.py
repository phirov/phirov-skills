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

# 输入文件（支持以下两种形式）：
#   1. 单文件路径："/workspace/我的教辅.pdf"（推荐：保持上传原名）
#   2. 目录路径："/workspace/"（自动取该目录下第一个 PDF 文件）
# 留空时：先尝试 /workspace/<原名>.pdf，再回退到 /workspace/input.pdf
INPUT_PDF = "/workspace/"

# 输出文件路径
# 设为 None 时自动按"原文件名-整理后.pdf"规则生成（如 我的教辅.pdf → 我的教辅-整理后.pdf）
# 或显式指定路径："/workspace/my_output.pdf"
OUTPUT_PDF = None

# 页眉中需要删除的文字（任意匹配即触发）
HEADER_TEXTS = ["@建宇老师", "方法学得牛", "剑指双一流"]

# 页码偏移量：new_page = original_page - PAGE_OFFSET
# 原文目录页=7(罗马i), 内容页8→1, 9→2, ... 100→93
PAGE_OFFSET = 7

# 目录页索引（0-based）= PDF第3页 → 索引2
TOC_PAGE_INDEX = 2

# 内容页起始索引（0-based）= PDF第5页 → 索引4
CONTENT_START_INDEX = 4

# 目录页自身页码是否改为罗马数字 "i"
TOC_AS_ROMAN = True

# 是否删除水印（本文件无水印，跳过）
REMOVE_WATERMARK = False

# 跳过页眉删除的页面索引
# P1=封面(0), P2=空白(1), P3=目录(2-保留), P4=空白(3)
# 目录保留页眉以便维持原版式，其余正文页(P5=索引4起)都删除页眉
SKIP_INDICES = {0, 1, 3}

# 章节定义：[编号, 标题, 新页码, PDF索引]
# 新页码 = 原始页码 - PAGE_OFFSET
# PDF索引 = 原始页码在PDF中的0-based索引
# 注意：不再需要手动配置 x 坐标和 TOC_Y_POSITIONS，脚本自动从 PDF 提取
# 章节定义：[编号, 标题, 新页码]
# 新页码 = 原页码 - PAGE_OFFSET
# PDF 0-based 索引 = CONTENT_START_INDEX + (新页码 - 1)
#   推导公式：书签/链接指向的页 = 内容起始页 + (新页码 - 1)
#   例如：新页码=1 → 索引 4+0=4 (P5)，新页码=5 → 索引 4+4=8 (P9)
# 不再需要手动配置 PDF 索引，脚本自动推导（见 _resolve_chapters）
CHAPTERS = [
    (1,  "1.一元一次方程的解法",   1),
    (2,  "2.一元一次方程的应用",   5),
    (3,  "3.二元一次方程组解法",   9),
    (4,  "4.二元一次方程组应用",   13),
    (5,  "5.不定方程（组）解法",   17),
    (6,  "6.不定方程（组）应用",   21),
    (7,  "7.归一归总问题",         25),
    (8,  "8.还原问题",             29),
    (9,  "9.和差问题",             34),
    (10, "10.和倍问题",            38),
    (11, "11.差倍问题",            42),
    (12, "12.植树问题",            46),
    (13, "13.盈亏问题",            50),
    (14, "14.年龄问题",            54),
    (15, "15.鸡兔同笼问题",        58),
    (16, "16.平均数问题",          62),
    (17, "17.周期问题",            66),
    (18, "18.牛吃草问题",          70),
    (19, "19.分数百分数问题",      74),
    (20, "20.用比例解应用题",      79),
    (21, "21.经济问题",            83),
    (22, "22.浓度问题",            87),
    (23, "23.工程问题",            91),
]


# ============================================================
# 辅助函数
# ============================================================

def _resolve_chapters():
    """将 CHAPTERS 简写形式 [编号, 标题, 新页码] 展开为 [编号, 标题, 新页码, PDF索引(0-based)]

    推导公式：PDF索引 = CONTENT_START_INDEX + (新页码 - 1)
        - 新页码=1 → 索引 4 (P5, 内容起始页)
        - 新页码=5 → 索引 8 (P9)

    同时进行断言校验：
        - 编号必须从 1 连续递增
        - 新页码必须从 1 开始，单调递增
        - 推导出的 PDF 索引必须 < 总页数
    """
    if not CHAPTERS:
        raise ValueError("CHAPTERS 不能为空")

    # 校验原始配置结构
    for i, ch in enumerate(CHAPTERS):
        if len(ch) != 3:
            raise ValueError(
                f"CHAPTERS 第 {i+1} 项格式错误: 期望 [编号, 标题, 新页码] 3 元素, "
                f"实际 {len(ch)} 元素: {ch}"
            )

    # 推导 PDF 索引
    resolved = []
    expected_num = 1
    expected_min_page = 1
    for ch in CHAPTERS:
        num, title, new_page = ch
        pdf_idx = CONTENT_START_INDEX + (new_page - 1)

        # 校验编号连续
        if num != expected_num:
            raise ValueError(
                f"章节编号不连续: 期望 {expected_num}, 实际 {num} (标题: {title})"
            )
        expected_num += 1

        # 校验新页码单调递增
        if new_page < expected_min_page:
            raise ValueError(
                f"新页码必须单调递增: '{title}' 新页码 {new_page} < 上一章 {expected_min_page}"
            )
        expected_min_page = new_page

        resolved.append((num, title, new_page, pdf_idx))

    return resolved


def _resolve_paths():
    """智能解析输入输出 PDF 路径

    输入解析规则（INPUT_PDF 依次尝试）：
        1. 若指向已存在的 .pdf 文件 → 直接使用
        2. 若指向目录 → 取该目录下第一个 .pdf 文件
        3. 留空或路径不存在 → 报错并给出搜索结果

    输出解析规则（OUTPUT_PDF）：
        1. 若显式设置 → 使用该路径
        2. 若为 None → 在输入文件同目录下生成 "<原名>-整理后.pdf"

    返回：
        (input_path, output_path) 元组
    """
    # ---- 解析输入路径 ----
    input_path = None

    if not INPUT_PDF:
        # 留空：扫描默认 workspace 目录
        search_dirs = ["/workspace"]
    elif os.path.isfile(INPUT_PDF):
        # 是文件
        input_path = INPUT_PDF
    elif os.path.isdir(INPUT_PDF):
        # 是目录
        search_dirs = [INPUT_PDF]
    else:
        # 既不是文件也不是目录（路径不存在）
        search_dirs = [os.path.dirname(INPUT_PDF) or "/workspace"]

    if input_path is None:
        # 在搜索目录中找第一个 PDF
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if name.lower().endswith(".pdf"):
                    input_path = os.path.join(d, name)
                    break
            if input_path:
                break

    if input_path is None or not os.path.isfile(input_path):
        raise FileNotFoundError(
            f"未找到输入 PDF 文件。\n"
            f"  INPUT_PDF = {INPUT_PDF!r}\n"
            f"  搜索目录: {search_dirs}\n"
            f"  请将待处理 PDF 放到 /workspace/ 目录，或在 INPUT_PDF 中显式指定路径"
        )

    # ---- 解析输出路径 ----
    if OUTPUT_PDF:
        output_path = OUTPUT_PDF
    else:
        # 默认：同目录 + "<原名>-整理后.pdf"
        dir_name = os.path.dirname(input_path)
        base_name = os.path.basename(input_path)
        stem, ext = os.path.splitext(base_name)
        output_path = os.path.join(dir_name, f"{stem}-整理后{ext}")

    return input_path, output_path


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


def rebuild_toc(doc, resolved_chapters):
    """重建目录页 dots 和页码（overlay=True 白块覆盖 + 动态坐标提取）

    参数：
        resolved_chapters: 完整 [编号, 标题, 新页码, PDF索引(0-based)] 列表

    核心原理：
    1. 使用 get_text("dict") 自动提取每行 dots span 的精确坐标
    2. 先用 add_redact_annot + apply_redactions 彻底清除旧 dots 和旧页码文本层
    3. 用 overlay=True 的白块覆盖旧 dots + 旧页码（白块在顶层）
    4. insert_text 在白块之后调用，确保新内容在最顶层
    5. insert_y = span_y0 + 15（与旧页码基线对齐）
    """
    DOT_W = fitz.get_text_length(".", "TiRo", 14.1)
    DIGIT_W = fitz.get_text_length("0", "TiRo", 14.1)

    page0 = doc[TOC_PAGE_INDEX]
    lines_data = get_toc_lines_data(page0)

    if len(lines_data) != len(resolved_chapters):
        print(f"  ⚠ 警告: dots 行数 ({len(lines_data)}) ≠ 章节配置数 ({len(resolved_chapters)})")

    # 步骤0: 清除目录行末旧页码（数字部分），保留 dots 文本层供后续使用
    # Quark的dots+页码是同一span，redact范围仅限行末数字（x>525）避免破坏dots
    for line in lines_data:
        # 行末页码数字区域（x>525，dots span 终点 538.6 后是数字）
        # 由于 dots+pageNum 在同 span，精确切分需根据字符数估算
        # 旧页码最长2位数字，约占 x=535~545
        page0.add_redact_annot(
            fitz.Rect(530, line["y0"], 545, line["y1"]), text=""
        )
    page0.apply_redactions()

    # 步骤1: 画白块覆盖旧 dots + 旧页码（overlay=True，确保在旧内容之上）
    for line in lines_data:
        page0.draw_rect(
            fitz.Rect(line["x0"] - 2, line["y0"], 545, line["y1"]),
            fill=(1, 1, 1), color=None, overlay=True,
        )

    # 步骤2: 插入新 dots 和页码（在 draw_rect 之后调用，确保在最顶层）
    for i, line in enumerate(lines_data):
        if i >= len(resolved_chapters):
            break
        new_page = resolved_chapters[i][2]
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


def add_navigation(doc, resolved_chapters):
    """添加书签和目录跳转链接（使用动态提取的行坐标）

    参数：
        resolved_chapters: 完整 [编号, 标题, 新页码, PDF索引(0-based)] 列表
    """
    page0 = doc[TOC_PAGE_INDEX]
    lines_data = get_toc_lines_data(page0)

    if len(lines_data) != len(resolved_chapters):
        print(f"  ⚠ 警告: dots 行数 ({len(lines_data)}) ≠ 章节配置数 ({len(resolved_chapters)})")

    # 校验：推导出的 PDF 索引不能超出文档范围
    for num, title, new_page, pdf_idx in resolved_chapters:
        if pdf_idx < 0 or pdf_idx >= doc.page_count:
            raise ValueError(
                f"章节 {num} '{title}' 推导的 PDF 索引 {pdf_idx} 超出范围 "
                f"[0, {doc.page_count-1}]。请检查 CONTENT_START_INDEX={CONTENT_START_INDEX} "
                f"和新页码 {new_page} 是否匹配实际 PDF 结构。"
            )

    # 书签：pdf_idx + 1 = 1-based PDF 页码
    toc_list = [[1, title, pdf_idx + 1] for _, title, _, pdf_idx in resolved_chapters]
    doc.set_toc(toc_list)

    # TOC 链接：使用动态提取的行坐标
    for i, (_, title, new_page, pdf_idx) in enumerate(resolved_chapters):
        if i < len(lines_data):
            line = lines_data[i]
            page0.insert_link({
                "kind": fitz.LINK_GOTO,
                "from": fitz.Rect(55, line["y0"] - 4, 545, line["y1"] + 2),
                "page": pdf_idx,
            })

    print(f"[5/5] 导航已添加 (书签 {len(toc_list)} 个, 链接 {len(resolved_chapters)} 个)")


def verify(doc, resolved_chapters):
    """验证处理结果

    参数：
        resolved_chapters: 完整 [编号, 标题, 新页码, PDF索引(0-based)] 列表
    """
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

    # 链接精准性验证：每个链接的目标页应包含对应章节标题
    print("\n  --- 链接精准性校验 ---")
    mismatch_count = 0
    for i, link in enumerate(links):
        if i >= len(resolved_chapters):
            break
        _, expected_title, _, _ = resolved_chapters[i]
        target_idx = link["page"]
        if target_idx < 0 or target_idx >= doc.page_count:
            print(f"  ⚠ link{i} 目标页 {target_idx} 超出范围")
            mismatch_count += 1
            continue
        # 取目标页文本，截取章节编号部分
        target_text = doc[target_idx].get_text()
        # 提取章节编号，如 "1." "12." "23."
        num_str = str(i + 1) + "."
        if num_str in target_text:
            # 进一步校验：章节标题前 5 个汉字是否匹配
            short_title = expected_title.split(".", 1)[1][:5] if "." in expected_title else expected_title[:5]
            if short_title in target_text:
                pass  # 匹配，静默通过
            else:
                print(f"  ⚠ link{i} → P{target_idx+1}: 编号匹配但标题不符 (期望 '{short_title}')")
                mismatch_count += 1
        else:
            print(f"  ⚠ link{i} → P{target_idx+1}: 未找到章节编号 '{num_str}'")
            mismatch_count += 1
    if mismatch_count == 0:
        print(f"  ✅ 所有 {len(links)} 个链接均精准命中目标章节")


def main():
    # 1. 解析并校验 CHAPTERS（自动推导 PDF 索引）
    resolved_chapters = _resolve_chapters()
    print(f"已加载 {len(resolved_chapters)} 个章节，自动推导 PDF 索引：")
    for num, title, new_page, pdf_idx in resolved_chapters[:3]:
        print(f"   第{num}章 新页码={new_page} → PDF P{pdf_idx+1}（索引 {pdf_idx}）")
    if len(resolved_chapters) > 3:
        print(f"   ... 共 {len(resolved_chapters)} 项")
    print()

    # 2. 智能解析输入输出路径
    input_path, output_path = _resolve_paths()
    print(f"输入文件: {input_path}")
    print(f"输出文件: {output_path}")
    print()

    doc = fitz.open(input_path)
    print(f"处理文件: {input_path} ({doc.page_count} 页)")

    # 3. 校验：内容起始索引必须 < 总页数
    if CONTENT_START_INDEX >= doc.page_count:
        raise ValueError(
            f"CONTENT_START_INDEX={CONTENT_START_INDEX} 超出文档范围（共 {doc.page_count} 页）"
        )

    # 4. 注意：先删水印再删页眉，避免 redact 改写内容流导致水印正则失效
    if REMOVE_WATERMARK:
        remove_watermarks(doc)
    remove_headers(doc, skip_indices=SKIP_INDICES)
    renumber_pages(doc, content_start_index=CONTENT_START_INDEX)
    rebuild_toc(doc, resolved_chapters)
    add_navigation(doc, resolved_chapters)

    # 5. 保存
    tmp = output_path + ".tmp"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, output_path)

    # 6. 验证
    doc2 = fitz.open(output_path)
    verify(doc2, resolved_chapters)
    doc2.close()

    orig_size = os.path.getsize(input_path)
    new_size = os.path.getsize(output_path)
    print(f"\n✅ 完成: {output_path}")
    print(f"   原始大小: {orig_size / 1024:.0f} KB → 处理后: {new_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
