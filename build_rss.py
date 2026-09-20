#!/usr/bin/env python3
"""Génère un flux RSS des dernières publications PubMed sur le DVI.

Appelé quotidiennement par la GitHub Action (.github/workflows/rss.yml).
Authentification : NCBI_API_KEY en secret d'environnement (optionnel mais recommandé).
Sortie : feed.xml à la racine du repo, servi en raw par Utopia.
"""
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TERM = (
    '"disaster victim identification"[Title/Abstract] '
    'OR "post-mortem CT"[Title/Abstract] OR "PMCT"[Title/Abstract] '
    'OR "forensic imaging"[Title/Abstract] OR "forensic radiology"[Title/Abstract] '
    'OR "mass fatality"[Title/Abstract]'
)
LIMIT = 30

api_key = os.environ.get("NCBI_API_KEY", "")
params_common = {"api_key": api_key} if api_key else {}


def get_json(path, **params):
    r = requests.get(f"{EUTILS}/{path}", params={**params_common, **params}, timeout=30)
    r.raise_for_status()
    return r.json()


def get_text(path, **params):
    r = requests.get(f"{EUTILS}/{path}", params={**params_common, **params}, timeout=30)
    r.raise_for_status()
    return r.text


def main():
    ids = get_json(
        "esearch.fcgi",
        db="pubmed", term=TERM, retmax=LIMIT, sort="date",
        retmode="json", datetype="edat", reldate=90,
    )["esearchresult"]["idlist"]
    if not ids:
        print("aucun résultat — flux vide")
        ids = []

    items = []
    if ids:
        xml = get_text(
            "efetch.fcgi", db="pubmed", id=",".join(ids),
            retmode="xml", rettype="abstract",
        )
        root = ET.fromstring(xml)
        for art in root.findall(".//PubmedArticle"):
            pmid = (art.findtext(".//PMID") or "").strip()
            title = " ".join((art.findtext(".//ArticleTitle") or "").split())
            journal = (art.findtext(".//Journal/Title") or "").strip()
            year = (art.findtext(".//JournalIssue/PubDate/Year")
                    or art.findtext(".//JournalIssue/PubDate/MedlineDate") or "")
            abstract = " ".join((art.findtext(".//AbstractText") or "").split())
            authors = [
                f"{a.findtext('LastName') or ''} {a.findtext('Initials') or ''}".strip()
                for a in art.findall(".//Author")[:6]
            ]
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            desc = f"<p><b>{journal} ({year})</b> — {', '.join(a for a in authors if a)}</p>"
            if abstract:
                desc += f"<p>{abstract[:1200]}{'…' if len(abstract) > 1200 else ''}</p>"
            items.append({
                "title": title or f"PubMed {pmid}",
                "link": link,
                "guid": link,
                "pubdate": format_datetime(datetime.now(timezone.utc)),
                "description": desc,
            })

    now = format_datetime(datetime.now(timezone.utc))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>PubMed DVI / Forensic Imaging — veille quotidienne</title>",
        "<link>https://pubmed.ncbi.nlm.nih.gov/</link>",
        "<description>Publications PubMed récentes : disaster victim identification, PMCT, forensic imaging (flux généré quotidiennement par GitHub Action)</description>",
        "<language>en</language>",
        f"<lastBuildDate>{now}</lastBuildDate>",
    ]
    for it in items:
        lines += [
            "<item>",
            f"<title>{it['title']}</title>",
            f"<link>{it['link']}</link>",
            f"<guid>{it['guid']}</guid>",
            f"<pubDate>{it['pubdate']}</pubDate>",
            f"<description><![CDATA[{it['description']}]]></description>",
            "</item>",
        ]
    lines += ["</channel></rss>"]

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"feed.xml écrit : {len(items)} items")


if __name__ == "__main__":
    main()
