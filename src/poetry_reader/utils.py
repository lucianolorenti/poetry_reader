"""Utility functions shared across the poetry_reader package."""

from pathlib import Path
from typing import Dict, Any, Tuple


def parse_markdown_file(file_path: str) -> Dict[str, Any]:
    """Parse a markdown file and extract metadata and content.

    Expected format:
    Titulo: {titulo}
    Autor: {autor}

    {texto}

    Args:
        file_path: Path to markdown file

    Returns:
        Dict with keys: autor, titulo, texto, filepath
    """
    content = Path(file_path).read_text(encoding="utf-8")

    lines = content.split("\n")
    titulo = ""
    autor = ""
    texto_start = 0

    # Parse header lines
    for i, line in enumerate(lines):
        if line.startswith("Titulo:"):
            titulo = line.replace("Titulo:", "").strip()
        elif line.startswith("Autor:"):
            autor = line.replace("Autor:", "").strip()
        elif line.strip() == "" and titulo and autor:
            # Empty line after both headers marks start of text
            texto_start = i + 1
            break

    # Extract text content
    texto = "\n".join(lines[texto_start:]).strip()

    if not titulo:
        # Use filename as fallback
        titulo = Path(file_path).stem

    if not autor:
        autor = "Desconocido"

    return {
        "autor": autor,
        "titulo": titulo,
        "texto": texto,
        "filepath": file_path,
    }


def parse_md_file(path: str) -> Tuple[str, str, str]:
    """Parse a markdown file with the expected format:
    First non-empty line: starts with 'Titulo:' or 'Título:' or 'Title:' -> title
    Second non-empty line: starts with 'Autor:' or 'Author:' -> author
    Remaining lines: poem content.

    Returns (title, author, content_str).
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n\r") for line in f.readlines()]

    stripped = [ln.strip() for ln in lines]
    non_empty = [ln for ln in stripped if ln != ""]

    title = None
    author = None

    if len(non_empty) >= 1:
        first = non_empty[0]
        if ":" in first:
            key, val = first.split(":", 1)
            if key.strip().lower() in ("titulo", "título", "title"):
                title = val.strip()

    if len(non_empty) >= 2:
        second = non_empty[1]
        if ":" in second:
            key, val = second.split(":", 1)
            if key.strip().lower() in ("autor", "author"):
                author = val.strip()

    if title is None or author is None:
        for ln in stripped[:4]:
            if ln and ":" in ln:
                key, val = ln.split(":", 1)
                k = key.strip().lower()
                if title is None and k in ("titulo", "título", "title"):
                    title = val.strip()
                if author is None and k in ("autor", "author"):
                    author = val.strip()

    start_idx = 0
    header_count = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "":
            continue
        if ":" in ln and header_count < 2:
            header_count += 1
            start_idx = i + 1
            continue
        if header_count >= 2:
            start_idx = i
            break
    if header_count < 2:
        count = 0
        for i, ln in enumerate(lines):
            if ln.strip() != "":
                count += 1
                if count >= 2:
                    start_idx = i + 1
                    break

    content_lines = lines[start_idx:]
    while content_lines and content_lines[0].strip() == "":
        content_lines = content_lines[1:]

    content = "\n".join(content_lines).strip()

    if not title:
        title = Path(path).stem
    if not author:
        author = ""

    return title, author, content
