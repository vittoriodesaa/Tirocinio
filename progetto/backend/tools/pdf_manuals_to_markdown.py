#!/usr/bin/env python3
"""
Convert every PDF under a directory tree to Markdown (headings, lists, emphasis).

Uses pymupdf4llm (PyMuPDF layout) for structure-aware extraction. Install deps:

    uv pip install -r requirements-manuals.txt

Example:

    ./scripts/pdf_manuals_to_markdown.py
    ./scripts/pdf_manuals_to_markdown.py -i manuals -o manuals_md --show-progress
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _clean_markdown(md: str) -> str:
    """Normalize spacing; turn '## **Title**' into '## Title' when the line is only that."""
    md = re.sub(r"^(#{1,6})\s*\*\*(.+?)\*\*\s*$", r"\1 \2", md, flags=re.MULTILINE)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def _iter_pdfs(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() == ".pdf":
            out.append(p)
    return out


def _convert_one(
    pdf_path: Path,
    *,
    header: bool,
    footer: bool,
    show_progress: bool,
    page_separators: bool,
    dpi: int,
    ocr_language: str,
    front_matter: bool,
    write_images: bool,
    image_path: Path | None,
) -> str:
    try:
        import pymupdf4llm
    except ImportError as e:
        raise SystemExit(
            "Missing dependency pymupdf4llm. Install with:\n"
            "  uv pip install -r requirements-manuals.txt\n"
        ) from e

    kwargs: dict = {
        "header": header,
        "footer": footer,
        "show_progress": show_progress,
        "page_separators": page_separators,
        "dpi": dpi,
        "ocr_language": ocr_language,
    }
    if write_images:
        kwargs["write_images"] = True
        kwargs["image_path"] = str(image_path) if image_path else ""

    md = pymupdf4llm.to_markdown(str(pdf_path), **kwargs)
    md = _clean_markdown(md)

    if front_matter:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rel = pdf_path.name
        fm = (
            "---\n"
            f"source_pdf: {rel}\n"
            f"converted_at: {ts}\n"
            "---\n\n"
        )
        md = fm + md

    return md


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert all PDFs under a folder to Markdown, preserving structure.",
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        default=_repo_root() / "manuals",
        help="Root directory to scan for PDFs (default: <repo>/manuals)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_repo_root() / "manuals_md",
        help="Root directory for .md output (default: <repo>/manuals_md)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing Markdown files (default: skip if .md already exists)",
    )
    parser.add_argument(
        "--include-pdf-headers-footers",
        action="store_true",
        help="Keep repeating PDF page header/footer text in the Markdown",
    )
    parser.add_argument("--show-progress", action="store_true", help="Progress from converter")
    parser.add_argument(
        "--page-separators",
        action="store_true",
        help="Insert visible separators between pages",
    )
    parser.add_argument("--dpi", type=int, default=150, help="DPI when rasterizing (images/OCR)")
    parser.add_argument(
        "--ocr-language",
        default="ita+eng",
        help="OCR languages (Tesseract-style), e.g. ita+eng or eng",
    )
    parser.add_argument(
        "--front-matter",
        action="store_true",
        help="Prepend YAML front matter with source_pdf and converted_at",
    )
    parser.add_argument(
        "--write-images",
        action="store_true",
        help="Extract images to disk (see --image-dir)",
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=None,
        help="Directory for extracted images (default: <output-dir>/_images/<pdf-stem>)",
    )
    parser.add_argument(
        "--name-glob",
        default="*",
        help='Only PDFs whose filename matches this glob (e.g. "Guida*.pdf")',
    )

    args = parser.parse_args(argv)

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    pdfs = [p for p in _iter_pdfs(input_dir) if fnmatch.fnmatch(p.name, args.name_glob)]
    if not pdfs:
        print(
            f"No PDF files under {input_dir} matching --name-glob {args.name_glob!r}",
            file=sys.stderr,
        )
        return 1

    header = footer = args.include_pdf_headers_footers
    skipped = 0
    errors = 0

    for pdf_path in pdfs:
        rel = pdf_path.relative_to(input_dir)
        out_path = (output_dir / rel).with_suffix(".md")
        if out_path.exists() and not args.overwrite:
            print(f"skip (exists): {out_path}")
            skipped += 1
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        image_path: Path | None = None
        if args.write_images:
            image_path = args.image_dir or (output_dir / "_images" / pdf_path.stem)

        try:
            md = _convert_one(
                pdf_path,
                header=header,
                footer=footer,
                show_progress=args.show_progress,
                page_separators=args.page_separators,
                dpi=args.dpi,
                ocr_language=args.ocr_language,
                front_matter=args.front_matter,
                write_images=args.write_images,
                image_path=image_path,
            )
            out_path.write_text(md, encoding="utf-8")
            print(f"wrote {out_path}")
        except Exception as e:
            print(f"ERROR {pdf_path}: {e}", file=sys.stderr)
            errors += 1

    print(f"Done. wrote {len(pdfs) - skipped - errors}, skipped {skipped}, errors {errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
