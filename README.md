# Лабораторная работа №5 (практика 3)

**Тематическое моделирование веб-данных и кластеризация городов по блюдам.**

Результаты в **[REPORT.md](REPORT.md)**

## Установка и быстрый запуск (Windows PowerShell)

Команды выполняются из папки `Lab5 Zurin`:

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt

.\.venv\Scripts\python.exe run_all.py
```

При переносе на другой компьютер `.venv` не копировать: создать заново. Полный запуск занимает ориентировочно 2–8 минут в зависимости от процессора; каждая проверенная комбинация метода и K выводится в консоль. Установка пакетов требует интернета, повторный анализ приложенных данных работает без сети.

`requirements.txt` закрепляет прямые зависимости, `requirements-lock.txt` — также все транзитивные зависимости проверенного окружения. Ресурсы NLTK находятся в `data/nltk_data`, ищутся относительно файла программы, а не текущего каталога. Ничего не скачивается при импорте или запуске моделирования.

## Команды из задания

```powershell
.\.venv\Scripts\python.exe topic_modeling.py --dataset news --method lda --topics auto --output results/news_topics
.\.venv\Scripts\python.exe topic_modeling.py --dataset products --method nmf --topics 15 --output results/product_categories
.\.venv\Scripts\python.exe topic_modeling.py --dataset mixed --method both --topics 10 --compare --output results/mixed_example
```

Чтобы воспроизвести основные приложенные результаты:

```powershell
.\.venv\Scripts\python.exe topic_modeling.py --dataset news --method both --topics auto --compare --pyldavis
.\.venv\Scripts\python.exe topic_modeling.py --dataset products --method both --topics auto --compare --pyldavis
.\.venv\Scripts\python.exe topic_modeling.py --dataset mixed --method both --topics 10 --compare
.\.venv\Scripts\python.exe city_clustering.py
.\.venv\Scripts\python.exe verify_results.py
.\.venv\Scripts\python.exe build_report.py
```

| Параметр | Поведение |
|---|---|
| `--dataset news/products/mixed` | Корпус; mixed объединяет оба и проверяет минимум по каждому типу |
| `--input путь.json` или `.csv` | Собственный корпус вместо приложенного |
| `--method lda/nmf/both` | Реальный выбор обучаемых методов |
| `--topics auto` | Все K от 3 до 20 включительно; максимум c_v отдельно для каждого метода |
| `--topics 15` | Ровно 15 тем |
| `--compare` | Обучить оба метода независимо от `--method`, вывести сравнительную таблицу |
| `--output results/name` | **Префикс**, не каталог и не имя единственного файла: `results/name_lda_topics.json` и т. д. |
| `--max-features 1000` | Верхняя граница словаря; для первого опыта можно 100 |
| `--top-words 10` | Топ-слова и одинаковый top-N для c_v обеих моделей; рисунки топ-5 и топ-10 |
| `--passes 15` | Число проходов sklearn LDA (`max_iter`, аналог passes в Gensim) |
| `--max-iter 1000` | Предел итераций NMF |
| `--language en/ru` | Язык NLP: английский WordNet/POS или русский pymorphy3 |
| `--seed 42` | Воспроизводимая инициализация |
| `--pyldavis` | Дополнительный интерактивный HTML для LDA; его JS/CSS загружаются с CDN |
| `--quiet` | В консоли только предупреждения/ошибки, полный прогресс остаётся в логе |

Без `--output` результаты пишутся в `results/<dataset>_*` относительно программы. Явно указанный относительный префикс разрешается относительно текущего рабочего каталога. Повторный запуск с тем же префиксом заменяет соответствующие результаты. Для другого эксперимента используйте другой префикс; файлы ранее запущенных других методов автоматически не удаляются.


| Файл | Происхождение и отбор |
|---|---|
| `data/news.json` | 500 статей BBC из корпуса UCD, 2004–2005; перемешивание seed=42, дедупликация, категории не используются при обучении |
| `data/products.json` | 234 уникальных товара Software из Amazon Reviews 2018 (UCSD), реальные описания и отзывы из архивного корпуса |
| `data/sources.json` | URL архивов, SHA-256, время подготовки в UTC и правило отбора |
| `data/cities/city_evidence.json` | Найденные блюда, URL и домен, статус извлечения, короткое подтверждение и хеш текста |
| `data/cities/pages/` | HTML-кэш исходных страниц для проверки извлечения |

Товары выбраны с описанием 15–200 слов и одним существующим отзывом 10–80 слов.
Краткий отзыв выбран первым в порядке исходного архива; это смещение отбора отмечено в отчёте. Лимит 500 в сборщике — верхняя граница, а не ровно 500. После отбора коротких записей найдено 234 товара.

Первичные страницы корпусов: [BBC / UCD](http://mlg.ucd.ie/datasets/bbc.html), [Amazon Reviews 2018 / UCSD](https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/). Корпуса исторические, а не актуальные новости или действующий ассортимент магазина. Поле `collected_at` относится к подготовке локальной выгрузки, не дате публикации статьи/отзыва. BBC URL указывает на архив и имя файла.

Повторный сбор:

```powershell
.\.venv\Scripts\python.exe collect_data.py
.\.venv\Scripts\python.exe city_clustering.py --collect
```

Оба сборщика используют таймауты, повторные GET при 429/503 и других временных ошибках, учитывают `Retry-After`, сохраняют журналы. Кэш архивов в `data/downloads/`; `collect_data.py --offline` пересобирает JSON из уже скачанных архивов. При недостатке документов сборщик возвращает ненулевой код. Страницы городов загружаются по списку `city_sources.json`, сформированному поиском по каждому городу; извлечение блюд и расчёт частот автоматические, интернет-поисковик не вызывается при воспроизведении.

## Формат собственных данных

JSON — массив объектов; CSV — UTF-8/UTF-8 BOM, заголовок обязателен. Новости: `id`, `title`, `text` (либо `content`/`summary`), `url`, необязательный `source`. Тело новости должно содержать минимум 50 слов до NLP. Товары: `id`, `title`, `description`, `reviews`, `url`, `source`. `reviews` — список строк или объектов `{"text": "текст отзыва"}`; в CSV это строка с JSON-массивом. Для mixed обязательно поле `dataset` со значением `news` или `products` у каждой записи. Категории не подмешиваются в тексты модели.

Минимум 200 документов каждого типа проверяется **после** удаления дублей, пустых текстов и нулевых векторов. Нарушения схемы и недобор приводят к ошибке; причины отклонения строк записаны в `<prefix>_audit.json`.

## Выходные файлы

Для каждого префикса сохраняются:

- `_audit.json`, `_cleaned.json`, `_vocabulary.csv` — качество данных и подготовленный корпус.
- `_coherence.csv`, `_coherence.png` — оценки всех проверенных K и график.
- `_lda_topics.json`, `_nmf_topics.json` — темы, c_v каждой темы, слова с исходными и нормированными весами, документы-примеры.
- `_<method>_keywords.csv` — те же топ-слова с весами в табличном формате.
- `_<method>_documents.csv` — ID, название, URL, доли тем, ведущая тема; строки соответствуют `_cleaned.json`.
- `_<method>_raw_weights.csv` — исходные веса; у NMF сумма не обязана равняться 1.
- `_<method>_top5.png`, `_top10.png`, `_distribution.png`, `_heatmap.png` — рисунки.
- `_lda_interactive.html` — если указан `--pyldavis`.
- `_summary.json`, `_run.log`, `_report.md` — параметры, версии, хеши исходного кода и входных данных, итоговая таблица и интерпретация.

Все PNG и Markdown доступны без интернета. Для pyLDAvis требуется сеть для CDN; статические рисунки покрывают обязательные визуализации.

`results/cities/`: исходные частоты [0,1], нормированные векторы, метки трёх методов, silhouette и inertia по K, ARI, проверка гипотез о парах городов, диаграмма PCA, дендрограмма и тепловая карта.

## Проверка

`verify_results.py` сверяет хеши, число документов, матрицы, суммы долей, все 18 значений K и выбор максимума coherence.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe verify_results.py
```

Логи проверок: `results/tests.txt`, `results/verification.txt`.

## Клонирование с GitHub

```powershell
git clone https://github.com/ArtemyZurin/lab5-zurin.git
cd lab5-zurin
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run_all.py
```

Виртуальное окружение и исходные скачанные архивы не включены в Git. Подготовленные данные, NLP-словари, отчёт и результаты включены.
