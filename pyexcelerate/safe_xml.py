from xml.sax.saxutils import escape


def _replacement_dictionary():
    control_codepoints = range(32)
    control_codepoints.remove(9)
    control_codepoints.remove(10)
    control_codepoints.remove(13)
    for char in u'\t\r\n ':
        assert ord(char) not in control_codepoints
    return {point: u'\ufffd' for point in control_codepoints}

TRANS_DICT = _replacement_dictionary()


def replace_invalid_xml_chars(s):
    """http://www.w3.org/TR/REC-xml/#charsets implies that characters < 0x20
       may not be part of XML 1.0 spec (except that 0x09 0x0A 0x0D [tab, CR, LF] are allowed).
       It's slightly ambiguous.
       Excel definitely hates them in XLSX documents, and replaces them with
       _x00nn_; escaping literal versions of that by including _x005F_
       (an encoded underscore). LibreOffice doesn't understand these.
       Therefore, we replace these forbidden characters with U+FFFD.
       We also call escape, to convert & < > to &amp; &lt; &gt;
       https://github.com/scraperwiki/spreadsheet-download-tool/issues/67"""
    s = unicode(s)  # this may fail.
    return escape(s.translate(TRANS_DICT))


def test_replace_invalid_xml_chars():
    r = replace_invalid_xml_chars
    assert r(u'dog\x03cat') == u'dog\ufffdcat'
    assert r(u'<&>') == u'&lt;&amp;&gt;'
    assert r(u'\t\r\n ') == u'\t\r\n '
