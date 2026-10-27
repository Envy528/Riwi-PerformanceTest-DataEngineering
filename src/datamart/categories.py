"""Product category assignment based on keyword rules."""

import re
from pathlib import Path

import pandas as pd

# Specific categories are checked before the generic "Home" one.
CATEGORY_PRIORITY = ["Electronics", "Stationery", "Clothing", "Sports", "Home"]
DEFAULT_CATEGORY = "Other"


def load_keyword_patterns(path: Path) -> dict[str, re.Pattern]:
    """Build one regex per category that matches whole words and their plurals."""
    keywords = pd.read_csv(path)
    patterns = {}
    for category in CATEGORY_PRIORITY:
        words = keywords.loc[keywords["category"] == category, "keyword"]
        alternatives = "|".join(re.escape(word) for word in words)
        patterns[category] = re.compile(rf"(?<![A-Z])(?:{alternatives})(?:S|ES)?(?![A-Z])")
    return patterns


def classify(description: str, patterns: dict[str, re.Pattern]) -> str:
    """Return the first category whose keywords appear in the description."""
    for category in CATEGORY_PRIORITY:
        if patterns[category].search(description):
            return category
    return DEFAULT_CATEGORY
