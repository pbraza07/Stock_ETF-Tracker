from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import requests

from persistence import DEFAULT_BRANCH, DEFAULT_REPO, format_et, now_et

PDF_REPO_DIR = "data/generated_pdfs"
PDF_STATIC_DIR = Path("static") / "generated_pdfs"

# Durable user artifacts. Release ZIPs must NEVER contain or overwrite these live paths.
# GitHub is the default durable store; MARKETSCOPE_PDF_PERSIST_DIR may additionally
# point to a Render persistent disk for a second durable copy.
PROTECTED_PDF_REPO_DIR = PDF_REPO_DIR
PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"


def durable_pdf_storage_configured() -> bool:
    """True when a redeploy-safe PDF store is configured."""
    return bool(
        os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
        or os.getenv("MARKETSCOPE_PDF_PERSIST_DIR", "").strip()
    )


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MarketScope-Render",
    }


def _clean_artifact_name(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "MarketScope_PDF")).strip("._")
    stem = stem or "MarketScope_PDF"
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    return stem


def artifact_name(record: dict) -> str:
    existing = str(record.get("pdf_artifact_name") or "").strip()
    if existing:
        return _clean_artifact_name(existing)
    record_id = str(record.get("id") or "MarketScope_PDF")
    return _clean_artifact_name(record_id)


def download_filename(record: dict) -> str:
    existing = str(record.get("pdf_download_filename") or "").strip()
    if existing:
        return _clean_artifact_name(existing)
    name = str(record.get("name") or record.get("id") or "Portfolio_Simulation")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "Portfolio_Simulation"
    created = str(record.get("created_date") or now_et().date().isoformat())
    return _clean_artifact_name(f"MarketScope_{safe}_{created}.pdf")


def repo_pdf_path(record: dict) -> str:
    existing = str(record.get("pdf_repo_path") or "").strip().lstrip("/")
    if existing and existing.startswith(f"{PDF_REPO_DIR}/"):
        return existing
    return f"{PDF_REPO_DIR}/{artifact_name(record)}"


def static_pdf_path(base_dir: Path, record: dict) -> Path:
    return Path(base_dir) / PDF_STATIC_DIR / artifact_name(record)


def pdf_viewer_url(record: dict) -> str:
    # The viewer is a checked-in static HTML page; filenames are sanitized before
    # becoming query parameters and the PDF is fetched from the same app origin.
    return (
        f"/app/static/pdf_viewer.html?file={quote(artifact_name(record))}"
        f"&name={quote(download_filename(record))}"
    )


def _persistent_mirror_path(record: dict) -> Path | None:
    root = os.getenv("MARKETSCOPE_PDF_PERSIST_DIR", "").strip()
    if not root:
        return None
    return Path(root).expanduser().resolve() / artifact_name(record)


def _write_server_copies(pdf_bytes: bytes, record: dict, base_dir: Path) -> Path:
    local = static_pdf_path(base_dir, record)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(pdf_bytes)

    mirror = _persistent_mirror_path(record)
    if mirror:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_bytes(pdf_bytes)
    return local


def _github_put_binary(path: str, payload: bytes, message: str, token: str) -> tuple[bool, str]:
    url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/{path}"
    headers = _headers(token)
    try:
        current = requests.get(url, headers=headers, params={"ref": DEFAULT_BRANCH}, timeout=15)
        sha = (current.json() or {}).get("sha") if current.status_code == 200 else None
        if current.status_code not in (200, 404):
            return False, f"GitHub PDF read failed ({current.status_code})"
        commit_message = message if "[skip render]" in message.lower() else f"{message} [skip render]"
        body = {
            "message": commit_message,
            "content": base64.b64encode(payload).decode("ascii"),
            "branch": DEFAULT_BRANCH,
        }
        if sha:
            body["sha"] = sha
        saved = requests.put(url, headers=headers, json=body, timeout=45)
        if saved.status_code not in (200, 201):
            return False, f"GitHub PDF save failed ({saved.status_code}): {saved.text[:220]}"
        return True, "PDF saved permanently to GitHub and on the MarketScope server."
    except Exception as exc:
        return False, f"GitHub PDF persistence error: {exc}"


def persist_pdf_artifact(
    pdf_bytes: bytes,
    record: dict,
    base_dir: Path,
    message: str,
) -> tuple[bool, str, dict]:
    """Save a real PDF file on the app server and, when configured, GitHub.

    The local static copy gives phones a normal HTTPS PDF URL for viewing/sharing.
    GitHub is the durable recovery copy for Render instances without a persistent disk.
    MARKETSCOPE_PDF_PERSIST_DIR can additionally point at a mounted persistent disk.
    """
    if not isinstance(pdf_bytes, (bytes, bytearray)) or not bytes(pdf_bytes).startswith(b"%PDF"):
        raise ValueError("PDF artifact must contain valid PDF bytes")

    stamp = now_et()
    record_for_name = dict(record)
    name = artifact_name(record_for_name)
    repo_path = f"{PDF_REPO_DIR}/{name}"
    _write_server_copies(bytes(pdf_bytes), record_for_name, base_dir)

    metadata = {
        "pdf_artifact_name": name,
        "pdf_download_filename": download_filename(record),
        "pdf_repo_path": repo_path,
        "pdf_saved_at_et": stamp.isoformat(),
        "pdf_saved_at_display_et": format_et(stamp),
        "pdf_storage": "server",
    }

    token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
    if not token:
        mirror = _persistent_mirror_path(record_for_name)
        metadata["pdf_storage"] = "server+persistent-disk" if mirror else "server"
        return False, (
            "PDF saved as a real file on the MarketScope server. "
            "For restart/redeploy durability on Render, keep MARKETSCOPE_GITHUB_TOKEN configured "
            "or set MARKETSCOPE_PDF_PERSIST_DIR to a mounted persistent disk."
        ), metadata

    ok, msg = _github_put_binary(repo_path, bytes(pdf_bytes), message, token)
    if ok:
        metadata["pdf_storage"] = "server+github"
    return ok, msg, metadata


