"""Built-in parsers and the parser router."""

from __future__ import annotations

from locus_engine.parsers.csv_parser import CsvParser
from locus_engine.parsers.html import HtmlParser
from locus_engine.parsers.records import RecordsParser
from locus_engine.parsers.router import ParserRouter

__all__ = ["CsvParser", "HtmlParser", "RecordsParser", "ParserRouter"]
