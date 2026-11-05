"""Download delle occorrenze GBIF associate alla Svizzera."""

from __future__ import annotations

import base64
import json
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


_API = "https://api.gbif.org/v1"
_DOWNLOAD_URL = "https://api.gbif.org/occurrence/download/request"


def scarica_gbif_svizzera(
    username: str,
    password: str,
    email: str,
    *,
    limite_righe: int | None = None,
    intervallo_controllo: int = 30,
    attesa_massima: int = 24 * 60 * 60,
) -> pd.DataFrame:
    """Richiede e scarica le occorrenze GBIF con country code CH.

    Il download e' asincrono: GBIF invia anche una notifica via email quando
    l'archivio e' pronto. La funzione attende il completamento e legge il CSV
    contenuto nell'archivio in un DataFrame Pandas. Se `limite_righe` e'
    specificato, il DataFrame viene limitato a quel numero di righe; l'archivio
    completo di GBIF viene comunque richiesto e scaricato.
    """
    if not username or not password or not email:
        raise ValueError("Username, password ed email GBIF sono obbligatori.")
    if intervallo_controllo <= 0 or attesa_massima <= 0:
        raise ValueError("Intervalli e tempi di attesa devono essere positivi.")
    if limite_righe is not None and (
        isinstance(limite_righe, bool)
        or not isinstance(limite_righe, int)
        or limite_righe <= 0
    ):
        raise ValueError("limite_righe deve essere un intero positivo oppure None.")

    credenziali = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")
    corpo = {
        "notificationAddresses": [email],
        "sendNotification": True,
        "format": "SIMPLE_CSV",
        "predicate": {
            "type": "equals",
            "key": "COUNTRY",
            "value": "CH",
        },
    }
    richiesta = Request(
        f"{_API}/occurrence/download/request",
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credenziali}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(richiesta, timeout=60) as risposta:
        chiave = risposta.read().decode("utf-8").strip().strip('"')
    if not chiave:
        raise RuntimeError("GBIF non ha restituito la chiave del download.")

    print(f"Download GBIF richiesto: {chiave}")
    scadenza = time.monotonic() + attesa_massima
    while True:
        if time.monotonic() >= scadenza:
            raise TimeoutError(
                f"Il download GBIF {chiave} non e' pronto entro il tempo previsto."
            )

        richiesta_stato = Request(f"{_API}/occurrence/download/{chiave}")
        with urlopen(richiesta_stato, timeout=60) as risposta:
            stato_download = json.load(risposta)

        stato = stato_download.get("status")
        print(f"Stato del download: {stato}")
        if stato == "SUCCEEDED":
            break
        if stato in {"FAILED", "CANCELLED", "KILLED"}:
            raise RuntimeError(f"Download GBIF non riuscito: {stato_download}")

        time.sleep(min(intervallo_controllo, max(0, scadenza - time.monotonic())))

    url_archivio = f"{_DOWNLOAD_URL}/{chiave}.zip"
    with tempfile.TemporaryDirectory() as cartella_temporanea:
        percorso_archivio = Path(cartella_temporanea) / "download.zip"
        with urlopen(Request(url_archivio), timeout=120) as risposta:
            with percorso_archivio.open("wb") as archivio_locale:
                shutil.copyfileobj(risposta, archivio_locale)

        with zipfile.ZipFile(percorso_archivio) as archivio:
            file_occorrenze = next(
                (
                    nome
                    for nome in archivio.namelist()
                    if Path(nome).name == "occurrence.txt"
                ),
                None,
            )
            if file_occorrenze is None:
                raise RuntimeError(
                    "Nell'archivio GBIF non e' stato trovato occurrence.txt."
                )

            with archivio.open(file_occorrenze) as dati:
                return pd.read_csv(
                    dati,
                    sep="\t",
                    encoding="utf-8-sig",
                    low_memory=False,
                    nrows=limite_righe,
                )


def main() -> None:
    """Avvia il download da terminale, chiedendo le credenziali in modo sicuro."""
    import getpass

    username = input("Username GBIF: ").strip()
    password = getpass.getpass("Password GBIF: ")
    email = input("Email per la notifica GBIF: ").strip()

    dataframe = scarica_gbif_svizzera(username, password, email)
    print(f"\nScaricate {len(dataframe):,} occorrenze.")
    print(dataframe.head())


if __name__ == "__main__":
    main()
