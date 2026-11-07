"""Retrieve GBIF Switzerland occurrences through search or SQL downloads."""

from __future__ import annotations

import base64
import json
import os
import re
import time
import zipfile
from io import BytesIO
from json import JSONDecodeError
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from dotenv import load_dotenv


_API = "https://api.gbif.org/v1/occurrence/download"
_SEARCH_API = "https://api.gbif.org/v1/occurrence/search"
_SQL_FILE = Path(__file__).with_suffix(".sql")
_PAGE_SIZE = 300
_MAX_SEARCH_OFFSET = 100_000
_MAX_ROWS = 100_000
_POLL_INTERVAL = 10
_MAX_WAIT_SECONDS = 60 * 60
_FIELD_PATTERN = re.compile(r'^"?([a-z][a-z0-9_]*)"?$')


def _read_sql_template(sql_file: str | Path) -> str:
    """Build a valid SELECT from the editable, one-column-per-line SQL template."""
    lines = Path(sql_file).read_text(encoding="utf-8").splitlines()
    select_index = next(
        (index for index, line in enumerate(lines) if line.strip().upper() == "SELECT"),
        None,
    )
    if select_index is None:
        raise ValueError(f"Nel file SQL manca SELECT: {sql_file}")

    from_index = next(
        (
            index
            for index in range(select_index + 1, len(lines))
            if lines[index].strip().upper() == "FROM OCCURRENCE"
        ),
        None,
    )
    if from_index is None:
        raise ValueError(f"Nel file SQL manca FROM occurrence: {sql_file}")

    fields = []
    for line in lines[select_index + 1 : from_index]:
        field = line.strip()
        if not field or field.startswith("--"):
            continue
        field = field.split(" -- ", 1)[0].strip()
        field = field.lstrip(",").strip()
        match = _FIELD_PATTERN.fullmatch(field)
        if match is None:
            raise ValueError(f"Nome colonna SQL non valido: {field!r}")
        fields.append(f'"{match.group(1)}"')

    if not fields:
        raise ValueError("Seleziona almeno una colonna nel file SQL.")

    return "\n".join(
        [
            *lines[: select_index + 1],
            "    " + ",\n    ".join(fields),
            *lines[from_index:],
        ]
    )


def _basic_auth_header(username: str, password: str) -> str:
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {credentials}"


def _read_json_response(request: Request) -> dict[str, object]:
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("La risposta GBIF non è un oggetto JSON.")
    return payload


def _download_key_from_response(request: Request) -> str:
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8").strip()
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"GBIF ha rifiutato la richiesta SQL (HTTP {error.code}): {details}"
        ) from error

    try:
        payload = json.loads(body)
    except JSONDecodeError:
        download_key = body.strip('"')
    else:
        if isinstance(payload, str):
            download_key = payload
        elif isinstance(payload, dict):
            download_key = str(payload.get("key") or payload.get("downloadKey") or "")
        else:
            download_key = ""

    if not download_key:
        raise RuntimeError(f"GBIF non ha restituito una chiave di download: {body!r}")
    return download_key


def _wait_for_download(download_key: str, auth_header: str) -> None:
    status_url = f"{_API}/{download_key}"
    deadline = time.monotonic() + _MAX_WAIT_SECONDS
    started_at = time.monotonic()
    last_reported_at = started_at
    previous_status: object = None
    while time.monotonic() < deadline:
        request = Request(status_url, headers={"Authorization": auth_header})
        status_data = _read_json_response(request)
        status = status_data.get("status")
        if status == "SUCCEEDED":
            elapsed = int(time.monotonic() - started_at)
            print(f"Download GBIF completato in {elapsed // 60} min {elapsed % 60} s.")
            return
        if status in {"FAILED", "CANCELLED"}:
            raise RuntimeError(
                f"Download GBIF {download_key} terminato con stato {status}: "
                f"{status_data.get('error', 'nessun dettaglio fornito')}"
            )
        now = time.monotonic()
        if status != previous_status or now - last_reported_at >= 60:
            elapsed = int(now - started_at)
            print(
                f"Download GBIF {download_key}: stato {status or 'sconosciuto'} "
                f"(attesa {elapsed // 60} min {elapsed % 60} s).",
                flush=True,
            )
            previous_status = status
            last_reported_at = now
        time.sleep(_POLL_INTERVAL)

    raise TimeoutError(
        f"Il download GBIF {download_key} non è terminato entro "
        f"{_MAX_WAIT_SECONDS // 60} minuti."
    )


def _read_download(download_key: str, auth_header: str) -> pd.DataFrame:
    download_url = f"{_API}/request/{download_key}.zip"
    request = Request(download_url, headers={"Authorization": auth_header})
    with urlopen(request, timeout=120) as response:
        archive_bytes = response.read()

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        data_files = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".tsv")
        ]
        if not data_files:
            data_files = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".txt")
            ]
        if not data_files:
            raise RuntimeError(
                f"L'archivio GBIF {download_key} non contiene un file TSV."
            )
        with archive.open(data_files[0]) as data_file:
            return pd.read_csv(data_file, sep="\t")


