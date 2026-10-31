from so_recommender.clean.htmltext import collapse_lines, html_to_text, plain_text


def test_code_blocks_are_split_from_the_text():
    body = (
        "<p>I'm trying to merge two dictionaries:</p>\n"
        '<pre class="lang-py"><code>x = {&#39;a&#39;: 1}\ny = {&#39;b&#39;: 2}\n</code></pre>\n'
        "<p>Is there a <code>dict</code> method &amp; a one-liner?</p>"
    )
    text, code = html_to_text(body)
    assert text == "I'm trying to merge two dictionaries:\nIs there a dict method & a one-liner?"
    assert code == ["x = {'a': 1}\ny = {'b': 2}"]


def test_block_tags_become_lines_and_links_keep_their_text():
    text, code = html_to_text(
        "<h2>Answer</h2><ul><li>one</li><li>two <a href='/q/1'>link</a></li></ul>line<br>next"
    )
    assert text == "Answer\none\ntwo link\nline\nnext"
    assert code == []


def test_empty_code_blocks_are_dropped_and_unclosed_pre_is_kept():
    assert html_to_text("<pre><code>   \n</code></pre><p>hi</p>") == ("hi", [])
    assert html_to_text("<p>see</p><pre><code>print(1)") == ("see", ["print(1)"])


def test_none_stays_none():
    assert html_to_text(None) is None
    assert plain_text(None) is None


def test_plain_text_decodes_entities_and_collapses_whitespace():
    assert plain_text("  What does the &quot;yield&quot;\n keyword do?  ") == (
        'What does the "yield" keyword do?'
    )
    assert plain_text("Tom&#39;s  &amp;  Jerry") == "Tom's & Jerry"


def test_collapse_lines():
    assert collapse_lines("  a   b \n\n\t c  \r\n") == "a b\nc"
