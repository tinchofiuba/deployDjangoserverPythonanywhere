# deployDjangoserverPythonanywhere
Script de Python para desplegar un servidor gestionado con Django y PythonAnywhere.

## Requisitos previos
- Tener una cuenta activa en [PythonAnywhere](https://www.pythonanywhere.com/).
- Clonar este repositorio en tu `/home/<usuario>/` de PythonAnywhere.
- Contar con un archivo `requirements.txt` en la raíz del proyecto.

## 1. Crear el entorno virtual e instalar dependencias
Desde la consola Bash de PythonAnywhere, ejecuta:

```bash
python3 scripts/setup_virtualenv.py
```

El script te pedirá:
- **Nombre del virtualenv** que se creará dentro de `~/.virtualenvs/`.
- **Ruta del archivo `requirements.txt`** (por defecto `./requirements.txt`).
- **Intérprete de Python** a utilizar (por defecto `python3.10` en PythonAnywhere).

Ejemplo de interacción:

```
=== Setup de entorno virtual para PythonAnywhere ===
Nombre del virtualenv a crear: venv_api
Directorio raíz para los virtualenvs [/home/usuario/.virtualenvs]: 
Intérprete de Python a usar [python3.10]: 
Ruta al archivo requirements.txt [requirements.txt]: 
```

Al finalizar, verás un resumen con el comando para activar el entorno:

```bash
source ~/.virtualenvs/venv_api/bin/activate
```

## Próximos pasos
- Activar el entorno virtual recién creado.
- Ejecutar las migraciones (`python manage.py migrate`).
- Recopilar archivos estáticos (`python manage.py collectstatic`).
- Configurar la aplicación web desde el panel de PythonAnywhere.

Se agregarán scripts adicionales para automatizar estos pasos en las siguientes iteraciones.
