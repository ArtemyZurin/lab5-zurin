"""Лабораторная №5. Очистка → NLP → Count/TF-IDF → LDA/NMF → c_v."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.metadata
import json
import logging
import math
import re
import sys
import time
import warnings
from collections import Counter
from functools import lru_cache
from pathlib import Path

import ftfy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nltk
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent
nltk.data.path.insert(0, str(ROOT / "data/nltk_data"))
LOG = logging.getLogger("lab5")
TOKEN = re.compile(r"[a-zа-яё]+", re.IGNORECASE)


def clean_text(value: str) -> str:
    """Repair encoding, remove executable/hidden markup, entities, URLs, whitespace."""
    text = ftfy.fix_text(html.unescape(value))
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "noscript"]):
            element.decompose()
        text = soup.get_text(" ", strip=True)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    return " ".join(text.lower().replace("ё", "е").split())


class Preprocessor:
    def __init__(self, language="en"):
        self.language = language
        self.stop = set(stopwords.words("english" if language == "en" else "russian"))
        self.stop |= {"said", "also", "would", "could", "mr", "mrs", "http", "www", "com"}
        if language == "ru":
            import pymorphy3
            self.morph = pymorphy3.MorphAnalyzer()
        else:
            self.lemmatizer = WordNetLemmatizer()

    @lru_cache(maxsize=100000)
    def lemma(self, word, tag="N"):
        if self.language == "ru":
            return self.morph.parse(word)[0].normal_form
        pos = {"J": "a", "V": "v", "N": "n", "R": "r"}.get(tag[:1], "n")
        return self.lemmatizer.lemmatize(word, pos)

    def __call__(self, text):
        words = TOKEN.findall(text)
        words = [w for w in words if len(w) > 2 and w not in self.stop]
        tagged = nltk.pos_tag(words, lang="eng") if self.language == "en" else [(w, "N") for w in words]
        lemmas = [self.lemma(w, tag) for w, tag in tagged]
        return [w for w in lemmas if len(w) > 2 and w not in self.stop]


def read_rows(path):
    if not path.is_file():
        raise ValueError(f"Файл не найден: {path}. Используйте collect_data.py или --input.")
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        raise ValueError("Вход должен быть JSON (массив объектов) или CSV с заголовком")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Ожидается массив объектов документов")
    return rows


def document_text(row, dataset):
    title = row.get("title", "")
    kind = row.get("dataset", dataset)
    if kind == "products":
        body = row.get("description", "")
        reviews = row.get("reviews", [])
        if isinstance(reviews, str):
            try:
                reviews = json.loads(reviews)
            except json.JSONDecodeError as exc:
                raise ValueError("Поле reviews в CSV должно содержать JSON-массив") from exc
        if not isinstance(reviews, list):
            raise ValueError("Поле reviews должно быть массивом")
        review_text = " ".join(r if isinstance(r, str) else str(r.get("text", r.get("comment", ""))) for r in reviews)
        if not isinstance(body, str) or not clean_text(body) or not clean_text(review_text):
            return None, "missing_description_or_reviews"
        body = body + " " + review_text
    else:
        body = row.get("text", row.get("content", row.get("summary", "")))
        if not isinstance(body, str) or len(TOKEN.findall(clean_text(body))) < 50:
            return None, "missing_or_short_article"
    if not isinstance(title, str):
        raise ValueError("Поле title должно быть строкой")
    # Deduplicate by content independently of potentially different titles/URLs.
    return (clean_text(title + " " + body), clean_text(body)), None


def prepare(rows, dataset, language):
    preprocessor = Preprocessor(language)
    documents, rejected = [], []
    seen_urls, seen_text, seen_tokens, seen_ids = set(), set(), set(), set()
    for index, row in enumerate(rows):
        pair, reason = document_text(row, dataset)
        url = str(row.get("url", "")).strip()
        doc_id = str(row.get("id") or f"{dataset}:{index + 1}")
        if not reason:
            text, body = pair
            fingerprint = hashlib.sha256(body.encode()).hexdigest()
            if doc_id in seen_ids:
                reason = "duplicate_id"
            elif url and url in seen_urls:
                reason = "duplicate_url"
            elif fingerprint in seen_text:
                reason = "duplicate_content"
            else:
                tokens = preprocessor(text)
                token_key = " ".join(tokens)
                if len(tokens) < 5:
                    reason = "too_few_tokens"
                elif token_key in seen_tokens:
                    reason = "duplicate_tokens"
                else:
                    seen_ids.add(doc_id)
                    seen_urls.add(url)
                    seen_text.add(fingerprint)
                    seen_tokens.add(token_key)
                    documents.append({"id": doc_id, "title": row.get("title", ""), "url": url,
                                      "dataset": row.get("dataset", dataset), "source": row.get("source", ""),
                                      "text": text, "tokens": tokens})
        if reason:
            rejected.append({"row": index + 1, "id": doc_id, "reason": reason})
        if (index + 1) % 100 == 0:
            LOG.info("Предобработка: %d/%d", index + 1, len(rows))
    audit = {"input": len(rows), "accepted": len(documents), "rejected": len(rejected),
             "reasons": dict(Counter(r["reason"] for r in rejected)), "rejected_rows": rejected}
    return documents, audit


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def output_path(prefix, suffix):
    return Path(str(prefix) + suffix)


def plot_top_words(model, feature_names, n_top_words, title, path):
    """Dynamic grid supports any K, including K=3 and K=20."""
    k = model.components_.shape[0]
    columns = min(4, k)
    rows = math.ceil(k / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(6 * columns, 4.2 * rows), squeeze=False)
    for index, ax in enumerate(axes.flat):
        if index >= k:
            ax.set_visible(False)
            continue
        weights = model.components_[index]
        ids = weights.argsort()[-n_top_words:][::-1]
        ax.barh(np.asarray(feature_names)[ids], weights[ids], color="#257b9d")
        ax.invert_yaxis()
        ax.set_title(f"Тема {index + 1}")
        ax.set_xlabel("Вес в components_")
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0, 1, .97))
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fit_model(method, k, matrix, args):
    model = (LatentDirichletAllocation(n_components=k, max_iter=args.passes, learning_method="batch",
             random_state=args.seed, n_jobs=1) if method == "lda" else
             NMF(n_components=k, init="nndsvda", random_state=args.seed, max_iter=args.max_iter,
                 solver="cd", beta_loss="frobenius", tol=1e-4))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        weights = model.fit_transform(matrix)
    messages = [str(w.message) for w in caught]
    for message in messages:
        LOG.warning("%s K=%d: %s", method, k, message)
    return model, weights, messages


def export_model(prefix, method, result, names, docs, counts, top_words, pyldavis):
    model, weights = result["model"], result["weights"]
    k = model.components_.shape[0]
    sums = weights.sum(axis=1, keepdims=True)
    distribution = np.divide(weights, sums, out=np.zeros_like(weights), where=sums > 0)
    frame = pd.DataFrame(distribution, columns=[f"topic_{i+1}" for i in range(k)])
    frame.insert(0, "url", [d["url"] for d in docs])
    frame.insert(0, "title", [d["title"] for d in docs])
    frame.insert(0, "id", [d["id"] for d in docs])
    frame["assigned"] = sums[:, 0] > 0
    frame["dominant_topic"] = np.where(sums[:, 0] > 0, distribution.argmax(axis=1) + 1, 0)
    frame.to_csv(output_path(prefix, f"_{method}_documents.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(weights, columns=[f"topic_{i+1}" for i in range(k)], index=[d["id"] for d in docs]).to_csv(
        output_path(prefix, f"_{method}_raw_weights.csv"), index_label="id", encoding="utf-8-sig")
    topics, flat = [], []
    for i, component in enumerate(model.components_):
        total = component.sum()
        ids = component.argsort()[-top_words:][::-1]
        words = [{"word": str(names[j]), "weight": float(component[j]),
                  "normalized_weight": float(component[j] / total) if total else 0.0} for j in ids]
        top_docs = np.argsort(distribution[:, i])[-3:][::-1]
        topics.append({"topic": i + 1, "label": " / ".join(w["word"] for w in words[:3]),
                       "coherence_cv": float(result["per_topic"][i]), "words": words,
                       "examples": [{"id": docs[j]["id"], "title": docs[j]["title"], "weight": float(distribution[j, i])} for j in top_docs]})
        flat.extend({"topic": i + 1, **word} for word in words)
    payload = {"method": method, "k": k, "coherence_cv": result["score"], "fit_seconds": result["seconds"],
               "warnings": result["warnings"], "unassigned_documents": int((sums[:, 0] == 0).sum()),
               "distribution_kind": "posterior probabilities" if method == "lda" else "L1-normalized NMF weights; not posterior probabilities",
               "topics": topics}
    save_json(output_path(prefix, f"_{method}_topics.json"), payload)
    pd.DataFrame(flat).to_csv(output_path(prefix, f"_{method}_keywords.csv"), index=False, encoding="utf-8-sig")
    for n in sorted({min(5, top_words), top_words}):
        plot_top_words(model, names, n, f"{method.upper()}, K={k}, c_v={result['score']:.4f}, топ-{n}",
                       output_path(prefix, f"_{method}_top{n}.png"))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(np.arange(1, k + 1), distribution.mean(axis=0), color="#257b9d")
    ax.set(xlabel="Тема", ylabel="Средняя доля", title=f"{method.upper()}: тематическое распределение корпуса")
    fig.tight_layout()
    fig.savefig(output_path(prefix, f"_{method}_distribution.png"), dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 6))
    order = np.argsort(distribution.argmax(axis=1), kind="stable")
    image = ax.imshow(distribution[order], aspect="auto", interpolation="nearest", cmap="Blues")
    ax.set(xlabel="Тема", ylabel="Документы (сортировка по ведущей теме)", title=method.upper())
    fig.colorbar(image, ax=ax, label="Доля темы")
    fig.tight_layout()
    fig.savefig(output_path(prefix, f"_{method}_heatmap.png"), dpi=150)
    plt.close(fig)
    if pyldavis and method == "lda":
        import pyLDAvis
        prepared = pyLDAvis.prepare(model.components_ / model.components_.sum(axis=1, keepdims=True),
            distribution, np.asarray(counts.sum(axis=1)).ravel(), list(names),
            np.asarray(counts.sum(axis=0)).ravel(), sort_topics=False, n_jobs=1)
        pyLDAvis.save_html(prepared, str(output_path(prefix, "_lda_interactive.html")))
    return payload


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Тематическое моделирование: LDA (Count) и NMF (TF-IDF)")
    parser.add_argument("--dataset", choices=["news", "products", "mixed"], default="news")
    parser.add_argument("--input", type=Path, help="Собственный JSON/CSV вместо встроенного корпуса")
    parser.add_argument("--method", choices=["lda", "nmf", "both"], default="both")
    parser.add_argument("--topics", default="auto", help="Число тем >=2 либо auto (3..20)")
    parser.add_argument("--compare", action="store_true", help="Обучить и сравнить оба метода")
    parser.add_argument("--output", type=Path, help="Префикс файлов, например results/news")
    parser.add_argument("--language", choices=["en", "ru"], default="en")
    parser.add_argument("--max-features", type=int, default=1000)
    parser.add_argument("--top-words", type=int, default=10)
    parser.add_argument("--passes", type=int, default=15, help="Проходы LDA (max_iter sklearn)")
    parser.add_argument("--max-iter", type=int, default=1000, help="Итерации NMF")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pyldavis", action="store_true", help="Дополнительный интерактивный HTML LDA")
    parser.add_argument("--quiet", action="store_true", help="Только предупреждения и ошибки")
    args = parser.parse_args(argv)
    if args.topics != "auto":
        try:
            args.topics = int(args.topics)
        except ValueError:
            parser.error("--topics: требуется целое число или auto")
        if args.topics < 2:
            parser.error("--topics должно быть >=2")
    for key in ["max_features", "top_words", "passes", "max_iter"]:
        if getattr(args, key) < 1:
            parser.error(f"--{key.replace('_', '-')} должно быть положительным")
    if args.top_words < 2:
        parser.error("Для coherence требуется минимум 2 топ-слова")
    return args


def run(args):
    prefix = args.output or ROOT / "results" / args.dataset
    prefix.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True,
                        handlers=[logging.FileHandler(output_path(prefix, "_run.log"), encoding="utf-8")])
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING if args.quiet else logging.INFO)
    logging.getLogger().addHandler(console)
    for name in ["gensim", "matplotlib", "numexpr"]:
        logging.getLogger(name).setLevel(logging.WARNING)
    if args.input:
        paths = [args.input]
        rows = read_rows(args.input)
        if args.dataset == "mixed" and any(r.get("dataset") not in {"news", "products"} for r in rows):
            raise ValueError("Для mixed каждый документ должен иметь dataset=news или products")
    else:
        kinds = ["news", "products"] if args.dataset == "mixed" else [args.dataset]
        paths = [ROOT / "data" / f"{kind}.json" for kind in kinds]
        rows = [dict(row, dataset=kind) for kind, path in zip(kinds, paths) for row in read_rows(path)]
    LOG.info("1/4 Очистка и NLP: %d документов", len(rows))
    docs, audit = prepare(rows, args.dataset, args.language)
    save_json(output_path(prefix, "_audit.json"), audit)
    groups = Counter(d["dataset"] for d in docs)
    required = ["news", "products"] if args.dataset == "mixed" else [args.dataset]
    if any(groups[kind] < 200 for kind in required):
        raise ValueError(f"После очистки {dict(groups)}. Требуется >=200 документов каждого типа. См. {prefix}_audit.json")
    LOG.info("2/4 Векторизация: принято %d, отклонено %d", len(docs), audit["rejected"])
    texts = [" ".join(d["tokens"]) for d in docs]
    settings = dict(tokenizer=str.split, token_pattern=None, lowercase=False, min_df=2, max_df=.95,
                    max_features=args.max_features)
    count_vectorizer = CountVectorizer(**settings)
    counts = count_vectorizer.fit_transform(texts)
    names = count_vectorizer.get_feature_names_out()
    tfidf_vectorizer = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False,
                                     vocabulary=count_vectorizer.vocabulary_)
    tfidf = tfidf_vectorizer.fit_transform(texts)
    nonzero = np.asarray(counts.sum(axis=1)).ravel() > 0
    if not nonzero.all():
        removed = [d for d, keep in zip(docs, nonzero) if not keep]
        audit["zero_vector_ids"] = [d["id"] for d in removed]
        docs = [d for d, keep in zip(docs, nonzero) if keep]
        counts, tfidf = counts[nonzero], tfidf[nonzero]
        LOG.warning("Документы с нулевым вектором исключены: %d", len(removed))
    audit["modeled"] = len(docs)
    audit["vocabulary_size"] = len(names)
    audit["mean_tokens"] = float(np.mean([len(d["tokens"]) for d in docs]))
    audit["median_tokens"] = float(np.median([len(d["tokens"]) for d in docs]))
    save_json(output_path(prefix, "_audit.json"), audit)
    groups = Counter(d["dataset"] for d in docs)
    if any(groups[kind] < 200 for kind in required):
        raise ValueError("После удаления нулевых векторов осталось менее 200 документов одного из типов")
    ks = list(range(3, 21)) if args.topics == "auto" else [args.topics]
    if max(ks) > min(counts.shape) or args.top_words > len(names):
        raise ValueError(f"Недостаточный размер матрицы {counts.shape} для K={max(ks)} / top_words={args.top_words}")
    save_json(output_path(prefix, "_cleaned.json"), docs)
    pd.DataFrame({"term": names, "count": np.asarray(counts.sum(axis=0)).ravel()}).to_csv(
        output_path(prefix, "_vocabulary.csv"), index=False, encoding="utf-8-sig")
    token_texts = [d["tokens"] for d in docs]
    dictionary = Dictionary(token_texts)
    methods = ["lda", "nmf"] if args.compare or args.method == "both" else [args.method]
    scores, best, exports = [], {}, {}
    LOG.info("3/4 Обучение: %s; K=%s", methods, ks)
    for method in methods:
        matrix = counts if method == "lda" else tfidf
        for k in ks:
            started = time.perf_counter()
            with threadpool_limits(limits=1):
                model, weights, messages = fit_model(method, k, matrix, args)
            seconds = time.perf_counter() - started
            topics = [[str(names[j]) for j in component.argsort()[-args.top_words:][::-1]] for component in model.components_]
            cm = CoherenceModel(topics=topics, texts=token_texts, dictionary=dictionary,
                                coherence="c_v", window_size=110, topn=args.top_words, processes=1)
            per_topic = cm.get_coherence_per_topic()
            score = float(np.mean(per_topic))
            if not math.isfinite(score):
                raise ValueError(f"Неопределённый coherence: {method}, K={k}")
            scores.append({"method": method, "k": k, "coherence_cv": score, "fit_seconds": seconds,
                           "convergence_warning": bool(messages)})
            LOG.info("%s K=%d: c_v=%.4f, обучение %.2f с", method.upper(), k, score, seconds)
            if method not in best or score > best[method]["score"]:
                best[method] = dict(model=model, weights=weights, per_topic=per_topic, score=score,
                                    seconds=seconds, warnings=messages)
        exports[method] = export_model(prefix, method, best[method], names, docs, counts, args.top_words, args.pyldavis)
    LOG.info("4/4 Сохранение сравнения и отчёта")
    pd.DataFrame(scores).to_csv(output_path(prefix, "_coherence.csv"), index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(10, 5))
    for method in methods:
        part = [r for r in scores if r["method"] == method]
        ax.plot([r["k"] for r in part], [r["coherence_cv"] for r in part], "o-", label=method.upper())
    ax.set(xlabel="Число тем K", ylabel="Coherence c_v", title="Подбор K на одинаковом корпусе")
    ax.set_xticks(ks)
    ax.legend()
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(output_path(prefix, "_coherence.png"), dpi=150)
    plt.close(fig)
    comparison = {m: {k: exports[m][k] for k in ["k", "coherence_cv", "fit_seconds", "unassigned_documents", "warnings"]} for m in methods}
    metadata = {"dataset": args.dataset, "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "inputs": [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "versions": {p: importlib.metadata.version(p) for p in ["numpy", "scipy", "scikit-learn", "gensim", "nltk", "ftfy"]},
                "audit": {k: v for k, v in audit.items() if k != "rejected_rows"}, "models": comparison,
                "selection": "maximum in-sample c_v; fixed seed; no held-out generalization claim"}
    save_json(output_path(prefix, "_summary.json"), metadata)
    lines = [f"# Тематическое моделирование: {args.dataset}", "", f"Документов: {len(docs)}; словарь: {len(names)}; seed={args.seed}.",
             "", "| Метод | K | c_v | Обучение, с |", "|---|---:|---:|---:|"]
    for method, values in comparison.items():
        lines.append(f"| {method.upper()} | {values['k']} | {values['coherence_cv']:.4f} | {values['fit_seconds']:.2f} |")
    lines += ["", "K выбран по максимуму c_v на том же корпусе. Это описательная оценка, не качество на новых данных.",
              "LDA использует CountVectorizer, NMF — TF-IDF с тем же словарём. Веса NMF нормированы по строкам и не являются вероятностями LDA.",
              "Слова в label — автоматические подсказки для интерпретации, не экспертные категории.", ""]
    if len(methods) == 2:
        winner = max(methods, key=lambda m: comparison[m]["coherence_cv"])
        lines += [f"На этом запуске выше c_v у **{winner.upper()}**. Вывод относится только к данному корпусу и настройкам.", "",
                  "| Тема | LDA: ключевые слова | NMF: ключевые слова |", "|---:|---|---|"]
        for index in range(max(exports[m]["k"] for m in methods)):
            cells = [", ".join(w["word"] for w in exports[m]["topics"][index]["words"][:5]) if index < exports[m]["k"] else "—" for m in methods]
            lines.append(f"| {index+1} | {cells[0]} | {cells[1]} |")
        lines += ["", "Номера тем разных моделей не выровнены: строка таблицы не означает соответствие тем.", ""]
    for method in methods:
        lines += [f"## {method.upper()}", ""]
        for topic in exports[method]["topics"]:
            lines.append(f"- Тема {topic['topic']} ({topic['coherence_cv']:.3f}): {topic['label']}. Пример: {topic['examples'][0]['title']}.")
        lines += ["", f"![Топ-слова]({prefix.name}_{method}_top{args.top_words}.png)", ""]
    output_path(prefix, "_report.md").write_text("\n".join(lines), encoding="utf-8")
    LOG.info("Готово: %s_report.md; документов=%d; модели=%s", prefix.resolve(), len(docs), comparison)
    return metadata


def main(argv=None):
    args = parse_args(argv)
    try:
        run(args)
        return 0
    except (ValueError, OSError, LookupError) as exc:
        LOG.error("Ошибка: %s", exc)
        if isinstance(exc, LookupError):
            LOG.error("Словари NLP не найдены: запустите collect_data.py после установки зависимостей")
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
