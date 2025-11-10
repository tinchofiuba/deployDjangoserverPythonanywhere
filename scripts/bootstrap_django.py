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
    parser.add_argument(
        "--project-name",
        help="Nombre del proyecto Django a crear si aún no existe manage.py.",
    )
    parser.add_argument(
        "--force-startproject",
        action="store_true",
        help="Forzar la creación de un nuevo proyecto Django si no existe manage.py.",
    )
    parser.add_argument(
        "--skip-auto-static-root",
        action="store_true",
        help="No agregar automáticamente STATIC_ROOT ni crear su directorio.",
    )
    return parser.parse_args(argv)


def mostrar_comando(comando: list[str]) -> None:
    printable = " ".join(shlex.quote(str(arg)) for arg in comando)
    print(f"$ {printable}")


def run_command(
    comando: list[str],
    *,
    dry_run: bool,
    cwd: Optional[Path] = None,
    capture_output: bool = False,
) -> None:
    mostrar_comando(comando)
    if dry_run:
        print("[dry-run] Comando no ejecutado.")
        return
    subprocess.run(comando, check=True, cwd=cwd, capture_output=capture_output)


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


def run_manage_py_capture(
    venv_python: Path,
    manage_py: Path,
    argumentos: list[str],
    *,
    dry_run: bool,
) -> str:
    comando = [str(venv_python), str(manage_py), *argumentos]
    mostrar_comando(comando)
    if dry_run:
        print("[dry-run] Comando no ejecutado (sin salida).")
        return ""
    resultado = subprocess.run(
        comando,
        check=True,
        capture_output=True,
        text=True,
    )
    salida = resultado.stdout.strip()
    if resultado.stderr:
        print(resultado.stderr.strip())
    return salida


def crear_proyecto_django(
    venv_python: Path,
    destino: Path,
    nombre: str,
    *,
    dry_run: bool,
) -> None:
    if not nombre:
        raise BootstrapError("El nombre del proyecto Django no puede estar vacío.")
    if not destino.exists():
        raise BootstrapError(
            f"El directorio destino {destino} no existe. Créalo antes de continuar."
        )
    comando = [str(venv_python), "-m", "django", "startproject", nombre, "."]
    print(f"Creando proyecto Django '{nombre}' en {destino}")
    run_command(comando, dry_run=dry_run, cwd=destino)


def detectar_settings_file(manage_py: Path) -> Optional[Path]:
    for candidato in [
        manage_py.parent / "settings.py",
        manage_py.parent / manage_py.stem / "settings.py",
    ]:
        if candidato.exists():
            return candidato

    try:
        contenido = manage_py.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    for linea in contenido.splitlines():
        if "DJANGO_SETTINGS_MODULE" in linea and "=" in linea:
            derecha = linea.split("=", 1)[1].strip().strip("'\"")
            if not derecha:
                continue
            modulo = derecha
            break
    else:
        modulo = None

    if not modulo:
        return None

    partes = modulo.split(".")
    ruta = manage_py.parent
    for parte in partes[:-1]:
        ruta /= parte
    return ruta / f"{partes[-1]}.py"


