#!/usr/bin/env python3
"""Basic readability checker for Markdown files."""
from __future__ import annotations

import re
import sys
from pathlib import Path

VOWELS = "aeiouy"


def count_syllables(word: str) -> int:
    w = word.lower()
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    syllables = 0
    prev_is_vowel = False
    for ch in w:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_is_vowel:
            syllables += 1
        prev_is_vowel = is_vowel
    if w.endswith("e") and syllables > 1:
        syllables -= 1
    return max(1, syllables)


def flesch_reading_ease(words: int, sentences: int, syllables: int) -> float:
    if sentences == 0 or words == 0:
        return 0.0
    return 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)


def analyze(text: str) -> tuple[float, int, int, int]:
    sentence_regex = re.compile(r"(?<=[.!?])\s+")
    sentences = [s.strip() for s in sentence_regex.split(text) if s.strip()]
    sentence_count = len(sentences)
    words = 0
    syllables = 0
    long_sentences = 0
    word_regex = re.compile(r"[A-Za-z']+")
    for sentence in sentences:
        sentence_words = word_regex.findall(sentence)
        word_count = len(sentence_words)
        if word_count > 22:
            long_sentences += 1
        words += word_count
        for word in sentence_words:
            syllables += count_syllables(word)
    fre = flesch_reading_ease(words, sentence_count, syllables)
    return fre, long_sentences, words, sentence_count


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: readability_check.py <file>", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    fre, long_sentences, words, sentence_count = analyze(text)
    print(f"Flesch Reading Ease: {fre:.2f}")
    print(f"Total sentences: {sentence_count}")
    print(f"Sentences > 22 words: {long_sentences}")
    print(f"Total words: {words}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
