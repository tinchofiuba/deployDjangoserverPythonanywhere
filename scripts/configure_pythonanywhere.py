#!/usr/bin/env python3
"""
Configura automáticamente una webapp de PythonAnywhere usando su API.

Pasos que cubre:
1. Crea la webapp (Manual configuration) si no existe.
2. Configura el virtualenv, el código fuente y el Working directory.
3. Registra los mapeos de archivos estáticos.
4. Opcionalmente recarga la webapp.

Requisitos:
- Haber exportado PYTHONANYWHERE_API_TOKEN (por ejemplo desde postactivate del venv).
- El usuario deberá haber configurado previamente la clave SSH y clonado el repo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


API_BASE = "https://www.pythonanywhere.com/api/v0/user/{username}"


def build_headers(token: str, has_payload: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"Token {token}"}
    if has_payload:
        headers["Content-Type"] = "application/json"
    return headers


def make_request(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers=build_headers(token, payload is not None),
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as response:
            content = response.read().decode("utf-8")
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"raw": content}
            return None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Solicitud {method} {url} devolvió {exc.code}: {body}"
        ) from exc


def webapp_exists(base_url: str, domain: str, token: str) -> bool:
    url = f"{base_url}/webapps/{domain}/"
    req = urllib.request.Request(
        url=url,
        headers=build_headers(token),
        method="GET",
    )
    try:
        urllib.request.urlopen(req).close()
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(
            f"No se pudo comprobar la existencia de la webapp: {exc}"
        ) from exc


def crear_webapp(base_url: str, domain: str, python_version: str, token: str) -> None:
    url = f"{base_url}/webapps/"
    payload = {"domain_name": domain, "python_version": python_version}
    make_request("POST", url, token, payload)
    print(f"✅ Webapp creada: {domain} (Python {python_version})")


def configurar_virtualenv(base_url: str, domain: str, venv_path: Path, token: str) -> None:
    url = f"{base_url}/webapps/{domain}/virtualenv/"
    payload = {"path": str(venv_path)}
    make_request("POST", url, token, payload)
    print(f"✅ Virtualenv configurado: {venv_path}")


def configurar_codigo(
    base_url: str,
    domain: str,
    project_root: Path,
    token: str,
) -> None:
    url = f"{base_url}/webapps/{domain}/sourcecode/"
    payload = {
        "path": str(project_root),
        "working_directory": str(project_root),
    }
    make_request("POST", url, token, payload)
    print(f"✅ Código fuente configurado en {project_root}")


def configurar_staticfiles(
    base_url: str,
    domain: str,
    static_url: str,
    static_path: Optional[Path],
    token: str,
) -> None:
    if not static_path:
        print("ℹ️ Se omitió la configuración de static files (no se proporcionó ruta).")
        return
    url = f"{base_url}/webapps/{domain}/static_files/"
    payload = {
        "mappings": [
            {
                "url": static_url,
                "path": str(static_path),
            }
        ]
    }
    make_request("POST", url, token, payload)
    print(f"✅ Static files configurados: {static_url} → {static_path}")


def recargar_webapp(base_url: str, domain: str, token: str) -> None:
    url = f"{base_url}/webapps/{domain}/reload/"
    make_request("POST", url, token)
    print("🔁 Webapp recargada correctamente.")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configura una webapp de PythonAnywhere usando su API."
    )
    parser.add_argument("--domain", required=True, help="Dominio completo (ej. miapp.pythonanywhere.com).")
    parser.add_argument("--project-root", required=True, help="Ruta al proyecto Django.")
    parser.add_argument("--venv", required=True, help="Ruta al virtualenv.")
    parser.add_argument("--static-path", help="Ruta a STATIC_ROOT (si no se indica, se omite).")
    parser.add_argument("--static-url", default="/static/", help="URL pública para los archivos estáticos.")
    parser.add_argument("--python-version", default="3.10", help="Versión de Python para la webapp.")
    parser.add_argument("--skip-create", action="store_true", help="No intentar crear la webapp si no existe.")
    parser.add_argument("--skip-static", action="store_true", help="No configurar los archivos estáticos.")
    parser.add_argument("--no-reload", action="store_true", help="No reiniciar la webapp al finalizar.")
    parser.add_argument("--username", help="Usuario de PythonAnywhere (default: nombre del HOME).")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar pasos sin llamar a la API.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    token = os.environ.get("PYTHONANYWHERE_API_TOKEN")
    if not token:
        print("❌ PYTHONANYWHERE_API_TOKEN no está definido en el entorno.", file=sys.stderr)
        return 1

    username = args.username or Path.home().name
    base_url = API_BASE.format(username=username)
    domain = args.domain.strip()
    project_root = Path(args.project_root).expanduser().resolve()
    venv_path = Path(args.venv).expanduser().resolve()
    static_path = Path(args.static_path).expanduser().resolve() if args.static_path else None

    if args.dry_run:
        print("🧪 Modo dry-run: se mostrarían las solicitudes, pero no se ejecutarán.")
        print(f"Usuario: {username}")
        print(f"Dominio: {domain}")
        print(f"Proyecto: {project_root}")
        print(f"Virtualenv: {venv_path}")
        if static_path:
            print(f"Static: {args.static_url} → {static_path}")
        return 0

    try:
        existe = webapp_exists(base_url, domain, token)
        if not existe:
            if args.skip_create:
                raise RuntimeError(
                    f"La webapp {domain} no existe y se solicitó no crearla (--skip-create)."
                )
            crear_webapp(base_url, domain, args.python_version, token)
        else:
            print(f"ℹ️ La webapp {domain} ya existe, se actualizará la configuración.")

        configurar_virtualenv(base_url, domain, venv_path, token)
        configurar_codigo(base_url, domain, project_root, token)

        if not args.skip_static:
            configurar_staticfiles(base_url, domain, args.static_url, static_path, token)
        else:
            print("ℹ️ Se omitió la configuración de static files (--skip-static).")

        if args.no_reload:
            print("ℹ️ No se recargó la webapp (--no-reload).")
        else:
            recargar_webapp(base_url, domain, token)

        print("\n✅ Configuración mediante API completada.")
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ Error al configurar la webapp: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

