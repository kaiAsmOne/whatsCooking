#!/usr/bin/env python3
"""Publish the kokebok Markdown recipes to Ghost via the Admin API.

Git is the source of truth: every recipe file becomes one Ghost post, matched by slug.
  chicken/thigh/flour-five-spice.md  ->  slug "chicken-thigh-flour-five-spice"

- Creates missing posts, updates existing ones (edits made in Ghost are overwritten).
- Tags: protein (or folder for sauces/sides), method, status, frontmatter tags,
  plus the internal tag #kokebok that marks posts owned by this script.
- status: idea -> Ghost draft, everything else -> published.
- Recipe files removed from git -> their Ghost post is set back to draft (never deleted).
- Relative links between recipes (body and pairs_with) become Ghost URLs.

Env:
  GHOST_URL          https://example.com              (required)
  GHOST_ADMIN_KEY    <id>:<secret> from a custom integration (required)
  GHOST_PERMALINK    URL pattern for links, default "/{slug}/"
                     (use "/kokebok/{slug}/" with the routes.yaml in the README)
Flags:
  --dry-run          print what would happen, no API writes (still needs URL+key to read)
  --offline          render only, no API at all; prints slugs, titles, tags

Deps: pip install markdown pyyaml
"""
import base64, hashlib, hmac, json, os, re, sys, time
import urllib.error, urllib.request
from pathlib import Path, PurePosixPath

import markdown
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"tools", ".git", ".github"}
SKIP_FILES = {"README.md", "_template.md"}
OWNER_TAG = "#kokebok"
OWNER_TAG_SLUG = "hash-kokebok"
GHOST_DRAFT_STATUSES = {"idea"}


# ---------------------------------------------------------------- recipes

def recipe_files():
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if len(rel.parts) < 2 or rel.parts[0] in SKIP_DIRS or rel.parts[0].startswith("."):
            continue
        if p.name in SKIP_FILES:
            continue
        yield rel


def slug_for(rel) -> str:
    s = PurePosixPath(rel).with_suffix("").as_posix().lower().replace("/", "-")
    return re.sub(r"[^a-z0-9\-]+", "-", s).strip("-")


def split_frontmatter(text: str):
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
        if m:
            return (yaml.safe_load(m.group(1)) or {}), m.group(2)
    return {}, text


def link_target(src_rel, href, known: dict, permalink: str):
    """Resolve a relative .md link from src_rel to a Ghost URL, or None if not a recipe."""
    if re.match(r"^[a-z]+:|^/|^#", href) or not href.split("#")[0].endswith(".md"):
        return None
    path, _, frag = href.partition("#")
    target = os.path.normpath(os.path.join(os.path.dirname(PurePosixPath(src_rel).as_posix()), path))
    slug = known.get(PurePosixPath(target).as_posix())
    if not slug:
        return None
    return permalink.format(slug=slug) + (f"#{frag}" if frag else "")


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render(rel, known, permalink):
    fm, body = split_frontmatter((ROOT / rel).read_text(encoding="utf-8"))
    title = (fm.get("title") or PurePosixPath(rel).stem.replace("-", " ").capitalize()).strip()

    def fix(m):
        url = link_target(rel, m.group(2), known, permalink)
        return f"[{m.group(1)}]({url})" if url else m.group(0)

    body = re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", fix, body)

    meta = []
    for key, label in (("serves", "Serves"), ("base_weight", "Base"), ("method", "Method"),
                       ("cut", "Cut"), ("status", "Status")):
        if fm.get(key):
            meta.append(f"<strong>{label}:</strong> {esc(fm[key])}")
    head = f"<p>{' · '.join(meta)}</p>" if meta else ""

    pairs = []
    for href in fm.get("pairs_with") or []:
        url = link_target(rel, href, known, permalink)
        name = PurePosixPath(href).stem.replace("-", " ")
        target = ROOT / os.path.normpath(os.path.join(PurePosixPath(rel).parent.as_posix(), href))
        if target.is_file():
            name = split_frontmatter(target.read_text(encoding="utf-8"))[0].get("title") or name
        pairs.append(f'<a href="{url}">{esc(name)}</a>' if url else esc(name))
    if pairs:
        head += f"<p><strong>Goes with:</strong> {', '.join(pairs)}</p>"

    html = head + markdown.markdown(body, extensions=["extra", "sane_lists"])

    folder = PurePosixPath(rel).parts[0]
    protein = fm.get("protein")
    primary = protein if protein and str(protein).lower() != "none" else folder
    tags = [primary]
    for t in [fm.get("method"), fm.get("status"), *(fm.get("tags") or [])]:
        if t and str(t) not in tags:
            tags.append(str(t))
    tags.append(OWNER_TAG)

    excerpt = f"{primary.capitalize()}"
    if fm.get("cut"):
        excerpt += f", {str(fm['cut']).split(',')[0]}"
    if fm.get("method"):
        excerpt += f" · {fm['method']}"

    return {
        "slug": slug_for(rel),
        "title": title,
        "html": html,
        "tags": [{"name": t} for t in tags],
        "custom_excerpt": excerpt[:300],
        "status": "draft" if str(fm.get("status", "")).lower() in GHOST_DRAFT_STATUSES else "published",
    }


