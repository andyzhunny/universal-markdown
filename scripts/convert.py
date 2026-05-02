#!/usr/bin/env python3
"""
universal-markdown 核心脚本
自动识别文件夹中的 Word / PDF / 图片文件，调用不同后端转换：
  - Word (.docx .doc) → MarkItDown
  - PDF (.pdf)        → PyMuPDF 提取嵌入图 + 全页渲染，再统一 OCR
  - 图片 (.jpg .jpeg .png .bmp .webp .tiff) → DeepSeek-OCR (SiliconFlow)
输出目录结构: <输出目录>/原文件名.md
处理完成后生成 _summary.md 汇总报告。
"""

import base64
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import requests

# ==================== 配置 ====================
API_KEY = os.environ.get(
    "SILICONFLOW_API_KEY",
    "sk-cfkskxizyaryrcgqmendodbojpvyzxlnxfpdlgffnabjngem"
)
MODEL = "deepseek-ai/DeepSeek-OCR"
OCR_URL = "https://api.siliconflow.cn/v1/chat/completions"

# 支持的文件类型
MARKITDOWN_EXTS = {".docx", ".doc"}          # Word 走 MarkItDown
PDF_EXT = {".pdf"}                            # PDF 单独处理
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif", ".gif"}
ALL_SUPPORTED = MARKITDOWN_EXTS | PDF_EXT | IMAGE_EXTS

# OCR 超时（秒）
OCR_TIMEOUT = 120


# ==================== 通用 OCR 引擎（接收 bytes） ====================
def _ocr_bytes(image_bytes: bytes, mime: str, filename: str = "image") -> str:
    """给定图片字节数据，调用 DeepSeek-OCR 返回纯文字。"""
    img_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": "请识别这张图片中的所有文字，并原样输出文字内容。"}
            ]
        }],
        "max_tokens": 4096,
        "temperature": 0
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    r = requests.post(OCR_URL, json=payload, headers=headers, timeout=OCR_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"API错误 {r.status_code}: {r.text[:200]}")
    content = r.json()["choices"][0]["message"]["content"].strip()
    content = re.sub(r"<\|ref\|>.*?<\|/ref\|>", "", content, flags=re.DOTALL)
    content = re.sub(r"<\|det\|>.*?<\|/det\|>", "", content, flags=re.DOTALL)
    return content.strip()


