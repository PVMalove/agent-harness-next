# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Признаки атрибуции AI-ассистента в публичных метаданных Git.

Шаблон совпадает с `scripts/check_public_metadata.py` (CI) и hook `block-public-attribution.sh`;
тест `tests/scripts/test_public_metadata_policy.py` держит копии одинаковыми.
"""

from __future__ import annotations

import re

ASSISTANT_ATTRIBUTION = re.compile(
    r"(?<![a-z0-9])co-authored[- ]by\s*:\s*"
    r"(?:claude(?:\s+code)?|openai|chatgpt|copilot|gemini|codex|gpt(?:[-_ ]?[0-9][a-z0-9._-]*)?)"
    r"(?=\s*(?:<|_?(?:\r?\n|$)))|"
    r"(?<![a-z0-9])(generated|written|created|authored|produced)\s+(with|by|using|via)\s+"
    r"\[?(claude|chatgpt|openai|copilot|gemini|codex|gpt[-_ ]?[0-9]|ai(?![a-z0-9]))|"
    r"(?<![a-z0-9])ai[-_ ]?generated(?![a-z0-9])|"
    r"(?<![a-z0-9.-])(claude\.ai|chatgpt\.com|chat\.openai\.com)/",
    re.IGNORECASE,
)
