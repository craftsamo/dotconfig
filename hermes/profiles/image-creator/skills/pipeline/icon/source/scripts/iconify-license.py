#!/usr/bin/env python3
"""Print one line describing an Iconify set's license (stdin: /collections JSON)."""
import json
import sys

prefix = sys.argv[1]
data = json.load(sys.stdin)
info = data.get(prefix) or next(iter(data.values()), {})
lic = info.get("license", {})
author = info.get("author", {})
print(
    f"{info.get('name', prefix)} — {lic.get('title', '?')} ({lic.get('spdx', '?')}) "
    f"{lic.get('url', '')} author={author.get('name', '?')} {author.get('url', '')}".strip()
)
