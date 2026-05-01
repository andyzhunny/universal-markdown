# universal-markdown

**Convert Word, PDF and Images to Markdown with a single command.**

Supports both text-based PDFs (fast extraction) and scanned/image PDFs (OCR), automatically routing to the best method.

---

## Features

- **Smart PDF routing** — detects whether a PDF contains selectable text or is a scanned image, and automatically uses the fastest method
- **Dual OCR strategy for scanned PDFs** — extracts embedded images *and* renders full pages as fallback, ensuring no content is missed
- **Pure Python** — no heavy runtime dependencies, works on Windows, macOS and Linux
- **Batch processing** — process an entire folder with one command
- **Clean output** — one `.md` file per input document, plus an automated summary report

---

## Supported File Types

| Input Format | Handling Method | Output |
|---|---|---|
| `.docx`, `.doc` | MarkItDown CLI | Markdown text |
| `.pdf` (text-based) | MarkItDown CLI | Markdown text (fast) |
| `.pdf` (scanned/image) | PyMuPDF image extraction + DeepSeek-OCR | Markdown text |
| `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`, `.tiff` | DeepSeek-OCR | Markdown text |
| Other formats | Ignored (no error) | — |

---

## Prerequisites

- **Python 3.8+**
- **SiliconFlow API Key** (free tier available — see [Configuration](#configuration) below)

### Dependencies

```bash
pip install markitdown pymupdf requests
```

- `markitdown` — converts Word (`.docx`/`.doc`) and text-based PDF documents to Markdown
- `pymupdf` — extracts embedded images from PDFs and renders pages as images
- `requests` — calls the DeepSeek-OCR API

---

## Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/universal-markdown.git
cd universal-markdown
```

Or download and unzip the repository manually.

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install markitdown pymupdf requests
```

### Step 3 — Configure your API key

Create a `.env` file in the project root (or export it as an environment variable):

```bash
# Windows (Command Prompt)
set SILICONFLOW_API_KEY=your_api_key_here

# Windows (PowerShell)
$env:SILICONFLOW_API_KEY="your_api_key_here"

# macOS / Linux
export SILICONFLOW_API_KEY=your_api_key_here
```

---

## Getting a SiliconFlow API Key

> **Why SiliconFlow?** — This project uses the [SiliconFlow](https://siliconflow.cn) platform to access **DeepSeek-OCR**, a free high-accuracy OCR model. You do **not** need a separate OCR service.

### Registration (free, takes 1 minute)

1. Go to [siliconflow.cn](https://siliconflow.cn) and register an account
2. Log in and navigate to **Dashboard → API Keys**
3. Click **Create New Key** and copy the key
4. Paste the key into your `.env` file or environment variable

> **Note:** DeepSeek-OCR on SiliconFlow's free tier includes a monthly quota. For personal/light use it is sufficient. Check the [SiliconFlow pricing page](https://siliconflow.cn/pricing) for details.

---

## Usage

### Basic command

```bash
python scripts/convert.py "path/to/your/folder"
```

### Specify output directory (optional)

```bash
python scripts/convert.py "path/to/input" "path/to/output"
```

### What happens

The script scans the target folder for all supported files, converts each one, and writes results to the output folder:

```
input_folder/
├── document1.docx       →  output_folder/document1.md
├── report.pdf           →  output_folder/report.md
├── certificate.jpg      →  output_folder/certificate.md
└── _summary.md          →  conversion report (auto-generated)
```

If no output directory is specified, a `converted/` subfolder is created inside the input folder.

### Example

```bash
# Convert all files in a credentials folder
python scripts/convert.py "E:\Desktop\Credentials"

# Convert with explicit output path
python scripts/convert.py "E:\Desktop\Credentials" "C:\Users\hp\Desktop\Output"
```

### Sample output

```
[INFO] 扫描目录: E:\Desktop\Credentials
[INFO] 输出目录: E:\Desktop\Credentials\converted
[INFO] 找到 10 个文件，开始处理...

======================================================================
[1/10] 身份证正面.jpg
      类型: Image-OCR
      [OK] -> 身份证正面.md  (0.3 KB, 2.1s)
[2/10] 毕业证.pdf
      类型: PDF-OCR
      [OK] -> 毕业证.md  (1.2 KB, 8.5s)
...
======================================================================
处理完成！总计 10，成功 10，失败 0
输出目录: E:\Desktop\Credentials\converted
汇总已保存: E:\Desktop\Credentials\converted\_summary.md
```

---

## How PDF Routing Works

When the script encounters a PDF, it samples the first 3 pages:

| Condition | Decision |
|---|---|
| Text length > 50 characters | **Text-based PDF** → MarkItDown (fast, preserves structure) |
| Text length ≤ 50 characters + images present | **Scanned PDF** → Image extraction + full-page render → OCR |
| No text and no images | Fallback to MarkItDown |

This means a 300-page text PDF completes in seconds, while a scanned certificate still gets full OCR coverage.

---

## File Structure

```
universal-markdown/
├── README.md              ← This file
├── SKILL.md               ← WorkBuddy Skill metadata
├── LICENSE                ← MIT License
├── .gitignore            ← Git ignore rules
├── requirements.txt       ← Python dependencies
└── scripts/
    └── convert.py        ← Main conversion script
```

---

## Configuration Options

Edit the top of `scripts/convert.py` to change defaults:

```python
API_KEY = os.environ.get("SILICONFLOW_API_KEY", "your_default_key_here")
MODEL = "deepseek-ai/DeepSeek-OCR"
OCR_URL = "https://api.siliconflow.cn/v1/chat/completions"
OCR_TIMEOUT = 120          # seconds per image
```

---

## Troubleshooting

**`markitdown not found`**
```bash
pip install markitdown
```

**`API error 401`**
Your SiliconFlow API key is invalid or expired. Check your key at [siliconflow.cn/dashboard](https://siliconflow.cn/dashboard).

**`OCR results are empty or garbled`**
- For scanned PDFs: ensure the images in the PDF are not heavily compressed or rotated
- Try with a higher render scale: in `convert_pdf()`, increase `fitz.Matrix(2, 2)` to `fitz.Matrix(3, 3)`

**Chinese characters not recognized correctly**
DeepSeek-OCR has strong multilingual support including Chinese. Ensure your input image has sufficient resolution (at least 300 DPI recommended for scanned documents).

---

## License

MIT License — free to use, modify and distribute. See [LICENSE](LICENSE).

---

## Acknowledgements

- [MarkItDown](https://github.com/microsoft/markitdown) — Microsoft library for converting Office documents to Markdown
- [PyMuPDF](https://pymupdf.readthedocs.io/) — Python binding for MuPDF, used for PDF image extraction
- [SiliconFlow](https://siliconflow.cn) — API platform providing DeepSeek-OCR
