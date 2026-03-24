# tools/merge_and_translate.py
import re
from pathlib import Path
import argostranslate.translate as tr

# Carpeta por carpeta (en orden)
ORDERED_DIRS = [
    "00-Introduction",
    "01-Part_One",
    "02-Part_Two",
    "03-Part_Three",
    "04-Part_Four",
    "05-Appendix",
]

# Ficheros sueltos de la raíz que queremos añadir al FINAL (en este orden)
ROOT_FILES_ORDER = [
    "Conclusion*.md",                 # Conclusión
    "Glossary*.md",                   # Glosario
    "Index_of_Terms*.md",             # Índice de términos
    "Online_Contribution*.md",        # FAQ contribución (opcional)
    "README.md",                      # README (filtraremos la sección "Table of Contents")
]

# ¿Quieres conservar TODO el README sin filtrar?
PRESERVE_README_AS_IS = False  # Cambia a True si quieres incluirlo íntegro (incluida su TOC)

root = Path(".")
build = Path("build")
build.mkdir(exist_ok=True)

# --- Utilidades ---

def list_chapter_files():
    """Lista todos los .md de las carpetas de capítulos, en orden y ordenados por nombre."""
    files = []
    for d in ORDERED_DIRS:
        p = root / d
        if p.is_dir():
            files += sorted(p.glob("*.md"), key=lambda x: x.name)
    return files

def list_root_files():
    """Devuelve los ficheros raíz en el orden deseado, si existen."""
    files = []
    for pattern in ROOT_FILES_ORDER:
        matched = sorted(root.glob(pattern), key=lambda x: x.name)
        files.extend(matched)
    return files

def is_readme(path: Path) -> bool:
    return path.name.lower() == "readme.md"

def strip_sections_by_title(md_text: str, titles_to_strip):
    """
    Elimina secciones completas cuyo encabezado H1..H6 coincida (case-insensitive)
    con alguna cadena en 'titles_to_strip'. Quita desde el encabezado hasta
    el siguiente encabezado del mismo nivel o superior.
    """
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
                # Saltar hasta próximo heading de nivel <= 'level'
                i += 1
                while i < len(lines):
                    m2 = re.match(r'^\s*#{1,6}\s+', lines[i])
                    if m2:
                        # Compara nivel
                        lvl2 = len(re.match(r'^\s*(#{1,6})', lines[i]).group(1))
                        if lvl2 <= level:
                            break
                    i += 1
                continue  # no añadimos esta sección
        out.append(line)
        i += 1
    return "\n".join(out)

# Traducción preservando bloques de código y backticks
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
        # No traducir encabezados ni líneas que sean solo imagen/enlace
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

    parts = re.split(r"(\n\s*\n)", text)  # conserva separadores
    for i in range(0, len(parts), 2):
        parts[i] = translate_paragraph(parts[i])
    text = "".join(parts)

    # Restaurar
    text = re.sub(r"§§INLINE(\d+)§§", lambda m: inlines[int(m.group(1))], text)
    text = re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)
    return text

# --- Flujo principal ---

def main():
    # 1) Capítulos por carpetas
    chapter_files = list_chapter_files()

    # 2) Ficheros raíz al final (Conclusión, Glosario, Índice..., README)
    extra_files = list_root_files()

    # 3) Excluir el manuscrito-índice y evitar duplicados accidentales
    def skip(f: Path) -> bool:
        name = f.name
        if name.lower() == "readme.md":
            return False
        if name.lower() == "license" or name.lower() == "license.md":
            return True
        if name.startswith("Agentic_Design_Patterns"):
            return True  # es el "índice" con enlaces externos
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
            text_es = translate_md(text)
            if not first:
                out.write("\n\n\\newpage\n\n")
            out.write(text_es)
            first = False

        # Escribe extras (Conclusión, Glosario, Índice..., README)
        for md in extra_files:
            text = md.read_text(encoding="utf-8")
            if is_readme(md) and not PRESERVE_README_AS_IS:
                # Elimina la sección "Table of Contents" del README para no duplicar el TOC
                text = strip_sections_by_title(text, ["Table of Contents"])
            text_es = translate_md(text)
            out.write("\n\n\\newpage\n\n")
            out.write(text_es)

    print(f"OK: {out_path} ({len(chapter_files)} capítulos + {len(extra_files)} anexos raíz)")

if __name__ == "__main__":
    main()
