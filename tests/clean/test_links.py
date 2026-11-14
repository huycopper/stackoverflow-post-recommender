import pytest

pytest.importorskip("pyspark")

from so_recommender.clean.normalize import (  # noqa: E402
    _parse_body,
    _parse_comment,
    remove_duplicate_banner,
    replace_so_links,
)


def test_links_to_other_questions_and_answers_become_a_placeholder():
    assert (
        replace_so_links(
            'Also, related: <a href="https://stackoverflow.com/questions/13187778/convert">'
            "Convert pandas dataframe to NumPy array</a>"
        )
        == "Also, related: [link]"
    )
    assert replace_so_links('See <a href="/a/17087427/2327379">this</a>.') == "See [link]."
    assert replace_so_links('<a href="//stackoverflow.com/q/1">x</a>') == "[link]"
    assert replace_so_links("check stackoverflow.com/questions/20250771/foo") == "check [link]"


def test_links_to_other_stack_exchange_sites_are_replaced_too():
    meta = '<a href="https://meta.stackoverflow.com/questions/1/x">How to ask</a>'
    assert replace_so_links(meta) == "[link]"
    assert replace_so_links("see meta.stackoverflow.com/questions/334822") == "see [link]"
    assert replace_so_links("superuser.com/q/12 and math.stackexchange.com/a/5") == (
        "[link] and [link]"
    )


def test_other_links_are_kept():
    docs = '<a href="https://docs.python.org/3/library/re.html">re docs</a>'
    help_page = '<a href="/help/how-to-ask">How to Ask</a>'
    assert replace_so_links(docs) == docs
    assert replace_so_links(help_page) == help_page
    assert replace_so_links("github.com/amoffat/sh") == "github.com/amoffat/sh"
    assert replace_so_links(None) is None


def test_comment_text_keeps_the_rest_of_the_comment():
    body = 'Look here: <a href="/questions/5/any-way">Any way to clear IDLE?</a> &amp; retry'
    assert _parse_comment(body) == "Look here: [link] & retry"


def test_wrap_marks_are_removed_and_split_urls_are_caught():
    assert _parse_comment("drop all duplic&#8204;&#8203;ate rows") == "drop all duplicate rows"
    body = "help: https://stackoverflow.<wbr>com/questions/3724551/python-uniquenes&#8204;&#8203;s"
    assert _parse_comment(body) == "help: [link]"


def test_body_links_are_replaced_in_the_text_but_not_in_the_code():
    body = (
        '<p>I read <a href="/questions/38987/merge">How do I merge two dictionaries?</a> '
        "and stackoverflow.com/q/1 but it fails:</p>"
        '<pre><code>url = "https://stackoverflow.com/questions/1"\n</code></pre>'
    )
    parsed = _parse_body(body)
    assert parsed["text"] == "I read [link] and [link] but it fails:"
    assert parsed["code"] == ['url = "https://stackoverflow.com/questions/1"']


def test_the_old_duplicate_box_is_removed_from_the_top_of_a_body():
    body = (
        "<blockquote>\n  <p><strong>Possible Duplicate:</strong><br>\n"
        '  <a href="https://stackoverflow.com/questions/49146/exe">How can I make an EXE file?</a>'
        "  </p>\n</blockquote>\n\n<p>I am new to Python.</p>"
    )
    assert _parse_body(body)["text"] == "I am new to Python."


def test_sentences_the_author_wrote_about_duplicates_are_kept():
    body = (
        "<p>I want X.</p><p>Edit: I don't think this is a possible duplicate of "
        '<a href="/questions/1/y">Y</a>.</p>'
    )
    assert remove_duplicate_banner(body) == body
    assert _parse_body(body)["text"] == (
        "I want X.\nEdit: I don't think this is a possible duplicate of [link]."
    )
