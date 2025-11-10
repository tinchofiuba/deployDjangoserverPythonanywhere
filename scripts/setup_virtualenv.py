#!/usr/bin/env python3
"""
Script interactivo para crear y preparar un entorno virtual en PythonAnywhere.

Flujo:
1. Solicita al usuario el nombre del entorno virtual (se creará en ~/.virtualenvs/<nombre>).
2. Permite indicar el intérprete de Python a usar (por defecto python3.10).
3. Genera el virtualenv si no existe.
4. Instala las dependencias definidas en requirements.txt.
5. Muestra las instrucciones finales para activar el entorno.

Ejemplo de uso dentro de la consola Bash de PythonAnywhere:
    $ python3 scripts/setup_virtualenv.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


DEFAULT_VENV_ROOT = Path.home() / ".virtualenvs"
DEFAULT_REQUIREMENTS_FILE = Path("requirements.txt")
DEFAULT_PYTHON_BINARY = "python3.10"


class SetupError(RuntimeError):
    """Error controlado durante la creación del virtualenv."""


def prompt(texto: str, valor_por_defecto: Optional[str] = None) -> str:
    """
    Pregunta por consola y devuelve la respuesta.

    Si el usuario no escribe nada y existe un valor por defecto, se devuelve ese valor.
    """
    if valor_por_defecto:
        mensaje = f"{texto} [{valor_por_defecto}]: "
    else:
        mensaje = f"{texto}: "

    respuesta = input(mensaje).strip()
    if not respuesta and valor_por_defecto is not None:
        return valor_por_defecto
    return respuesta


def validar_requirements(path: Path) -> None:
    """Verifica que el archivo requirements.txt exista."""
    if not path.exists():
        raise SetupError(
            f"No se encontró el archivo de dependencias en {path}. "
            "Asegurate de ejecutar este script desde la raíz del repositorio."
        )


def crear_virtualenv(destino: Path, python_bin: str) -> None:
    """Crea el entorno virtual usando el intérprete indicado."""
    if destino.exists():
        raise SetupError(
            f"El entorno virtual ya existe en {destino}. "
            "Elegí otro nombre o eliminá el entorno anterior manualmente."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)

    comando = [python_bin, "-m", "venv", str(destino)]
    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            "Fallo la creación del virtualenv. "
            f"Revisá que el intérprete '{python_bin}' exista en el sistema."
        ) from exc


def instalar_dependencias(venv_path: Path, requirements_path: Path) -> None:
    """Instala las dependencias dentro del entorno virtual recién creado."""
    pip_path = venv_path / "bin" / "pip"
    if not pip_path.exists():
        raise SetupError(
            f"No se encontró pip en {pip_path}. "
            "Verifica que el virtualenv se haya creado correctamente."
        )

    comando = [str(pip_path), "install", "-r", str(requirements_path)]
    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            "Ocurrió un error instalando las dependencias. "
            "Revisá el archivo requirements.txt y el log mostrado arriba."
        ) from exc


def mostrar_resumen_final(venv_path: Path) -> None:
    """Muestra instrucciones para activar el entorno virtual."""
    activate_script = venv_path / "bin" / "activate"
    print("\n✅ Entorno virtual listo.")
    print("Para activarlo en futuras sesiones ejecuta:")
    print(f"    source {activate_script}")
    print("\nPara desactivarlo, utiliza:")
    print("    deactivate")


def main() -> int:
    try:
        print("=== Setup de entorno virtual para PythonAnywhere ===")

        venv_name = prompt("Nombre del virtualenv a crear", None)
        if not venv_name:
            raise SetupError("El nombre del virtualenv no puede estar vacío.")

        venv_root_input = prompt(
            "Directorio raíz para los virtualenvs", str(DEFAULT_VENV_ROOT)
        )
        venv_root = Path(os.path.expanduser(venv_root_input)).resolve()
        venv_path = venv_root / venv_name

        python_bin = prompt(
            "Intérprete de Python a usar", DEFAULT_PYTHON_BINARY
        )

        requirements_input = prompt(
            "Ruta al archivo requirements.txt", str(DEFAULT_REQUIREMENTS_FILE)
        )
        requirements_path = Path(requirements_input).resolve()

        validar_requirements(requirements_path)
        crear_virtualenv(venv_path, python_bin)
        instalar_dependencias(venv_path, requirements_path)
        mostrar_resumen_final(venv_path)

        return 0

    except SetupError as error:
        print(f"\n❌ Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

