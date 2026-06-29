"""Translate CAD text entities to Chinese."""

from typing import List, Optional
import re


class TextTranslator:
    """Auto-translate non-Chinese text to Chinese using deep-translator."""

    def __init__(self):
        self._translator = None

    def _get_translator(self):
        if self._translator is None:
            try:
                from deep_translator import GoogleTranslator
                self._translator = GoogleTranslator(source='auto', target='zh-CN')
            except Exception:
                self._translator = False
        return self._translator if self._translator is not False else None

    def translate(self, text: str) -> str:
        """Translate text to Chinese if it contains non-Chinese characters."""
        if not text or self._is_chinese(text):
            return text

        t = self._get_translator()
        if t is None:
            return text  # network unavailable, skip

        try:
            # split long text into chunks for translation
            if len(text) > 500:
                result = t.translate(text)
            else:
                result = t.translate(text)
            return result if result else text
        except Exception:
            return text  # translation failed, return original

    def translate_batch(self, texts: List[str]) -> List[str]:
        """Translate multiple texts efficiently."""
        return [self.translate(t) for t in texts]

    def _is_chinese(self, text: str) -> bool:
        """Check if text is predominantly Chinese."""
        if not text.strip():
            return True
        chinese_chars = len(re.findall(r'[一-鿿]', text))
        total_chars = len(re.sub(r'\s', '', text))
        if total_chars == 0:
            return True
        return chinese_chars / total_chars > 0.5
