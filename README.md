# Kokebok

Personal recipe repo. Plain Markdown, one file per recipe, versioned with git.

## Structure

```
<protein>/<cut>/<method-or-seasoning>.md     # e.g. chicken/thigh/flour-five-spice.md
<protein>/README.md                          # generated index for that protein
sauces/                                      # shared sauces, linked from recipes
_template.md                                 # copy this for new recipes
tools/build_index.py                         # regenerates the README indexes
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
