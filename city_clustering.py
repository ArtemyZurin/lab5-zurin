"""Пример 2: автоматический поиск блюд на выбранных веб-страницах, 3 кластеризации."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import KMeans, AgglomerativeClustering, SpectralClustering
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits

from collect_data import session, download, write_json
from topic_modeling import clean_text

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("cities")
# Dictionary-based extraction: specific names, spelling variants, no generic 'soup/salad'.
DISHES = {
    "посику́нчики": r"пос[ие]кунчик\w*", "шаньги": r"шан(?:ьг|ег|еж)\w*",
    "пельмени": r"пельмен\w*|пель[ -]?нян\w*", "пистики": r"пистик\w*",
    "кундюмы": r"кундюм\w*", "строганина": r"строганин\w*", "вареники": r"вареник\w*",
    "эчпочмак": r"[эу]чпочмак\w*|треугольник\w*", "чак-чак": r"чак[ -]?чак\w*",
    "элеш": r"элеш\w*", "губадия": r"губади\w*", "кыстыбый": r"кыстыб\w*",
    "бэлеш": r"б[аэе]л[еиэ]ш\w*", "бешбармак": r"б[еи]шбармак\w*",
    "манты": r"мант(?:ы|ов|ами|ах)", "шурпа": r"ш[уо]рп\w*|шулп\w*",
    "казы": r"казы(?:лык)?\w*", "токмач": r"токмач\w*", "азу": r"азу",
    "баурсак": r"ба[уо]рсак\w*", "кулама": r"кул+ам\w*",
    "блины": r"блин(?:ы|ов|ами|ах|чик\w*)", "расстегай": r"расстега\w*",
    "кулебяка": r"кулебяк\w*", "калач": r"калач\w*", "оливье": r"оливье",
    "окрошка": r"окрошк\w*", "солянка": r"солянк\w*", "борщ": r"борщ\w*",
    "уха": r"ух(?:а|и|у|ой|ою)", "щи": r"щи|щей|щами", "холодец": r"холод(?:ец|ца|цом)",
    "птичье молоко": r"птичье молоко", "пышки": r"пышк\w*",
    "корюшка": r"корюшк\w*", "шаверма": r"шаверм\w*|шаурм\w*",
    "бефстроганов": r"бефстроганов\w*|говядин\w* по[ -]строгановск\w*",
    "буузы": r"бууз\w*|буз(?:ы|а|ов)", "калитки": r"калитк\w*",
    "лохикейтто": r"лохикей?т+о|лохикейт+т?о|л?охикейто|каларуок\w*",
    "ряпушка": r"ряпушк\w*", "суши": r"суши", "роллы": r"ролл\w*",
    "поке": r"поке", "том-ям": r"том[ -]?ям\w*", "папоротник": r"папоротник\w*",
    "севиче": r"севиче", "тартар": r"тартар\w*", "гравлакс": r"гравлакс\w*"
}


def extract_dishes(text):
    text = clean_text(text)
    return sorted(name for name, pattern in DISHES.items() if re.search(r"\b(?:" + pattern + r")\b", text))


def collect(config_path, out):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    jobs = [(city, url) for city, urls in config.items() for url in urls]
    cache = out / "pages"
    cache.mkdir(parents=True, exist_ok=True)

    def one(job):
        city, url = job
        path = cache / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".html")
        row = {"city": city, "url": url, "domain": urlsplit(url).netloc.removeprefix("www."),
               "collected_at": datetime.now(timezone.utc).isoformat()}
        try:
            download(session(), url, path)
            raw = path.read_bytes()
            soup = BeautifulSoup(raw, "html.parser", from_encoding="utf-8")
            for node in soup.select("script,style,nav,footer,header,aside,noscript,form"):
                node.decompose()
            node = soup.select_one("article") or soup.select_one("main") or soup.body
            if node is None:
                raise ValueError("Нет содержимого страницы")
            text = node.get_text(" ", strip=True)
            dishes = extract_dishes(text)
            if not dishes:
                raise ValueError("На странице не найдены блюда из словаря")
            row.update(status="ok", dishes=dishes, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       extraction="article/main" if node.name in {"article", "main"} else "body_without_navigation",
                       title=soup.title.get_text(" ", strip=True) if soup.title else "", characters=len(text))
            # Short evidence contexts, at most 20 words per page, plus derived dish names.
            first = dishes[0]
            match = re.search(r"\b(?:" + DISHES[first] + r")\b", clean_text(text))
            row["evidence"] = " ".join(clean_text(text)[max(0, match.start()-45):match.end()+65].split()[:20])
            LOG.info("%s: %d блюд, %s", city, len(dishes), url)
        except (requests.RequestException, OSError, ValueError) as exc:
            row.update(status="error", error=str(exc))
            LOG.warning("%s: %s", url, exc)
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(one, jobs))
    write_json(out / "city_evidence.json", rows)
    return rows


def build_matrix(evidence):
    # One independent domain = one source, multiple pages from that domain are unioned.
    by_city = defaultdict(lambda: defaultdict(set))
    hashes = defaultdict(set)
    for row in evidence:
        if row["status"] == "ok":
            if row["text_sha256"] in hashes[row["city"]]:
                continue
            hashes[row["city"]].add(row["text_sha256"])
            by_city[row["city"]][row["domain"]].update(row["dishes"])
    expected = sorted({row["city"] for row in evidence})
    insufficient = [city for city in expected if len(by_city[city]) < 2]
    if insufficient:
        raise ValueError("Нужно минимум 2 независимых сайта с блюдами на город: " + ", ".join(insufficient))
    names = sorted({dish for sources in by_city.values() for dishes in sources.values() for dish in dishes})
    matrix = np.array([[sum(dish in d for d in by_city[city].values()) / len(by_city[city]) for dish in names] for city in expected])
    return expected, names, matrix, {c: len(by_city[c]) for c in expected}


def analyze(evidence, output):
    output.mkdir(parents=True, exist_ok=True)
    cities, names, frequencies, source_counts = build_matrix(evidence)
    pd.DataFrame(frequencies, index=cities, columns=names).to_csv(output / "city_dish_frequencies.csv", index_label="city", encoding="utf-8-sig")
    # Downweight broadly mentioned dishes, then L2 normalize for geometry.
    idf = np.log((1 + len(cities)) / (1 + (frequencies > 0).sum(axis=0))) + 1
    X = normalize(frequencies * idf)
    pd.DataFrame(X, index=cities, columns=names).to_csv(output / "city_vectors.csv", index_label="city", encoding="utf-8-sig")
    evaluations, candidates = [], {}
    for k in range(2, min(6, len(cities))):
        estimators = {"kmeans": KMeans(n_clusters=k, n_init=30, random_state=42),
                      "hierarchical": AgglomerativeClustering(n_clusters=k, linkage="ward"),
                      "spectral": SpectralClustering(n_clusters=k, affinity="precomputed", n_init=30, random_state=42)}
        for method, model in estimators.items():
            with threadpool_limits(limits=1):
                labels = model.fit_predict(np.clip(cosine_similarity(X), 0, 1) if method == "spectral" else X)
            score = float(silhouette_score(X, labels))
            evaluations.append({"method": method, "k": k, "silhouette": score,
                                "inertia": float(model.inertia_) if method == "kmeans" else None})
            candidates[method, k] = labels
    # Common K for method comparison, selected by mean silhouette across all 3 methods.
    ks = sorted({r["k"] for r in evaluations})
    k = max(ks, key=lambda n: np.mean([r["silhouette"] for r in evaluations if r["k"] == n]))
    labels = {m: candidates[m, k] for m in ["kmeans", "hierarchical", "spectral"]}
    pd.DataFrame({"city": cities, **labels}).to_csv(output / "city_clusters.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(evaluations).to_csv(output / "city_metrics.csv", index=False, encoding="utf-8-sig")
    stability = {a + " / " + b: float(adjusted_rand_score(labels[a], labels[b])) for a, b in
                 [("kmeans", "hierarchical"), ("kmeans", "spectral"), ("hierarchical", "spectral")]}
    pairs = {}
    for a, b in [("Пермь", "Кунгур"), ("Казань", "Уфа")]:
        pairs[a + " / " + b] = {m: bool(lab[cities.index(a)] == lab[cities.index(b)]) for m, lab in labels.items()}
    summary = {"k": k, "source_counts": source_counts, "features": len(names), "ari": stability,
               "expected_pairs_same_cluster": pairs, "clusters": {},
               "limitations": "Small convenience sample of selected pages; restaurant menus and regional travel articles differ. Frequency means share of sampled domains, not popularity among residents. Expected regional pairs are hypotheses, not forced labels."}
    for method, lab in labels.items():
        summary["clusters"][method] = []
        for cluster in sorted(set(lab)):
            mask = lab == cluster
            mean = frequencies[mask].mean(axis=0)
            top = np.argsort(mean)[-6:][::-1]
            summary["clusters"][method].append({"cluster": int(cluster), "cities": list(np.array(cities)[mask]),
                "top_dishes": [{"dish": names[i], "frequency": float(mean[i])} for i in top if mean[i] > 0]})
    write_json(output / "city_summary.json", summary)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for method in labels:
        points = [r for r in evaluations if r["method"] == method]
        axes[0].plot([r["k"] for r in points], [r["silhouette"] for r in points], "o-", label=method)
    points = [r for r in evaluations if r["method"] == "kmeans"]
    axes[1].plot([r["k"] for r in points], [r["inertia"] for r in points], "o-")
    axes[0].set(title="Silhouette", xlabel="K", ylabel="Оценка силуэта")
    axes[0].legend()
    axes[1].set(title="Метод локтя (KMeans)", xlabel="K", ylabel="Инерция")
    fig.tight_layout()
    fig.savefig(output / "city_k_selection.png", dpi=160)
    plt.close(fig)
    pca = PCA(n_components=2)
    xy = pca.fit_transform(X)
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    for ax, (method, lab) in zip(axes, labels.items()):
        ax.scatter(xy[:, 0], xy[:, 1], c=lab, cmap="tab10", s=100)
        for i, city in enumerate(cities):
            ax.annotate(city, xy[i], xytext=(4, 5 + 6*(i % 2)), textcoords="offset points", fontsize=8)
        ax.set(title=f"{method}, K={k}", xlabel="PC1", ylabel="PC2")
        ax.margins(x=.18, y=.12)
    fig.suptitle(f"PCA только для визуализации; объяснено {pca.explained_variance_ratio_.sum():.1%} дисперсии")
    fig.tight_layout()
    fig.savefig(output / "city_clusters.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5))
    dendrogram(linkage(X, method="ward"), labels=cities, leaf_rotation=30, ax=ax)
    ax.set_title("Иерархическая кластеризация, Ward")
    fig.tight_layout()
    fig.savefig(output / "city_dendrogram.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(max(12, len(names)*.32), 5))
    im = ax.imshow(frequencies, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_yticks(range(len(cities)), cities)
    ax.set_xticks(range(len(names)), names, rotation=90)
    fig.colorbar(im, ax=ax, label="Доля независимых сайтов с упоминанием")
    fig.tight_layout()
    fig.savefig(output / "city_dishes.png", dpi=160)
    plt.close(fig)
    lines = ["# Кластеризация городов по блюдам", "", f"Городов: {len(cities)}; блюд: {len(names)}; выбран K={k}.",
             "K выбран по среднему silhouette трёх методов на полном пространстве нормированных признаков.", "",
             "Частота — доля выбранных независимых доменов, где упоминается блюдо. Несколько страниц одного сайта объединяются.",
             "Перед кластеризацией применены IDF и L2-нормализация; PCA используется только на рисунке.", ""]
    for method, clusters in summary["clusters"].items():
        lines += [f"## {method}", ""]
        for cluster in clusters:
            lines.append(f"- {', '.join(cluster['cities'])}: {', '.join(d['dish'] for d in cluster['top_dishes'])}.")
    lines += ["", "## Проверка гипотез", ""]
    for pair, results in pairs.items():
        lines.append(f"- {pair}: " + "; ".join(f"{m}: {'вместе' if yes else 'раздельно'}" for m, yes in results.items()))
    lines += ["", "ARI между методами: " + "; ".join(f"{key}={value:.3f}" for key, value in stability.items()), "",
              "Ограничения: небольшая выборка, ручной выбор URL и словаря; меню ресторанов смешиваются с региональными обзорами. Особенно это влияет на Кунгур. Результат описывает собранные страницы, а не объективные границы национальных кухонь. Неподтверждённые пары не исправляются вручную.", "",
              "![Города](city_clusters.png)", "", "![Выбор K](city_k_selection.png)", "", "## Источники", ""]
    lines += [f"- {r['city']}: [{r.get('title', r['url'])}]({r['url']}) — {r['status']}." for r in evidence]
    (output / "city_report.md").write_text("\n".join(lines), encoding="utf-8")
    LOG.info("Готово: %s; K=%d; ARI=%s", output / "city_report.md", k, stability)


def main(argv=None):
    p = argparse.ArgumentParser(description="Кластеризация городов по упоминаниям блюд")
    p.add_argument("--collect", action="store_true", help="Загрузить страницы; без флага используется сохранённая выгрузка")
    p.add_argument("--sources", type=Path, default=ROOT / "city_sources.json")
    p.add_argument("--data-dir", type=Path, default=ROOT / "data/cities")
    p.add_argument("--output", type=Path, default=ROOT / "results/cities")
    args = p.parse_args(argv)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(),
        logging.FileHandler(args.data_dir / "collection.log", encoding="utf-8")])
    try:
        evidence = collect(args.sources, args.data_dir) if args.collect else json.loads((args.data_dir / "city_evidence.json").read_text(encoding="utf-8"))
        analyze(evidence, args.output)
        return 0
    except (ValueError, OSError) as exc:
        LOG.error("Не завершено: %s", exc)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
