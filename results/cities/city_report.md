# Кластеризация городов по блюдам

Городов: 9; блюд: 48; выбран K=5.
K выбран по среднему silhouette трёх методов на полном пространстве нормированных признаков.

Частота — доля выбранных независимых доменов, где упоминается блюдо. Несколько страниц одного сайта объединяются.
Перед кластеризацией применены IDF и L2-нормализация; PCA используется только на рисунке.

## kmeans

- Новосибирск, Пермь, Хабаровск: строганина, пельмени, уха, шаньги, посику́нчики, папоротник.
- Санкт-Петербург: шаверма, корюшка, пышки, тартар, пельмени, блины.
- Казань, Уфа: эчпочмак, чак-чак, кыстыбый, манты, казы, бэлеш.
- Петрозаводск: калитки, ряпушка, уха, лохикейтто.
- Кунгур, Москва: оливье, солянка, расстегай, щи, калач, роллы.
## hierarchical

- Кунгур, Москва: оливье, солянка, расстегай, щи, калач, роллы.
- Казань, Уфа: эчпочмак, чак-чак, кыстыбый, манты, казы, бэлеш.
- Новосибирск, Пермь, Хабаровск: строганина, пельмени, уха, шаньги, посику́нчики, папоротник.
- Петрозаводск: калитки, ряпушка, уха, лохикейтто.
- Санкт-Петербург: шаверма, корюшка, пышки, тартар, пельмени, блины.
## spectral

- Санкт-Петербург: шаверма, корюшка, пышки, тартар, пельмени, блины.
- Новосибирск, Пермь, Хабаровск: строганина, пельмени, уха, шаньги, посику́нчики, папоротник.
- Кунгур, Москва: оливье, солянка, расстегай, щи, калач, роллы.
- Петрозаводск: калитки, ряпушка, уха, лохикейтто.
- Казань, Уфа: эчпочмак, чак-чак, кыстыбый, манты, казы, бэлеш.

## Проверка гипотез

- Пермь / Кунгур: kmeans: раздельно; hierarchical: раздельно; spectral: раздельно
- Казань / Уфа: kmeans: вместе; hierarchical: вместе; spectral: вместе

ARI между методами: kmeans / hierarchical=1.000; kmeans / spectral=1.000; hierarchical / spectral=1.000

Ограничения: небольшая выборка, ручной выбор URL и словаря; меню ресторанов смешиваются с региональными обзорами. Особенно это влияет на Кунгур. Результат описывает собранные страницы, а не объективные границы национальных кухонь. Неподтверждённые пары не исправляются вручную.

![Города](city_clusters.png)

![Выбор K](city_k_selection.png)

## Источники

