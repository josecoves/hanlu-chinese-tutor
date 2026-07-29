import jieba

_ADDED_WORDS: set[str] = set()


def segment(text: str, lexicon=()) -> list[str]:
    new_words = set(lexicon) - _ADDED_WORDS
    for word in new_words:
        jieba.add_word(word)
    _ADDED_WORDS.update(new_words)
    return [token for token in jieba.lcut(text) if token.strip()]
