# phirov-skills

CodeBuddy AI Agent 技能合集。

## Skills

| 技能 | 版本 | 发布日期 | 说明 |
|------|------|----------|------|
| [pdf-edu-processor](pdf-edu-processor/) | [v0.3.2](https://github.com/phirov/phirov-skills/releases/tag/v0.3.2) | 2026-07-05 | PDF 教辅材料后处理 — 页眉/水印删除、页码重编号、目录美化、书签导航 |

## pdf-edu-processor 最新版本 (v0.3.2)

### v0.3.2 新增（双模式页码）

- `PAGE_NUMBER_MODE = "chinese" | "numeric" | "auto"`，默认 `auto`
- `auto` 模式自动扫描前 5 页页脚识别中英文格式（"第N页 共M页" / "N/M" / "N of M" / "N"）
- `numeric` 模式使用 TiRo 字体（不嵌 CJK，文件体积小），居中
- 多页目录支持罗马数字 i/ii/iii/...
- 新增 `PAGE_TOTAL` 配置项允许手动覆盖总页数
- `verify()` 增强为 4 种页脚格式多模式匹配

**用户价值**：英文/数字 PDF（如教材、试卷、扫描件）开箱即用，无需手动配置模式。

### v0.3.1 新增（智能路径解析）

- `INPUT_PDF` 支持单文件路径或目录路径：目录路径时自动取该目录下第一个 PDF
- `OUTPUT_PDF` 留空时自动按"原名-整理后.pdf"生成（如 `我的教辅.pdf` → `我的教辅-整理后.pdf`）
- 找不到文件时给出清晰提示

**用户价值**：AI Agent 无需将上传的 PDF 重命名为 `input.pdf`，保留用户原文件名即可。

### 核心功能

- **页眉清理**：删除教师署名、机构标语、logo
- **水印去除**：支持 Artifact BDC 块和内联文字两种模式
- **页码重编号**：目录/正文页码偏移，支持罗马数字
- **双模式页码**：chinese/numeric/auto 自动识别，支持纯数字/英文 of/数字斜杠
- **目录美化**：点号对齐、添加书签和跳转链接

### v0.3.0 特性

- `_resolve_chapters()` 自动推导 PDF 索引：`CHAPTERS` 简化为 3 元组
- 链接精准性校验：每个跳转链接都验证目标页内容
- 运行时断言：章节编号连续性、新页码单调递增、PDF 索引在文档范围内

### 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|----------|
| [v0.3.2](https://github.com/phirov/phirov-skills/releases/tag/v0.3.2) | 2026-07-05 | 双模式页码（chinese/numeric/auto），多页目录罗马数字，PAGE_TOTAL 手动覆盖 |
| [v0.3.1](https://github.com/phirov/phirov-skills/releases/tag/v0.3.1) | 2026-07-05 | 智能路径解析，保留上传文件原名 |
| [v0.3.0](https://github.com/phirov/phirov-skills/releases/tag/v0.3.0) | 2026-07-05 | CHAPTERS 简化为 3 元组，自动推导 PDF 索引，链接精准性校验 |
| [v0.2.0](https://github.com/phirov/phirov-skills/releases/tag/v0.2.0) | 2026-07-04 | 修复目录页码错位，动态坐标提取 |
| [v0.1.0](https://github.com/phirov/phirov-skills/releases/tag/v0.1.0) | 2026-07-04 | 首次发布 |

## 安装

### 方式一：CodeBuddy Agent 自动安装（推荐）

在 CodeBuddy 对话中直接对 AI 说：

> 帮我安装"PDF教辅材料后处理"这个技能：https://github.com/phirov/phirov-skills/pdf-edu-processor

AI 会自动完成以下工作：
1. 克隆本仓库到本地
2. 复制 `pdf-edu-processor` 目录到 `~/.codebuddy/skills/`
3. 校验 SKILL.md 完整性
4. 告知安装完成

### 方式二：手动安装

```bash
# 1. 克隆整个仓库（用于查看所有 skill 源码和文档）
git clone https://github.com/phirov/phirov-skills.git

# 2. 复制单个 skill 目录到 CodeBuddy skills 路径
cp -r phirov-skills/pdf-edu-processor ~/.codebuddy/skills/

# 3. （可选）校验安装结果
ls ~/.codebuddy/skills/pdf-edu-processor/
# 应看到：CHANGELOG.md  SKILL.md  scripts/

# 4. （可选）安装依赖
pip3 install PyMuPDF
```

### 安装验证

安装完成后，在 CodeBuddy 对话中尝试触发 skill：

> 我有一份教辅 PDF 含有教师署名和角标水印，请帮我清理页眉、重编号页码并美化目录。

如果 AI 识别到 `pdf-edu-processor` 技能并开始读取 `~/.codebuddy/skills/pdf-edu-processor/SKILL.md`，说明安装成功。

### 升级

```bash
# 拉取最新代码
cd phirov-skills && git pull

# 覆盖更新
cp -rf pdf-edu-processor ~/.codebuddy/skills/
```

或者使用 GitHub Release 页面下载指定版本：[Releases](https://github.com/phirov/phirov-skills/releases)

### 卸载

```bash
rm -rf ~/.codebuddy/skills/pdf-edu-processor
```

## 许可

MIT
