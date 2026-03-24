# tools/merge_and_translate.py
import re
from pathlib import Path
import argostranslate.translate as tr

# Orden de secciones (carpetas)
ORDERED_DIRS = [
    "00-Introduction",
    "01-Part_One",
    "02-Part_Two",
    "03-Part_Three",
    "04-Part_Four",
    "05-Appendix",
]

# Ficheros sueltos en la raíz que queremos añadir al final (si existen)
ROOT_GLOBS = [
    "Conclusion*.md",
    "Glossary*.md",
    "Index_of_Terms*.md",
    "Online_Contribution*.md",
]

root = Path(".")
build = Path("build")
build.mkdir(exist_ok=True)

def list_md_files():
    files = []
    # Carpeta a carpeta, en orden
    for d in ORDERED_DIRS:
        p = root / d
        if p.is_dir():
            files += sorted(p.glob("*.md"), key=lambda x: x.name)
    # Añade ficheros raíz deseados, si existen
    for pat in ROOT_GLOBS:
        files += sorted(root.glob(pat), key=lambda x: x.name)
    # Excluir README y el manuscrito-índice si cayesen aquí
    files = [f for f in files if f.name.lower() not in {"readme.md"} and not f.name.startswith("Agentic_Design_Patterns")]
    return files

# Traductor de párrafos preservando código y backticks
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
        # No traducir encabezados puros ni líneas que sean solo imagen/enlace
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

    parts = re.split(r"(\n\s*\n)", text)  # conserva separadores en parts[1], [3], ...
    for i in range(0, len(parts), 2):
        parts[i] = translate_paragraph(parts[i])
    text = "".join(parts)

    # Restaurar backticks y fences
    text = re.sub(r"§§INLINE(\d+)§§", lambda m: inlines[int(m.group(1))], text)
    text = re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)
    return text

def main():
    files = list_md_files()
    if not files:
        raise SystemExit("No se encontraron capítulos en las carpetas esperadas.")

    out_path = build / "book-es.md"
    with out_path.open("w", encoding="utf-8") as out:
        first = True
        for md in files:
            text = md.read_text(encoding="utf-8")
            text_es = translate_md(text)
            if not first:
                # Salto de página entre archivos (LaTeX raw: funciona con xelatex)
                out.write("\n\n\\newpage\n\n")
            out.write(text_es)
            first = False
    print(f"OK: {out_path} ({len(files)} archivos incluidos)")

if __name__ == "__main__":
    main()
