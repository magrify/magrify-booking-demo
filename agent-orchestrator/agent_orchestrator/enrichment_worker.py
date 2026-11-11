"""Small, dependency-light CartelBot enrichment/evaluation worker.

The Cloudflare Worker remains the product API and approval surface. This
module handles bounded CSV/JSON enrichment jobs separately so slow website
fetches and lead-quality scoring never sit in the critical request path.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from .data_controls import redact

MAX_LEADS = 500
MAX_BODY_BYTES = 1_000_000


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: list[str] = []
        self.headings: list[str] = []
        self.description = ""
        self._in_title = False
        self._heading_depth = 0
        self._in_description = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() in {"h1", "h2", "h3"}:
            self._heading_depth += 1
        if tag.lower() == "meta" and attrs_map.get("name", "").lower() == "description":
            self.description = attrs_map.get("content", "")[:500]

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() in {"h1", "h2", "h3"} and self._heading_depth:
            self._heading_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title.append(text)
        if self._heading_depth:
            self.headings.append(text)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> urllib.request.Request | None:
        if not _safe_url(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_url(raw_url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(raw_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"}:
            return None
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except OSError:
            return None
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return None
        return parsed.geturl()[:2048]
    except ValueError:
        return None


def fetch_website_signals(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Fetch only public HTML metadata; reject private/loopback destinations."""
    safe_url = _safe_url(url)
    if not safe_url:
        return {"website_status": "rejected"}
    request = urllib.request.Request(
        safe_url,
        headers={"User-Agent": "CartelBot-Enrichment/1.0 (+https://cartelbot.com)"},
    )
    try:
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                raw = raw[:MAX_BODY_BYTES]
            parser = _PageParser()
            parser.feed(raw.decode("utf-8", errors="ignore"))
            return {
                "website_status": "ok",
                "website_title": " ".join(parser.title)[:300],
                "website_description": parser.description,
                "website_headings": parser.headings[:12],
            }
    except Exception as error:  # bounded enrichment failure is per-lead
        return {"website_status": "failed", "website_error": type(error).__name__}


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]{3,}", value.lower()) if term not in {"the", "and", "for"}}


def score_lead(lead: dict[str, Any], icp: str) -> dict[str, Any]:
    """Return a transparent fit score rather than an opaque model judgment."""
    icp_terms = _terms(icp)
    source = " ".join(str(lead.get(key, "")) for key in ("name", "company", "title", "industry", "description", "website_title", "website_description"))
    matched = sorted(icp_terms.intersection(_terms(source)))
    completeness = sum(bool(str(lead.get(key, "")).strip()) for key in ("name", "company", "email", "website")) / 4
    fit = (len(matched) / max(len(icp_terms), 1)) * 0.7 + completeness * 0.3
    return {
        "fit_score": round(min(1.0, fit), 4),
        "fit_label": "high" if fit >= 0.7 else "medium" if fit >= 0.4 else "low",
        "matched_terms": matched[:20],
        "completeness": round(completeness, 4),
    }


def enrich_leads(*, leads: list[dict[str, Any]], icp: str, fetch_websites: bool = False) -> dict[str, Any]:
    if not icp.strip():
        raise ValueError("icp is required")
    if len(leads) > MAX_LEADS:
        raise ValueError(f"maximum {MAX_LEADS} leads per job")
    enriched: list[dict[str, Any]] = []
    for raw in leads:
        lead = {str(key): value for key, value in raw.items()}
        if fetch_websites and lead.get("website"):
            lead.update(fetch_website_signals(str(lead["website"])))
        lead.update(score_lead(lead, icp))
        enriched.append(redact(lead))
    high = sum(item.get("fit_label") == "high" for item in enriched)
    return {
        "leads": enriched,
        "evaluation": {
            "lead_count": len(enriched),
            "high_fit_count": high,
            "enrichment_completeness": round(sum(item.get("completeness", 0) for item in enriched) / max(len(enriched), 1), 4),
        },
    }


def parse_csv_leads(csv_text: str) -> list[dict[str, Any]]:
    if len(csv_text.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("CSV exceeds the 1 MB limit")
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if len(rows) > MAX_LEADS:
        raise ValueError(f"maximum {MAX_LEADS} leads per job")
    return [dict(row) for row in rows]


def process_payload(payload: dict[str, Any]) -> dict[str, Any]:
    leads = payload.get("leads")
    if leads is None and isinstance(payload.get("csv"), str):
        leads = parse_csv_leads(payload["csv"])
    if not isinstance(leads, list) or any(not isinstance(item, dict) for item in leads):
        raise ValueError("leads must be an array of objects or csv must be supplied")
    return enrich_leads(
        leads=leads,
        icp=str(payload.get("icp", "")),
        fetch_websites=bool(payload.get("fetch_websites", False)),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CartelBot lead enrichment worker")
    parser.add_argument("input", help="JSON file containing {icp, leads} or {icp, csv}")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        payload = json.load(handle)
    print(json.dumps(process_payload(payload), indent=2))


if __name__ == "__main__":
    main()
