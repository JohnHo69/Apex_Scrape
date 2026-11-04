import re
import os
import json

from pathlib import Path

html_path = Path(__file__).resolve().parent / "pages" / "home" / "rendered.html"
html = html_path.read_text(encoding="utf-8")

# Find ALL external URLs
urls = set(re.findall(r'(?:src|href)=["\'](["\']|([^"\']+))["\']', html))
external = set()
for match in urls:
    url = match[1] if match[1] else match[0]
    if url.startswith('http') or url.startswith('//'):
        external.add(url)

print("=== All external resource URLs ===")
domains = {}
for u in sorted(external):
    m = re.match(r'(?:https?:)?//([^/]+)', u)
    if m:
        d = m.group(1)
        if d not in domains:
            domains[d] = []
        domains[d].append(u)

for d in sorted(domains.keys()):
    print(f"\n{d} ({len(domains[d])} refs):")
    for u in domains[d][:3]:
        print(f"  {u[:120]}")
    if len(domains[d]) > 3:
        print(f"  ... and {len(domains[d])-3} more")

# Check nav link patterns
print("\n\n=== Navigation link patterns ===")
nav_links = re.findall(r'data-target-page-alias=["\']([^"\']+)["\']', html)
for l in sorted(set(nav_links)):
    print(f"  alias: {l}")

# Check href patterns that are relative
rel_hrefs = set(re.findall(r'href=["\'](?!http|#|mailto|tel|javascript)([^"\']+)["\']', html))
print("\n=== Relative hrefs ===")
for h in sorted(rel_hrefs):
    print(f"  {h}")
