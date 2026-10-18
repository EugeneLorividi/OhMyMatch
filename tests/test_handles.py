from app.handles import ADJECTIVES, NOUNS, generate_handle, is_generated_handle


def test_generated_handles_are_valid():
    for _ in range(200):
        assert is_generated_handle(generate_handle())


def test_word_lists_have_no_duplicates():
    assert len(set(ADJECTIVES)) == len(ADJECTIVES)
    assert len(set(NOUNS)) == len(NOUNS)


def test_free_text_is_rejected():
    for value in [
        "",
        "anna-smith-42",
        "quiet-otter",
        "quiet-otter-9",
        "quiet-otter-100",
        "Quiet-Otter-42",
        "quiet-otter-42 ",
        "quiet-otter-42<script>",
    ]:
        assert not is_generated_handle(value), value
