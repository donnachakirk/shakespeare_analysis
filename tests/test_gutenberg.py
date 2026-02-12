from shakespeare_geo.gutenberg import strip_gutenberg_header_footer


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
