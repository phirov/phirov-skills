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

# 页码模式（v0.3.2 新增）：
#   "chinese" - 中文页脚 "第N页 共M页"（v0.3.1 行为，使用 NotoSansCJK 字体）
#   "numeric" - 纯数字页脚 "N" / "N/M" / "N of M"（使用 TiRo 字体，文件更小）
#   "auto"    - 自动扫描前 MODE_DETECT_SAMPLES 页页脚识别格式（默认）
PAGE_NUMBER_MODE = "auto"

# auto 模式扫描的样本页数（建议 5）
MODE_DETECT_SAMPLES = 5

# 总页数显式覆盖：None = 自动从页脚推断；整数 = 强制使用
# 用于 PDF 本身未含"共N页"标记的场景（如纯数字"N"页脚）
PAGE_TOTAL = None

# 目录页索引（0-based）= PDF第3页 → 索引2
TOC_PAGE_INDEX = 2

# 内容页起始索引（0-based）= PDF第5页 → 索引4
CONTENT_START_INDEX = 4

# 目录页自身页码是否改为罗马数字 "i"
TOC_AS_ROMAN = True

# 是否删除水印（本文件无水印，跳过）
REMOVE_WATERMARK = True

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
    (1,  "1.几何图形的认识",            1),
    (2,  "2.几何图形找规律",            9),
    (3,  "3.角度的计算方法",           15),
    (4,  "4.几何的空间想象",           21),
    (5,  "5.巧求周长",                 25),
    (6,  "6.图形的分割与拼接",         32),
    (7,  "7.平移、旋转及割补",         38),
    (8,  "8.不规则图形的面积",         43),
    (9,  "9.格点图形的面积",           48),
    (10, "10.三角形面积与底高的关系",  53),
    (11, "11.相似三角形",              59),
    (12, "12.四边形模型",              64),
    (13, "13.梯形模型",                69),
    (14, "14.燕尾模型",                74),
    (15, "15.共角模型",                79),
    (16, "16.圆与扇形",                84),
    (17, "17.长方体及正方体",          90),
    (18, "18.圆柱与圆锥",              96),
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
        r'q\s+1\s+0\s+0\s+-1\s+0\s+0\s+cm\s+BT\s+/FT(?:8|22).*?/GS13\s+gs.*?ET\s+Q',
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
    """重编号目录页和内容页页码（v0.3.2 双模式：chinese/numeric/auto）

    v0.3.1 修复：原脚本用 isdigit() 判断页码词，但 Quark 生成的 PDF 把"第N页"分成
    多个词（如 "第8"、"页共107"、"页"），纯数字词根本不存在，导致页码重编号
    静默失效。

    v0.3.2 增强：
      1. 支持 chinese（"第N页 共M页"）和 numeric（"N" / "N/M" / "N of M"）两种页脚格式
      2. auto 模式自动扫描前 MODE_DETECT_SAMPLES 页页脚识别格式
      3. numeric 模式使用 TiRo 字体（不嵌 CJK，文件体积小）
      4. 多页目录支持罗马数字 i/ii/iii/...
      5. PAGE_TOTAL 手动覆盖总页数
    """
    # 优先使用系统 NotoSansCJK 字体支持中文"第/页"；否则回退到 TiRo（仅数字）
    FONT_FILE = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    try:
        if not os.path.isfile(FONT_FILE):
            FONT_FILE = None
    except Exception:
        FONT_FILE = None

    # 模式解析
    global _RESOLVED_MODE, _RESOLVED_TOTAL
    _RESOLVED_MODE, _RESOLVED_TOTAL = _resolve_page_mode(doc, content_start_index)
    if PAGE_TOTAL is not None:
        # 用户手动覆盖：直接当作"新总数"，不再偏移
        _RESOLVED_TOTAL = PAGE_TOTAL
    elif _RESOLVED_TOTAL is not None:
        # 从旧页脚推断的旧总数：按 PAGE_OFFSET 同步到新总数
        _RESOLVED_TOTAL = _RESOLVED_TOTAL - PAGE_OFFSET

    # 目录页处理（v0.3.3 重构：先扫描再 redact，与正文页模式解耦）
    # 关键：必须在 redact 之前扫描，否则页脚被清空，目录页无法被识别
    toc_pages = _count_toc_pages(doc, content_start_index)

    if not toc_pages:
        print(f"  ⚠ 警告: 未识别到目录页 (TOC_PAGE_INDEX={TOC_PAGE_INDEX}, "
              f"CONTENT_START_INDEX={content_start_index})")
    else:
        # 步骤 1: 清除所有目录页底部原始页码（不论原页码格式）
        for idx in toc_pages:
            page0 = doc[idx]
            for w in page0.get_text("words"):
                if w[1] > 770 and w[4].strip():
                    page0.add_redact_annot(fitz.Rect(w[0] - 5, w[1] - 2, w[2] + 5, w[3] + 2))
            page0.apply_redactions()

        # 步骤 2: 写入新页码
        if TOC_AS_ROMAN:
            # TOC_AS_ROMAN 强制覆盖：不论 _RESOLVED_MODE 是 chinese/numeric/auto，
            # 目录页一律改写为罗马数字 i/ii/iii/...
            for k, idx in enumerate(toc_pages):
                roman = _to_roman(k + 1)
                doc[idx].insert_text(
                    fitz.Point(294, 797), roman,
                    fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
                )
        elif _RESOLVED_MODE == "numeric":
            # numeric + 非 roman：把目录页当作内容页处理
            for idx in toc_pages:
                old_num, old_total = _match_footer_token_extended(doc[idx])
                if old_num is not None:
                    new_num = old_num - PAGE_OFFSET
                    if new_num >= 1:
                        new_total = (old_total - PAGE_OFFSET) if old_total is not None else None
                        if new_total is None and _RESOLVED_TOTAL is not None:
                            new_total = _RESOLVED_TOTAL
                        _write_numeric_page(doc[idx], new_num, new_total)
        # chinese + 非 roman：目录页不重编号（保持原中文页码 7/8/...）

    # 内容页
    count = 0
    for i in range(content_start_index, doc.page_count):
        page = doc[i]
        old_num, old_total = _match_footer_token_extended(page)
        if old_num is None:
            continue
        new_num = old_num - PAGE_OFFSET
        if new_num < 1:
            continue

        if _RESOLVED_MODE == "chinese":
            _write_chinese_page(page, new_num, _RESOLVED_TOTAL, FONT_FILE)
        else:
            new_total = (old_total - PAGE_OFFSET) if old_total is not None else None
            if new_total is None and _RESOLVED_TOTAL is not None:
                new_total = _RESOLVED_TOTAL
            _write_numeric_page(page, new_num, new_total)
        count += 1

    print(f"[3/5] 页码已重编号 (mode={_RESOLVED_MODE}, total={_RESOLVED_TOTAL}, count={count})")