def scarica_gbif_svizzera_ricerca(limite_righe: int = 1000) -> pd.DataFrame:
    """Fetch up to ``limite_righe`` occurrences from GBIF's search API.

    Unlike the SQL download, this public paginated API does not require GBIF
    credentials and returns all fields included in each occurrence record.
    """
    if (
        isinstance(limite_righe, bool)
        or not isinstance(limite_righe, int)
        or not 0 < limite_righe <= _MAX_SEARCH_OFFSET
    ):
        raise ValueError(
            "limite_righe deve essere un intero tra 1 e "
            f"{_MAX_SEARCH_OFFSET:,} con l'API di ricerca GBIF."
        )

    occorrenze: list[dict[str, object]] = []
    offset = 0
    while len(occorrenze) < limite_righe:
        page_size = min(_PAGE_SIZE, limite_righe - len(occorrenze))
        params = urlencode(
            {"country": "CH", "limit": page_size, "offset": offset}
        )
        request = Request(
            f"{_SEARCH_API}?{params}",
            headers={"Accept": "application/json"},
        )
        with urlopen(request, timeout=60) as response:
            page = json.load(response)

        results = page.get("results") if isinstance(page, dict) else None
        if not isinstance(results, list):
            raise RuntimeError("La risposta GBIF non contiene una lista di risultati.")
        if not results:
            break
        if not all(isinstance(record, dict) for record in results):
            raise RuntimeError("La risposta GBIF contiene record in formato inatteso.")

        occorrenze.extend(results)
        offset += len(results)
        if len(results) < page_size:
            break

    return pd.DataFrame(occorrenze)


def scarica_gbif_svizzera_sql(
    limite_righe: int = 1000,
    sql: str | None = None,
    file_sql: str | Path | None = None,
) -> pd.DataFrame:
    """Submit a GBIF SQL download and return its TSV as a DataFrame.

    Pass a custom SELECT query through ``sql``. If omitted, the query is built
    from ``gbif_svizzera.sql`` or ``file_sql``. The row limit is appended to
    either query. Credentials are read from ``GBIF_USERNAME``/``GBIF_PASSWORD``
    or the aliases ``GBIF_USER``/``GBIF_PWD`` in the environment or project's
    ``.env`` file.
    """
    if (
        isinstance(limite_righe, bool)
        or not isinstance(limite_righe, int)
        or not 0 < limite_righe <= _MAX_ROWS
    ):
        raise ValueError(f"limite_righe deve essere un intero tra 1 e {_MAX_ROWS:,}.")
    if sql is not None and file_sql is not None:
        raise ValueError("Specifica sql oppure file_sql, non entrambi.")

    if sql is None:
        sql_path = Path(file_sql) if file_sql is not None else _SQL_FILE
        query = _read_sql_template(sql_path)
    else:
        query = sql.strip()
        if not query:
            raise ValueError("La query SQL non puo' essere vuota.")
        query = query.rstrip(";").strip()
        if not re.match(r"^SELECT\b", query, flags=re.IGNORECASE):
            raise ValueError("La query deve iniziare con SELECT.")
        if not re.search(r"\bFROM\s+occurrence\b", query, flags=re.IGNORECASE):
            raise ValueError("La query deve leggere dalla tabella occurrence.")

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    username = os.getenv("GBIF_USERNAME") or os.getenv("GBIF_USER")
    password = os.getenv("GBIF_PASSWORD") or os.getenv("GBIF_PWD")
    if not username or not password:
        raise RuntimeError(
            "Credenziali GBIF mancanti. Configura GBIF_USERNAME e "
            "GBIF_PASSWORD (oppure GBIF_USER e GBIF_PWD) nel file "
            f"{project_root / '.env'} o nelle variabili d'ambiente."
        )

    query = re.sub(r"\bLIMIT\s+\d+\s*;?\s*$", "", query, flags=re.IGNORECASE)
    query = f"{query.rstrip()}\nLIMIT {limite_righe}"

    auth_header = _basic_auth_header(username, password)
    request_body = json.dumps(
        {"format": "SQL_TSV_ZIP", "sendNotification": False, "sql": query}
    ).encode("utf-8")
    request = Request(
        f"{_API}/request",
        data=request_body,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "text/plain, application/json",
        },
        method="POST",
    )
    download_key = _download_key_from_response(request)
    print(f"Richiesta GBIF accettata. Chiave download: {download_key}", flush=True)
    _wait_for_download(download_key, auth_header)
    return _read_download(download_key, auth_header)
