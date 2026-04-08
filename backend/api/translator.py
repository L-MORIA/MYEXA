from google.cloud import translate_v2
import os

class Translator:
    def __init__(self):
        # Using Google Translate API (free tier available)
        # Alternative: use free API like LibreTranslate
        self.client = None
        self.use_free_api = True
    
    def translate(self, text: str, target_language: str) -> str:
        """Translate text to target language"""
        if self.use_free_api:
            return self._translate_free(text, target_language)
        else:
            return self._translate_google(text, target_language)
    
    def _translate_free(self, text: str, target_language: str) -> str:
        """Use free translation API (LibreTranslate)"""
        import requests
        
        lang_map = {
            "en": "en",
            "de": "de",
            "it": "it"
        }
        
        try:
            response = requests.post(
                "https://libretranslate.de/translate",
                json={
                    "q": text,
                    "source": "auto",
                    "target": lang_map.get(target_language, "en")
                },
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("translatedText", text)
        except Exception as e:
            print(f"Translation error: {e}")
        
        return text
    
    def _translate_google(self, text: str, target_language: str) -> str:
        """Use Google Translate API"""
        if not self.client:
            self.client = translate_v2.Client()
        
        try:
            result = self.client.translate_text(
                text,
                target_language=target_language
            )
            return result["translatedText"]
        except Exception as e:
            print(f"Google Translate error: {e}")
            return text
    
    def translate_to_multiple(self, text: str, languages: list) -> dict:
        """Translate text to multiple languages"""
        results = {"original": text}
        for lang in languages:
            results[lang] = self.translate(text, lang)
        return results