# ============================================================
# v0.3.2 新增：双模式页码辅助函数
# ============================================================

# 4 种页脚格式的正则（按优先级）
_FOOTER_PATTERNS = [
    # 1. 中文复合：第N页 / 第N页 共M页
    re.compile(r'^第(\d+)页(\s*共(\d+)页)?$'),
    # 2. 数字斜杠：N/M
    re.compile(r'^(\d+)\s*/\s*(\d+)$'),
    # 3. 英文 of：N of M
    re.compile(r'^(\d+)\s+of\s+(\d+)$', re.IGNORECASE),
    # 4. 纯数字：N
    re.compile(r'^(\d+)$'),
]


def _collect_footer_text(page):
    """收集页脚区域（y > 770）所有词，按 x 坐标拼接成单行字符串。
    返回 (full_text, [(x_center, original_text), ...])。
    """
    words = page.get_text("words")
    footer = [(w[0], w[4]) for w in words if w[1] > 770 and w[4].strip()]
    if not footer:
        return "", []
    footer.sort(key=lambda x: x[0])  # 按 x 排序
    full_text = "".join(t for _, t in footer)
    return full_text, footer


def _match_footer_token(page):
    """从页面页脚区域提取当前页码数字。
    返回 int 或 None（未匹配）。
    匹配 4 种格式：第N页 / N/M / N of M / N（Quark 生成的 PDF 中"第N页"常被拆成多词，需拼接）
    """
    full_text, _ = _collect_footer_text(page)
    if not full_text:
        return None
    # 优先级：复合模式（带"页"）→ 数字模式
    if "页" in full_text:
        m = _FOOTER_PATTERNS[0].match(full_text)
        if m:
            return int(m.group(1))
    else:
        for pat in _FOOTER_PATTERNS[1:3]:
            m = pat.match(full_text)
            if m:
                return int(m.group(1))
        m = _FOOTER_PATTERNS[3].match(full_text)
        if m:
            return int(m.group(1))
    return None


def _match_footer_token_extended(page):
    """从页面页脚区域提取 (当前页码, 总页数)。
    返回 (int, int|None)。
    """
    full_text, _ = _collect_footer_text(page)
    if not full_text:
        return None, None
    if "页" in full_text:
        m = _FOOTER_PATTERNS[0].match(full_text)
        if m:
            return int(m.group(1)), (int(m.group(3)) if m.group(3) else None)
    else:
        for pat in _FOOTER_PATTERNS[1:3]:
            m = pat.match(full_text)
            if m:
                return int(m.group(1)), int(m.group(2))
        m = _FOOTER_PATTERNS[3].match(full_text)
        if m:
            return int(m.group(1)), None
    return None, None


