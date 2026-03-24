# tools/merge_and_translate.py
import re
from pathlib import Path
import argostranslate.translate as tr

ORDERED_DIRS = [
    "00-Introduction",
    "01-Part_One",
    "02-Part_Two",
    "03-Part_Three",
    "04-Part_Four",
    "05-Appendix",
]

ROOT_FILES_ORDER = [
    "Conclusion*.md",
    "Glossary*.md",
    "Index_of_Terms*.md",
    "Online_Contribution*.md",
    "README.md",
]

PRESERVE_README_AS_IS = False

root = Path(".")
build = Path("build")
assets_dir = root / "assets"
build.mkdir(exist_ok=True)

def list_chapter_files():
    files = []
    for d in ORDERED_DIRS:
        p = root / d
        if p.is_dir():
            files += sorted(p.glob("*.md"), key=lambda x: x.name)
    return files

def list_root_files():
    files = []
    for pattern in ROOT_FILES_ORDER:
        files += sorted(root.glob(pattern), key=lambda x: x.name)
    return files

def is_readme(path: Path) -> bool:
    return path.name.lower() == "readme.md"

def strip_sections_by_title(md_text: str, titles_to_strip):
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

# ---------- NUEVO: normalización de rutas de imagen ----------

def _normalize_src(src: str, md_path: Path) -> str:
    """Normaliza la ruta de una imagen para que funcione desde la raíz (build/)."""
    s = src.strip()

    # No tocar URLs absolutas o data URIs
    if s.startswith(("http://", "https://", "data:")):
        return s

    # Arreglar erratas y ../assets -> assets
    s = s.replace("assests/", "assets/").replace("../assests/", "assets/")
    if s.startswith("../assets/"):
        s = s[3:]  # quita ../

    # Si es un nombre suelto, intenta resolver a assets/<archivo>
    if "/" not in s:
        cand = assets_dir / s
        if cand.exists():
            return f"assets/{s}"

    # Si la ruta es relativa al archivo original, intenta resolver y remapear a assets/
    abs_candidate = (md_path.parent / s).resolve()
    try:
        rel = abs_candidate.relative_to(root.resolve())
        rel_str = str(rel).replace("\\", "/")
        # Si está dentro de assets/, devuelve relativo a raíz
        if rel_str.startswith("assets/"):
            return rel_str
    except Exception:
        pass

    # Ultimo recurso: si ya comienza por assets/ lo dejamos
    return s

def fix_image_paths(md_text: str, md_path: Path) -> str:
    # ![alt](src)  -> normalizar "src"
    def repl(m):
        alt = m.group(1)
        src = m.group(2)
        new_src = _normalize_src(src, md_path)
        return f"![{alt}]({new_src})"
    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, md_text)

# ---------- Traducción preservando bloques ----------

FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE = re.compile(r"`[^`]+`")

def translate_md(text: str) -> str:
    fences, inlines = [], []

    def keep_fence(m):
        fences.append(m.group(0))
        return f"§§FENCE{len(fences)-1}§§"

    def keep_inline(m):
        inlines.append(m.group(0))
        return f"§§INLINE{len(inlines)-1}§§"

    text = FENCE.sub(keep_fence, text)
    text = INLINE.sub(keep_inline, text)

    def translate_paragraph(p: str) -> str:
        ps = p.strip()
        if not ps:
            return p
        if re.match(r"^\s*#{1,6}\s", ps):
            return p
        if re.match(r"^\s*(!?\[.*?\]\(.*?\))\s*$", ps):
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

    text = re.sub(r"§§INLINE(\d+)§§", lambda m: inlines[int(m.group(1))], text)
    text = re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)
    return text

def main():
    # Capítulos
    chapter_files = list_chapter_files()
    # Extras raíz
    extra_files = list_root_files()

    def skip(f: Path) -> bool:
        name = f.name
        if name.lower() in {"license", "license.md"}:
            return True
        if name.startswith("Agentic_Design_Patterns"):
            return True  # manuscrito-índice con enlaces externos
        return False

    chapter_files = [f for f in chapter_files if not skip(f)]
    extra_files = [f for f in extra_files if not skip(f)]

    if not chapter_files:
        raise SystemExit("No se encontraron capítulos en las carpetas esperadas.")

    out_path = build / "book-es.md"
    with out_path.open("w", encoding="utf-8") as out:
        first = True

        for md in chapter_files:
            text = md.read_text(encoding="utf-8")
            text = fix_image_paths(text, md)          # <<< normaliza rutas
            text_es = translate_md(text)
            if not first:
                out.write("\n\n\\newpage\n\n")
            out.write(text_es)
            first = False

        for md in extra_files:
            text = md.read_text(encoding="utf-8")
            if is_readme(md) and not PRESERVE_README_AS_IS:
                text = strip_sections_by_title(text, ["Table of Contents"])
            text = fix_image_paths(text, md)          # <<< normaliza rutas
            text_es = translate_md(text)
            out.write("\n\n\\newpage\n\n")
            out.write(text_es)

    print(f"OK: {out_path} ({len(chapter_files)} capítulos + {len(extra_files)} anexos raíz)")

if __name__ == "__main__":
    main()