def asegurar_static_root(
    venv_python: Path,
    manage_py: Path,
    project_root: Path,
    *,
    dry_run: bool,
    skip_auto: bool,
) -> Optional[Path]:
    settings_path = detectar_settings_file(manage_py)
    if not settings_path or not settings_path.exists():
        print(
            "⚠️ No se pudo determinar el archivo settings.py. "
            "Revisa la variable DJANGO_SETTINGS_MODULE en manage.py."
        )
        return None

    try:
        contenido = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️ No se pudo abrir {settings_path} para revisar STATIC_ROOT.")
        return None

    static_root_line = None
    for linea in contenido.splitlines():
        if "STATIC_ROOT" in linea and "=" in linea:
            static_root_line = linea
            break

    if static_root_line:
        derecha = static_root_line.split("=", 1)[1].strip()
        if derecha.startswith(("'", '"')):
            valor = derecha.strip("'\"")
            static_root_path = Path(valor)
        elif derecha.startswith("BASE_DIR"):
            parte = derecha.replace("BASE_DIR", "").strip()
            # Esperamos formato " / \"staticfiles\"" o similar
            parte = parte.strip()
            if parte.startswith("/"):
                parte = parte[1:]
            parte = parte.strip()
            if parte.startswith(("'", '"')):
                parte = parte.strip("'\"")
            static_root_path = (project_root / parte).resolve()
        else:
            static_root_path = Path(derecha)

        if not static_root_path.is_absolute():
            static_root_path = (project_root / static_root_path).resolve()

        if not static_root_path.exists():
            if skip_auto:
                print(
                    f"ℹ️ STATIC_ROOT apunta a {static_root_path}, pero no existe. "
                    "Crealo manualmente (flag --skip-auto-static-root activo)."
                )
            else:
                if dry_run:
                    print(f"[dry-run] mkdir -p {static_root_path}")
                else:
                    static_root_path.mkdir(parents=True, exist_ok=True)
                    print(f"Se creó el directorio {static_root_path}.")
        return static_root_path

    if skip_auto:
        print(
            "ℹ️ Se omitió agregar STATIC_ROOT automáticamente (flag --skip-auto-static-root). "
            "Configúralo manualmente para habilitar collectstatic."
        )
        return None

    print(
        f"STATIC_ROOT no estaba configurado en {settings_path}. "
        "Se agregará automáticamente."
    )
    static_root_path = (project_root / "staticfiles").resolve()
    if dry_run:
        print("[dry-run] No se modifica settings.py ni se crean carpetas.")
        return static_root_path

    with settings_path.open("a", encoding="utf-8") as archivo:
        archivo.write(
            "\n\n# Añadido automáticamente por scripts/bootstrap_django.py\n"
            "STATIC_ROOT = BASE_DIR / \"staticfiles\"\n"
        )
    static_root_path.mkdir(parents=True, exist_ok=True)
    print(
        f"Se agregó STATIC_ROOT = BASE_DIR / 'staticfiles' en {settings_path} "
        f"y se creó el directorio {static_root_path}."
    )
    return static_root_path


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        print("=== Bootstrap de Django en PythonAnywhere ===")

        project_root = resolver_project_root(args.project_root)
        asegurar_ruta(project_root, "el directorio del proyecto")

        manage_py = project_root / "manage.py"
        manage_existe = manage_py.exists()

        venv_path = resolver_virtualenv(args.venv)
        activate_script = asegurar_ruta(venv_path / "bin" / "activate", "el script activate")
        venv_python = venv_path / "bin" / "python"
        asegurar_ruta(venv_python, "el ejecutable python del virtualenv")

        dry_run = args.dry_run
        if dry_run:
            print("🧪 Modo dry-run: se mostrarán los comandos sin ejecutarlos.")

        if not manage_existe:
            print(
                f"\nNo se encontró manage.py en {project_root}. "
                "Podés señalar un proyecto existente o crear uno nuevo."
            )
            if prompt_bool("¿Deseas crear un nuevo proyecto Django aquí?", args.force_startproject):
                nombre_proyecto = (
                    args.project_name
                    or prompt("Nombre del proyecto Django (usado en startproject)")
                )
                crear_proyecto_django(
                    venv_python, project_root, nombre_proyecto, dry_run=dry_run
                )
                manage_py = project_root / "manage.py"
                manage_existe = manage_py.exists()
                if not manage_existe:
                    raise BootstrapError(
                        "Luego de ejecutar startproject no se encontró manage.py. "
                        "Verifica manualmente la estructura creada."
                    )
            else:
                respuesta = prompt(
                    "Ingresa la ruta completa a un manage.py existente"
                )
                manage_py = Path(respuesta).expanduser().resolve()
                asegurar_ruta(manage_py, "manage.py")
                project_root = manage_py.parent

        requirements_path = resolver_requirements(project_root, args.requirements)
        asegurar_ruta(requirements_path, "requirements.txt")

        static_root_path = asegurar_static_root(
            venv_python,
            manage_py,
            project_root,
            dry_run=dry_run,
            skip_auto=args.skip_auto_static_root,
        )

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
        if static_root_path:
            print(f"STATIC_ROOT: {static_root_path}")
        else:
            print("STATIC_ROOT: no configurado (collectstatic podría fallar)")
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