def _resolve_page_mode(doc, content_start_index):
    """根据 PAGE_NUMBER_MODE 返回 (mode, total)。

    - "chinese" / "numeric"：直接返回 (mode, PAGE_TOTAL)
    - "auto"：扫描前 MODE_DETECT_SAMPLES 个内容页（含目录页）页脚识别格式
        1) 命中 ^第\\d+页 或包含 "页" 字 → ("chinese", total_from_共N页)
        2) 命中 ^\\d+$ 或 ^\\d+/\\d+$ 或 ^\\d+\\s*of\\s*\\d+$ → ("numeric", total_from_denom)
        3) 都没命中 → 默认 "chinese"（向后兼容）
    """
    if PAGE_NUMBER_MODE in ("chinese", "numeric"):
        return PAGE_NUMBER_MODE, PAGE_TOTAL

    # auto 模式
    scan_range = list(range(min(MODE_DETECT_SAMPLES, doc.page_count)))
    for i in scan_range:
        old_num, old_total = _match_footer_token_extended(doc[i])
        if old_num is None:
            continue
        # 检测到"第N页"格式 → chinese
        full_text, _ = _collect_footer_text(doc[i])
        if "页" in full_text:
            return "chinese", old_total
        # 否则 numeric
        return "numeric", old_total

    # 全部未匹配，默认 chinese（向后兼容）
    return "chinese", PAGE_TOTAL


