import os
import re
from pathlib import Path

dist = Path('dist')
broken_assets = []
warning_pages = []
total_asset_refs = 0

for html_file in dist.rglob('*.html'):
    content = html_file.read_text(encoding='utf-8', errors='ignore')
    
    # Check for accidental assets/other page links
    if 'assets/other/' in content:
        matches = re.findall(r'[\'"][^\'"]*assets/other/[^\'"]*[\'"]', content)
        for m in matches:
            if any(p in m.lower() for p in ['epoxy', 'floor', 'cleaning', 'about', 'contact', 'service', 'area', 'gallery', 'faq']):
                warning_pages.append((str(html_file.relative_to(dist)), m))

    # Check asset paths (img, script, link)
    src_hrefs = re.findall(r'(?:src|href)=[\'"]([^\'"#?]+)[\'"]', content)
    for ref in src_hrefs:
        if ref.startswith(('http:', 'https:', '//', 'mailto:', 'tel:', 'javascript:', 'data:')):
            continue
        total_asset_refs += 1
        # If root-relative
        if ref.startswith('/'):
            target = dist / ref.lstrip('/')
        else:
            target = (html_file.parent / ref).resolve()
            
        exists = target.exists() or (target.is_dir() and (target / 'index.html').exists())
        if not exists:
            broken_assets.append((str(html_file.relative_to(dist)), ref))

print(f"Total local references checked: {total_asset_refs}")
print(f"Broken references: {len(broken_assets)}")
print(f"Warning pages: {len(warning_pages)}")
if broken_assets:
    print("Sample broken references:")
    for src, ref in broken_assets[:20]:
        print(f"  In {src}: {ref}")
if warning_pages:
    print("Sample warning pages:")
    for src, ref in warning_pages[:10]:
        print(f"  In {src}: {ref}")
