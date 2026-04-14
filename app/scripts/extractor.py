"""
Engine de extração OCR/texto via markitdown + pdfplumber.
Processa PDFs em chunks de N páginas, extrai estruturas semânticas
e formata em markdown otimizado para contexto LLM.
"""

import io
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from markitdown import MarkItDown

from app.config.settings import settings


@dataclass
class PageResult:
    page_num: int
    raw_text: str
    markdown: str
    tables: list[dict]
    word_count: int
    has_tables: bool
    has_images: bool


@dataclass
class ChunkResult:
    chunk_index: int
    start_page: int
    end_page: int
    pages: list[PageResult]
    markdown_combined: str
    tables_combined: list[dict]
    summary_tokens_estimate: int


@dataclass
class DocumentMeta:
    filename: str
    total_pages: int
    total_chunks: int
    chunk_size: int
    language_hint: str = "pt"
    has_tables: bool = False
    has_images: bool = False
    word_count_total: int = 0


def _extract_tables_from_page(page: pdfplumber.page.Page) -> list[dict]:
    """Extrai tabelas de uma página e converte para dicionário estruturado."""
    tables = []
    raw_tables = page.extract_tables()
    for idx, table in enumerate(raw_tables):
        if not table or len(table) < 2:
            continue
        header = [str(h or "").strip() for h in table[0]]
        rows = []
        for row in table[1:]:
            cleaned = [str(c or "").strip() for c in row]
            if any(cleaned):
                rows.append(dict(zip(header, cleaned)))
        tables.append(
            {
                "table_index": idx,
                "headers": header,
                "rows": rows,
                "row_count": len(rows),
            }
        )
    return tables


def _table_to_markdown(table: dict) -> str:
    """Converte tabela estruturada em markdown."""
    headers = table["headers"]
    if not headers:
        return ""
    sep = "|".join(["---"] * len(headers))
    header_row = "| " + " | ".join(headers) + " |"
    sep_row = "| " + sep + " |"
    lines = [header_row, sep_row]
    for row in table["rows"]:
        cells = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _clean_text(text: str) -> str:
    """Remove artefatos comuns de extração PDF."""
    if not text:
        return ""

    text = re.sub(r"-\n(\w)", r"\1", text)
    text = re.sub(r" {2,}", " ", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue

        if len(re.findall(r"[a-zA-ZÀ-ÿ]", stripped)) >= 3:
            lines.append(stripped)
    return "\n".join(lines).strip()


def _page_to_markdown(page_num: int, text: str, tables: list[dict]) -> str:
    """Monta markdown estruturado de uma página com texto e tabelas."""
    sections = [f"## Página {page_num}\n"]

    clean = _clean_text(text)
    if clean:
        sections.append(clean)

    for table in tables:
        md_table = _table_to_markdown(table)
        if md_table:
            sections.append(f"\n**Tabela {table['table_index'] + 1}:**\n{md_table}")

    return "\n\n".join(sections)


def extract_chunk(
    pdf_bytes: bytes,
    chunk_index: int,
    start_page: int,
    end_page: int,
) -> ChunkResult:
    """
    Extrai texto e tabelas de um intervalo de páginas do PDF.
    Usa pdfplumber para extração granular e markitdown como fallback/normalização.
    """
    page_results: list[PageResult] = []
    all_tables: list[dict] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_idx in range(start_page, min(end_page + 1, len(pdf.pages))):
            page = pdf.pages[page_idx]
            page_num = page_idx + 1

            raw_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

            tables = _extract_tables_from_page(page)
            all_tables.extend(tables)

            has_images = len(page.images) > 0

            markdown = _page_to_markdown(page_num, raw_text, tables)
            word_count = len(raw_text.split())

            page_results.append(
                PageResult(
                    page_num=page_num,
                    raw_text=raw_text,
                    markdown=markdown,
                    tables=tables,
                    word_count=word_count,
                    has_tables=len(tables) > 0,
                    has_images=has_images,
                )
            )

    if all(not p.raw_text.strip() for p in page_results):
        page_results = _fallback_markitdown(
            pdf_bytes, chunk_index, start_page, end_page
        )

    markdown_combined = _build_chunk_markdown(chunk_index, page_results)
    total_words = sum(p.word_count for p in page_results)
    token_estimate = int(total_words * 0.75)

    return ChunkResult(
        chunk_index=chunk_index,
        start_page=start_page + 1,
        end_page=min(end_page + 1, start_page + len(page_results)),
        pages=page_results,
        markdown_combined=markdown_combined,
        tables_combined=all_tables,
        summary_tokens_estimate=token_estimate,
    )


def _fallback_markitdown(
    pdf_bytes: bytes,
    chunk_index: int,
    start_page: int,
    end_page: int,
) -> list[PageResult]:
    """Fallback via markitdown para PDFs que não têm texto extraível."""
    md_converter = MarkItDown()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = md_converter.convert(tmp_path)
        text = result.text_content or ""
        pages = text.split("\f")
        page_results = []
        for i, page_text in enumerate(pages[start_page : end_page + 1]):
            page_num = start_page + i + 1
            cleaned = _clean_text(page_text)
            page_results.append(
                PageResult(
                    page_num=page_num,
                    raw_text=cleaned,
                    markdown=f"## Página {page_num}\n\n{cleaned}",
                    tables=[],
                    word_count=len(cleaned.split()),
                    has_tables=False,
                    has_images=False,
                )
            )
        return page_results
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_chunk_markdown(chunk_index: int, pages: list[PageResult]) -> str:
    """Constrói markdown consolidado do chunk otimizado para contexto LLM."""
    header = f"# Chunk {chunk_index + 1} | Páginas {pages[0].page_num}–{pages[-1].page_num}\n"
    sections = [header]
    for page in pages:
        if page.markdown.strip():
            sections.append(page.markdown)
    return "\n\n---\n\n".join(sections)


def compute_chunks(total_pages: int, chunk_size: int = None) -> list[tuple[int, int]]:
    """
    Retorna lista de (start_page, end_page) 0-indexed para cada chunk.
    chunk_size padrão vem das configurações.
    """
    size = chunk_size or settings.chunk_size_pages
    chunks = []
    for start in range(0, total_pages, size):
        end = min(start + size - 1, total_pages - 1)
        chunks.append((start, end))
    return chunks


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Retorna número de páginas do PDF."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return len(pdf.pages)
