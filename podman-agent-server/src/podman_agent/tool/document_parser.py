"""文档解析模块：将 Office/PDF/文本文件转换为 Markdown 格式。

支持的文件类型：
- Word 文档 (.docx)
- Excel 表格 (.xlsx)
- PowerPoint 演示文稿 (.pptx)
- PDF 文档 (.pdf)
- 纯文本文件 (.txt, .md, .csv, .json, .xml, .yaml, .yml, .log, .ini, .cfg, .conf)
"""
from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {
    # Office 文档
    ".docx": "word",
    ".xlsx": "excel",
    ".pptx": "powerpoint",
    # PDF
    ".pdf": "pdf",
    # 文本文件
    ".txt": "text",
    ".md": "text",
    ".csv": "text",
    ".json": "text",
    ".xml": "text",
    ".yaml": "text",
    ".yml": "text",
    ".log": "text",
    ".ini": "text",
    ".cfg": "text",
    ".conf": "text",
    ".py": "text",
    ".js": "text",
    ".ts": "text",
    ".html": "text",
    ".css": "text",
    ".sh": "text",
    ".bash": "text",
}

# 文件大小限制（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024


def get_file_type(filename: str) -> str | None:
    """根据文件名获取文件类型。"""
    ext = os.path.splitext(filename)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext)


def parse_document(file_path: str, filename: str) -> str:
    """将文档解析为 Markdown 格式。

    Args:
        file_path: 文件的完整路径
        filename: 原始文件名

    Returns:
        解析后的 Markdown 字符串
    """
    file_type = get_file_type(filename)
    if not file_type:
        raise ValueError(f"不支持的文件类型: {filename}")

    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"文件过大: {file_size / 1024 / 1024:.1f}MB > 10MB")

    try:
        if file_type == "word":
            return _parse_docx(file_path)
        elif file_type == "excel":
            return _parse_xlsx(file_path)
        elif file_type == "powerpoint":
            return _parse_pptx(file_path)
        elif file_type == "pdf":
            return _parse_pdf(file_path)
        else:
            return _parse_text(file_path)
    except Exception as e:
        logger.error(f"解析文档失败: {filename}, 错误: {e}")
        raise


def _parse_docx(file_path: str) -> str:
    """解析 Word 文档为 Markdown。"""
    from docx import Document

    doc = Document(file_path)
    lines: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue

        # 根据样式判断标题级别
        style_name = para.style.name.lower() if para.style else ""
        if "heading 1" in style_name or style_name == "title":
            lines.append(f"# {text}")
        elif "heading 2" in style_name:
            lines.append(f"## {text}")
        elif "heading 3" in style_name:
            lines.append(f"### {text}")
        elif "heading 4" in style_name:
            lines.append(f"#### {text}")
        elif "list" in style_name:
            lines.append(f"- {text}")
        else:
            # 处理内联格式
            formatted = _format_docx_paragraph(para)
            lines.append(formatted)

    # 处理表格
    for table in doc.tables:
        lines.append("")
        lines.extend(_format_docx_table(table))
        lines.append("")

    return "\n".join(lines)


def _format_docx_paragraph(para: Any) -> str:
    """格式化 Word 段落的内联样式。"""
    parts: list[str] = []
    for run in para.runs:
        text = run.text
        if not text:
            continue
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"
        parts.append(text)
    return "".join(parts)


def _format_docx_table(table: Any) -> list[str]:
    """将 Word 表格格式化为 Markdown 表格。"""
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)

    if not rows:
        return []

    # 生成 Markdown 表格
    result: list[str] = []
    # 表头
    result.append("| " + " | ".join(rows[0]) + " |")
    result.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    # 数据行
    for row in rows[1:]:
        # 补齐列数
        while len(row) < len(rows[0]):
            row.append("")
        result.append("| " + " | ".join(row[:len(rows[0])]) + " |")

    return result


def _parse_xlsx(file_path: str) -> str:
    """解析 Excel 文件为 Markdown 表格。"""
    from openpyxl import load_workbook

    wb = load_workbook(file_path, read_only=True, data_only=True)
    sections: list[str] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows: list[list[str]] = []

        for row in ws.iter_rows(values_only=True):
            cells = [str(cell) if cell is not None else "" for cell in row]
            # 跳过全空行
            if any(c.strip() for c in cells):
                rows.append(cells)

        if not rows:
            continue

        # 确定最大列数
        max_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        section = [f"## {sheet_name}", ""]
        # 表头
        section.append("| " + " | ".join(rows[0]) + " |")
        section.append("| " + " | ".join(["---"] * max_cols) + " |")
        # 数据行
        for row in rows[1:]:
            section.append("| " + " | ".join(row) + " |")
        sections.append("\n".join(section))

    wb.close()
    return "\n\n".join(sections)


def _parse_pptx(file_path: str) -> str:
    """解析 PowerPoint 文件为 Markdown。"""
    from pptx import Presentation

    prs = Presentation(file_path)
    sections: list[str] = []

    for i, slide in enumerate(prs.slides, 1):
        slide_content: list[str] = [f"## 幻灯片 {i}"]

        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        # 判断是否为标题
                        if shape.shape_type == 13:  # TITLE
                            slide_content.append(f"# {text}")
                        else:
                            slide_content.append(text)

            if shape.has_table:
                slide_content.append("")
                table = shape.table
                rows: list[list[str]] = []
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    rows.append(cells)
                if rows:
                    slide_content.append("| " + " | ".join(rows[0]) + " |")
                    slide_content.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                    for row in rows[1:]:
                        slide_content.append("| " + " | ".join(row) + " |")

        # 处理备注
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                slide_content.append("")
                slide_content.append(f"**备注:** {notes}")

        sections.append("\n\n".join(slide_content))

    return "\n\n---\n\n".join(sections)


def _parse_pdf(file_path: str) -> str:
    """解析 PDF 文件为 Markdown。"""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    sections: list[str] = []

    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            sections.append(f"## 第 {i} 页\n\n{text.strip()}")

    if not sections:
        return "（PDF 文档无可提取文本）"

    return "\n\n---\n\n".join(sections)


def _parse_text(file_path: str) -> str:
    """解析纯文本文件。"""
    # 尝试多种编码
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            # 检测文件类型并添加代码块标记
            ext = os.path.splitext(file_path)[1].lower()
            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".html": "html",
                ".css": "css",
                ".json": "json",
                ".xml": "xml",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".sh": "bash",
                ".bash": "bash",
                ".csv": "csv",
                ".md": "markdown",
            }
            lang = lang_map.get(ext, "")
            if lang and ext not in (".txt", ".md", ".csv"):
                return f"```{lang}\n{content}\n```"
            return content
        except UnicodeDecodeError:
            continue

    return "（无法解码文件内容）"
