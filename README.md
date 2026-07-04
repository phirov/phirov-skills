# phirov-skills

CodeBuddy AI Agent 技能合集。

## Skills

| 技能 | 版本 | 发布日期 | 说明 |
|------|------|----------|------|
| [pdf-edu-processor](pdf-edu-processor/) | [v0.3.0](https://github.com/phirov/phirov-skills/releases/tag/v0.3.0) | 2026-07-05 | PDF 教辅材料后处理 — 页眉/水印删除、页码重编号、目录美化、书签导航 |

## pdf-edu-processor 最新版本 (v0.3.0)

### 核心功能

- **页眉清理**：删除教师署名、机构标语、logo
- **水印去除**：支持 Artifact BDC 块和内联文字两种模式
- **页码重编号**：目录/正文页码偏移，支持罗马数字
- **目录美化**：点号对齐、添加书签和跳转链接

### v0.3.0 新增

- **`_resolve_chapters()` 自动推导 PDF 索引**：`CHAPTERS` 简化为 3 元组 `[编号, 标题, 新页码]`，彻底消除人工配置错误
- **链接精准性校验**：`verify()` 新增逐链接目标页内容比对，确保书签和跳转链接真正指向章节标题页
- **运行时断言**：章节编号连续性、新页码单调递增、PDF 索引在文档范围内

### v0.3.0 修复

- 书签/目录链接跳错页（v0.2.0 引入）：`CHAPTERS` 第 4 列（PDF 索引）易混淆"原页码"和"PDF 物理页"，新版完全不需要这个字段

### 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|----------|
| [v0.3.0](https://github.com/phirov/phirov-skills/releases/tag/v0.3.0) | 2026-07-05 | CHAPTERS 简化为 3 元组，自动推导 PDF 索引，链接精准性校验 |
| [v0.2.0](https://github.com/phirov/phirov-skills/releases/tag/v0.2.0) | 2026-07-04 | 修复目录页码错位，动态坐标提取 |
| [v0.1.0](https://github.com/phirov/phirov-skills/releases/tag/v0.1.0) | 2026-07-04 | 首次发布 |

## 安装

将所需 skill 目录复制到 CodeBuddy 的 skills 路径：

```bash
cp -r pdf-edu-processor ~/.codebuddy/skills/
```

## 许可

MIT
