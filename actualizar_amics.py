
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AMICS - Generador automático de lista M3U desde IPFS ELCANO.

- Consulta exclusivamente el IPNS de ELCANO mediante el gateway local IPFS.
- No utiliza gateways públicos ni fuentes alternativas.
- Obtiene los canales de hashes_acestream.m3u.
- Conserva la cabecera y la zona personal de amics_base.m3u.
- No sustituye la lista anterior si la descarga o validación falla.
"""

import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

CARPETA = Path(__file__).resolve().parent

ARCHIVO_BASE = CARPETA / "amics_base.m3u"
ARCHIVO_SALIDA = CARPETA / "amics.m3u"

IPNS_ELCANO = (
    "k51qzi5uqu5dh5qej4b9wlcr5i6vhc7rcfkekhrxqek5c9lk6gdaiik820fecs"
)

URL_IPFS = (
    "http://127.0.0.1:8080/ipns/"
    + IPNS_ELCANO
    + "/hashes_acestream.m3u"
)

TIEMPO_ESPERA = 90

# --------------------------------------------------
# DESCARGA EXCLUSIVAMENTE DESDE IPFS LOCAL
# --------------------------------------------------

def descargar_lista():
    print("Consultando IPNS de ELCANO mediante IPFS local...")
    print(URL_IPFS)

    peticion = urllib.request.Request(
        URL_IPFS,
        headers={"User-Agent": "Amics-IPFS-Updater/1.0"}
    )

    try:
        with urllib.request.urlopen(
            peticion,
            timeout=TIEMPO_ESPERA
        ) as respuesta:
            contenido = respuesta.read().decode(
                "utf-8-sig",
                errors="replace"
            )

        if not contenido.strip():
            raise RuntimeError("IPFS ha devuelto un archivo vacío.")

        return contenido

    except Exception as error:
        raise RuntimeError(
            "No se ha podido obtener la lista desde IPFS local: "
            + str(error)
        )


# --------------------------------------------------
# EXTRACCIÓN Y VALIDACIÓN DE CANALES
# --------------------------------------------------

def extraer_canales(contenido):
    lineas = contenido.replace("\r\n", "\n").split("\n")

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
            (informacion, "acestream://" + identificador)
        )

        informacion = None

    # Eliminar duplicados conservando el orden.
    resultado = []
    vistos = set()

    for info, enlace in canales:
        if enlace in vistos:
            continue

        vistos.add(enlace)
        resultado.append((info, enlace))

    if not resultado:
        raise RuntimeError(
            "No se ha encontrado ningún canal AceStream válido "
            "en el archivo recibido."
        )

    return resultado


# --------------------------------------------------
# CABECERA Y ZONA PERSONAL
# --------------------------------------------------

def cargar_base():
    if not ARCHIVO_BASE.exists():
        raise RuntimeError(
            "No existe amics_base.m3u en la raíz del repositorio."
        )

    texto = ARCHIVO_BASE.read_text(
        encoding="utf-8-sig"
    )

    if not texto.strip().startswith("#EXTM3U"):
        raise RuntimeError(
            "amics_base.m3u no contiene una cabecera M3U válida."
        )

    return texto


def separar_base(texto):
    lineas = texto.replace("\r\n", "\n").split("\n")

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


# --------------------------------------------------
# GENERACIÓN DE LA LISTA
# --------------------------------------------------

def generar_lista(canales, texto_base):
    cabecera, zona_personal = separar_base(texto_base)

    salida = [
        cabecera,
        "",
        "# ==========================================",
        "# CANALES AUTOMÁTICOS ELCANO - IPFS",
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


# --------------------------------------------------
# GUARDADO SEGURO
# --------------------------------------------------

def guardar_lista(contenido):
    temporal = ARCHIVO_SALIDA.with_suffix(".m3u.tmp")

    temporal.write_text(
        contenido,
        encoding="utf-8"
    )

    # Sustitución atómica: la lista anterior permanece
    # intacta si se produce un error antes de este punto.
    temporal.replace(ARCHIVO_SALIDA)


# --------------------------------------------------
# PROGRAMA PRINCIPAL
# --------------------------------------------------

def main():
    print("======================================")
    print("       ACTUALIZADOR AMICS")
    print("======================================")

    try:
        texto_base = cargar_base()

        contenido_ipfs = descargar_lista()

        canales = extraer_canales(contenido_ipfs)

        print(
            "Canales AceStream válidos encontrados:",
            len(canales)
        )

        nueva_lista = generar_lista(
            canales,
            texto_base
        )

        guardar_lista(nueva_lista)

        print("--------------------------------------")
        print("Lista generada correctamente.")
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