# ---------------------------------------------------------------- Ghost API

class Ghost:
    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/ghost/api/admin"
        self.kid, secret = key.split(":")
        self.secret = bytes.fromhex(secret)

    def _token(self):
        b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
        now = int(time.time())
        head = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": self.kid}).encode())
        body = b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
        sig = b64(hmac.new(self.secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
        return f"{head}.{body}.{sig}"

    def req(self, method, path, data=None):
        r = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Authorization": f"Ghost {self._token()}", "Accept-Version": "v5.0",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise SystemExit(f"Ghost API {method} {path}: {e.code} {e.read().decode(errors='replace')[:500]}")

    def owned_posts(self):
        res = self.req("GET", f"/posts/?filter=tag:{OWNER_TAG_SLUG}&limit=all"
                              "&fields=id,slug,status,updated_at&formats=html")
        return {p["slug"]: p for p in (res or {}).get("posts", [])}

    def get_by_slug(self, slug):
        res = self.req("GET", f"/posts/slug/{slug}/?fields=id,slug,status,updated_at")
        return res["posts"][0] if res else None

    def create(self, post):
        return self.req("POST", "/posts/?source=html", {"posts": [post]})

    def update(self, existing, post):
        post = {**post, "updated_at": existing["updated_at"]}
        return self.req("PUT", f"/posts/{existing['id']}/?source=html", {"posts": [post]})

    def set_status(self, existing, status):
        return self.req("PUT", f"/posts/{existing['id']}/",
                        {"posts": [{"status": status, "updated_at": existing["updated_at"]}]})


# ---------------------------------------------------------------- main

def main(argv):
    dry, offline = "--dry-run" in argv, "--offline" in argv
    permalink = os.environ.get("GHOST_PERMALINK", "/{slug}/")
    rels = list(recipe_files())
    known = {PurePosixPath(r).as_posix(): slug_for(r) for r in rels}
    posts = [render(r, known, permalink) for r in rels]

    dupes = {p["slug"] for p in posts if sum(q["slug"] == p["slug"] for q in posts) > 1}
    if dupes:
        raise SystemExit(f"duplicate slugs: {sorted(dupes)}")

    if offline:
        for p in posts:
            print(f"{p['status']:9} {p['slug']:45} {p['title']}  [{', '.join(t['name'] for t in p['tags'])}]")
        return

    url, key = os.environ.get("GHOST_URL"), os.environ.get("GHOST_ADMIN_KEY")
    if not url or not key:
        raise SystemExit("GHOST_URL and GHOST_ADMIN_KEY must be set")
    g = Ghost(url, key)
    owned = g.owned_posts()
    created = updated = retired = 0

    for p in posts:
        existing = owned.get(p["slug"]) or g.get_by_slug(p["slug"])
        if existing and p["slug"] not in owned:
            print(f"adopt   {p['slug']} (existing post without {OWNER_TAG})")
        if existing:
            print(f"update  {p['slug']} -> {p['status']}")
            if not dry:
                g.update(existing, p)
            updated += 1
        else:
            print(f"create  {p['slug']} -> {p['status']}")
            if not dry:
                g.create(p)
            created += 1

    live = {p["slug"] for p in posts}
    for slug, existing in owned.items():
        if slug not in live and existing["status"] != "draft":
            print(f"retire  {slug} -> draft (file removed from repo)")
            if not dry:
                g.set_status(existing, "draft")
            retired += 1

    print(f"done: {created} created, {updated} updated, {retired} retired{' (dry run)' if dry else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