# ==================== MarkItDown（Word 专用） ====================
def convert_word(file_path: Path, output_path: Path) -> tuple[bool, str]:
    """调用 MarkItDown CLI 将 Word 文档转为 Markdown。"""
    try:
        result = subprocess.run(
            ["markitdown", str(file_path), "-o", str(output_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return True, "OK"
        if output_path.exists():
            return False, f"[MarkItDown错误但文件已生成] {result.stderr[:200]}"
        return False, f"[MarkItDown错误] {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, "[超时]"
    except FileNotFoundError:
        return False, "[markitdown 未找到，请先安装: pip install markitdown]"
    except Exception as e:
        return False, f"[异常] {e}"


# ==================== 图片文件 OCR ====================
def convert_image(file_path: Path, output_path: Path) -> tuple[bool, str]:
    """对图片文件调用 OCR，结果写入 output_path。"""
    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        suffix = file_path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".bmp": "image/bmp", ".webp": "image/webp",
            ".tiff": "image/tiff", ".tif": "image/tiff", ".gif": "image/gif",
        }
        mime = mime_map.get(suffix, "image/jpeg")
        content = _ocr_bytes(image_bytes, mime, file_path.name)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {file_path.name}\n\n{content}\n")
        return True, "OK"
    except Exception as e:
        return False, str(e)


# ==================== PDF OCR 核心（强制全页渲染，供验证重做和扫描件使用）====================
def _do_pdf_ocr(file_path: Path, output_path: Path) -> None:
    """强制对 PDF 做高清渲染 OCR，绕过文字层直接识别图像内容。"""
    doc = fitz.open(str(file_path))
    all_parts = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(3, 3)  # 高清渲染 3x
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        if len(img_bytes) <= 5000:
            continue
        text = _ocr_bytes(img_bytes, "image/png", f"{file_path.name}[p{page_num+1}]")
        text = re.sub(r"<\|ref\|>.*?<\|/ref\|>", "", text, flags=re.DOTALL)
        text = re.sub(r"<\|det\|>.*?<\|/det\|>", "", text, flags=re.DOTALL)
        if text and len(text) > 5:
            all_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
    doc.close()
    if all_parts:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {file_path.name}\n\n" + "\n\n".join(all_parts) + "\n")


# ==================== PDF 智能处理 ====================
def convert_pdf(file_path: Path, output_path: Path) -> tuple[bool, str]:
    """
    处理 PDF（智能路由）：
      - 若 PDF 有文字层（真实文本 PDF）：走 MarkItDown，速度快且保留结构
      - 若 PDF 无文字层（扫描件）       ：提嵌入图 + 全页渲染 → OCR
    """
    try:
        doc = fitz.open(str(file_path))

        # --- 探测文字层：采样前3页，统计实际文字量 ---
        total_text_len = 0
        total_img_count = 0
        sample_pages = min(3, len(doc))
        for page_num in range(sample_pages):
            page = doc[page_num]
            t = page.get_text()
            total_text_len += len(t.strip())
            total_img_count += len(page.get_images())

        doc.close()

        has_real_text = total_text_len > 50          # 有实质文字内容
        is_scanned = total_img_count > 0 and total_text_len <= 50  # 有图无文字 = 扫描件

        # --- 分支一：真实文字 PDF → MarkItDown（+ 事后验证）---
        if has_real_text and not is_scanned:
            ok, detail = convert_word(file_path, output_path)
            # 验证：MarkItDown 提取少于 100 字符 → 说明文字层不完整，改走 OCR
            if ok and output_path.exists():
                text = output_path.read_text(encoding="utf-8")
                if len(text.strip()) < 100:
                    # 丢弃不完整结果，改用 OCR
                    _do_pdf_ocr(file_path, output_path)
                    detail = "OCR(验证重做)"
            return ok, detail

        # --- 分支二：扫描件 PDF → OCR（嵌入图 + 全页渲染）---
        doc = fitz.open(str(file_path))
        all_text_parts = []
        extracted_count = 0

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 提取嵌入图片
            img_list = page.get_images(full=True)
            for img_info in img_list:
                xref = img_info[0]
                try:
                    extracted = doc.extract_image(xref)
                    img_bytes = extracted["image"]
                    ext = extracted["ext"]
                    if len(img_bytes) < 5000:        # 过滤水印小图
                        continue
                    mime = f"image/{ext}" if ext in ("jpeg", "png", "bmp", "webp", "gif", "tiff") else "image/jpeg"
                    text = _ocr_bytes(img_bytes, mime, f"{file_path.name}[p{page_num+1}]")
                    if text:
                        all_text_parts.append(f"--- 第 {page_num + 1} 页（嵌入图）---\n{text}")
                        extracted_count += 1
                except Exception:
                    continue

            # 全页渲染兜底
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            if len(img_bytes) > 5000:
                text = _ocr_bytes(img_bytes, "image/png", f"{file_path.name}[p{page_num+1} render]")
                if text and len(text) > 5:
                    all_text_parts.append(f"--- 第 {page_num + 1} 页（全页渲染）---\n{text}")
                    extracted_count += 1

        doc.close()

        if all_text_parts:
            full_text = "\n\n".join(all_text_parts)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# {file_path.name}\n\n{full_text}\n")
            return True, f"OK ({extracted_count} 图)"
        else:
            # 扫描件但无嵌入图且无文字 → 强制全页 OCR
            _do_pdf_ocr(file_path, output_path)
            if output_path.exists() and output_path.stat().st_size > 50:
                return True, "OCR(全页渲染)"
            return convert_word(file_path, output_path)

    except Exception as e:
        return False, f"[PDF处理异常] {e}"


# ==================== 主程序 ====================
def process_folder(src_dir: Path, out_dir: Path | None = None):
    if out_dir is None:
        out_dir = src_dir / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        f for f in src_dir.iterdir()
        if f.is_file() and f.suffix.lower() in ALL_SUPPORTED
    ]
    files.sort(key=lambda x: x.name)

    if not files:
        print(f"[!] 在 {src_dir} 中未找到支持的文档文件（Word/PDF/图片）")
        print(f"    支持类型: {', '.join(ALL_SUPPORTED)}")
        return

    print(f"[INFO] 扫描目录: {src_dir}")
    print(f"[INFO] 输出目录: {out_dir}")
    print(f"[INFO] 找到 {len(files)} 个文件，开始处理...\n")
    print("=" * 70)

    results = []
    ok_count = 0
    fail_count = 0

    for i, f in enumerate(files, 1):
        ext = f.suffix.lower()
        stem = f.stem
        output_file = out_dir / f"{stem}.md"

        if ext in MARKITDOWN_EXTS:
            type_label = "MarkItDown"
        elif ext in PDF_EXT:
            type_label = "PDF-OCR"
        else:
            type_label = "Image-OCR"

        print(f"[{i}/{len(files)}] {f.name}")
        print(f"      类型: {type_label}")

        start = time.time()
        if ext in MARKITDOWN_EXTS:
            ok, detail = convert_word(f, output_file)
        elif ext in PDF_EXT:
            ok, detail = convert_pdf(f, output_file)
        else:
            ok, detail = convert_image(f, output_file)
        elapsed = time.time() - start

        status = "OK" if ok else "FAIL"
        if ok:
            ok_count += 1
            size_kb = output_file.stat().st_size / 1024
            print(f"      [{status}] -> {output_file.name}  ({size_kb:.1f} KB, {elapsed:.1f}s)")
        else:
            fail_count += 1
            print(f"      [{status}] {detail}")

        results.append({
            "num": i, "file": f.name, "type": type_label,
            "status": status, "detail": detail,
            "output": output_file.name, "time_s": round(elapsed, 1)
        })
        print()

    # 汇总报告
    print("=" * 70)
    print(f"处理完成！总计 {len(files)}，成功 {ok_count}，失败 {fail_count}")
    print(f"输出目录: {out_dir}")

    summary_path = out_dir / "_summary.md"
    with open(summary_path, "w", encoding="utf-8") as sf:
        sf.write(f"# 文档转换汇总\n\n")
        sf.write(f"- **扫描目录**: `{src_dir}`\n")
        sf.write(f"- **输出目录**: `{out_dir}`\n")
        sf.write(f"- **总文件数**: {len(files)}\n")
        sf.write(f"- **成功**: {ok_count}\n")
        sf.write(f"- **失败**: {fail_count}\n\n")
        sf.write("## 详情\n\n")
        sf.write("| # | 文件名 | 类型 | 状态 | 用时 | 输出 |\n")
        sf.write("|---|--------|------|------|------|------|\n")
        for r in results:
            sf.write(f"| {r['num']} | {r['file']} | {r['type']} | {r['status']} | {r['time_s']}s | `{r['output']}` |\n")
        if fail_count > 0:
            sf.write("\n## 失败详情\n\n")
            for r in results:
                if r["status"] == "FAIL":
                    sf.write(f"- `{r['file']}`: {r['detail']}\n")

    print(f"\n汇总已保存: {summary_path}")


# ==================== 入口 ====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python convert.py <文件夹路径> [输出目录]")
        print("示例: python convert.py 'E:\\Desktop\\其他\\证件扫描件'")
        print("示例: python convert.py 'C:\\Users\\hp\\Downloads' 'C:\\Users\\hp\\Desktop\\输出'")
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"[错误] 路径不存在: {src}")
        sys.exit(1)
    if not src.is_dir():
        print(f"[错误] 路径不是文件夹: {src}")
        sys.exit(1)

    out = Path(sys.argv[2]) if len(sys.argv) >= 3 else None
    process_folder(src, out)
