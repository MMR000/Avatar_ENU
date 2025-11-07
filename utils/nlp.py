# utils/nlp.py
"""
Token‑based splitter (2–10 words per segment)
--------------------------------------------
* Split text by spaces (simple tokenisation).
* When we see a punctuation token containing a sentence‑ending mark (., ，,。),
  _and_ the current buffer has ≥2 tokens, we cut the segment.
* If the buffer reaches 10 tokens without punctuation, force a cut.
* Any tail shorter than 2 tokens is appended to the previous segment to
  avoid one‑word clips.
"""

import re
import stanza
from utils.classify import classify_sentence_structure

# Download once and create the Kazakh pipeline
stanza.download("kk")
nlp = stanza.Pipeline("kk")

_PUNCT_RE = re.compile(r"[.,，。]")


def _smart_split(text: str, min_tok: int = 2, max_tok: int = 10):
    """Return a list of segments, each 2–10 tokens long."""
    tokens = text.split()
    segments = []
    buf = []

    for tok in tokens:
        buf.append(tok)
        hit_punct = bool(_PUNCT_RE.search(tok))
        over_max = len(buf) >= max_tok

        if (hit_punct and len(buf) >= min_tok) or over_max:
            segments.append(" ".join(buf))
            buf = []

    # Flush remaining tokens
    if buf:
        if len(buf) < min_tok and segments:
            # Append tail to previous segment
            segments[-1] += " " + " ".join(buf)
        else:
            segments.append(" ".join(buf))

    return segments


def parse_text(text: str):
    """Split text and attach random action IDs via classify_sentence_structure."""
    sentences = _smart_split(text)
    stanza_outputs = []

    for s in sentences:
        doc = nlp(s)
        action_id, _ = classify_sentence_structure(doc)
        stanza_outputs.append({
            "sentence": s,
            "classification": action_id,
            "structure": "N/A",
        })

    return sentences, stanza_outputs



# import stanza
# from utils.classify import classify_sentence_structure
#
# stanza.download('kk')
# nlp = stanza.Pipeline('kk')
#
# def parse_text(text):
#     sentences = [sentence.strip() + '.' for sentence in text.split('.') if sentence.strip()]
#     stanza_outputs = []
#
#     for sentence in sentences:
#         doc = nlp(sentence)
#         classification, structure_coverage = classify_sentence_structure(doc)
#
#         stanza_outputs.append({
#             'sentence': sentence,
#             'classification': classification,
#             'structure': structure_coverage
#         })
#
#     return sentences, stanza_outputs
