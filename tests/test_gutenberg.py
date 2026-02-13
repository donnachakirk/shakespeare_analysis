from shakespeare_geo.gutenberg import strip_gutenberg_header_footer, trim_play_front_matter


def test_strip_gutenberg_header_footer_extracts_body():
    text = """Header line
*** START OF THE PROJECT GUTENBERG EBOOK ROMEO AND JULIET ***
BODY LINE 1
BODY LINE 2
*** END OF THE PROJECT GUTENBERG EBOOK ROMEO AND JULIET ***
Footer line
"""

    assert strip_gutenberg_header_footer(text) == "BODY LINE 1\nBODY LINE 2"


def test_strip_gutenberg_header_footer_no_markers_returns_original():
    text = "No markers here"
    assert strip_gutenberg_header_footer(text) == text


def test_trim_play_front_matter_starts_after_dramatis():
    text = """Contents
ACT I
Scene I.

Dramatis Personae
ROMEO

THE PROLOGUE
CHORUS.
In fair Verona, where we lay our scene,
"""
    trimmed = trim_play_front_matter(text)
    assert trimmed.startswith("THE PROLOGUE")


def test_trim_play_front_matter_uses_second_act_i_when_contents_present():
    text = """Contents
ACT I
Scene I.

ACT I
SCENE I. A public place.
ROMEO.
Verona.
"""
    trimmed = trim_play_front_matter(text)
    assert trimmed.startswith("ACT I\nSCENE I. A public place.")
