# 版式与生成

## 页面

A4 纵向；上下边距 1 英寸（2.54 cm），左右边距 1.25 英寸（3.17 cm）。

## 字体与段落

- 封面标题：宋体 + Times New Roman，18 pt，加粗，黑色，居中。
- 封面日期：宋体，16 pt，加粗，黑色，居中。
- 目录标题"目录"：宋体，18 pt，加粗，黑色，居中。
- 一级/二级/三级标题：宋体 + Times New Roman，16 pt，加粗，黑色，左对齐，1.2 倍行距，段前 6 pt、段后 4 pt，与下段同页。
- 正文：仿宋 + Times New Roman，16 pt，常规，黑色，左对齐，首行缩进 2 字符（32 pt），1.5 倍行距，段前段后 0，孤行控制。
- 项目符号列表：仿宋，16 pt，1.5 倍行距，悬挂缩进，黑色。
- 表题：宋体，12 pt，黑色，居中。
- 页脚：居中 PAGE 字段，宋体 9 pt（目录页隐藏页眉页脚，正文页显示页码）。

## 标题编号

一级用"一、二、三……"，二级用"2.1"，三级用"4.2.1"。标题文字沿用已有编号，不叠加"第一章"等正式称谓。目录只收录一级到三级标题。

## 目录

使用真正的 Word 自动目录字段 `TOC \o "1-3" \h \z \u`。目录项宋体 + Times New Roman、12 pt、黑色，一级左缩进 0、二级约 0.28 英寸、三级约 0.56 英寸，点状引导线连接右对齐页码。不得手工录入目录正文或页码。

## Markdown 输入约定

- `# 标题`：唯一一级大标题作为封面标题（报告名）。
- `## 一、……`：一级标题；`### 2.1 ……`：二级标题；`#### 4.2.1 ……`：三级标题。
- 空行分隔的普通段落：正文。
- `- ` 或 `* `：项目符号列表。
- 管道表格 `| a | b |`：自动转为黑白表格，并在上方按顺序生成"表1、表2……"表题。
- `![alt](相对/绝对图片路径)`：嵌入图片并按版心缩放，图片路径相对 Markdown 所在目录。

## 生成步骤

需要安装有 `lxml` 的 Python 3 环境。脚本在 `vendor/` 下自带 `python-docx` 与 `mistune`，无需另装。

### 方式一：一键流水线生成（推荐）

```bash
# 自动执行：线索检查 -> Markdown 转 DOCX -> 插入三级自动目录 -> Word 字段刷新（支持中文路径与无 Word 环境自动降级）
python scripts/build_docx.py source.md --out 调研报告.docx

# 如需同时导出 PDF 与逐页预览 PNG：
python scripts/build_docx.py source.md --out 调研报告.docx --render-dir build/render
```

### 方式二：分步执行

```powershell
# 1. Markdown -> DOCX
python scripts/markdown_to_docx.py source.md --mode decision-proposal --out build/base.docx --report build/parse.json

# 2. 插入三级自动目录
python scripts/ensure_toc.py build/base.docx --out 调研报告.docx

# 3. 更新目录、页码与交叉引用字段（Windows + 本机安装 Word 时可选执行，脚本已内置中文路径自动中转）
powershell -ExecutionPolicy Bypass -File scripts/update_word_fields.ps1 -InputDocx 调研报告.docx

# 4. 逐页渲染为 PNG 供检查（需要 Word，支持 pdftoppm 或 PyMuPDF 自动降级）
powershell -ExecutionPolicy Bypass -File scripts/render_with_word.ps1 -InputDocx 调研报告.docx -OutputDir build/render
```

### 注意事项

- **行内强调格式**：中文报告正文体例不使用粗体，建议直接用中文引号 `“……”` 强调；若源稿含有紧贴中文标点的 `**……**`，转换器会自动剥离多余星号，但注意不要在 `**` 内外重复套双层引号。
- **编号批量重排要按作用域**：新增/删除章节后重排章号、节号、表号时，全局 `str.replace` 会串号产生 `6..1` 之类脏数据。按“当前章标题”作用域替换，事后 grep `^###|^####|如表N所示` 三处做一致性校验。
- **无 Word 环境说明**：若运行环境为 macOS/Linux 或未安装 Microsoft Word，`build_docx.py` 会自动跳过 COM 刷新步骤；生成的 `.docx` 已内置 `w:updateFields="true"` 标记，首次用 Word 打开时会自动提示更新目录与页码。

## 验收清单

- 目录为自动字段，覆盖一级到三级标题，页码与正文一致，无空目录、无静态目录残留、无多余空白页。
- 标题层级与 Markdown 一致，编号连续（一、二、三……；2.1、2.2……；4.2.1……）。
- 表格白底黑字、0.5 pt 黑色网格、表头加粗、表题连续（表1、表2……）、跨页重复表头。
- 正文仿宋 16 pt、首行缩进 2 字符、1.5 倍行距；无裁切、重叠、孤立标题、异常换行。
- 所有数字、厂商名、产品名、日期、结论与来源一致；没有从参考资料带入的项目专属事实。
