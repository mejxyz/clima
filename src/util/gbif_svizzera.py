"""Ricerca paginata delle occorrenze GBIF associate alla Svizzera."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


_API = "https://api.gbif.org/v1/occurrence/search"
_PAGE_SIZE = 300
_MAX_OFFSET = 100_000


def scarica_gbif_svizzera(limite_righe: int = 1000) -> pd.DataFrame:
    """Interroga l'API GBIF e restituisce al massimo `limite_righe` occorrenze.

    La funzione richiede pagine da massimo 300 record e non scarica un archivio
    completo. Restituisce i primi risultati forniti dall'API, non un campione
    casuale. GBIF consente la ricerca fino a un offset massimo di 100.000.
    """
    if (
        isinstance(limite_righe, bool)
        or not isinstance(limite_righe, int)
        or limite_righe <= 0
    ):
        raise ValueError("limite_righe deve essere un intero positivo.")
    if limite_righe > _MAX_OFFSET:
        raise ValueError(
            f"limite_righe non puo' superare {_MAX_OFFSET:,} con l'API di ricerca GBIF."
        )

    occorrenze: list[dict[str, object]] = []
    offset = 0
    while len(occorrenze) < limite_righe:
        dimensione_pagina = min(_PAGE_SIZE, limite_righe - len(occorrenze))
        parametri = urlencode(
            {
                "country": "CH",
                "limit": dimensione_pagina,
                "offset": offset,
            }
        )
        richiesta = Request(
            f"{_API}?{parametri}",
            headers={"Accept": "application/json"},
        )
        with urlopen(richiesta, timeout=60) as risposta:
            pagina = json.load(risposta)

        risultati = pagina.get("results")
        if not isinstance(risultati, list):
            raise RuntimeError("La risposta GBIF non contiene una lista di risultati.")
        if not risultati:
            break

        occorrenze.extend(risultati)
        offset += len(risultati)
        if len(risultati) < dimensione_pagina:
            break

    return pd.DataFrame(occorrenze)