def _load_from_github(record: dict, timeout: int = 20) -> bytes | None:
    repo_path = repo_pdf_path(record)
    token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
    try:
        if token:
            url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/{repo_path}"
            response = requests.get(url, headers=_headers(token), params={"ref": DEFAULT_BRANCH}, timeout=timeout)
            if response.status_code == 200:
                payload = response.json() or {}
                encoded = str(payload.get("content") or "").replace("\n", "")
                if encoded:
                    data = base64.b64decode(encoded)
                    return data if data.startswith(b"%PDF") else None
        raw = f"https://raw.githubusercontent.com/{DEFAULT_REPO}/{DEFAULT_BRANCH}/{repo_path}"
        response = requests.get(raw, timeout=timeout)
        if response.status_code == 200 and response.content.startswith(b"%PDF"):
            return response.content
    except Exception:
        return None
    return None


def load_pdf_artifact(
    record: dict,
    base_dir: Path,
    builder: Callable[[dict], bytes] | None = None,
    persist_rebuilt: bool = True,
) -> bytes:
    """Load the stored PDF, restoring the server copy when needed.

    Older pre-v5.9.19 saved records have no persisted PDF artifact. They are rebuilt
    once from their saved record and then upgraded into the new PDF storage path.
    """
    local = static_pdf_path(base_dir, record)
    try:
        data = local.read_bytes()
        if data.startswith(b"%PDF"):
            return data
    except Exception:
        pass

    mirror = _persistent_mirror_path(record)
    if mirror:
        try:
            data = mirror.read_bytes()
            if data.startswith(b"%PDF"):
                _write_server_copies(data, record, base_dir)
                return data
        except Exception:
            pass

    checked_out_backup = Path(base_dir) / repo_pdf_path(record)
    try:
        data = checked_out_backup.read_bytes()
        if data.startswith(b"%PDF"):
            _write_server_copies(data, record, base_dir)
            return data
    except Exception:
        pass

    remote = _load_from_github(record)
    if remote:
        _write_server_copies(remote, record, base_dir)
        return remote

    if builder is None:
        raise FileNotFoundError(f"Stored PDF artifact not found for {record.get('id') or 'record'}")

    rebuilt = builder(record)
    if not rebuilt.startswith(b"%PDF"):
        raise ValueError("PDF builder did not return a valid PDF")
    if persist_rebuilt:
        persist_pdf_artifact(
            rebuilt,
            record,
            base_dir,
            f"data: migrate MarketScope PDF artifact {record.get('id') or artifact_name(record)}",
        )
    else:
        _write_server_copies(rebuilt, record, base_dir)
    return rebuilt


def delete_pdf_artifact(record: dict, base_dir: Path, message: str) -> tuple[bool, str]:
    """Delete server/persistent-disk copies and the GitHub PDF when authorized."""
    local = static_pdf_path(base_dir, record)
    try:
        local.unlink(missing_ok=True)
    except Exception:
        pass

    mirror = _persistent_mirror_path(record)
    if mirror:
        try:
            mirror.unlink(missing_ok=True)
        except Exception:
            pass

    token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
    if not token:
        return False, "PDF removed from the current server; GitHub deletion requires MARKETSCOPE_GITHUB_TOKEN."

    path = repo_pdf_path(record)
    url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/{path}"
    headers = _headers(token)
    try:
        current = requests.get(url, headers=headers, params={"ref": DEFAULT_BRANCH}, timeout=15)
        if current.status_code == 404:
            return True, "PDF removed from the MarketScope server."
        if current.status_code != 200:
            return False, f"GitHub PDF delete lookup failed ({current.status_code})"
        sha = (current.json() or {}).get("sha")
        commit_message = message if "[skip render]" in message.lower() else f"{message} [skip render]"
        body = {"message": commit_message, "sha": sha, "branch": DEFAULT_BRANCH}
        deleted = requests.delete(url, headers=headers, json=body, timeout=30)
        if deleted.status_code != 200:
            return False, f"GitHub PDF delete failed ({deleted.status_code}): {deleted.text[:220]}"
        return True, "PDF removed from the server and durable PDF store."
    except Exception as exc:
        return False, f"GitHub PDF delete error: {exc}"
