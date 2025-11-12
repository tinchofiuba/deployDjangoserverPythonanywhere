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
import ast
import os
import re
import shlex
import subprocess
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional
REPO_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPO_SCRIPT_DIR.parent


class BootstrapError(RuntimeError):
    """Error controlado durante el bootstrap de Django."""


def prompt(texto: str, valor_por_defecto: Optional[str] = None) -> str:
    """Solicita un valor por consola."""
    if valor_por_defecto:
        mensaje = f"{texto} [{valor_por_defecto}]: "
    else:
        mensaje = f"{texto}: "
    respuesta = input(mensaje).strip()
    if respuesta:
        print(f"✅ {texto}: {respuesta}")
        print()
        return respuesta
    if valor_por_defecto is not None:
        print(f"✅ {texto}: {valor_por_defecto} (por defecto)")
        print()
        return valor_por_defecto
    print()
    return respuesta


def _accion_desde_pregunta(texto: str) -> str:
    s = texto.strip()
    if s.startswith("¿") and s.endswith("?"):
        s = s[1:-1].strip()
    return s or texto


def prompt_bool(texto: str, valor_por_defecto: bool = True) -> bool:
    """Pide confirmación sí/no, devolviendo el booleano resultante."""
    sufijo = "S/n" if valor_por_defecto else "s/N"
    respuesta = input(f"{texto} ({sufijo}): ").strip().lower()

    if not respuesta:
        decision = valor_por_defecto
        origen = " (valor por defecto)"
    else:
        decision = respuesta in {"s", "si", "sí", "y", "yes"}
        origen = ""

    accion = _accion_desde_pregunta(texto)
    if decision:
        print(f"✅ {accion}{origen}")
    else:
        print(f"❌ {accion}{origen}")
    print()
    return decision


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
    parser.add_argument(
        "--domain",
        help="Dominio de la aplicación en PythonAnywhere (ej. miapp.pythonanywhere.com).",
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
    respuesta = prompt("Ruta al requirements.txt", str(por_defecto))
    return Path(respuesta).expanduser().resolve()


def resolver_dominio(valor_cli: Optional[str], project_root: Path) -> str:
    if valor_cli:
        return valor_cli.strip()
    base = project_root.name or "mi_app"
    sugerido = f"{base}.pythonanywhere.com"
    respuesta = prompt(
        "Dominio de la webapp en PythonAnywhere (ej. miapp.pythonanywhere.com)",
        sugerido,
    )
    return respuesta.strip()


def obtener_version_python(venv_python: Path, dry_run: bool) -> str:
    if dry_run:
        return "3.10"
    try:
        resultado = subprocess.run(
            [str(venv_python), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        salida = resultado.stdout.strip() or resultado.stderr.strip()
        if " " in salida:
            return salida.split(" ")[-1]
        return salida
    except subprocess.CalledProcessError:
        return "3.10"


def obtener_api_token_desde_postactivate(venv_path: Path) -> Optional[str]:
    postactivate = venv_path / "bin" / "postactivate"
    if not postactivate.exists():
        return None

    for line in postactivate.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export PYTHONANYWHERE_API_TOKEN="):
            _, valor = line.split("=", 1)
            valor = valor.strip()
            if valor.startswith('"') and valor.endswith('"'):
                valor = valor[1:-1]
            elif valor.startswith("'") and valor.endswith("'"):
                valor = valor[1:-1]
            return valor or None
    return None


def obtener_api_token(venv_path: Path) -> Optional[str]:
    token = os.environ.get("PYTHONANYWHERE_API_TOKEN")
    if token:
        return token.strip()
    return obtener_api_token_desde_postactivate(venv_path)


def agregar_linea_unica(archivo: Path, linea: str) -> None:
    if archivo.exists():
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        if linea in lineas:
            return
        lineas.append(linea)
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    else:
        archivo.write_text(linea + "\n", encoding="utf-8")


def solicitar_token_interactivo(venv_path: Path) -> Optional[str]:
    token = getpass(
        "Ingresa el API token de PythonAnywhere (no se mostrará al escribir): "
    ).strip()
    if not token:
        print("❌ No se introdujo la API token.")
        print()
        return None

    if prompt_bool("¿Deseas guardarla en el virtualenv para próximas ejecuciones?", True):
        postactivate = venv_path / "bin" / "postactivate"
        postdeactivate = venv_path / "bin" / "postdeactivate"
        postactivate.parent.mkdir(parents=True, exist_ok=True)
        agregar_linea_unica(
            postactivate, f'export PYTHONANYWHERE_API_TOKEN="{token}"'
        )
        agregar_linea_unica(postdeactivate, "unset PYTHONANYWHERE_API_TOKEN")
        print("✅ API token guardada en el virtualenv.")
        print(f"   Archivo: {postactivate}")
        print(
            "   Al activar el virtualenv se exportará automáticamente y se limpiará al desactivarlo."
        )
        print()
    else:
        print("✅ La API token se usará sólo en esta ejecución.")
        print()

    return token


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
    try:
        contenido = manage_py.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    modulo = None
    patrones = [
        re.compile(
            r"setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)['\"]"
        ),
        re.compile(r"DJANGO_SETTINGS_MODULE['\"]\s*=\s*['\"]([^'\"]+)['\"]"),
    ]
    for patron in patrones:
        coincidencia = patron.search(contenido)
        if coincidencia:
            modulo = coincidencia.group(1)
            break

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
            'STATIC_ROOT = BASE_DIR / "staticfiles"\n'
        )
    static_root_path.mkdir(parents=True, exist_ok=True)
    print(
        f"Se agregó STATIC_ROOT = BASE_DIR / 'staticfiles' en {settings_path} "
        f"y se creó el directorio {static_root_path}."
    )
    return static_root_path


def asegurar_allowed_hosts(manage_py: Path, domain: str, *, dry_run: bool) -> None:
    domain = domain.strip()
    if not domain:
        return
    settings_path = detectar_settings_file(manage_py)
    if not settings_path or not settings_path.exists():
        print(
            "⚠️ No se pudo determinar el archivo settings.py para actualizar ALLOWED_HOSTS."
        )
        return

    try:
        contenido = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"⚠️ No se pudo abrir {settings_path} para actualizar ALLOWED_HOSTS.")
        return

    patron = re.compile(r"ALLOWED_HOSTS\s*=\s*(\[[^\]]*\])", re.MULTILINE)
    match = patron.search(contenido)

    hosts_a_agregar = [
        domain,
        f"www.{domain}",
        "127.0.0.1",
        "localhost",
    ]

    if match:
        lista_txt = match.group(1)
        try:
            actuales = ast.literal_eval(lista_txt)
            if not isinstance(actuales, list):
                raise ValueError
        except (ValueError, SyntaxError):
            print(
                f"⚠️ No se pudo interpretar ALLOWED_HOSTS en {settings_path}. "
                "Actualizalo manualmente."
            )
            return

        modificada = False
        for host in hosts_a_agregar:
            if host not in actuales:
                actuales.append(host)
                modificada = True

        if not modificada:
            return

        nueva_lista = "[" + ", ".join(f"'{h}'" for h in actuales) + "]"
        nuevo_contenido = (
            contenido[: match.start(1)] + nueva_lista + contenido[match.end(1) :]
        )
    else:
        nueva_lista = "[" + ", ".join(f"'{h}'" for h in hosts_a_agregar) + "]"
        bloque = (
            "\n# Añadido automáticamente por scripts/bootstrap_django.py\n"
            f"ALLOWED_HOSTS = {nueva_lista}\n"
        )
        nuevo_contenido = contenido + bloque

    if dry_run:
        print(
            "\n[dry-run] Se omitió la actualización de ALLOWED_HOSTS. "
            "Host sugeridos:\n"
            + "\n".join(f"  - {h}" for h in hosts_a_agregar)
        )
        return

    settings_path.write_text(nuevo_contenido, encoding="utf-8")
    print(
        "✅ ALLOWED_HOSTS actualizado con los dominios sugeridos "
        f"en {settings_path}."
    )


def agregar_a_gitignore(repo_root: Path, project_root: Path) -> None:
    try:
        relative = project_root.relative_to(repo_root)
    except ValueError:
        return

    if not relative.parts:
        return
    if relative.parts[0] == "scripts":
        return

    gitignore_path = repo_root / ".gitignore"
    entry = f"{relative}/"

    if gitignore_path.exists():
        lineas = gitignore_path.read_text(encoding="utf-8").splitlines()
        if any(line.strip() == entry for line in lineas):
            return
    else:
        lineas = []

    lineas.append(entry)
    gitignore_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"ℹ️ Se añadió '{entry}' a {gitignore_path} para ignorar el proyecto Django.")


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        print("=== Bootstrap de Django en PythonAnywhere ===")

        project_root = resolver_project_root(args.project_root)
        asegurar_ruta(project_root, "el directorio del proyecto")

        manage_py = project_root / "manage.py"
        manage_existe = manage_py.exists()

        venv_path = resolver_virtualenv(args.venv)
        activate_script = asegurar_ruta(
            venv_path / "bin" / "activate", "el script activate"
        )
        dry_run = args.dry_run
        if dry_run:
            print("🧪 Modo dry-run: se mostrarán los comandos sin ejecutarlos.")

        venv_python = venv_path / "bin" / "python"
        asegurar_ruta(venv_python, "el ejecutable python del virtualenv")
        python_version = obtener_version_python(venv_python, dry_run)
        python_version_api = (
            ".".join(python_version.split(".")[:2]) if python_version else "3.10"
        )

        if not manage_existe:
            print(
                f"\nNo se encontró manage.py en {project_root}. "
                "Podés señalar un proyecto existente o crear uno nuevo."
            )
            if prompt_bool(
                "¿Deseas crear un nuevo proyecto Django aquí?", args.force_startproject
            ):
                base_nombre = args.project_name or project_root.name or "mi_proyecto"
                if not base_nombre.endswith("_api"):
                    sugerencia_nombre = f"{base_nombre}_api"
                else:
                    sugerencia_nombre = base_nombre
                nombre_proyecto = prompt(
                    "Nombre del proyecto Django (usado en startproject)",
                    sugerencia_nombre,
                )
                if args.project_name:
                    nombre_proyecto = args.project_name
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
                respuesta = prompt("Ingresa la ruta completa a un manage.py existente")
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

        domain = resolver_dominio(args.domain, project_root)

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
        print(f"Python del venv: {python_version}")
        print(f"Requirements: {requirements_path}")
        print(f"Dominio: {domain}")
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

        asegurar_allowed_hosts(manage_py, domain, dry_run=dry_run)
        print("\n✅ Bootstrap de Django completado.")
        print("Recuerda desde el panel de PythonAnywhere:")
        print("  - Configurar el virtualenv en Web → Manual configuration.")
        print("  - Verificar que el archivo WSGI apunta al settings correcto.")
        print(
            "  - Actualizar las rutas de archivos estáticos y media en la sección Static files."
        )
        print("  - Reiniciar la webapp para aplicar los cambios.")

        if dry_run:
            print(
                "\n⚠️ Como estaba en modo dry-run, ninguna acción se ejecutó realmente."
            )

        agregar_a_gitignore(REPO_ROOT, project_root)

        configure_script = REPO_SCRIPT_DIR / "configure_pythonanywhere.py"
        comando_config = [
            sys.executable,
            str(configure_script),
            "--domain",
            domain,
            "--project-root",
            str(project_root),
            "--venv",
            str(venv_path),
            "--python-version",
            python_version_api,
        ]
        if static_root_path:
            comando_config += ["--static-path", str(static_root_path)]
        comando_config_str = " ".join(shlex.quote(str(part)) for part in comando_config)

        token_disponible = obtener_api_token(venv_path)
        if configure_script.exists():
            if token_disponible:
                print(
                    "\n¿Deseas configurar la webapp en PythonAnywhere usando la API "
                    "con el token disponible?"
                )
                if prompt_bool("Configurar webapp mediante la API", False):
                    env = os.environ.copy()
                    env["PYTHONANYWHERE_API_TOKEN"] = token_disponible
                    mostrar_comando(comando_config)
                    try:
                        subprocess.run(comando_config, check=True, env=env)
                    except subprocess.CalledProcessError as exc:
                        print(
                            "⚠️ Ocurrió un error al llamar al configurador de la API. "
                            "Revisá la salida anterior para más detalles."
                        )
                        raise BootstrapError(
                            "Falló la configuración automática mediante API."
                        ) from exc
            else:
                print(
                    "\n⚠️ No se detectó PYTHONANYWHERE_API_TOKEN en el entorno ni "
                    "registrado en el virtualenv."
                )
                if prompt_bool("¿Deseas introducir la API token ahora?", False):
                    token_manual = solicitar_token_interactivo(venv_path)
                    if token_manual:
                        env = os.environ.copy()
                        env["PYTHONANYWHERE_API_TOKEN"] = token_manual
                        mostrar_comando(comando_config)
                        try:
                            subprocess.run(comando_config, check=True, env=env)
                        except subprocess.CalledProcessError as exc:
                            print(
                                "⚠️ Ocurrió un error al llamar al configurador de la API. "
                                "Revisá la salida anterior para más detalles."
                            )
                            raise BootstrapError(
                                "Falló la configuración automática mediante API."
                            ) from exc
                        token_disponible = token_manual
                if not token_disponible:
                    print(
                        "\nCuando el token esté disponible, ejecuta manualmente:\n"
                        f"    source {activate_script}\n"
                        f"    {comando_config_str}"
                    )
        else:
            print(
                "\nℹ️ Si deseas automatizar la configuración en PythonAnywhere, "
                "ejecuta (cuando esté disponible):\n"
                f"    {comando_config_str}"
            )

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
