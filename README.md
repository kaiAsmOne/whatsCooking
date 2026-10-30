# Kokebok

Personal recipe repo. Plain Markdown, one file per recipe, versioned with git.

## Structure

```
<protein>/<cut>/<method-or-seasoning>.md     # e.g. chicken/thigh/flour-five-spice.md
<protein>/README.md                          # generated index for that protein
sauces/                                      # shared sauces, linked from recipes
sides/                                       # side dishes, linked from recipes
_template.md                                 # copy this for new recipes
tools/build_index.py                         # regenerates the README indexes
tools/ghost_sync.py                          # publishes recipes to Ghost (see below)
.github/workflows/ghost-sync.yml             # runs ghost_sync.py on push
```

Each protein folder answers one question: *what are the different ways I cook this?*
File names describe the seasoning or method, not the dish name, so the list reads as a menu of options.

## Conventions

- Metric weights only: g, kg, ml, dl, l. Count items converted to grams (1 garlic clove ≈ 5 g).
- Fresh ginger and garlic, never powders.
- Chili: habanero (own, liquid form), dosed to taste.
- Fish sauce: Norwegian sild fish sauce unless stated.
- Palate: Northern Vietnamese register. Savory, pepper-forward, sugar only for balance.
- `status:` in frontmatter is one of `idea` → `draft` → `tested` → `rotation`.
- Calibrations go in **Changelog** with a date, so the reason for a change survives.

## Adding a recipe

```sh
cp _template.md chicken/thigh/new-thing.md
$EDITOR chicken/thigh/new-thing.md
python3 tools/build_index.py
git add -A && git commit -m "chicken/thigh: new-thing"
```

## Publishing to Ghost

`.github/workflows/ghost-sync.yml` runs `tools/ghost_sync.py` on every push to `main` that touches Markdown.
Each recipe becomes a Ghost post with the slug `<folder>-<cut>-<file>`, e.g. `chicken-thigh-flour-five-spice`.

- Git is the source of truth: edits made in Ghost are overwritten on the next sync.
- Tags: protein (or `sauces`/`sides`), method, status, frontmatter `tags`, plus the internal tag `#kokebok`.
  Ghost's tag pages (`/tag/chicken/`, `/tag/rotation/`) are the indexes.
- `status: idea` stays a Ghost draft; everything else is published.
- Deleting a recipe file sets its post back to draft. Nothing is ever deleted in Ghost.
- Links between recipes (body and `pairs_with`) become Ghost URLs.

### Setup (once)

1. Ghost admin → **Settings → Integrations → Add custom integration** → copy the **Admin API key** and **API URL**.
2. GitHub repo → **Settings → Secrets and variables → Actions**:
   - Secret `GHOST_URL`: e.g. `https://example.com`
   - Secret `GHOST_ADMIN_KEY`: the `id:secret` admin key
   - Variable `GHOST_PERMALINK` (optional): `/kokebok/{slug}/` if you use the routes below, otherwise leave unset
3. **Actions → Sync recipes to Ghost → Run workflow** with *dry run* ticked, and check the log.
4. Run it again without dry run.

### Keeping recipes off the blog front page (optional)

Ghost admin → **Settings → Labs → Routes**: download `routes.yaml`, change it to the following and upload it.
Then set `GHOST_PERMALINK` to `/kokebok/{slug}/`.

```yaml
routes:

collections:
  /kokebok/:
    permalink: /kokebok/{slug}/
    template: index
    filter: tag:hash-kokebok
  /:
    permalink: /{slug}/
    template: index
    filter: tag:-hash-kokebok

taxonomies:
  tag: /tag/{slug}/
  author: /author/{slug}/
```

### Local runs

```sh
python3 -m venv .venv && .venv/bin/pip install markdown pyyaml
.venv/bin/python tools/ghost_sync.py --offline       # render only, shows slugs/tags, no API
GHOST_URL=... GHOST_ADMIN_KEY=... .venv/bin/python tools/ghost_sync.py --dry-run
```
