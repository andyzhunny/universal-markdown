---
name: universal-markdown
license: MIT
metadata:
  version: "1.1.0"
  category: document-processing
  author: MiniMaxAI
  description: >
    通用文档格式转换器：自动识别文件夹中的 Word(.docx/.doc)、PDF 和图片文件，
    调用不同后端进行文本提取：
    - Word (.docx/.doc) → MarkItDown
    - PDF → 智能路由 + 事后验证：
      - 有文字层（真实文本 PDF）→ MarkItDown（快速、保留结构）
      - MarkItDown 提取 < 100 字符 → 自动改走 OCR（防止 TCPDF 等矢量 PDF 漏内容）
      - 无文字层（扫描件 PDF）→ PyMuPDF 提嵌入图 + 全页渲染 OCR
    - 图片（jpg/png/bmp/webp/tiff）→ DeepSeek-OCR（SiliconFlow）
    - OCR 结果自动去重（连续重复行超过 5 次合并为 1 条）
    输出汇总到 _summary.md，适合大批量证件、文档、扫描件的批量 OCR 场景。
triggers:
  - 文档转换
  - 批量OCR
  - 图片转文字
  - PDF转md
  - Word转md
  - markitdown
  - ocr识别
  - 证件识别
---

# universal-doc-converter

通用文档格式转换 Skill，支持 Word / PDF / 图片三种格式批量转 Markdown。

## 依赖

- Python 3.8+
- `markitdown`：`pip install markitdown`
- PyMuPDF：`pip install pymupdf`
- SiliconFlow API Key（用于图片 OCR，从环境变量 `SILICONFLOW_API_KEY` 读取）

## 核心脚本

`scripts/convert.py` — 主程序，处理整个文件夹。

### 使用方式

```bash
python scripts/convert.py <文件夹路径> [输出目录]
```

- 不指定输出目录时，默认在 `<文件夹路径>/converted/` 下输出
- 输出文件与原文件同名，扩展名改为 `.md`
- 处理完成后生成 `_summary.md` 汇总报告

### 处理逻辑

| 文件类型 | 后端 | 说明 |
|---------|------|------|
| `.docx` / `.doc` | MarkItDown | CLI 调用，输出纯文本 |
| `.pdf` | MarkItDown + 验证 | 先 MarkItDown；提取 < 100 字符自动改走 OCR |
| `.pdf`（扫描件） | PyMuPDF 全页 OCR | 提嵌入图 + 全页高清渲染（3x），SiliconFlow DeepSeek-OCR 识别 |
| `.jpg` / `.jpeg` / `.png` / `.bmp` / `.webp` / `.tiff` | DeepSeek-OCR | SiliconFlow API base64 传输 |

### 验证机制（v1.1.0 新增）

- **PDF 事后验证**：MarkItDown 处理后，若提取内容 < 100 字符，自动改用 OCR 重做（防止 TCPDF 等矢量 PDF、证书类 PDF 漏内容）
- **OCR 去重**：OCR 结果中连续重复行超过 5 次自动合并为 1 条（证书装饰文字重复问题）

### API 配置

API Key 和模型在脚本开头配置，从环境变量 `SILICONFLOW_API_KEY` 读取，
若未设置则使用默认值。

## 示例

```
python scripts/convert.py "E:\Desktop\其他\证件扫描件"
python scripts/convert.py "C:\Users\hp\Downloads\文档" "C:\Users\hp\Desktop\输出"
```