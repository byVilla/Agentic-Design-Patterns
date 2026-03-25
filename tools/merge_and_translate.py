# tools/merge_and_translate.py
# -*- coding: utf-8 -*-
"""
Fusiona y traduce al español (registro técnico) la documentación Markdown del repo:
- Recorre carpetas 00..05 en orden y concatena sus .md
- Añade ficheros raíz (Conclusión, Glosario, Índice, FAQ, README)
- Normaliza rutas de imágenes para que funcionen desde la raíz (build/) **PRESERVANDO** la sintaxis ![alt](src)
- Traduce preservando bloques de código/backticks
- Traduce encabezados y añade el término original en inglés entre paréntesis
- Inserta \newpage entre archivos para un paginado limpio (PDF con xelatex)
Requisitos: argostranslate (modelo EN->ES instalado previamente en el workflow)
"""

from __future__ import annotations
import re
from pathlib import Path
import argostranslate.translate as tr

# ============= Configuración =============

ORDERED_DIRS = [
    "00-Introduction",
    "01-Part_One",
    "02-Part_Two",
    "03-Part_Three",
    "04-Part_Four",
    "05-Appendix",
]

ROOT_FILES_ORDER = [
    "Conclusion*.md",                 # Conclusión
    "Glossary*.md",                   # Glosario
    "Index_of_Terms*.md",             # Índice de términos
    "Online_Contribution*.md",        # FAQ contribución (opcional)
    "README.md",                      # README (filtramos su TOC por defecto)
]

PRESERVE_README_AS_IS = False  # pon True si quieres incluir TODO el README sin filtrar

# Términos a mantener en inglés en headings (se añaden entre paréntesis)
KEEP_EN_TERMS = [
    "Prompt Chaining",
    "Routing",
    "Parallelization",
    "Reflection",
    "Tool Use",
    "Planning",
    "Multi-Agent",
    "Memory Management",
    "Learning and Adaptation",
    "Model Context Protocol (MCP)",
    "Goal Setting and Monitoring",
    "Exception Handling and Recovery",
    "Human-in-the-Loop",
    "Knowledge Retrieval (RAG)",
    "Inter-Agent Communication (A2A)",
    "Resource-Aware Optimization",
    "Reasoning Techniques",
    "Guardrails/Safety Patterns",
    "Evaluation and Monitoring",
    "Prioritization",
    "Exploration and Discovery",
    "Appendix",
]
HEADINGS_APPEND_ENGLISH = True

# ============= Paths / regex =============

root = Path(".")
build = Path("build")
assets_dir = root / "assets"
build.mkdir(exist_ok=True)

HEADING_RE = re.compile(r"^(\s*)(#{1,6})\s+(.*)$", re.MULTILINE)
FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE = re.compile(r"`[^`]+`")

# ============= Utilidades =============

def list_chapter_files() -> list[Path]:
    files: list[Path] = []
    for d in ORDERED_DIRS:
        p = root / d
        if p.is_dir():
            files += sorted(p.glob("*.md"), key=lambda x: x.name)
    return files

def list_root_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ROOT_FILES_ORDER:
        files += sorted(root.glob(pattern), key=lambda x: x.name)
    return files

def is_readme(path: Path) -> bool:
    return path.name.lower() == "readme.md"

def strip_sections_by_title(md_text: str, titles_to_strip: list[str]) -> str:
    """Quita secciones enteras cuyo heading coincide con títulos dados."""
    lines = md_text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\s*)(#{1,6})\s+(.*)$', line)
        if m:
            level = len(m.group(2))
            title = m.group(3).strip().lower()
            if any(title.startswith(t.strip().lower()) for t in titles_to_strip):
                i += 1
                while i < len(lines):
                    m2 = re.match(r'^\s*#{1,6}\s+', lines[i])
                    if m2:
                        lvl2 = len(re.match(r'^\s*(#{1,6})', lines[i]).group(1))
                        if lvl2 <= level:
                            break
                    i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)

# ============= Normalización de imágenes =============

def _normalize_src(src: str, md_path: Path) -> str:
    """
    Normaliza la ruta para que funcione desde la raíz (build/):
    - ../assets/...  -> assets/...
    - ./assets/...   -> assets/...
    - assests/...    -> assets/...
    - nombre suelto  -> assets/<nombre> si existe
    - rutas relativas -> si caen dentro de assets/, remapear a 'assets/...'
    """
    s = src.strip()

    # No tocar URLs absolutas ni data URIs
    if s.startswith(("http://", "https://", "data:")):
        return s

    # Correcciones comunes
    s = s.replace("assests/", "assets/").replace("../assests/", "assets/")
    s = s.replace("../assets/", "assets/").replace("./assets/", "assets/")

    # Nombre suelto -> mirar en assets/
    if "/" not in s:
        cand = assets_dir / s
        if cand.exists():
            return f"assets/{s}"

    # Resolver desde el archivo actual
    abs_candidate = (md_path.parent / s).resolve()
    try:
        rel = abs_candidate.relative_to(root.resolve())
        rel_str = str(rel).replace("\\", "/")
        if rel_str.startswith("assets/"):
            return rel_str
    except Exception:
        pass

    return s

