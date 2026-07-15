---
name: chompsaw-project-designer
description: Design ChompSaw cardboard projects and generate actual-size printable pattern PDFs (US Letter 8.5"x11" or Legal 8.5"x14"). Use this skill whenever the user mentions the ChompSaw, Chompshop, cardboard project designs, printable cutouts/patterns/templates for cardboard builds, or asks to design a cardboard toy, model, or structure they will cut out - even if they don't say "pattern" or "PDF" explicitly. Also use it when updating or resizing a previously generated ChompSaw pattern.
---

# ChompSaw Project Designer

Turn a project idea ("a cardboard castle", "a marble run", "a pom-pom cannon")
into two deliverables:

1. **A build guide** (`.md`) - materials, parts list, cutting steps, assembly,
   safety notes.
2. **A printable pattern PDF** - every part drawn at true 1:1 scale so the
   user prints at 100%, traces onto cardboard, and cuts on the ChompSaw.

## Before designing anything

Read `references/chompsaw-constraints.md`. It covers what the tool can and
can't cut (3 mm cardboard, forward-push cutting, curves by rotation, starter
holes for interior cuts), the companion tools (Hole Punch, Scoring Tool), the
structural techniques that work in cardboard (slot joints, tabs, lamination,
tubes), and the kid-safety rules. Every part you design must be cuttable
under those constraints - the constraints file is what keeps designs from
being pretty drawings that can't actually be built.

## Step 1 - Scope the design

Establish with the user (or decide sensibly if they defer):
- What the finished object should do (roll? launch? open? hold weight?)
- Approximate finished size
- Paper size: **letter** (default) or **legal**. Legal buys 77 mm of extra
  part length - suggest it when a part would otherwise need splitting.

Decompose the object into **flat 2D parts**. Cardboard construction is the
art of flat pieces plus joints: walls, discs, wedges, gussets, rings, tabs.
For each part decide: exact dimensions in mm, quantity, joints (slots, tabs,
glue faces), and any punched holes. Favor designs where mating dimensions
reference each other (a slot is 3.5 mm wide because cardboard is 3 mm; a
cradle notch radius matches the tube radius) - and say so in the guide, so
the user can adapt if their materials differ.

## Step 2 - Check parts against the paper

Printable area with 12 mm margins:
- Letter: **192 x 255 mm**
- Legal: **192 x 332 mm**

Parts must fit in either orientation (the `fits()` helper checks this). If a
part is too big:
- Split it into sections with **alignment tabs or splice plates**, and mark
  the joint with dashed guide lines plus a note.
- Or draw a **half-pattern** on a fold line for symmetric parts ("place on
  fold" like sewing patterns).
- Or suggest switching to legal paper if that alone solves it.
Never silently scale a part down - true size is the whole point.

## Step 3 - Write the build guide

Create a markdown guide in `/mnt/user-data/outputs/` with: a one-line pitch,
difficulty and build time, materials, ChompSaw tools used, a parts table
(letter codes A, B, C... matching the PDF), numbered cutting steps with
technique tips (rotation for curves, punch-then-feed for interior holes),
assembly steps, launch/play instructions if relevant, a safety section, and
troubleshooting. Remind users that all cutting happens before any gluing.

## Step 4 - Generate the pattern PDF

Use the bundled library - don't rewrite the drawing primitives:

```python
import sys; sys.path.insert(0, "<this skill's scripts/ directory>")
from pattern_pdf import PatternDoc

doc = PatternDoc("/home/claude/patterns.pdf", "Pom-Pom Cannon", paper="letter")
doc.new_page()
doc.title_block([
    "1. Print all pages at 100% scale (Actual Size). Check the calibration bar.",
    "2. Cut patterns out roughly, trace onto cardboard (3 mm or thinner) with pencil.",
    "3. Solid lines = ChompSaw cuts. Crosshairs = Hole Punch. Dashed = do not cut.",
])
doc.calibration_bar(12, doc.page_h_mm - 45)
doc.part_label(12, 200, "PART A - BASE PLATE (cut 1)")
doc.rounded_rect(14, 90, 180, 100, radius=12)
doc.punch(30, 140)          # hole punch mark
doc.guide_line(30, 100, 170, 100)  # dashed placement guide
doc.save()
```

What the library gives you (all coordinates/dimensions in mm, origin at
bottom-left of the page):
- `new_page()`, `save()`, automatic footers with page numbers
- `fits(w, h)` - printable-area check for the chosen paper
- `title_block(lines)`, `part_label()`, `note()`
- `calibration_bar(x, y)` - REQUIRED on page 1 of every pattern set
- `punch(x, y)` - crosshair Hole Punch mark
- `rect`, `rounded_rect`, `circle`, `donut` (auto starter-punch),
  `polygon(points)`, and `path(segments)` for mixed line/arc outlines
- `notched_edge_points(p1, p2, r)` - computes the geometry for a
  semicircular cradle notch on a sloped edge (see its docstring)
- `guide_line`, `guide_rect` - dashed non-cut guides

Layout judgment: group small parts on shared pages, one big part per page,
label every part with its letter code and quantity ("cut 2"), and put a short
note near tricky parts (starter-hole locations, fit-test advice like "must
slide freely inside your tube - trim if it drags").

## Step 5 - Verify before delivering

Rasterize and LOOK at every page - geometry bugs (inverted arcs, overlapping
parts, labels colliding with outlines) are invisible in code and obvious in
pixels:

```bash
pdftoppm -png -r 60 patterns.pdf check
```

View each `check-N.png`. Confirm: calibration bar on page 1, no part touches
the 12 mm margins, notches/arcs curve the right way, every interior cutout
has a punch mark, labels don't overlap outlines.

## Step 6 - Deliver

Copy the guide and PDF to `/mnt/user-data/outputs/` and present both files.
Summarize what's on each PDF page and mention the 100%-scale printing
requirement. If the design assumed a material dimension (tube diameter,
cardboard thickness), state the assumption and offer to regenerate to match
the user's actual materials - real tubes and boxes vary.
