"""Labelled relevance corpus shared by the tests and the diagnostics.

Each item is a realistic stand-in for an Exa result: a title plus a
`highlights` body. The highlights deliberately contain the query phrase in the
BODY of the irrelevant items — that mirrors reality, because Exa builds
`highlights` by selecting passages that match the query, so an off-topic page
can still quote the query back. Scoring such a blob against the query is
therefore close to tautological, which is exactly the failure mode the filter
must survive.

`relevant` is the label a human would assign to the item.
"""

CORPUS = {
    "ru": {
        "query": "искусственный интеллект в медицине",
        "items": [
            {
                "title": "ИИ в медицине: диагностика по снимкам",
                "relevant": True,
                "highlights": (
                    "Искусственный интеллект в медицине уже сегодня используется для анализа "
                    "медицинских снимков: нейросети обучаются на размеченных наборах данных и "
                    "выделяют патологии, которые не всегда замечает врач. В кардиологии "
                    "алгоритмы помогают оценивать риск инфаркта по данным ЭКГ, в офтальмологии "
                    "— выявлять диабетическую ретинопатию на снимках глазного дна. Ключевое "
                    "ограничение — необходимость валидации на локальных данных клиники, "
                    "поскольку модель, обученная на одной популяции пациентов, может работать "
                    "хуже на другой. Крупные фармкомпании уже инвестируют в платформы "
                    "анализа медицинских данных. Отдельный вызов — объяснимость: врач должен "
                    "понимать, почему система поставила тот или иной диагноз, иначе клиническая "
                    "польза остаётся ограниченной."
                ),
            },
            {
                "title": "Машинное обучение в диагностике рака",
                "relevant": True,
                "highlights": (
                    "Ранняя диагностика онкологических заболеваний — область, где искусственный "
                    "интеллект в медицине даёт наибольший эффект. Алгоритмы глубокого обучения "
                    "анализируют гистологические снимки и выделяют зоны с атипичной структурой, "
                    "что сокращает время, необходимое патологу на первичный просмотр. По данным "
                    "исследований, внедрение таких систем в клиническую практику снижает "
                    "количество диагностических ошибок на десятки процентов. Важно, что система "
                    "работает как система второго мнения: окончательное решение остаётся за "
                    "врачом, а модель лишь ранжирует и подсвечивает подозрительные участки."
                ),
            },
            {
                "title": "ChatGPT в клинической практике: что говорят врачи",
                "relevant": True,
                "highlights": (
                    "Опрос двух тысяч врачей показал, что около четверти используют генеративные "
                    "модели для подготовки к приёму пациентов. Искусственный интеллект в медицине "
                    "в этом сценарии работает как справочный инструмент: черновик письма, "
                    "структурирование истории болезни, расшифровка результатов анализов. "
                    "Одновременно врачи отмечают риски — модель может «уверенно» выдумывать "
                    "несуществующие ссылки на исследования и рекомендовать препараты, не "
                    "содержащиеся в актуальных клинических рекомендациях."
                ),
            },
            {
                "title": "Регулирование медицинского ИИ в ЕС и США",
                "relevant": True,
                "highlights": (
                    "Регуляторы разных стран подходят к медицинским алгоритмам по-разному: "
                    "американский FDA использует предопределённый набор критериев и "
                    "предварительно согласовывает план клинических испытаний, европейский "
                    "CE-центр — подход с более жёсткими требованиями к клинической "
                    "доказательной базе и прозрачности. Отдельная сложность — обновление моделей: "
                    "любая дообучка после сертификации требует повторной валидации. Общий тренд — "
                    "переход от регулирования как такового к регулированию на основе "
                    "непрерывного мониторинга качества в клинике."
                ),
            },
            {
                "title": "Нейросети в анализе электрокардиограмм",
                "relevant": True,
                "highlights": (
                    "Алгоритмы анализа ЭКГ на основе свёрточных нейронных сетей показали "
                    "способность выявлять фибрилляцию предсердий и ишемию с чувствительностью, "
                    "превышающей врачебную оценку на эталонных наборах. В исследовании на "
                    "более чем ста тысячах записей ЭКГ алгоритм показал снижение количества "
                    "пропущенных нарушений ритма по сравнению с ручной расшифровкой. "
                    "Ограничение остаётся прежним: обобщающая способность зависит от "
                    "представительности обучающей выборки и оборудования, на котором "
                    "регистрировалась кардиограмма."
                ),
            },
            {
                "title": "Стоматология и телемедицина: цифровые диагностические кабинеты",
                "relevant": True,
                "highlights": (
                    "Телемедицинские кабинеты с компьютерным зрением расширяют доступ к "
                    "диагностике в отдалённых регионах. Программное обеспечение анализирует "
                    "рентгенологические снимки и фотографии, предварительно оценивая состояние "
                    "тканей. Такие системы не заменяют врача, но позволяют оператору "
                    "первичного звонка принять решение о необходимости очного осмотра."
                ),
            },
            {
                "title": "Кулинарные рецепты с тыквой на Хэллоуин",
                "relevant": False,
                "highlights": (
                    "Тыква — универсальный продукт осеннего сезона. Для многих читателей "
                    "искусственный интеллект в медицине давно перестал быть просто темой "
                    "научных публикаций и превратился в инструмент, который можно применять "
                    "для самых разных задач. Например, при выборе продуктов для ужина "
                    "приложения подсказывают, какие специи сочетаются с тыквой, а "
                    "кулинарные блогеры публикуют десятки вариантов запекания. Главное — "
                    "использовать проверенные рецепты и учитывать собственные предпочтения, "
                    "потому что вкусы у всех разные."
                ),
            },
            {
                "title": "Обзор смартфонов среднего класса",
                "relevant": False,
                "highlights": (
                    "В этом году рынок смартфонов среднего класса заметно наполнился "
                    "моделями с хорошей камерой и аккумулятором на два дня. Некоторые "
                    "производители начали добавлять функции, где искусственный интеллект в "
                    "медицине используется как маркетинговый ярлык — улучшение фотографий, "
                    "подбор текста для заметок, прогноз энергопотребления. На практике "
                    "такие функции едва заметны в повседневном использовании, зато заметно "
                    "удорожают устройство."
                ),
            },
            {
                "title": "Городские велосипедные маршруты",
                "relevant": False,
                "highlights": (
                    "Велосипедные маршруты в крупных городах становятся длиннее с каждым годом. "
                    "Планировщики всё чаще используют данные телеметрии, где искусственный "
                    "интеллект в медицине служит лишь примером того, как подобные системы "
                    "работают на больших объёмах данных. Для самих велосипедистов главным "
                    "остаётся наличие велодорожек и освещённых участков на всём пути."
                ),
            },
            {
                "title": "Как выбрать кофемолку для дома",
                "relevant": False,
                "highlights": (
                    "Выбор кофемолки зависит от того, какой кофе вы предпочитаете. Для эспрессо "
                    "нужны жернова, для фильтр-кофе — подойдёт и более простая конструкция. "
                    "Словосочетание «искусственный интеллект в медицине» в рекламных "
                    "материалах этого сегмента не встречается, но именно такие точные "
                    "характеристики и помогают сделать выбор осмысленным."
                ),
            },
        ],
    },
    "en": {
        "query": "artificial intelligence in medicine",
        "items": [
            {
                "title": "AI in Medicine: How Machine Learning Is Changing Diagnostics",
                "relevant": True,
                "highlights": (
                    "Artificial intelligence in medicine has moved from research labs into "
                    "routine clinical practice. Machine learning models trained on large "
                    "annotated datasets now detect pathology in medical images with accuracy "
                    "that frequently matches or exceeds experienced radiologists. Cardiology "
                    "applications assess myocardial infarction risk from ECG traces, while "
                    "ophthalmology systems screen fundus photographs for diabetic retinopathy. "
                    "The central caveat is generalisation: a model trained on one patient "
                    "population frequently performs worse on another, so every deployment "
                    "requires local validation. Pharmaceutical companies have invested heavily "
                    "in platforms that curate clinical data for model training, and regulators "
                    "in both Europe and the United States have published dedicated guidance "
                    "for machine-learning-based medical devices."
                ),
            },
            {
                "title": "Deep Learning for Early Cancer Detection",
                "relevant": True,
                "highlights": (
                    "Early cancer detection is where artificial intelligence in medicine has "
                    "produced the largest measured benefit. Deep learning systems analyse "
                    "histopathology slides and highlight regions with atypical structure, "
                    "reducing the time a pathologist spends on primary review. Studies across "
                    "several institutions report substantial reductions in diagnostic error "
                    "rates after deployment. These systems work as a second opinion: the "
                    "clinician remains responsible for the final diagnosis, while the model "
                    "ranks and flags suspicious areas so that attention is directed efficiently."
                ),
            },
            {
                "title": "Clinicians Report on LLM Use in Everyday Practice",
                "relevant": True,
                "highlights": (
                    "A survey of two thousand physicians found that roughly a quarter now use "
                    "generative models to prepare for patient encounters. Artificial "
                    "intelligence in medicine in this scenario functions as a reference tool: "
                    "drafting letters, structuring the medical history, and summarising lab "
                    "results. Doctors also report clear risks, noting that models will "
                    "confidently cite studies that do not exist and may recommend "
                    "medications absent from current clinical guidelines."
                ),
            },
            {
                "title": "Regulating Clinical AI Across Jurisdictions",
                "relevant": True,
                "highlights": (
                    "Regulators take different approaches to medical algorithms. The American "
                    "FDA applies a predetermined set of criteria and pre-agrees the clinical "
                    "trial plan, while the European CE process demands stronger clinical "
                    "evidence and transparency. Model updates create a distinct difficulty: "
                    "any retraining after certification requires revalidation. The broader "
                    "trend moves away from approving software once towards continuous "
                    "post-market monitoring of quality inside the clinic."
                ),
            },
            {
                "title": "Neural Networks for ECG Interpretation",
                "relevant": True,
                "highlights": (
                    "Convolutional network algorithms for ECG analysis have demonstrated the "
                    "ability to identify atrial fibrillation and ischaemia with sensitivity "
                    "that exceeds clinician review on benchmark datasets. In a trial covering "
                    "more than a hundred thousand ECG recordings, the algorithm reduced the "
                    "number of missed rhythm abnormalities compared with manual "
                    "interpretation. Generalisation still depends on how representative the "
                    "training population is and on the equipment used for recording."
                ),
            },
            {
                "title": "Pumpkin Recipes for Autumn",
                "relevant": False,
                "highlights": (
                    "Pumpkin is the defining ingredient of the autumn season. For many readers "
                    "artificial intelligence in medicine has long since stopped being merely a "
                    "topic in scientific publications and become a tool applied to all sorts of "
                    "practical problems. Recipe applications suggest which spices pair with "
                    "pumpkin, and food bloggers publish dozens of roasting variations. The "
                    "important thing is to use tested recipes and account for personal taste, "
                    "because preferences differ widely."
                ),
            },
            {
                "title": "Mid-Range Smartphone Reviews",
                "relevant": False,
                "highlights": (
                    "The mid-range smartphone market has filled with models offering capable "
                    "cameras and two-day battery life. Manufacturers increasingly add features "
                    "where artificial intelligence in medicine serves as a marketing label — "
                    "photo enhancement, note summarisation, power forecasting. In daily use "
                    "these features are barely noticeable, yet they measurably raise the price "
                    "of the device."
                ),
            },
            {
                "title": "Urban Cycling Routes Compared",
                "relevant": False,
                "highlights": (
                    "Cycling routes in large cities grow longer every year. Planners increasingly "
                    "use telemetry data, and artificial intelligence in medicine serves as a "
                    "frequent example of how similar systems handle very large datasets. For "
                    "riders themselves the essentials remain bike lanes and lit sections along "
                    "the whole route."
                ),
            },
        ],
    },
    "de": {
        "query": "Künstliche Intelligenz in der Medizin",
        "items": [
            {
                "title": "KI in der Medizin: Diagnose per Bildgebung",
                "relevant": True,
                "highlights": (
                    "Künstliche Intelligenz in der Medizin wird heute routinely eingesetzt, um "
                    "medizinische Bilder zu analysieren: Neuronale Netze werden auf annotierten "
                    "Datensätzen trainiert und erkennen Pathologien, die Ärzte nicht immer "
                    "sehen. In der Kardiologie helfen Algorithmen, das Risiko eines Herzinfarkts "
                    "aus EKG-Daten abzuschätzen, in der Augenheilkunde wird diabetische "
                    "Retinopathie auf Fundusbildern erkannt. Die zentrale Einschränkung ist die "
                    "Validierung mit lokalen Daten der jeweiligen Klinik, denn ein Modell, das "
                    "an einer Population trainiert wurde, funktioniert bei einer anderen oft "
                    "schlechter. Auch die Erklärbarkeit bleibt ein offenes Thema, da Ärzte "
                    "nachvollziehen müssen, warum das System eine Diagnose stellt."
                ),
            },
            {
                "title": "Deep Learning beim Krebsscreening",
                "relevant": True,
                "highlights": (
                    "Die frühe Krebsdiagnose ist der Bereich, in dem künstliche Intelligenz in "
                    "der Medizin den größten messbaren Nutzen bringt. Systeme des Deep Learning "
                    "analysieren histologische Schnitte und markieren Areale mit atypischer "
                    "Struktur, wodurch sich die Zeit verkürzt, die Pathologen für die "
                    "Erstbegutachtung benötigen. Solche Systeme arbeiten als Zweitmeinung: Die "
                    "endgültige Diagnose bleibt beim Arzt, während das Modell verdächtige "
                    "Bereiche priorisiert und hervorhebt."
                ),
            },
            {
                "title": "Sprachmodelle in der klinischen Praxis",
                "relevant": True,
                "highlights": (
                    "Eine Umfrage unter zweitausend Ärzten zeigt, dass etwa ein Viertel "
                    "generative Modelle zur Vorbereitung auf Patientengespräche nutzt. "
                    "Künstliche Intelligenz in der Medizin fungiert hier als Nachschlagewerkzeug: "
                    "Entwürfe für Arztbriefe, Strukturierung der Anamnese, Zusammenfassung von "
                    "Laborbefunden. zugleich berichten Ärzte von Risiken, da Modelle "
                    "zuversichtlich nicht existierende Studien zitieren."
                ),
            },
            {
                "title": "Rechtliche Anforderungen an Medizin-KI",
                "relevant": True,
                "highlights": (
                    "Die europäische CE-Zertifizierung stellt strengere Anforderungen an die "
                    "klinische Evidenz und Transparenz als das amerikanische FDA, das einen "
                    "vorab vereinbarten Prüfplan verlangt. Jede Nachschulung des Modells nach "
                    "der Zulassung erfordert eine erneute Validierung. Der allgemeine Trend "
                    "geht von der einmaligen Zulassung hin zur kontinuierlichen Überwachung der "
                    "Qualität in der Klinik."
                ),
            },
            {
                "title": "Kürbissuppe für den Herbst",
                "relevant": False,
                "highlights": (
                    "Kürbis ist das typische Herbstgemüse. Für viele Leser ist künstliche "
                    "Intelligenz in der Medizin lange kein Thema wissenschaftlicher Publikationen "
                    "mehr, sondern ein Werkzeug für ganz alltägliche Aufgaben. Rezept-Apps "
                    "schlagen passende Gewürze vor, und Kochblogs veröffentlichen Dutzende "
                    "Zubereitungen. Am wichtigsten sind erprobte Rezepte und der eigene "
                    "Geschmack, denn dieser unterscheidet sich von Mensch zu Mensch."
                ),
            },
            {
                "title": "Fahrradrouten durch die Stadt",
                "relevant": False,
                "highlights": (
                    "Fahrradrouten in Großstädten werden jedes Jahr länger. Die Planung nutzt "
                    "zunehmend Telemetriedaten, wobei künstliche Intelligenz in der Medizin "
                    "häufig als Beispiel dafür dient, wie ähnliche Systeme mit sehr großen "
                    "Datenmengen umgehen. Für Radfahrer bleiben Fahrradwege und beleuchtete "
                    "Abschnitte entscheidend."
                ),
            },
        ],
    },
    "it": {
        "query": "intelligenza artificiale in medicina",
        "items": [
            {
                "title": "IA in medicina: la diagnosi con le immagini",
                "relevant": True,
                "highlights": (
                    "L'intelligenza artificiale in medicina è ormai usata quotidianamente per "
                    "analizzare le immagini mediche: le reti neurali vengono addestrate su "
                    "insiemi di dati annotati e individuano patologie che il medico non nota "
                    "sempre. In cardiologia gli algoritmi valutano il rischio di infarto a "
                    "partire dall'ECG, in oftalmologia lo screening del fondo oculare individua "
                    "la retinopatia diabetica. Il limite principale è la validazione sui dati "
                    "locali della clinica, perché un modello addestrato su una popolazione "
                    "spesso lavora peggio su un'altra. Anche la spiegabilità resta una "
                    "sfida aperta: il medico deve capire perché il sistema ha formulato una "
                    "diagnosi."
                ),
            },
            {
                "title": "Deep learning nella diagnosi precoce dei tumori",
                "relevant": True,
                "highlights": (
                    "La diagnosi precoce dei tumori è l'ambito in cui l'intelligenza artificiale "
                    "in medicina produce il beneficio maggiore misurato. I sistemi di deep "
                    "learning analizzano i vetrini istologici ed evidenziano aree con "
                    "struttura atipica, riducendo il tempo che il patologo dedica alla prima "
                    "lettura. Questi sistemi funzionano come seconda opinione: la diagnosi "
                    "finale resta al medico, mentre il modello ordina e segnala le aree "
                    "sospette."
                ),
            },
            {
                "title": "L'uso dei modelli linguistici nella pratica clinica",
                "relevant": True,
                "highlights": (
                    "Un'indagine su duemila medici mostra che circa un quarto utilizza modelli "
                    "generativi per preparare le visite. L'intelligenza artificiale in medicina "
                    "qui funziona come strumento di consulto: bozze di lettere, strutturazione "
                    "dell'anamnesi, sintesi degli esami. I medici segnalano anche rischi "
                    "concreti: i modelli citano in modo sicuro studi inesistenti e possono "
                    "consigliare farmaci assenti dalle linee guida."
                ),
            },
            {
                "title": "Regolamentazione dell'IA clinica in Europa",
                "relevant": True,
                "highlights": (
                    "La marcatura CE europea richiede prove cliniche più rigorose e maggiore "
                    "trasparenza rispetto all'iter FDA, che impone di concordare in anticipo "
                    "il piano della sperimentazione. Ogni riaddestramento del modello dopo "
                    "l'approvazione richiede una nuova validazione. La tendenza generale va "
                    "verso una sorveglianza continua della qualità all'interno della struttura "
                    "sanitaria."
                ),
            },
            {
                "title": "Ricette con la zucca per l'autunno",
                "relevant": False,
                "highlights": (
                    "La zucca è l'ingrediente tipico dell'autunno. Per molti lettori "
                    "l'intelligenza artificiale in medicina ha smesso di essere solo un tema "
                    "di pubblicazioni scientifiche ed è diventata uno strumento per compiti "
                    "quotidiani. Le app di ricette suggeriscono le spezie più adatte e i blog "
                    "culinari pubblicano decine di varianti. L'importante è usare ricette "
                    "collaudate e tenere conto dei propri gusti."
                ),
            },
            {
                "title": "Gite in bicicletta in città",
                "relevant": False,
                "highlights": (
                    "Le piste ciclabili nelle grandi città diventano ogni anno più lunghe. "
                    "L'intelligenza artificiale in medicina viene spesso citata come esempio "
                    "di come sistemi analogi gestiscono volumi di dati molto grandi. Per i "
                    "ciclisti restano decisive le ciclabili e i tratti illuminati."
                ),
            },
        ],
    },
}
