# tools/install_model.py
import sys
import argostranslate.package as pkg

FROM = "en"
TO = "es"

# Actualiza índice de paquetes y descarga el modelo correcto
pkg.update_package_index()  # consulta el índice oficial
available = pkg.get_available_packages()

# Filtra el paquete en->es
try:
    model = next(p for p in available if p.from_code == FROM and p.to_code == TO)
except StopIteration:
    sys.exit(f"No se encontró modelo {FROM}->{TO} en el índice de Argos.")

download_path = model.download()  # descarga desde la URL actualizada del índice
pkg.install_from_path(download_path)
print(f"Modelo {FROM}->{TO} instalado desde {download_path}")
