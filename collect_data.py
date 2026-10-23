"""Download public research corpora; preserve provenance and original Lab4 files."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import random
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger(__name__)
SOURCES = {
    "bbc-fulltext.zip": "http://mlg.ucd.ie/files/datasets/bbc-fulltext.zip",
    "meta_Software.json.gz": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_v2/metaFiles2/meta_Software.json.gz",
    "Software_5.json.gz": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_v2/categoryFilesSmall/Software_5.json.gz",
}


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "Zurin-Lab5/1.0 (educational corpus analysis)"
    retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def download(s, url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        LOG.info("Кэш: %s", target.name)
        return
    LOG.info("Загрузка: %s", url)
    with s.get(url, timeout=(20, 120), stream=True) as response:
        response.raise_for_status()
        temp = target.with_suffix(target.suffix + ".partial")
        with temp.open("wb") as f:
            for chunk in response.iter_content(1024 * 1024):
                f.write(chunk)
        temp.replace(target)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    parser = argparse.ArgumentParser(description="Сбор открытых корпусов для лабораторной №5")
    parser.add_argument("--limit", type=int, default=500, help="Максимум документов на корпус (>=200)")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--offline", action="store_true", help="Пересобрать из скачанных архивов без сети")
    args = parser.parse_args()
    if args.limit < 200:
        parser.error("--limit должен быть не меньше 200")
    data = args.data_dir
    data.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[
        logging.StreamHandler(), logging.FileHandler(data / "collection.log", encoding="utf-8")])
    collected_at = datetime.now(timezone.utc).isoformat()
    manifest = {"collected_at": collected_at, "seed": 42, "sources": [],
                "note": "Lab4 contains only 120 titles per corpus. Research corpora supplement insufficient original exports; they are not claimed to be Lab4 scraper output."}
    legacy = data / "legacy_lab4"
    legacy.mkdir(exist_ok=True)
    for filename in ["news.json", "prices.csv"]:
        src = ROOT.parent / "Lab4 Zurin" / filename
        if src.exists():
            shutil.copy2(src, legacy / filename)
    s = session()
    for name, url in SOURCES.items():
        path = data / "downloads" / name
        if args.offline and not path.is_file():
            raise ValueError("Для offline не хватает архива: " + str(path))
        download(s, url, path)
        manifest["sources"].append({"url": url, "file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    news = []
    with ZipFile(data / "downloads/bbc-fulltext.zip") as archive:
        names = sorted(n for n in archive.namelist() if n.endswith(".txt") and len(n.split("/")) == 3)
        random.Random(42).shuffle(names)
        seen = set()
        for name in names:
            text = archive.read(name).decode("utf-8", errors="replace")
            key = " ".join(text.lower().split())
            if key in seen:
                continue
            seen.add(key)
            title, _, body = text.strip().partition("\n")
            news.append({"id": "bbc:" + name, "title": title.strip(), "text": body.strip(),
                         "url": SOURCES["bbc-fulltext.zip"] + "#" + name, "source": "BBC / UCD research corpus (2004–2005)",
                         "category": name.split("/")[1], "language": "en", "collected_at": collected_at})
            if len(news) >= args.limit:
                break
    reviews = defaultdict(list)
    for row in read_gz(data / "downloads/Software_5.json.gz"):
        text = row.get("reviewText", "").strip()
        # Use a naturally short existing review, never generated or truncated text.
        if 10 <= len(text.split()) <= 80 and len(reviews[row["asin"]]) < 1:
            reviews[row["asin"]].append({"text": text, "rating": row.get("overall"), "unix_time": row.get("unixReviewTime")})
    products, seen = [], set()
    metadata = list(read_gz(data / "downloads/meta_Software.json.gz"))
    random.Random(42).shuffle(metadata)
    for row in metadata:
        asin = row.get("asin")
        description = row.get("description", [])
        description = " ".join(str(x) for x in description) if isinstance(description, list) else str(description or "")
        if not asin or asin in seen or not reviews[asin] or not 15 <= len(description.split()) <= 200 or not row.get("title"):
            continue
        seen.add(asin)
        products.append({"id": "amazon:" + asin, "title": row["title"], "description": description,
                         "reviews": reviews[asin], "url": "https://www.amazon.com/dp/" + asin,
                         "source": "Amazon Reviews 2018 / UCSD / Software", "language": "en",
                         "category": row.get("category", []), "collected_at": collected_at})
        if len(products) >= args.limit:
            break
    write_json(data / "news.json", news)
    write_json(data / "products.json", products)
    manifest["counts"] = {"news": len(news), "products": len(products)}
    manifest["product_selection"] = "15..200 whitespace-delimited words in original description; first existing review with 10..80 words; one review per product; no truncation or generation; shuffled metadata seed=42. Selection favors concise reviews."
    write_json(data / "sources.json", manifest)
    LOG.info("Сохранено: новости=%d, товары с описаниями и отзывами=%d", len(news), len(products))
    if min(len(news), len(products)) < 200:
        raise ValueError("Недобор: требуется минимум 200 документов в каждом корпусе")
    if not args.offline:
        import nltk
        for resource in ["wordnet", "omw-1.4", "stopwords", "averaged_perceptron_tagger_eng"]:
            if not nltk.download(resource, download_dir=str(data / "nltk_data"), quiet=True):
                raise RuntimeError("Не загружен ресурс NLTK: " + resource)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, requests.RequestException) as exc:
        LOG.error("Сбор не завершён: %s", exc)
        sys.exit(1)