def _fix_markdown_images(md_text: str, md_path: Path) -> str:
    """
    Reescribe ![alt](src) -> ![alt](src_normalizada)
    Conserva el 'alt' y la estructura Markdown.
    """
    def repl(m):
        alt = m.group(1) or ""
        src = m.group(2)
        new_src = _normalize_src(src, md_path)
        return f"![{alt}]({new_src})"
    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, md_text)

def _fix_html_images(md_text: str, md_path: Path) -> str:
    """
    Reescribe <img ... src="..."> -> <img ... src="src_normalizada">
    """
    def repl(m):
        before = m.group(1) or ""
        src = m.group(2)
        after = m.group(3) or ""
        new_src = _normalize_src(src, md_path)
        return f'<img{before}src="{new_src}"{after}>'
    return re.sub(r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*)>', repl, md_text, flags=re.IGNORECASE)

def _fix_reference_defs(md_text: str, md_path: Path) -> str:
    """
    Reescribe definiciones de referencia: [label]: ruta -> [label]: ruta_normalizada
    """
    def repl(m):
        label = m.group(1)
        url = m.group(2)
        new_url = _normalize_src(url, md_path)
        return f'[{label}]: {new_url}'
    return re.sub(r'^\s*\[([^\]]+)\]:\s*(\S+)\s*$', repl, md_text, flags=re.MULTILINE)

def fix_image_paths(md_text: str, md_path: Path) -> str:
    md_text = _fix_markdown_images(md_text, md_path)
    md_text = _fix_html_images(md_text, md_path)
    md_text = _fix_reference_defs(md_text, md_path)
    return md_text

# ============= Traducción =============

def translate_heading_line(m: re.Match) -> str:
    """Traduce un heading y añade (EnglishTerm) si corresponde."""
    indent, hashes, original_text = m.group(1), m.group(2), m.group(3)
    try:
        es = tr.translate(original_text, "en", "es")
    except Exception:
        es = original_text  # fallback

    if HEADINGS_APPEND_ENGLISH:
        keep = [t for t in KEEP_EN_TERMS if t.lower() in original_text.lower()]
        if keep:
            suffix = " (" + ", ".join(keep) + ")"
            if suffix not in es:
                es = es + suffix

    return f"{indent}{hashes} {es}"

def translate_md(text: str) -> str:
    """
    Traduce Markdown preservando código/backticks; headings se traducen en una pasada final.
    """
    fences, inlines = [], []

    def keep_fence(m):
        fences.append(m.group(0))
        return f"§§FENCE{len(fences)-1}§§"

    def keep_inline(m):
        inlines.append(m.group(0))
        return f"§§INLINE{len(inlines)-1}§§"

    # Proteger bloques de código y backticks
    text = FENCE.sub(keep_fence, text)
    text = INLINE.sub(keep_inline, text)

    # Traducción por párrafos (saltando headings aquí)
    def translate_paragraph(p: str) -> str:
        ps = p.strip()
        if not ps:
            return p
        if re.match(r"^\s*(!?\[.*?\]\(.*?\))\s*$", ps):  # imagen o enlace puro
            return p
        if re.match(r"^\s*#{1,6}\s", ps):                # heading -> lo tratamos luego
            return p
        if len(ps) < 6:
            return p
        try:
            return tr.translate(p, "en", "es")
        except Exception:
            return p

    parts = re.split(r"(\n\s*\n)", text)
    for i in range(0, len(parts), 2):
        parts[i] = translate_paragraph(parts[i])
    text = "".join(parts)

    # Restaurar inline y fences
    text = re.sub(r"§§INLINE(\d+)§§", lambda m: inlines[int(m.group(1))], text)
    text = re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)

    # Pasada final: headings
    text = HEADING_RE.sub(translate_heading_line, text)
    return text

# ============= Flujo principal =============

def main() -> None:
    # 1) Capítulos por carpetas
    chapter_files = list_chapter_files()
    # 2) Ficheros raíz
    extra_files = list_root_files()

    # 3) Excluir manuscrito-índice y licencia
    def skip(f: Path) -> bool:
        name = f.name
        if name.lower() in {"license", "license.md"}:
            return True
        if name.startswith("Agentic_Design_Patterns"):
            return True  # índice externo, sin cuerpo
        return False

    chapter_files = [f for f in chapter_files if not skip(f)]
    extra_files = [f for f in extra_files if not skip(f)]

    if not chapter_files:
        raise SystemExit("No se encontraron capítulos en las carpetas esperadas.")

    out_path = build / "book-es.md"
    with out_path.open("w", encoding="utf-8") as out:
        first = True

        # Escribe capítulos
        for md in chapter_files:
            text = md.read_text(encoding="utf-8")
            text = fix_image_paths(text, md)          # <<< normaliza rutas conservando ![alt](src)
            text_es = translate_md(text)
            if not first:
                out.write("\n\n\\newpage\n\n")
            out.write(text_es)
            first = False

        # Escribe anexos/raíces
        for md in extra_files:
            text = md.read_text(encoding="utf-8")
            if is_readme(md) and not PRESERVE_README_AS_IS:
                text = strip_sections_by_title(text, ["Table of Contents"])
            text = fix_image_paths(text, md)
            text_es = translate_md(text)
            out.write("\n\n\\newpage\n\n")
            out.write(text_es)

    print(f"OK: {out_path} ({len(chapter_files)} capítulos + {len(extra_files)} anexos raíz)")

if __name__ == "__main__":
    main()
