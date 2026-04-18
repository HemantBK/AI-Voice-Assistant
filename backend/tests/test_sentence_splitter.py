from app.streaming.sentence_splitter import (
    IncrementalSentenceSplitter,
    split_sentences,
)


def test_split_sentences_basic():
    assert split_sentences("Hello world. How are you? I am fine!") == [
        "Hello world.",
        "How are you?",
        "I am fine!",
    ]


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_split_sentences_no_boundary():
    text = "This is a long sentence without punctuation"
    assert split_sentences(text) == [text]


def test_split_sentences_short_merge():
    # Both are < 8 chars — second merges into first.
    assert split_sentences("Hi. Bye.") == ["Hi. Bye."]


def test_incremental_streams_on_boundary():
    s = IncrementalSentenceSplitter()
    out = []
    for tok in ["Hello", " world", ". ", "How are", " you", "?", " tail"]:
        out.extend(s.push(tok))
    out.extend(s.flush())
    assert out == ["Hello world.", "How are you?", "tail"]


def test_incremental_no_boundary_flush():
    s = IncrementalSentenceSplitter()
    out = list(s.push("just words")) + list(s.flush())
    assert out == ["just words"]
