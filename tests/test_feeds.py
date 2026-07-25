from farewatch.feeds import _parse_entries

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>Example Deals</title>
  <item>
    <title>United: Newark - Kauai $444 Roundtrip</title>
    <link>https://example.com/deal-1</link>
  </item>
  <item>
    <title>Delta: Atlanta - Paris $650 Roundtrip</title>
    <link>https://example.com/deal-2</link>
  </item>
</channel>
</rss>
"""

ATOM_SAMPLE = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom Deals</title>
  <entry>
    <title>Business Class: New York to London $1735</title>
    <link href="https://example.com/atom-deal-1"/>
  </entry>
</feed>
"""


def test_parses_rss_items():
    entries = list(_parse_entries(RSS_SAMPLE))
    assert entries == [
        ("United: Newark - Kauai $444 Roundtrip", "https://example.com/deal-1"),
        ("Delta: Atlanta - Paris $650 Roundtrip", "https://example.com/deal-2"),
    ]


def test_parses_atom_entries():
    entries = list(_parse_entries(ATOM_SAMPLE))
    assert entries == [
        ("Business Class: New York to London $1735", "https://example.com/atom-deal-1"),
    ]
