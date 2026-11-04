# Apex Epoxy Flooring Solutions - Scrape & Static Site

Complete archive and static site builder for [Apex Epoxy Flooring Solutions](https://www.apexepoxy-fs.com).

## Project Overview

This repository contains:
1. **Raw Scrape Data**: Full rendered and source HTML, assets, screenshots, and metadata for 41 crawled pages.
2. **Static Site Generator (`build_static_site.py`)**: Script that transforms the scraped pages and assets into a clean, fully self-contained static website in `dist/`.
3. **Integrity Verifier (`verify_site.py`)**: Link and asset verification suite to ensure zero broken links or missing assets.
4. **Production Build (`dist/`)**: Ready-to-deploy static website pre-configured for Vercel, Netlify, Cloudflare Pages, or GitHub Pages.

## Directory Structure

```text
├── assets/                  # Raw downloaded static assets (images, fonts, CSS, JS)
│   ├── css/
│   ├── font/
│   ├── image/
│   ├── javascript/
│   ├── other/
│   └── manifest.json        # Mapping of original URLs to local files
├── pages/                   # Scraped page data (source & rendered HTML, screenshots, headers)
│   ├── home/
│   ├── about/
│   ├── services_*/
│   └── service-area_*/
├── public_endpoints/        # Public endpoints (robots.txt, sitemap.xml, llms.txt)
├── dist/                    # Self-contained static production site (41 pages + assets)
│   ├── index.html           # Homepage
│   ├── about/
│   ├── services/
│   ├── service-area/
│   ├── assets/              # Local CSS, JS, fonts, and images
│   ├── feed/                # RSS2 and Atom XML feeds
│   ├── vercel.json          # Vercel deployment configuration
│   └── 404.html             # Custom branded 404 page
├── analyze_links.py         # Utility to analyze external URLs & navigation links
├── build_static_site.py     # Static site build generator
├── verify_site.py           # Verification script for local links and asset resolution
├── sitemap.json             # Structured metadata for all pages
├── sitemap.csv              # CSV format sitemap
└── apex_page_audit.csv      # Audit details for each crawled page
```

## Getting Started

### 1. Build the Static Site
Re-generate the production site in `dist/`:
```bash
python build_static_site.py
```

### 2. Verify Site Integrity
Run the link checker to verify all 3,200+ local asset references and internal links:
```bash
python verify_site.py
```

### 3. Local Preview
Serve the static site locally on port 3000:
```bash
python -m http.server -d dist 3000
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

## Deployment

### Deploy with Vercel CLI
```bash
# Deploy dist folder directly
cd dist
vercel --prod

# Or deploy from root (vercel.json is configured with outputDirectory: "dist")
vercel --prod
```

### Deploy to GitHub Pages / Netlify / Cloudflare Pages
Point the publish directory to `dist/`.

