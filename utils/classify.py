"""
Thread‑safe random action selector — no repeats until all 20 IDs are used.

* Maintains an internal bag of action IDs 1‑20.
* Each call pops one ID; when bag is empty it refills with a new random shuffle.
* Lock ensures parallel threads never get the same ID.
* The incoming `doc` parameter is ignored (kept for API compatibility).
"""

import random
import threading
from typing import Tuple

TOTAL_ACTIONS = 20
__all__ = ["classify_sentence_structure"]

_pool: list[int] = []              # remaining unique IDs
_lock = threading.Lock()

def _next_action_id() -> int:
    """Return a unique action ID, thread‑safe."""
    global _pool
    with _lock:
        if not _pool:
            _pool = random.sample(range(1, TOTAL_ACTIONS + 1), TOTAL_ACTIONS)
        return _pool.pop()

def classify_sentence_structure(doc) -> Tuple[int, str]:
    """Public API used by pipeline and CLI."""
    return _next_action_id(), "N/A"

# def classify_sentence_structure(doc):
#     components = set()
#     for sentence in doc.sentences:
#         for word in sentence.words:
#             if word.deprel == "nsubj":
#                 components.add("Subject")
#             elif word.deprel == "root":
#                 components.add("Predicate")
#             elif word.deprel in {"obj", "iobj"}:
#                 components.add("Object")
#             elif word.deprel in {"obl", "advmod"}:
#                 components.add("Circumstance")
#             elif word.deprel in {"amod", "compound"}:
#                 components.add("Attributive")
#
#     classification = classify_by_coverage(components)
#     structure_coverage = "-".join(sorted(components))
#     return classification, structure_coverage
#
# def classify_by_coverage(components):
#     classifications = {
#         frozenset(["Subject"]): 1,
#         frozenset(["Subject", "Predicate"]): 2,
#         frozenset(["Subject", "Predicate", "Object"]): 3,
#         frozenset(["Subject", "Predicate", "Circumstance"]): 4,
#         frozenset(["Subject", "Predicate", "Object", "Circumstance"]): 5,
#         frozenset(["Subject", "Circumstance", "Object", "Predicate"]): 6,
#         frozenset(["Subject", "Attributive", "Object", "Predicate"]): 7,
#         frozenset(["Object", "Attributive", "Subject", "Predicate"]): 8,
#         frozenset(["Object", "Circumstance", "Subject", "Predicate"]): 9,
#         frozenset(["Object", "Subject", "Circumstance", "Predicate"]): 10,
#         frozenset(["Circumstance", "Subject", "Object", "Predicate"]): 11,
#         frozenset(["Attributive", "Subject", "Object", "Predicate"]): 12,
#         frozenset(["Attributive", "Subject", "Circumstance", "Predicate"]): 13,
#         frozenset(["Subject", "Circumstance", "Attributive", "Object", "Predicate"]): 14,
#         frozenset(["Subject", "Attributive", "Object", "Circumstance", "Predicate"]): 15,
#         frozenset(["Circumstance", "Subject", "Attributive", "Object", "Predicate"]): 16,
#         frozenset(["Circumstance", "Object", "Attributive", "Subject", "Predicate"]): 17,
#         frozenset(["Attributive", "Subject", "Circumstance", "Object", "Predicate"]): 18,
#         frozenset(["Attributive", "Subject", "Object", "Circumstance", "Predicate"]): 19,
#         frozenset(["Attributive", "Object", "Subject", "Circumstance", "Predicate"]): 20,
#     }
#     return classifications.get(frozenset(components), 1)
