# Apex Epoxy Flooring Solutions - Production Web Build

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
