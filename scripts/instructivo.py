#!/usr/bin/env python3
"""
Muestra el instructivo generado por scripts/bootstrap_django.py.

Permite listar los instructivos disponibles y visualizar uno concreto
para recordar los pasos manuales en PythonAnywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


SUMMARY_DIR = Path(__file__).resolve().parent / "bootstrap_runs"


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualiza el instructivo final del bootstrap de Django."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Solo listar los instructivos disponibles.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Abrir el instructivo más reciente.",
    )
    parser.add_argument(
        "--file",
        help="Ruta a un archivo JSON específico generado por bootstrap_django.py.",
    )
    return parser.parse_args(argv)


def obtener_archivos() -> List[Path]:
    if not SUMMARY_DIR.exists():
        return []
    return sorted(SUMMARY_DIR.glob("bootstrap_*.json"))


def imprimir_lista(archivos: List[Path]) -> None:
    if not archivos:
        print("No hay instructivos guardados aún.")
        return
    print("Instructivos disponibles:")
    for idx, archivo in enumerate(archivos, start=1):
        print(f"  {idx}. {archivo.name}")


def seleccionar_interactivo(archivos: List[Path]) -> Optional[Path]:
    if not archivos:
        print("No hay instructivos disponibles.")
        return None
    imprimir_lista(archivos)
    while True:
        respuesta = input("Ingresa el número del instructivo a mostrar (o Enter para cancelar): ").strip()
        if not respuesta:
            return None
        if not respuesta.isdigit():
            print("Ingresa un número válido.")
            continue
        indice = int(respuesta)
        if 1 <= indice <= len(archivos):
            return archivos[indice - 1]
        print("Número fuera de rango.")


def cargar_json(ruta: Path) -> Dict[str, Any]:
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


def mostrar_instructivo(datos: Dict[str, Any]) -> None:
    domain = datos.get("domain", "<dominio>")
    project_root = datos.get("project_root", "<project_root>")
    manage_py = datos.get("manage_py", "<manage_py>")
    venv_path = datos.get("venv_path", "<venv_path>")
    static_root = datos.get("static_root") or f"{project_root}/staticfiles"
    python_version = datos.get("python_version", "<python_version>")
    wsgi_path = datos.get("wsgi_path", "/var/www/<usuario>_pythonanywhere_com_wsgi.py")
    requirements_path = datos.get("requirements_path", "<requirements>")
    timestamp = datos.get("timestamp")
    dry_run = datos.get("dry_run", False)

    cabecera = f"Instructivo guardado: {timestamp}" if timestamp else "Instructivo"
    print(f"\n=== {cabecera} ===")
    print(f"Proyecto raíz: {project_root}")
    print(f"manage.py: {manage_py}")
    print(f"Virtualenv: {venv_path} (Python {python_version})")
    print(f"requirements.txt: {requirements_path}")
    print(f"STATIC_ROOT: {static_root}")
    print(f"Archivo WSGI: {wsgi_path}")
    print(f"Dominio: {domain}")
    if dry_run:
        print("⚠️ Este instructivo proviene de una ejecución en modo dry-run.")

    print("\nChecklist manual:")
    print("1. Crear/validar WebApp:")
    print(
        f"   - Add a new web app → Manual configuration → Python {python_version}."
    )
    print(f"   - Dominio: {domain}")
    print("2. Web → Source code / Working directory:")
    print(f"   - Source code: {project_root}")
    print(f"   - Working directory: {project_root}")
    print("3. Web → Virtualenv:")
    print(f"   - Ruta: {venv_path}")
    print("4. Web → WSGI configuration file:")
    print(f"   - Edita {wsgi_path} y asegúrate de contener:")
    print(f"       path = \"{project_root}\"")
    print("       os.environ.setdefault('DJANGO_SETTINGS_MODULE', '<tu_proyecto>.settings')")
    print("   - Importa application = get_wsgi_application().")
    print("5. Web → Static files:")
    print("   - Mapeo recomendado: URL /static/ → "
          f"{static_root}")
    print("6. settings.py → ALLOWED_HOSTS:")
    print(
        f"   - Añade '{domain}', 'www.{domain}' y '127.0.0.1', 'localhost' si trabajas en local."
    )
    print("7. Web → Reload:")
    print("   - Pulsa “Reload” y renueva 'Run until 3 months from today'.")
    print("8. Logs & verificación:")
    print(
        f"   - Revisa {domain}.error.log, access.log y /var/log si aparece algún error."
    )
    print(f"   - Comprueba https://{domain}/ en el navegador.")
    print("==============================\n")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    archivos = obtener_archivos()

    if args.list:
        imprimir_lista(archivos)
        return 0

    objetivo: Optional[Path] = None

    if args.file:
        objetivo = Path(args.file).expanduser()
        if not objetivo.is_absolute():
            potencial = SUMMARY_DIR / objetivo
            if potencial.exists():
                objetivo = potencial
        if not objetivo.exists():
            print(f"No se encontró el instructivo en {objetivo}.")
            return 1
    elif args.latest:
        if archivos:
            objetivo = archivos[-1]
        else:
            print("No hay instructivos guardados aún.")
            return 1
    else:
        objetivo = seleccionar_interactivo(archivos)
        if objetivo is None:
            print("Operación cancelada.")
            return 0

    datos = cargar_json(objetivo)
    mostrar_instructivo(datos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

