#!/usr/bin/env python3
"""
doc_to_md.py — Converte file .doc / .docx in Markdown.

Dipendenze:
    pip install mammoth        # per .docx (nativo)
    pip install markdownify    # per pulire l'HTML di mammoth
    pandoc                     # opzionale, usato per .doc e come fallback

Uso:
    python doc_to_md.py documento.docx
    python doc_to_md.py documento.doc
    python doc_to_md.py documento.docx -o output.md
    python doc_to_md.py *.docx          # batch, crea file .md accanto agli originali
"""

import argparse
import subprocess
import sys
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def check_dependency(name: str) -> bool:
    """Restituisce True se il comando è disponibile nel PATH."""
    try:
        subprocess.run([name, "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def convert_with_mammoth(src: Path) -> str:
    """Converte .docx → Markdown tramite mammoth (puro Python)."""
    try:
        import mammoth  # type: ignore
    except ImportError:
        raise RuntimeError("❌  Installa mammoth:  pip install mammoth")

    # Prova a importare markdownify per una conversione più fedele
    try:
        from markdownify import markdownify  # type: ignore

        with open(src, "rb") as f:
            result = mammoth.convert_to_html(f)
        md = markdownify(result.value, heading_style="ATX")
    except ImportError:
        # Fallback: usa il convertitore Markdown integrato di mammoth
        with open(src, "rb") as f:
            result = mammoth.convert_to_markdown(f)
        md = result.value

    if result.messages:
        for msg in result.messages:
            print(f"  ⚠  {msg}", file=sys.stderr)

    return md.strip()


def convert_with_pandoc(src: Path) -> str:
    """Converte qualsiasi formato supportato → Markdown tramite pandoc."""
    if not check_dependency("pandoc"):
        raise RuntimeError(
            "❌  pandoc non trovato. Installalo da https://pandoc.org/installing.html"
        )

    result = subprocess.run(
        ["pandoc", str(src), "-f", "docx", "-t", "markdown", "--wrap=none"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def doc_to_docx(src: Path) -> Path:
    """Converte .doc → .docx con LibreOffice (richiesto solo per file .doc)."""
    if not check_dependency("soffice"):
        raise RuntimeError(
            "❌  LibreOffice non trovato.\n"
            "    Installalo da https://www.libreoffice.org o usa un .docx direttamente."
        )

    subprocess.run(
        ["soffice", "--headless", "--convert-to", "docx", str(src),
         "--outdir", str(src.parent)],
        capture_output=True,
        check=True,
    )
    converted = src.with_suffix(".docx")
    if not converted.exists():
        raise RuntimeError(f"❌  Conversione .doc → .docx fallita per: {src}")
    return converted


# ── Core ─────────────────────────────────────────────────────────────────────

def convert(src: Path, engine: str) -> str:
    """Converte src in Markdown e restituisce la stringa."""
    suffix = src.suffix.lower()

    if suffix == ".doc":
        print(f"  📄  Converto .doc → .docx prima della conversione…")
        src = doc_to_docx(src)
        suffix = ".docx"

    if suffix != ".docx":
        raise ValueError(f"❌  Formato non supportato: {suffix}  (usa .doc o .docx)")

    if engine == "pandoc":
        return convert_with_pandoc(src)
    else:
        return convert_with_mammoth(src)


def process_file(src: Path, dst: Path | None, engine: str) -> None:
    """Processa un singolo file."""
    if not src.exists():
        print(f"⚠  File non trovato, saltato: {src}", file=sys.stderr)
        return

    print(f"🔄  {src.name} …")
    md = convert(src, engine)

    output = dst or src.with_suffix(".md")
    output.write_text(md, encoding="utf-8")
    print(f"✅  Salvato: {output}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Converte .doc/.docx in Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Uno o più file .doc/.docx da convertire",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="OUTPUT",
        help="File di output (solo se viene passato un singolo file)",
    )
    parser.add_argument(
        "--engine",
        choices=["mammoth", "pandoc"],
        default="mammoth",
        help="Motore di conversione (default: mammoth)",
    )

    args = parser.parse_args()
    sources = [Path(f) for f in args.files]

    if args.output and len(sources) > 1:
        parser.error("--output può essere usato solo con un singolo file")

    dst = Path(args.output) if args.output else None

    for src in sources:
        process_file(src, dst if len(sources) == 1 else None, args.engine)


if __name__ == "__main__":
    main()
