# Тематическое моделирование: news

Документов: 495; словарь: 1000; seed=42.

| Метод | K | c_v | Обучение, с |
|---|---:|---:|---:|
| LDA | 12 | 0.6117 | 1.73 |

K выбран по максимуму c_v на том же корпусе. Это описательная оценка, не качество на новых данных.
LDA использует CountVectorizer, NMF — TF-IDF с тем же словарём. Веса NMF нормированы по строкам и не являются вероятностями LDA.
Слова в label — автоматические подсказки для интерпретации, не экспертные категории.

## LDA

- Тема 1 (0.508): game / people / technology. Пример: Media gadgets get moving.
- Тема 2 (0.509): film / best / award. Пример: Triple triumph for Little Britain.
- Тема 3 (0.548): company / firm / business. Пример: Japanese mogul arrested for fraud.
- Тема 4 (0.566): game / player / england. Пример: England 17-18 France.
- Тема 5 (0.475): game / roddick / nadal. Пример: Nadal puts Spain 2-0 up.
- Тема 6 (0.598): year / win / final. Пример: Holmes back on form in Birmingham.
- Тема 7 (0.718): year / rise / rate. Пример: 'Strong dollar' call halts slide.
- Тема 8 (0.641): music / service / network. Пример: Musicians 'upbeat' about the net.
- Тема 9 (0.807): labour / election / tax. Пример: Howard and Blair tax pledge clash.
- Тема 10 (0.436): government / work / plan. Пример: CSA chief who 'quit' still in job.
- Тема 11 (0.789): search / user / software. Пример: Search wars hit desktop PCs.
- Тема 12 (0.745): blair / minister / tell. Пример: Goldsmith: 'I was not leant on'.

![Топ-слова](news_topics_lda_top10.png)