- Пермь: [Экскурсии и дегустации | Кафе «Пермская кухня»](https://permkuhnya.ru/экскурсии-2/) — ok.
- Пермь: [Где поесть и что привезти из Пермского края](https://www.tutu.ru/geo/rossiya/perm_krai/article/vkusno_perm/) — ok.
- Пермь: [Гастромаршрут Проверено Туту по Пермскому краю](https://provereno.tutu.ru/gastro-perm) — ok.
- Кунгур: [Меню — Суши-бар «Такара», г. Кунгур](https://takara-kungur.ru/menu/) — ok.
- Кунгур: [Аппетитная кухня ВкусиМи — Сочетание элементов различных кулинарных традиций. Наша кухня не относят к какой-то конкретной кухне, мы брали идеи разных традиций и народов.](https://vkusimi.ru/) — ok.
- Кунгур: [Кунгур за 1 день: что посмотреть самостоятельно? Готовый маршрут по жемчужине Урала - Радиоточка Плюс Туристический Маршрут](https://radiotochki.net/blog/tourism/kungur-za-1-den-chto-posmotret-samostoyatelno-gotovyy-marshrut-po-zhemchuzhine-urala.html) — ok.
- Москва: [Гастрономическая карта региона Москва - Национальное конгресс-бюро](https://russiacb.com/regions/moskva/food-moscow/) — ok.
- Москва: [Калач с «ручкой», оливье и высокая гастрономия: как менялась московская еда - Ведомости.Город](https://www.vedomosti.ru/gorod/ourcity/articles/menyalas-moskovskaya) — ok.
- Москва: [Кухня Москвы: калачи, кулебяка и торт «Птичье молоко»](https://moy-region.ru/guides/kuhnya-moskvy) — ok.
- Санкт-Петербург: [https://pyshki.spb.ru/](https://pyshki.spb.ru/) — error.
- Санкт-Петербург: [Что попробовать в Питере 2026: пышки, корюшка, шаверма](https://excursionspb.com/gde-poest-v-peterburge/) — ok.
- Санкт-Петербург: [Где проесть корюшку в Петербурге в 2026 году Metro](https://www.metronews.ru/eda/reviews/gde-proest-koryushku-v-peterburge-v-2026-godu-2188267/) — ok.
- Казань: [Гастрономические удовольствия в Татарстане](https://visit-tatarstan.com/guides/gastronomicheskie-udovolstviya-v-tatarstane/) — ok.
- Казань: [Государственный комитет Республики Татарстан по туризму](https://tourism.tatarstan.ru/index.htm/news/2129203.htm) — ok.
- Казань: [Национальные блюда Татарстана остаются главными гастросувенирами Казани](https://www.tatar-inform.ru/news/stalo-izvestno-kakie-sedobnye-suveniry-turisty-uvozyat-iz-kazani-6003331) — ok.
- Уфа: [Национальная кухня | Terra Bashkiria](https://travelvillage.ru/catalog/food/) — ok.
- Уфа: [Чак-Чак Норрис: где в Уфе пробовать блюда локальной кухни? | Sobaka.ru](https://www.sobaka.ru/ufa/bars/chtogdeest/183019) — ok.
- Уфа: [Путеводитель по Уфе](https://www.russiadiscovery.ru/news/putevoditel_ufa/) — ok.
- Новосибирск: [Кухня Новосибирской области: что попробовать и привезти](https://moy-region.ru/guides/kuhnya-novosibirskoy-oblasti) — ok.
- Новосибирск: [Гастрономическая карта региона Новосибирская область - Национальное конгресс-бюро](https://russiacb.com/regions/novosibirsk/food-novosibirsk/) — ok.
- Новосибирск: [https://travel.yandex.ru/journal/kak-provesti-den-v-novosibirske/](https://travel.yandex.ru/journal/kak-provesti-den-v-novosibirske/) — error.
- Новосибирск: [https://openkitchen.eda.yandex/article/places/cities/gde-poprobovat-natsionalnuyu-kukhnyu-v-novosibirske](https://openkitchen.eda.yandex/article/places/cities/gde-poprobovat-natsionalnuyu-kukhnyu-v-novosibirske) — error.
- Хабаровск: [Местная кухня](https://zapovednye-mesta.rgo.ru/cuisine) — ok.
- Хабаровск: [Готовьте "вкусовые сосочки": чем Хабаровский край удивит гурманов - Nakhodka.Media](https://nakhodka.media/news/1343925/) — ok.
- Хабаровск: [В Хабаровском крае впервые провели гастроужин посреди тайги | Телеканал "ХАБАРОВСК"](https://khabarovsktv.ru/news/v-habarovskom-krae-vpervye-proveli-gastrouzhin-posredi-taygi) — ok.
- Петрозаводск: [Что попробовать в Карелии: карельская кухня в Петрозаводске — Поехали](https://poehalitur.ru/sovety/chto-poprobovat-kareliya) — ok.
- Петрозаводск: [Автопрогулка, набережная, карельские специалитеты: что посмотреть и где поесть в Петрозаводске](https://vezet.ru/blog/chto-posmotret-i-gde-poest-v-petrozavodske) — ok.
- Петрозаводск: [https://openkitchen.eda.yandex/article/places/cities/luchshie-restorany-i-kafe-petrozavodska-s-karelskoy-kuhney-i-ne-tolko](https://openkitchen.eda.yandex/article/places/cities/luchshie-restorany-i-kafe-petrozavodska-s-karelskoy-kuhney-i-ne-tolko) — error.