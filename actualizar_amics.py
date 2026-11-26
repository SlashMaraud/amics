
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AMICS - Generador automático de lista M3U desde IPFS.

Fuente principal:
ELCANO / hashes_acestream.m3u

Fuente de respaldo:
Segundo IPNS / hashes.m3u

Si ambas fuentes fallan, conserva la última lista válida.
No utiliza gateways públicos ni mezcla las fuentes.
"""

import re
import sys
import urllib.request
from pathlib import Path


# ==================================================
# CONFIGURACIÓN
# ==================================================

CARPETA = Path(__file__).resolve().parent

ARCHIVO_BASE = CARPETA / "amics_base.m3u"
ARCHIVO_SALIDA = CARPETA / "amics.m3u"

TIEMPO_ESPERA = 90

FUENTES = [
    (
        "PRINCIPAL - ELCANO",
        "http://127.0.0.1:8080/ipns/"
        "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs"
        "/hashes_acestream.m3u"
    ),
    (
        "RESPALDO - SEGUNDO IPNS",
        "http://127.0.0.1:8080/ipns/"
        "k51qzi5uqu5di462t7j4vu4akwfhvtjhy88qbupktvoacqfqe9uforjvhyi4wr"
        "/hashes.m3u"
    ),
]


# ==================================================
# DESCARGA DESDE IPFS LOCAL
# ==================================================

def descargar_lista(url, nombre):

    print()
    print("Consultando:", nombre)
    print(url)

    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Amics-IPFS-Updater/2.0"
        }
    )

    with urllib.request.urlopen(
        peticion,
        timeout=TIEMPO_ESPERA
    ) as respuesta:

        contenido = respuesta.read().decode(
            "utf-8-sig",
            errors="replace"
        )

    if not contenido.strip():
        raise RuntimeError("El archivo recibido está vacío.")

    return contenido


# ==================================================
# EXTRACCIÓN Y VALIDACIÓN DE CANALES
# ==================================================

def extraer_canales(contenido):

    lineas = contenido.replace(
        "\r\n", "\n"
    ).split("\n")

    canales = []
    informacion = None

    for linea in lineas:

        linea = linea.strip()

        if not linea:
            continue

        if linea.startswith("#EXTINF:"):
            informacion = linea
            continue

        if linea.startswith("#"):
            continue

        hash_match = re.search(
            r"(?:acestream://|id=)?([a-fA-F0-9]{40})",
            linea
        )

        if not hash_match:
            continue

        identificador = hash_match.group(1).lower()

        if informacion is None:
            informacion = (
                '#EXTINF:-1 tvg-id="'
                + identificador
                + '" group-title="ELCANO",'
                + identificador
            )

        canales.append(
            (
                informacion,
                "acestream://" + identificador
            )
        )

        informacion = None

    # Eliminar duplicados conservando el orden.

    resultado = []
    vistos = set()

    for informacion, enlace in canales:

        if enlace in vistos:
            continue

        vistos.add(enlace)

        resultado.append(
            (informacion, enlace)
        )

    if not resultado:
        raise RuntimeError(
            "No se ha encontrado ningún canal "
            "AceStream válido en el archivo."
        )

    return resultado


# ==================================================
# SELECCIÓN DE FUENTE PRINCIPAL O RESPALDO
# ==================================================

def obtener_canales():

    errores = []

    for nombre, url in FUENTES:

        try:

            contenido = descargar_lista(
                url,
                nombre
            )

            canales = extraer_canales(
                contenido
            )

            print()
            print("Fuente válida:", nombre)
            print(
                "Canales AceStream encontrados:",
                len(canales)
            )

            return canales, nombre

        except Exception as error:

            mensaje = (
                nombre + ": " + str(error)
            )

            errores.append(mensaje)

            print()
            print("FALLO:", mensaje)

            if nombre == FUENTES[0][0]:
                print(
                    "La fuente principal ha fallado. "
                    "Probando el respaldo..."
                )

    raise RuntimeError(
        "NINGUNA FUENTE HA PROPORCIONADO "
        "UNA LISTA VÁLIDA.\n"
        + "\n".join(errores)
    )


# ==================================================
# CABECERA Y ZONA PERSONAL
# ==================================================

def cargar_base():

    if not ARCHIVO_BASE.exists():

        raise RuntimeError(
            "No existe amics_base.m3u "
            "en la raíz del repositorio."
        )

    texto = ARCHIVO_BASE.read_text(
        encoding="utf-8-sig"
    )

    if not texto.strip().startswith("#EXTM3U"):

        raise RuntimeError(
            "amics_base.m3u no contiene "
            "una cabecera M3U válida."
        )

    return texto


def separar_base(texto):

    lineas = texto.replace(
        "\r\n", "\n"
    ).split("\n")

    inicio_personal = None

    marcadores = (
        "ZONA PERSONAL:",
        "SECCIÓN PERSONAL:",
        "CARPETA:",
    )

    for indice, linea in enumerate(lineas):

        if any(
            marcador in linea.upper()
            for marcador in marcadores
        ):

            inicio_personal = indice
            break

    if inicio_personal is None:

        cabecera = texto.rstrip()

        zona_personal = (
            "# ==========================================\n"
            "# ZONA PERSONAL:\n"
            "# Añade aquí tus canales propios.\n"
            "# =========================================="
        )

    else:

        cabecera = "\n".join(
            lineas[:inicio_personal]
        ).rstrip()

        zona_personal = "\n".join(
            lineas[inicio_personal:]
        ).strip()

    return cabecera, zona_personal


# ==================================================
# GENERACIÓN DE LA LISTA
# ==================================================

def generar_lista(canales, texto_base, fuente):

    cabecera, zona_personal = separar_base(
        texto_base
    )

    salida = [
        cabecera,
        "",
        "# ==========================================",
        "# CANALES AUTOMÁTICOS ELCANO - IPFS",
        "# Fuente utilizada: " + fuente,
        "# ==========================================",
        ""
    ]

    for informacion, enlace in canales:

        salida.append(informacion)
        salida.append(enlace)

    salida.extend([
        "",
        "# ==========================================",
        "# FIN DE CANALES AUTOMÁTICOS",
        "# ==========================================",
        "",
        zona_personal,
        ""
    ])

    return "\n".join(salida)


# ==================================================
# GUARDADO SEGURO
# ==================================================

def guardar_lista(contenido):

    temporal = ARCHIVO_SALIDA.with_suffix(
        ".m3u.tmp"
    )

    temporal.write_text(
        contenido,
        encoding="utf-8"
    )

    # Sustitución atómica.
    # La lista anterior permanece intacta
    # si se produce un error antes de este punto.

    temporal.replace(ARCHIVO_SALIDA)


# ==================================================
# PROGRAMA PRINCIPAL
# ==================================================

def main():

    print("======================================")
    print("          ACTUALIZADOR AMICS")
    print("       IPFS PRINCIPAL + RESPALDO")
    print("======================================")

    try:

        texto_base = cargar_base()

        canales, fuente = obtener_canales()

        nueva_lista = generar_lista(
            canales,
            texto_base,
            fuente
        )

        guardar_lista(nueva_lista)

        print("--------------------------------------")
        print("LISTA GENERADA CORRECTAMENTE")
        print("Fuente:", fuente)
        print("Archivo:", ARCHIVO_SALIDA.name)
        print("Canales:", len(canales))
        print("--------------------------------------")

    except Exception as error:

        print("--------------------------------------")
        print("ERROR: NO SE HA ACTUALIZADO LA LISTA")
        print(str(error))
        print("--------------------------------------")

        sys.exit(1)


if __name__ == "__main__":
    main()