def _to_roman(n):
    """1-based 整数 → 小写罗马数字（支持 1..3999）

    目录页页码惯例为小写（i, ii, iii），与大写（I, II, III）含义相同。
    返回小写形式以匹配学术/排版惯例。
    """
    if n < 1:
        return str(n)
    vals = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'),
            (100, 'c'), (90, 'xc'), (50, 'l'), (40, 'xl'),
            (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def _looks_like_toc_page(page):
    """结构特征识别：判断当前页是否是目录页

    v0.3.3 新增：原 _count_toc_pages 仅靠页脚匹配"第N页"格式识别目录页，
    导致原页码格式是纯数字（如 "8" / "8/100"）或英文 "8 of 100" 的目录页
    不被识别，TOC_AS_ROMAN 失效。

    现采用结构特征识别（与页脚格式无关）：
        1) 含"目录"标题（最常见，允许 PyMuPDF 提取的 CJK 错码 ·/□）
        2) 含 dots 行（ASCII "...." 或 CJK "·" 或 "□"）
        3) 含数字编号章节（"1." / "12."）
        满足任意两条即判定为目录页
    """
    text = page.get_text()
    if not text:
        return False

    # 特征1：含"目录"标题（精确 + 容错：PyMuPDF 对 CJK 字体解码异常时 "目录"→"··"）
    has_toc_title = bool(re.search(r'^\s*目\s*录\s*$', text, re.MULTILINE)) or \
                    bool(re.search(r'^\s*··\s*$', text, re.MULTILINE)) or \
                    bool(re.search(r'^\s*□□\s*$', text, re.MULTILINE)) or \
                    bool(re.search(r'^\s*\?\?\s*$', text, re.MULTILINE)) or \
                    ("目录" in text) or ("Contents" in text) or ("CONTENTS" in text)

    # 特征2：含 dots 行（ASCII dots 或 CJK 中圆点 ·）
    has_dots = ("...." in text) or ("····" in text) or ("·" * 4 in text) or ("..." in text and len(text) > 200)

    # 特征3：含章节编号（起始位置为 "数字.")
    has_chapter_num = bool(re.search(r'^\s*\d{1,2}\.\s*\S', text, re.MULTILINE))

    # 特征4：含页码范围（行末 2-3 位数字，跟在 dots 后）—— 兜底识别
    has_page_nums = bool(re.search(r'\.{2,}\s*\d{1,3}\s*$', text, re.MULTILINE))

    score = sum([has_toc_title, has_dots, has_chapter_num, has_page_nums])
    return score >= 2


def _count_toc_pages(doc, content_start_index):
    """从 TOC_PAGE_INDEX 起向后扫描，识别连续目录页范围。

    v0.3.3 改造：不再依赖页脚格式匹配（"第N页"），改用结构特征识别，
    兼容 chinese / numeric / auto 模式下所有原页码格式的目录页。

    返回目录页索引列表（含 TOC_PAGE_INDEX 本身）。
    """
    toc_pages = []
    for i in range(TOC_PAGE_INDEX, content_start_index):
        if _looks_like_toc_page(doc[i]):
            toc_pages.append(i)
        else:
            # 遇到非目录页即停止
            break
    return toc_pages


def _write_chinese_page(page, new_num, total, font_file):
    """写入中文页码 "第N页 [共M页]"，居中。

    - font_file 非空：用 NotoSansCJK 字体嵌入中文
    - font_file 为空：降级用 TiRo 字体（仅显示数字，"第/页"无法显示）
    """
    if total is not None:
        full_text = f"第{new_num}页 共{total}页"
    else:
        full_text = f"第{new_num}页"

    # 行级 redact（清除整段页脚）
    for w in page.get_text("words"):
        if w[1] > 770:
            page.add_redact_annot(fitz.Rect(w[0] - 3, w[1] - 3, w[2] + 3, w[3] + 3))
    page.apply_redactions()

    # 居中（用 TiRo 估算宽度，NotoSansCJK 与 TiRo 字符宽度近似）
    DIGIT_W = fitz.get_text_length("0", "TiRo", fontsize=10.0)
    CN_W = fitz.get_text_length("页", "TiRo", fontsize=10.0)
    # 中文字符宽度约等于数字宽度
    char_w = (DIGIT_W + CN_W) / 2
    nw = len(full_text) * char_w
    cx = 297.5

    if font_file:
        page.insert_text(
            fitz.Point(cx - nw / 2, 798), full_text,
            fontname="noto", fontsize=10.0, color=(0, 0, 0),
            fontfile=font_file,
        )
    else:
        page.insert_text(
            fitz.Point(cx - nw / 2, 798), full_text,
            fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
        )


def _write_numeric_page(page, new_num, new_total=None):
    """写入纯数字页码 "N" 或 "N / M"，居中（TiRo 字体，不嵌 CJK）。"""
    if new_total is not None:
        text = f"{new_num} / {new_total}"
    else:
        text = str(new_num)

    # 行级 redact
    for w in page.get_text("words"):
        if w[1] > 770:
            page.add_redact_annot(fitz.Rect(w[0] - 3, w[1] - 3, w[2] + 3, w[3] + 3))
    page.apply_redactions()

    DIGIT_W = fitz.get_text_length("0", "TiRo", 9.0)
    nw = len(text) * DIGIT_W
    cx = 297.5
    page.insert_text(
        fitz.Point(cx - nw / 2, 798), text,
        fontname="TiRo", fontsize=9.0, color=(0, 0, 0),
    )


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

    # 目录页页码（v0.3.2 + v0.3.3：多页目录全部检查）
    page_toc = doc[TOC_PAGE_INDEX]
    mode = globals().get("_RESOLVED_MODE", "chinese")
    toc_pages = _count_toc_pages(doc, CONTENT_START_INDEX)
    for k, idx in enumerate(toc_pages):
        page_toc = doc[idx]
        found = False
        for w in page_toc.get_text("words"):
            if w[1] > 780 and w[4].strip():
                actual = w[4].strip()
                if TOC_AS_ROMAN:
                    # 罗马数字：i, ii, iii, iv, v（小写，1~5）
                    expected = _to_roman(k + 1)
                    ok = actual.lower() == expected
                    print(f"  {'✅' if ok else '⚠'} 目录页 P{idx+1} 页码: '{actual}' "
                          f"(期望罗马数字 '{expected}', mode={mode})")
                else:
                    # 非 roman：chinese 期望"第N页"，numeric 期望纯数字
                    ok = (mode == "chinese" and re.match(r'^第\d+', actual)) or \
                         (mode == "numeric" and actual.isdigit())
                    print(f"  {'✅' if ok else '⚠'} 目录页 P{idx+1} 页码: '{actual}' (mode={mode})")
                found = True
                break
        if not found:
            print(f"  ⚠ 目录页 P{idx+1} 未检测到页码文字")

    # 模式自检行（v0.3.2 新增）
    resolved_total = globals().get("_RESOLVED_TOTAL", None)
    print(f"  ℹ  检测模式: {mode} | 推断总数: {resolved_total or PAGE_TOTAL or 'N/A'}")

    # 抽查内容页页码（v0.3.2：4 种格式多模式匹配）
    check_indices = [4, 9, 20, 50, 80, 100]
    for idx in check_indices:
        if idx < doc.page_count:
            for w in doc[idx].get_text("words"):
                if w[1] > 770 and w[4].strip():
                    t = w[4].strip()
                    ok = any(p.match(t) for p in _FOOTER_PATTERNS)
                    print(f"  {'✅' if ok else '⚠'} 第{idx + 1}页 页码: {t}")
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

    # 3.5 校验：v0.3.2 新增 PAGE_NUMBER_MODE 取值
    if PAGE_NUMBER_MODE not in ("chinese", "numeric", "auto"):
        raise ValueError(
            f"PAGE_NUMBER_MODE={PAGE_NUMBER_MODE!r} 必须是 'chinese' | 'numeric' | 'auto'"
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
