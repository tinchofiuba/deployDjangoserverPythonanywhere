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
from typing import Optional, Sequence
from getpass import getpass


DEFAULT_VENV_ROOT = Path.home() / ".virtualenvs"
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


def agregar_linea_unica(archivo: Path, linea: str) -> None:
    if archivo.exists():
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        if linea in lineas:
            return
        lineas.append(linea)
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    else:
        archivo.write_text(linea + "\n", encoding="utf-8")


def configurar_api_token(venv_path: Path) -> None:
    desea = prompt_bool(
        "¿Deseas guardar el API token de PythonAnywhere en este virtualenv?", False
    )
    if not desea:
        print("❌ No se introdujo la API token.")
        print()
        return

    token = getpass(
        "Ingresa el API token de PythonAnywhere (no se mostrará al escribir): "
    ).strip()
    if not token:
        print("❌ No se introdujo la API token.")
        print()
        return

    postactivate = venv_path / "bin" / "postactivate"
    postdeactivate = venv_path / "bin" / "postdeactivate"

    postactivate.parent.mkdir(parents=True, exist_ok=True)
    agregar_linea_unica(
        postactivate, f'export PYTHONANYWHERE_API_TOKEN="{token}"'
    )
    agregar_linea_unica(postdeactivate, "unset PYTHONANYWHERE_API_TOKEN")

    print("✅ Se introdujo la API token.")
    print(
        f"   Ubicación: {postactivate}\n"
        "   Al activar el virtualenv se exportará automáticamente y se limpiará al desactivarlo."
    )
    print()


REPO_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPO_SCRIPT_DIR.parent


IGNORED_FOLDERS = {
    "scripts",
    ".git",
    ".github",
    "__pycache__",
    ".venv",
    ".virtualenvs",
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
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
        help="Ruta al archivo requirements.txt del proyecto Django.",
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


def crear_virtualenv(
    destino: Path, python_bin: str, *, dry_run: bool, reuse: bool
) -> bool:
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


def detectar_candidatos_de_proyecto(repo_root: Path) -> list[Path]:
    candidatos = []
    for item in repo_root.iterdir():
        if not item.is_dir():
            continue
        if item.name in IGNORED_FOLDERS or item.name.startswith("."):
            continue
        candidatos.append(item)
    return candidatos


def seleccionar_requirements_automatico(repo_root: Path) -> Path:
    candidatos = detectar_candidatos_de_proyecto(repo_root)
    if not candidatos:
        raise SetupError(
            "No se encontró ningún directorio de proyecto en este repositorio.\n\n"
            "Asegurate de clonar primero el repositorio del proyecto a gestionar con Django "
            "dentro de este directorio (por ejemplo, una carpeta llamada\n"
            "    django_api_nombre_del_proyecto/\n"
            "que contenga un requirements.txt)."
        )

    encontrados = []

    for carpeta in candidatos:
        req = carpeta / "requirements.txt"
        if req.exists():
            encontrados.append(req)

    if not encontrados:
        nombres = ", ".join(c.name for c in candidatos) or "(ninguna detectada)"
        raise SetupError(
            "No se encontró requirements.txt en las carpetas de proyecto detectadas.\n"
            "Por favor, verificá que el proyecto a gestionar con Django tenga un "
            "archivo requirements.txt en su directorio raíz.\n"
            f"Carpetas detectadas: {nombres}."
        )

    if len(encontrados) == 1:
        return encontrados[0]

    print("⚠️ Se detectaron múltiples archivos requirements.txt en este repositorio.")
    print("Seleccioná cuál corresponde al proyecto que vas a gestionar con Django:")
    for idx, ruta in enumerate(encontrados, start=1):
        print(f"  {idx}. {ruta}")

    while True:
        respuesta = prompt(
            "Seleccioná el número del archivo a utilizar", valor_por_defecto="1"
        )
        if respuesta.isdigit():
            indice = int(respuesta)
            if 1 <= indice <= len(encontrados):
                return encontrados[indice - 1]
        print("Opción inválida. Intentá nuevamente.")


def main(argv: Optional[list[str]] = None) -> int:
    try:
        print("=== Setup de entorno virtual para PythonAnywhere ===")
        args = parse_args(argv or sys.argv[1:])

        if args.requirements:
            requirements_path = Path(args.requirements).expanduser().resolve()
            print(f"Se utilizará el requirements indicado: {requirements_path}")
        else:
            requirements_path = seleccionar_requirements_automatico(REPO_ROOT).resolve()
            print()
            print(f"Se utilizará el requirements del proyecto: {requirements_path}")

        validar_requirements(requirements_path)
        project_root = requirements_path.parent
        proyecto_nombre = project_root.name
        sugerido = f"{proyecto_nombre}_venv" if proyecto_nombre else "venv"

        venv_name = args.name or prompt(
            "Nombre del virtualenv a crear", sugerido
        )
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

        creado = crear_virtualenv(
            venv_path, python_bin, dry_run=args.dry_run, reuse=args.reuse
        )
        dependencias_instaladas = False
        if args.skip_install:
            print("Se omitió la instalación de dependencias (--skip-install).")
        else:
            instalar_dependencias(venv_path, requirements_path, dry_run=args.dry_run)
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
        else:
            configurar_api_token(venv_path)
            bootstrap_script = REPO_SCRIPT_DIR / "bootstrap_django.py"
            comando_str = (
                f"python {bootstrap_script.name if bootstrap_script.exists() else 'scripts/bootstrap_django.py'} "
                f"--project-root {project_root} --venv {venv_path} --requirements {requirements_path}"
            )
            if bootstrap_script.exists():
                print("\n¿Deseas ejecutar ahora el script de bootstrap para el proyecto Django?")
                if prompt_bool("Lanzar bootstrap_django.py", True):
                    comando = [
                        sys.executable,
                        str(bootstrap_script),
                        "--project-root",
                        str(project_root),
                        "--venv",
                        str(venv_path),
                        "--requirements",
                        str(requirements_path),
                    ]
                    _mostrar_comando(comando)
                    try:
                        subprocess.run(comando, check=True)
                    except subprocess.CalledProcessError as exc:
                        print(
                            "⚠️ Ocurrió un error al ejecutar bootstrap_django.py. "
                            "Revisá la salida anterior para más detalles."
                        )
                        raise SetupError("Falló la ejecución de bootstrap_django.py.") from exc
                else:
                    print(
                        "\nℹ️ Para continuar con la configuración del proyecto Django, ejecuta cuando quieras:\n"
                        f"    {comando_str}"
                    )
            else:
                print(
                    "\nℹ️ Para continuar con la configuración del proyecto Django, ejecuta:\n"
                    f"    {comando_str}"
                )

        return 0

    except SetupError as error:
        print(f"\n❌ Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
