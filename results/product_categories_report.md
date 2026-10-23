# Тематическое моделирование: products

Документов: 234; словарь: 1000; seed=42.

| Метод | K | c_v | Обучение, с |
|---|---:|---:|---:|
| NMF | 15 | 0.7365 | 0.07 |

K выбран по максимуму c_v на том же корпусе. Это описательная оценка, не качество на новых данных.
LDA использует CountVectorizer, NMF — TF-IDF с тем же словарём. Веса NMF нормированы по строкам и не являются вероятностями LDA.
Слова в label — автоматические подсказки для интерпретации, не экспертные категории.

## NMF

- Тема 1 (0.844): mcafee / every / online. Пример: McAfee Antivirus Plus 2012 - 3 Users [Old Version].
- Тема 2 (0.823): tax / turbotax / state. Пример: TurboTax Deluxe 2015 Federal + State Taxes - Tax Preparation Software - PC Download [Old Version].
- Тема 3 (0.768): video / edit / movie. Пример: Pinnacle Studio 18 Ultimate (Old Version).
- Тема 4 (0.919): office / microsoft / build. Пример: Microsoft Office Home and Student 2016 English.
- Тема 5 (0.660): norton / security / device. Пример: Norton Security Deluxe &ndash; 3 Devices &ndash; 1 Year Subscription &ndash; Product Key Card - 2019 Ready.
- Тема 6 (0.655): backup / acronis / image. Пример: Acronis True Image Backup &amp; Recovery 2014.
- Тема 7 (0.695): kaspersky / internet / security. Пример: Kaspersky Internet Security 1 -2015.
- Тема 8 (0.607): sage / business / accounting. Пример: Sage 50 Pro Accounting 2016.
- Тема 9 (0.875): tax / large / view. Пример: H&amp;R Block 2015 Premium + State Tax Software +  Refund Bonus Offer - Windows Download [Old Version].
- Тема 10 (0.773): trend / micro / titanium. Пример: Trend MicroTrend Micro Titanium Maximum Premium 2014 [Old Version].
- Тема 11 (0.564): window / home / windows. Пример: Microsoft Windows 10 Home USB Flash Drive [Old Version].
- Тема 12 (0.815): norton / antivirus / threat. Пример: Norton Antivirus 2014 - 1 User / 3 Licenses [Old Version].
- Тема 13 (0.579): clean / free / malware. Пример: Advanced SystemCare 7 FREE [Download].
- Тема 14 (0.757): photo / pro / edit. Пример: Corel PaintShop Pro X8 Ultimate [Old Version].
- Тема 15 (0.713): quicken / finance / ibank. Пример: iBank 4.

![Топ-слова](product_categories_nmf_top10.png)
