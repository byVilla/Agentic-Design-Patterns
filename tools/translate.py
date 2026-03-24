# tools/translate.py
import re
from pathlib import Path
import argostranslate.translate as tr

root = Path(".")
# Usa el manuscrito MD compilado en la raíz (el repo lo trae con ese prefijo)
candidates = sorted(root.glob("Agentic_Design_Patterns*.md"))
if not candidates:
    raise SystemExit("No se encontró el manuscrito compilado en la raíz.")
src = candidates[0]
text = src.read_text(encoding="utf-8")

# Proteger bloques de código y backticks
FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE = re.compile(r"`[^`]+`")
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
    # No traducir títulos ni líneas que sean solo imagen/enlace
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

# Traducción por párrafos (conservando separadores)
parts = re.split(r"(\n\s*\n)", text)
for i in range(0, len(parts), 2):
    parts[i] = translate_paragraph(parts[i])
text = "".join(parts)

# Restaurar lo protegido
text = re.sub(r"§§INLINE(\d+)§§", lambda m: inlines[int(m.group(1))], text)
text = re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)

out = Path("build")
out.mkdir(exist_ok=True)
(out / "book-es.md").write_text(text, encoding="utf-8")
print("OK: build/book-es.md")
