"""Extract the labelled relevance corpus into a shared, importable module.

Run once: python diagnostics/extract_corpus.py
It rewrites backend/tests/relevance_corpus.py from the copy that currently
lives inside diagnostics/embedding_quality.py, so the corpus is defined once.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "embedding_quality.py")
DST = os.path.join(HERE, "..", "backend", "tests", "relevance_corpus.py")

with open(SRC, encoding="utf-8") as fh:
    source = fh.read()

start = source.index("CORPUS = {")
# The dict ends at the line "}" at column 0 that follows it.
end = source.index("\n}\n", start) + len("\n}\n")
block = source[start:end]

header = '''"""Labelled relevance corpus shared by the tests and the diagnostics.

Each item is a realistic stand-in for an Exa result: a title plus a body
snippet. The `blob` deliberately contains the query phrase in the BODY of the
irrelevant items — that mirrors reality, because Exa builds `highlights` by
selecting passages that match the query, so an off-topic page can still quote
the query back. Scoring such a blob against the query is therefore close to
tautological, which is exactly the failure mode the filter must survive.

`relevant` is the label a human would assign to the item.
"""

'''

with open(DST, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(header + block)

print(f"wrote {os.path.normpath(DST)} ({len(block)} bytes of corpus)")
