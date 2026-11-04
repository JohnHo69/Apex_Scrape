#!/usr/bin/env python3
"""
Build script: Transform scraped Apex Epoxy site into a self-contained static site
ready for Vercel deployment.

What this does:
1. Creates proper directory structure matching the original URL paths
2. Copies rendered HTML to index.html files in each directory
3. Copies all assets (CSS, JS, images, fonts) locally
4. Rewrites CDN URLs in HTML to point to local assets
5. Rewrites internal links to work with the static site
6. Generates vercel.json for clean URL routing
7. Copies public endpoints (robots.txt, sitemap.xml, llms.txt)
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

# --- Configuration ---
SCRAPE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRAPE_DIR / "dist"
PAGES_DIR = SCRAPE_DIR / "pages"
ASSETS_DIR = SCRAPE_DIR / "assets"
PUBLIC_DIR = SCRAPE_DIR / "public_endpoints"

# Mapping from scrape slug (uses _ for /) to actual URL path
# e.g., "services_epoxy-floor-coatings" -> "services/epoxy-floor-coatings"
# e.g., "service-area_aurora-oh" -> "service-area/aurora-oh"


def get_url_path_from_slug(slug):
    """Convert scrape slug to URL path."""
    # The scraper replaces / with _ in folder names
    # "services_epoxy-floor-coatings" -> "services/epoxy-floor-coatings"
    # "service-area_aurora-oh" -> "service-area/aurora-oh"
    # But NOT for slugs like "annual-floor-cleaning-maintains-epoxy-systems-in-lakewood-oh"
    # Those are top-level pages

    # Known prefixes that use subdirectories
    prefixes = ["services_", "service-area_"]
    for prefix in prefixes:
        if slug.startswith(prefix):
            return slug.replace("_", "/", 1)

    return slug


def load_asset_manifest():
    """Load and parse the asset manifest to build URL -> local path mappings."""
    manifest_path = ASSETS_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Gather page URLs to ensure we NEVER treat HTML pages as static assets
    sitemap = load_sitemap()
    page_urls = set()
    for p in sitemap:
        u = p.get("url", "").rstrip("/")
        if u:
            page_urls.add(u)
            page_urls.add(u + "/")
        fu = p.get("final_url", "").rstrip("/")
        if fu:
            page_urls.add(fu)
            page_urls.add(fu + "/")

    url_map = {}
    for entry in manifest:
        url = entry.get("url", "")
        final_url = entry.get("final_url", url)
        local_path = entry.get("local_path", "")

        if not (url and local_path):
            continue

        # Skip page URLs so internal links are not rewritten to static assets
        if url.rstrip("/") in page_urls or final_url.rstrip("/") in page_urls:
            continue

        # Skip tracking / dynamic endpoints
        if any(tracker in url for tracker in ["google-analytics.com", "googletagmanager.com", "google.com/recaptcha", "vcita.com"]):
            continue

        local_path_normalized = local_path.replace("\\", "/")
        # Skip raw HTML dumps inside assets/other
        if local_path_normalized.startswith("assets/other/"):
            valid_exts = (".ico", ".json", ".xml", ".txt", ".svg", ".png", ".jpg", ".rss", ".atom", ".css", ".js", ".woff", ".woff2", ".ttf")
            if not any(local_path_normalized.endswith(ext) for ext in valid_exts):
                continue

        url_map[url] = local_path_normalized
        if final_url and final_url != url:
            url_map[final_url] = local_path_normalized

    return url_map


def load_sitemap():
    """Load sitemap.json to get the page list."""
    sitemap_path = SCRAPE_DIR / "sitemap.json"
    with open(sitemap_path, "r", encoding="utf-8") as f:
        return json.load(f)


def rewrite_html(html, asset_url_map, page_path_depth):
    """Rewrite HTML to use local assets and fix internal links."""

    # Calculate the relative prefix to get back to root
    # e.g., for /services/epoxy-floor-coatings/index.html, depth=2, prefix="../../"
    # e.g., for /about/index.html, depth=1, prefix="../"
    if page_path_depth == 0:
        rel_prefix = "./"
    else:
        rel_prefix = "../" * page_path_depth

    # 1. Replace CDN asset URLs with local paths
    # Sort by URL length descending to avoid partial replacements
    sorted_urls = sorted(asset_url_map.keys(), key=len, reverse=True)
    for url in sorted_urls:
        local_path = asset_url_map[url]
        local_ref = rel_prefix + local_path
        # Replace both the original URL and URL-encoded versions
        html = html.replace(url, local_ref)
        # Also try URL-decoded version
        decoded = unquote(url)
        if decoded != url:
            html = html.replace(decoded, local_ref)

    # 2. Fix the HomeUrl and canonical references
    html = html.replace("https://www.apexepoxy-fs.com/", rel_prefix)
    html = html.replace("https://www.apexepoxy-fs.com", rel_prefix.rstrip("/"))

    # 3. Fix the CDN preconnect hints (remove them since assets are local)
    html = re.sub(
        r'<link\s+rel="preconnect"\s+href="https://irp\.cdn-website\.com"[^>]*>',
        "",
        html,
    )
    html = re.sub(
        r'<link\s+rel="preconnect"\s+href="https://static\.cdn-website\.com"[^>]*>',
        "",
        html,
    )

    # 4. Remove the service worker registration (it won't work on static site)
    html = re.sub(
        r"navigator\.serviceWorker\s*\n\s*\.register\(serviceWorkerPath.*?\)\s*;?",
        "// Service worker disabled for static site",
        html,
        flags=re.DOTALL,
    )

    # 5. Remove AllowAjax/AJAX navigation (force full page loads)
    html = html.replace("AllowAjax: false", "AllowAjax: false")

    # 6. Fix canonical URL to be relative or remove it
    # Keep canonical but update domain later when custom domain is set

    # 7. Sanitize Mapbox tokens to comply with GitHub Push Protection
    html = re.sub(
        r'rtCommonProps\["common\.mapbox\.token"\]\s*=\s*[\'"][^\'"]*[\'"];?',
        'rtCommonProps["common.mapbox.token"] = "";',
        html,
    )
    html = html.replace(
        "pk.eyJ1IjoiZGFubnliMTIzIiwiYSI6ImNqMGljZ256dzAwMDAycXBkdWxwbDgzeXYifQ.Ck5P-0NKPVKAZ6SH98gxxw",
        "",
    )

    return html


def build_page(slug, url_path, asset_url_map):
    """Build a single page: copy HTML, rewrite URLs."""
    page_dir = PAGES_DIR / slug
    if not page_dir.exists():
        # Check if it exists under about or any other subfolder
        alt_page = PAGES_DIR / "about" / slug
        if alt_page.exists():
            page_dir = alt_page
        else:
            candidates = list(PAGES_DIR.glob(f"*/{slug}"))
            if candidates:
                page_dir = candidates[0]

    html_file = page_dir / "rendered.html"

    if not html_file.exists():
        print(f"  WARNING: No rendered.html for {slug}, trying source.html")
        html_file = page_dir / "source.html"
        if not html_file.exists():
            print(f"  ERROR: No HTML file found for {slug}, skipping")
            return False

    # Read the HTML
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    # Calculate path depth for relative URLs
    # For home (root index.html), depth is 0
    # For "about", depth is 1
    # For "services/epoxy-floor-coatings", depth is 2
    if url_path == "home" or not url_path:
        path_depth = 0
    else:
        path_depth = len(Path(url_path).parts)

    # Rewrite HTML
    rewritten_html = rewrite_html(html, asset_url_map, path_depth)

    # Determine output path
    if url_path == "home":
        out_dir = OUTPUT_DIR
    else:
        out_dir = OUTPUT_DIR / url_path

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(rewritten_html)

    # If home, also write dist/home/index.html so /home resolves directly
    if url_path == "home":
        home_dir = OUTPUT_DIR / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        home_html = rewrite_html(html, asset_url_map, 1)
        with open(home_dir / "index.html", "w", encoding="utf-8") as hf:
            hf.write(home_html)

    # If annual-floor-cleaning, also create dist/about/annual-floor-cleaning/index.html
    if slug == "annual-floor-cleaning":
        about_afc_dir = OUTPUT_DIR / "about" / "annual-floor-cleaning"
        about_afc_dir.mkdir(parents=True, exist_ok=True)
        afc_html = rewrite_html(html, asset_url_map, 2)
        with open(about_afc_dir / "index.html", "w", encoding="utf-8") as afcf:
            afcf.write(afc_html)

    return True


def copy_assets():
    """Copy all asset files to the output directory."""
    src_assets = ASSETS_DIR
    dst_assets = OUTPUT_DIR / "assets"

    asset_types = ["css", "javascript", "image", "font", "other"]
    total_copied = 0

    valid_other_exts = (
        ".ico", ".json", ".xml", ".txt", ".svg", ".png", ".jpg", ".jpeg",
        ".webp", ".gif", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot"
    )

    for asset_type in asset_types:
        src_dir = src_assets / asset_type
        dst_dir = dst_assets / asset_type

        if not src_dir.exists():
            continue

        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.iterdir():
            if not f.is_file():
                continue
            # For 'other' directory, skip raw HTML crawler page dumps
            if asset_type == "other":
                if not any(f.name.lower().endswith(ext) for ext in valid_other_exts):
                    continue
            shutil.copy2(f, dst_dir / f.name)
            total_copied += 1

    print(f"  Copied {total_copied} asset files")
    return total_copied


def copy_public_endpoints():
    """Copy robots.txt, sitemap.xml, llms.txt to root, and RSS/Atom feeds to /feed/."""
    files_to_copy = ["robots.txt", "sitemap.xml", "llms.txt"]
    for fname in files_to_copy:
        src = PUBLIC_DIR / fname
        if src.exists():
            shutil.copy2(src, OUTPUT_DIR / fname)
            print(f"  Copied {fname}")

    # Copy RSS and Atom feeds
    feed_dir = OUTPUT_DIR / "feed"
    feed_dir.mkdir(parents=True, exist_ok=True)
    rss_src = ASSETS_DIR / "other" / "e80c835e_rss2"
    atom_src = ASSETS_DIR / "other" / "d7520cf3_atom"
    if rss_src.exists():
        shutil.copy2(rss_src, feed_dir / "rss2")
        shutil.copy2(rss_src, feed_dir / "rss2.xml")
        print("  Copied feed/rss2")
    if atom_src.exists():
        shutil.copy2(atom_src, feed_dir / "atom")
        shutil.copy2(atom_src, feed_dir / "atom.xml")
        print("  Copied feed/atom")


def create_vercel_json():
    """Create vercel.json with proper routing configuration."""
    config = {
        "cleanUrls": True,
        "trailingSlash": False,
        "redirects": [
            {
                "source": "/home",
                "destination": "/",
                "permanent": True,
            },
            {
                "source": "/services",
                "destination": "/services/epoxy-floor-coatings",
                "permanent": True,
            },
            {
                "source": "/service-area",
                "destination": "/areas-we-serve",
                "permanent": True,
            },
        ],
        "rewrites": [
            {"source": "/services/:path*", "destination": "/services/:path*"},
            {
                "source": "/service-area/:path*",
                "destination": "/service-area/:path*",
            },
        ],
        "headers": [
            {
                "source": "/assets/(.*)",
                "headers": [
                    {
                        "key": "Cache-Control",
                        "value": "public, max-age=31536000, immutable",
                    }
                ],
            },
            {
                "source": "/(.*)",
                "headers": [
                    {"key": "X-Content-Type-Options", "value": "nosniff"},
                    {"key": "X-Frame-Options", "value": "SAMEORIGIN"},
                ],
            },
        ],
    }

    with open(OUTPUT_DIR / "vercel.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("  Created vercel.json")


def create_helper_redirects():
    """Create static fallback redirects for directory index requests."""
    redirects = {
        "services": "/services/epoxy-floor-coatings",
        "service-area": "/areas-we-serve",
    }
    for folder, dest in redirects.items():
        dir_path = OUTPUT_DIR / folder
        dir_path.mkdir(parents=True, exist_ok=True)
        idx_file = dir_path / "index.html"
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url={dest}">
    <link rel="canonical" href="{dest}">
    <title>Redirecting...</title>
</head>
<body>
    <p>Redirecting to <a href="{dest}">{dest}</a>...</p>
</body>
</html>"""
        with open(idx_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Created static fallback redirect: /{folder} -> {dest}")


def create_404_page(asset_url_map):
    """Create a custom 404 page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found | Apex Epoxy Flooring Solutions</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Poppins, 'Segoe UI', sans-serif;
            background: #f3f3f3;
            color: #242424;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 2rem;
        }
        .container {
            max-width: 600px;
        }
        h1 {
            font-family: Raleway, sans-serif;
            font-size: 4rem;
            font-weight: 700;
            color: #06498b;
            margin-bottom: 0.5rem;
        }
        h2 {
            font-family: Raleway, sans-serif;
            font-size: 1.5rem;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 1rem;
            color: #242424;
        }
        p {
            font-size: 1.1rem;
            line-height: 1.6;
            margin-bottom: 2rem;
            color: #575a5b;
        }
        .btn {
            display: inline-block;
            background: #06498b;
            color: #fff;
            padding: 14px 32px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            font-size: 1rem;
            transition: background 0.3s;
        }
        .btn:hover {
            background: #073a6c;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <h2>Page Not Found</h2>
        <p>The page you're looking for doesn't exist or has been moved. Let's get you back to our epoxy flooring solutions.</p>
        <a href="/" class="btn">Back to Home</a>
    </div>
</body>
</html>"""

    with open(OUTPUT_DIR / "404.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  Created 404.html")


def create_dist_readme():
    """Create README.md inside dist for web deployment documentation."""
    content = """# Apex Epoxy Flooring Solutions - Production Web Build

Production-ready static website bundle for Apex Epoxy Flooring Solutions.

## Features
- **41 Static Pages**: Complete page set with clean URLs and self-contained static assets.
- **Local Assets**: All images, CSS, JavaScript, and fonts hosted locally without external CDN dependencies.
- **Feeds**: Full RSS2 and Atom XML feeds included at `/feed/rss2` and `/feed/atom`.
- **SEO & Search**: `sitemap.xml`, `robots.txt`, and `llms.txt` pre-configured.
- **Routing**: `vercel.json` included for clean URLs, redirect fallbacks, and long-term asset caching headers.
- **Custom 404**: Branded `404.html` page included.

## Deployment

### Vercel
Connect this repository to Vercel or run:
```bash
vercel --prod
```

### Local Preview
```bash
python -m http.server 3000
```
Open [http://localhost:3000](http://localhost:3000).
"""
    with open(OUTPUT_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("  Created dist/README.md")


def main():
    print("=" * 60)
    print("APEX EPOXY STATIC SITE BUILDER")
    print("=" * 60)

    # Clean output directory
    if OUTPUT_DIR.exists():
        print(f"\nCleaning output directory: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Load asset manifest
    print("\n[1/6] Loading asset manifest...")
    asset_url_map = load_asset_manifest()
    print(f"  Loaded {len(asset_url_map)} URL -> local path mappings")

    # Load sitemap
    print("\n[2/6] Loading sitemap...")
    sitemap = load_sitemap()
    print(f"  Found {len(sitemap)} pages")

    # Copy assets
    print("\n[3/6] Copying assets...")
    copy_assets()

    # Build pages
    print("\n[4/6] Building pages...")
    success = 0
    failed = 0
    for page in sitemap:
        slug = page["slug"]
        url_path = get_url_path_from_slug(slug)
        print(f"  Building: {slug} -> /{url_path}")
        if build_page(slug, url_path, asset_url_map):
            success += 1
        else:
            failed += 1

    print(f"  Built {success} pages, {failed} failed")

    # Copy public endpoints
    print("\n[5/6] Copying public endpoints...")
    copy_public_endpoints()

    # Create Vercel config, helper redirects, 404 page, and README
    print("\n[6/6] Creating deployment config...")
    create_vercel_json()
    create_helper_redirects()
    create_404_page(asset_url_map)
    create_dist_readme()

    # Summary
    print("\n" + "=" * 60)
    print("BUILD COMPLETE!")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Pages: {success}")
    print(f"  Asset URLs mapped: {len(asset_url_map)}")
    print("=" * 60)

    # List the top-level output structure
    print("\nOutput structure:")
    for item in sorted(OUTPUT_DIR.iterdir()):
        if item.is_dir():
            count = sum(1 for _ in item.rglob("*") if _.is_file())
            print(f"  [DIR]  {item.name}/ ({count} files)")
        else:
            print(f"  [FILE] {item.name} ({item.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
