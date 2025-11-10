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

import argparse
import os
import shlex
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Interpreta argumentos opcionales para automatizar el flujo."""
    parser = argparse.ArgumentParser(
        description="Crea un virtualenv en PythonAnywhere con ayudas interactivas."
    )
    parser.add_argument(
        "--name",
        help="Nombre del virtualenv a crear (si no se pasa, se solicitará por consola).",
    )
    parser.add_argument(
        "--venv-root",
        help="Ruta base donde residirá el virtualenv (default: ~/.virtualenvs).",
    )
    parser.add_argument(
        "--python",
        help=f"Intérprete de Python a usar (default interactivo: {DEFAULT_PYTHON_BINARY}).",
    )
    parser.add_argument(
        "--requirements",
        help="Ruta al archivo requirements.txt (default interactivo: ./requirements.txt).",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Permite reutilizar un virtualenv existente sin recrearlo.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Omite la instalación de dependencias (útil para preparar entorno manualmente).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los comandos sin ejecutarlos realmente.",
    )
    return parser.parse_args(argv)


def validar_requirements(path: Path) -> None:
    """Verifica que el archivo requirements.txt exista."""
    if not path.exists():
        raise SetupError(
            f"No se encontró el archivo de dependencias en {path}. "
            "Asegurate de ejecutar este script desde la raíz del repositorio."
        )


def validar_interprete(python_bin: str, dry_run: bool) -> None:
    """Comprueba que el intérprete de Python exista y sea ejecutable."""
    if dry_run:
        print(f"[dry-run] Se omite validación del intérprete {python_bin}.")
        return

    try:
        resultado = subprocess.run(
            [python_bin, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise SetupError(
            f"No se encontró el intérprete '{python_bin}'. "
            "Asegurate de que esté instalado en PythonAnywhere."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            f"El intérprete '{python_bin}' devolvió un error al consultar la versión."
        ) from exc

    version = resultado.stdout.decode().strip() or resultado.stderr.decode().strip()
    if version:
        print(f"Detectado intérprete: {version}")


def _mostrar_comando(comando: list[str]) -> None:
    """Imprime el comando formateado de forma segura."""
    joined = " ".join(shlex.quote(str(item)) for item in comando)
    print(f"$ {joined}")


def crear_virtualenv(destino: Path, python_bin: str, *, dry_run: bool, reuse: bool) -> bool:
    """Crea el entorno virtual usando el intérprete indicado. Devuelve True si se creó."""
    if destino.exists():
        if reuse:
            print(f"El virtualenv {destino} ya existe y será reutilizado.")
            return False
        raise SetupError(
            f"El entorno virtual ya existe en {destino}. "
            "Elegí otro nombre, usá --reuse o eliminá el entorno anterior manualmente."
        )

    destino.parent.mkdir(parents=True, exist_ok=True)

    comando = [python_bin, "-m", "venv", str(destino)]
    _mostrar_comando(comando)
    if dry_run:
        print("[dry-run] Virtualenv no creado.")
        return False

    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            "Falló la creación del virtualenv. "
            f"Revisá que el intérprete '{python_bin}' exista en el sistema."
        ) from exc
    return True


def instalar_dependencias(
    venv_path: Path, requirements_path: Path, *, dry_run: bool
) -> None:
    """Instala las dependencias dentro del entorno virtual."""
    pip_path = venv_path / "bin" / "pip"
    if not pip_path.exists():
        raise SetupError(
            f"No se encontró pip en {pip_path}. "
            "Verifica que el virtualenv se haya creado correctamente."
        )

    comando = [str(pip_path), "install", "-r", str(requirements_path)]
    _mostrar_comando(comando)
    if dry_run:
        print("[dry-run] Dependencias no instaladas.")
        return

    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as exc:
        raise SetupError(
            "Ocurrió un error instalando las dependencias. "
            "Revisá el archivo requirements.txt y el log mostrado arriba."
        ) from exc


def mostrar_resumen_final(
    venv_path: Path,
    *,
    creado: bool,
    reutilizado: bool,
    dependencias_instaladas: bool,
    dry_run: bool,
) -> None:
    """Muestra instrucciones para activar el entorno virtual."""
    activate_script = venv_path / "bin" / "activate"
    if dry_run:
        print("\n🧪 Modo dry-run: no se realizaron cambios reales.")
    elif creado:
        print("\n✅ Entorno virtual listo.")
    elif reutilizado:
        print("\nℹ️ Se reutilizó el virtualenv existente.")
    else:
        print("\nℹ️ El virtualenv no se modificó.")

    print("Para activarlo en futuras sesiones ejecuta:")
    print(f"    source {activate_script}")
    if dependencias_instaladas:
        print("\nSe instalaron las dependencias desde requirements.txt.")
    else:
        print("\nNo se instalaron dependencias en esta ejecución.")
    print("\nPara desactivarlo, utiliza:")
    print("    deactivate")


def main(argv: Optional[list[str]] = None) -> int:
    try:
        print("=== Setup de entorno virtual para PythonAnywhere ===")
        args = parse_args(argv or sys.argv[1:])

        venv_name = args.name or prompt("Nombre del virtualenv a crear")
        if not venv_name:
            raise SetupError("El nombre del virtualenv no puede estar vacío.")

        venv_root_input = args.venv_root or prompt(
            "Directorio raíz para los virtualenvs", str(DEFAULT_VENV_ROOT)
        )
        venv_root = Path(os.path.expanduser(venv_root_input)).resolve()
        venv_path = venv_root / venv_name

        python_bin = args.python or prompt(
            "Intérprete de Python a usar", DEFAULT_PYTHON_BINARY
        )
        validar_interprete(python_bin, args.dry_run)

        requirements_input = args.requirements or prompt(
            "Ruta al archivo requirements.txt", str(DEFAULT_REQUIREMENTS_FILE)
        )
        requirements_path = Path(requirements_input).resolve()

        validar_requirements(requirements_path)

        creado = crear_virtualenv(
            venv_path, python_bin, dry_run=args.dry_run, reuse=args.reuse
        )
        dependencias_instaladas = False
        if args.skip_install:
            print("Se omitió la instalación de dependencias (--skip-install).")
        else:
            instalar_dependencias(
                venv_path, requirements_path, dry_run=args.dry_run
            )
            dependencias_instaladas = not args.dry_run

        mostrar_resumen_final(
            venv_path,
            creado=creado and not args.dry_run,
            reutilizado=args.reuse,
            dependencias_instaladas=dependencias_instaladas,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            print("\nModo dry-run: no se realizó ningún cambio en el sistema.")

        return 0

    except SetupError as error:
        print(f"\n❌ Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

