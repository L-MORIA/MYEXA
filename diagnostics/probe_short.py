from lingua import Language, LanguageDetectorBuilder
S = {Language.RUSSIAN:"ru", Language.ENGLISH:"en", Language.GERMAN:"de", Language.ITALIAN:"it"}
for label, b in [("restricted low", LanguageDetectorBuilder.from_languages(*S.keys()).with_low_accuracy_mode()),
                 ("restricted high", LanguageDetectorBuilder.from_languages(*S.keys()))]:
    d = b.build()
    print(f"--- {label} ---")
    samples = [
        ("artificial intelligence in medicine", "en"),
        ("Искусственный интеллект в медицине", "ru"),
        ("Künstliche Intelligenz in der Medizin", "de"),
        ("intelligenza artificiale in medicina", "it"),
        ("Clinicians Report on LLM Use in Everyday Practice", "en"),
        ("ИИ в медицине: диагностика по снимкам", "ru"),
        ("Machine Learning", "en"),
        ("Регулирование медицинского ИИ в ЕС и США", "ru"),
        ("Deep Learning for Early Cancer Detection", "en"),
    ]
    hits = 0
    for text, want in samples:
        det = d.detect_language_of(text)
        got = S.get(det, "none")
        hits += got == want
        print(f"  {'OK ' if got==want else 'BAD'} got={got:<5} want={want:<3} {text[:46]}")
    print(f"  accuracy: {hits}/{len(samples)}")
