#!/usr/bin/env python3
"""
Asistente interactivo para preparar un proyecto Django en PythonAnywhere.

Acciones que cubre:
1. Seleccionar la ruta del repositorio y el virtualenv existente.
2. (Opcional) actualizar pip dentro del entorno virtual.
3. Instalar dependencias desde requirements.txt.
4. Ejecutar comandos administrativos de Django: check, migrate, collectstatic.

Todo se ejecuta desde la consola Bash de PythonAnywhere. El objetivo es
facilitar el despliegue manteniendo un diálogo con la persona operadora.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional


class BootstrapError(RuntimeError):
    """Error controlado durante el bootstrap de Django."""


def prompt(texto: str, valor_por_defecto: Optional[str] = None) -> str:
    """Solicita un valor por consola."""
    if valor_por_defecto:
        mensaje = f"{texto} [{valor_por_defecto}]: "
    else:
        mensaje = f"{texto}: "
    respuesta = input(mensaje).strip()
    if not respuesta and valor_por_defecto is not None:
        return valor_por_defecto
    return respuesta


def prompt_bool(texto: str, valor_por_defecto: bool = True) -> bool:
    """Pide confirmación sí/no, devolviendo el booleano resultante."""
    sufijo = "S/n" if valor_por_defecto else "s/N"
    respuesta = input(f"{texto} ({sufijo}): ").strip().lower()
    if not respuesta:
        return valor_por_defecto
    return respuesta in {"s", "si", "sí", "y", "yes"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara un proyecto Django dentro de un virtualenv en PythonAnywhere."
    )
    parser.add_argument(
        "--project-root",
        help="Ruta al repositorio/proyecto donde vive manage.py (default interactivo: cwd).",
    )
    parser.add_argument(
        "--venv",
        help="Ruta completa al virtualenv existente (default interactivo: ~/.virtualenvs/<nombre>).",
    )
    parser.add_argument(
        "--requirements",
        help="Ruta al requirements.txt. Por defecto se usará <project-root>/requirements.txt.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="No instalar las dependencias con pip.",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="No ejecutar 'python manage.py check'.",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="No ejecutar 'python manage.py migrate'.",
    )
    parser.add_argument(
        "--skip-collectstatic",
        action="store_true",
        help="No ejecutar 'python manage.py collectstatic --noinput'.",
    )
    parser.add_argument(
        "--upgrade-pip",
        action="store_true",
        help="Actualizar pip antes de instalar dependencias.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar los comandos sin ejecutarlos realmente.",
    )
    return parser.parse_args(argv)


def mostrar_comando(comando: list[str]) -> None:
    printable = " ".join(shlex.quote(str(arg)) for arg in comando)
    print(f"$ {printable}")


def run_command(comando: list[str], *, dry_run: bool) -> None:
    mostrar_comando(comando)
    if dry_run:
        print("[dry-run] Comando no ejecutado.")
        return
    subprocess.run(comando, check=True)


def asegurar_ruta(path: Path, descripcion: str) -> Path:
    if not path.exists():
        raise BootstrapError(f"No se encontró {descripcion} en {path}.")
    return path


def resolver_project_root(valor_cli: Optional[str]) -> Path:
    if valor_cli:
        return Path(valor_cli).expanduser().resolve()
    respuesta = prompt(
        "Ruta del proyecto (donde está manage.py)", str(Path.cwd().resolve())
    )
    return Path(respuesta).expanduser().resolve()


def resolver_virtualenv(valor_cli: Optional[str]) -> Path:
    if valor_cli:
        return Path(valor_cli).expanduser().resolve()
    respuesta = prompt(
        "Ruta completa del virtualenv (ej. ~/.virtualenvs/mi_entorno)",
    )
    return Path(respuesta).expanduser().resolve()


def resolver_requirements(project_root: Path, valor_cli: Optional[str]) -> Path:
    if valor_cli:
        return Path(valor_cli).expanduser().resolve()
    por_defecto = project_root / "requirements.txt"
    respuesta = prompt(
        "Ruta al requirements.txt", str(por_defecto)
    )
    return Path(respuesta).expanduser().resolve()


def run_manage_py(
    venv_python: Path,
    manage_py: Path,
    argumentos: list[str],
    *,
    dry_run: bool,
) -> None:
    comando = [str(venv_python), str(manage_py), *argumentos]
    run_command(comando, dry_run=dry_run)


def run_pip(venv_python: Path, argumentos: list[str], *, dry_run: bool) -> None:
    comando = [str(venv_python), "-m", "pip", *argumentos]
    run_command(comando, dry_run=dry_run)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        print("=== Bootstrap de Django en PythonAnywhere ===")

        project_root = resolver_project_root(args.project_root)
        asegurar_ruta(project_root, "el directorio del proyecto")

        manage_py = project_root / "manage.py"
        if not manage_py.exists():
            respuesta = prompt(
                "No se encontró manage.py en la ruta indicada. Ingresa la ruta manualmente"
            )
            manage_py = Path(respuesta).expanduser().resolve()
        asegurar_ruta(manage_py, "manage.py")

        venv_path = resolver_virtualenv(args.venv)
        activate_script = asegurar_ruta(venv_path / "bin" / "activate", "el script activate")
        venv_python = venv_path / "bin" / "python"
        asegurar_ruta(venv_python, "el ejecutable python del virtualenv")

        requirements_path = resolver_requirements(project_root, args.requirements)
        asegurar_ruta(requirements_path, "requirements.txt")

        dry_run = args.dry_run
        if dry_run:
            print("🧪 Modo dry-run: se mostrarán los comandos sin ejecutarlos.")

        upgrade_pip = args.upgrade_pip or prompt_bool(
            "¿Actualizar pip en el virtualenv antes de instalar dependencias?", False
        )
        instalar = not args.skip_install and prompt_bool(
            "¿Instalar dependencias con pip install -r requirements.txt?", True
        )
        correr_check = not args.skip_check and prompt_bool(
            "¿Ejecutar 'python manage.py check'?", True
        )
        correr_migrate = not args.skip_migrate and prompt_bool(
            "¿Ejecutar 'python manage.py migrate'?", True
        )
        correr_collectstatic = not args.skip_collectstatic and prompt_bool(
            "¿Ejecutar 'python manage.py collectstatic --noinput'?", True
        )

        print("\n--- Resumen de acciones ---")
        print(f"Proyecto: {project_root}")
        print(f"manage.py: {manage_py}")
        print(f"Virtualenv: {venv_path}")
        print(f"Script activate: {activate_script}")
        print(f"Requirements: {requirements_path}")
        print(f"Actualizar pip: {'si' if upgrade_pip else 'no'}")
        print(f"Instalar dependencias: {'si' if instalar else 'no'}")
        print(f"manage.py check: {'si' if correr_check else 'no'}")
        print(f"manage.py migrate: {'si' if correr_migrate else 'no'}")
        print(f"collectstatic: {'si' if correr_collectstatic else 'no'}")
        print("---------------------------\n")

        if not prompt_bool("¿Confirmás continuar con estas acciones?", True):
            print("Proceso cancelado por la persona usuaria.")
            return 0

        if upgrade_pip:
            run_pip(venv_python, ["install", "--upgrade", "pip"], dry_run=dry_run)

        if instalar:
            run_pip(
                venv_python,
                ["install", "-r", str(requirements_path)],
                dry_run=dry_run,
            )

        if correr_check:
            run_manage_py(venv_python, manage_py, ["check"], dry_run=dry_run)

        if correr_migrate:
            run_manage_py(venv_python, manage_py, ["migrate"], dry_run=dry_run)

        if correr_collectstatic:
            run_manage_py(
                venv_python, manage_py, ["collectstatic", "--noinput"], dry_run=dry_run
            )

        print("\n✅ Bootstrap de Django completado.")
        print("Recuerda desde el panel de PythonAnywhere:")
        print("  - Configurar el virtualenv en Web → Manual configuration.")
        print("  - Verificar que el archivo WSGI apunta al settings correcto.")
        print("  - Actualizar las rutas de archivos estáticos y media en la sección Static files.")
        print("  - Reiniciar la webapp para aplicar los cambios.")

        if dry_run:
            print("\n⚠️ Como estaba en modo dry-run, ninguna acción se ejecutó realmente.")

        return 0

    except BootstrapError as error:
        print(f"\n❌ Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f"\n❌ Falló la ejecución de un comando: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nProceso cancelado por la persona usuaria.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

