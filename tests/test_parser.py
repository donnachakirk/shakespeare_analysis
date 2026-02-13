from shakespeare_geo.parser import (
    extract_sentence_for_span,
    find_span_for_text,
    index_text_lines,
)


def test_find_span_for_text_respects_search_cursor():
    text = "Verona then Mantua then Verona again."

    start1, end1, cursor = find_span_for_text(text, "Verona")
    start2, end2, _ = find_span_for_text(text, "Verona", start_at=cursor)

    assert text[start1:end1] == "Verona"
    assert text[start2:end2] == "Verona"
    assert start2 > start1


def test_extract_sentence_for_span_handles_line_and_punctuation_boundaries():
    text = "In fair Verona, where we lay our scene.\nFrom Mantua comes a letter.\n"

    start_verona = text.find("Verona")
    start_mantua = text.find("Mantua")

    assert (
        extract_sentence_for_span(text, start_verona, start_verona + len("Verona"))
        == "In fair Verona, where we lay our scene"
    )
    assert (
        extract_sentence_for_span(text, start_mantua, start_mantua + len("Mantua"))
        == "From Mantua comes a letter"
    )


def test_index_text_lines_marks_dialogue_only_for_spoken_lines():
    text = (
        "Contents\nCHORUS.\nIn fair Verona.\n"
        "THE PROLOGUE\nCHORUS.\nIn fair Verona, where we lay our scene,\n"
        "ACT I\nSCENE I. Verona.\nROMEO.\nTo Mantua I go.\n Enter BENVOLIO.\n"
    )
    contexts = index_text_lines(text)

    by_text = {ctx.text: ctx for ctx in contexts}
    assert by_text["In fair Verona."].is_dialogue is False
    assert by_text["THE PROLOGUE"].act == "PROLOGUE"
    assert by_text["In fair Verona, where we lay our scene,"].scene == "PROLOGUE"
    assert by_text["SCENE I. Verona."].is_dialogue is False
    assert by_text["ROMEO."].is_dialogue is False
    assert by_text["To Mantua I go."].is_dialogue is True
    assert by_text[" Enter BENVOLIO."].is_dialogue is False
