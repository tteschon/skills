"""pattern_pdf.py - helper library for ChompSaw printable pattern PDFs.

All dimensions are in millimeters. Pages are US Letter (216 x 279 mm) or
US Legal (216 x 356 mm). Everything is drawn at true 1:1 scale so users can
print at 100% and trace directly onto cardboard.

Conventions baked in:
  - solid dark lines  = ChompSaw cut lines
  - dashed gray lines = placement guides or score/fold lines (never cut)
  - crosshair circles = Hole Punch locations
  - page 1 always gets a 100 mm calibration bar

Typical use:
    from pattern_pdf import PatternDoc
    doc = PatternDoc("/home/claude/patterns.pdf", "My Project", paper="letter")
    doc.new_page()
    doc.title_block(["Print at 100% scale...", "..."])
    doc.calibration_bar(12, 230)
    doc.part_label(12, 215, "PART A - WALL (cut 2)")
    doc.rounded_rect(14, 100, 180, 100, radius=10)
    doc.punch(50, 150)
    doc.save()
"""
import math
from reportlab.lib.pagesizes import letter, legal
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

CUT = (0.13, 0.13, 0.13)
ACCENT = (0.85, 0.35, 0.10)
GRAY = (0.45, 0.45, 0.45)

PAPERS = {"letter": letter, "legal": legal}
# usable printable area with 12 mm margins, in mm
USABLE = {"letter": (192, 255), "legal": (192, 332)}


class PatternDoc:
    def __init__(self, path, project_name, paper="letter"):
        if paper not in PAPERS:
            raise ValueError("paper must be 'letter' or 'legal'")
        self.paper = paper
        self.pagesize = PAPERS[paper]
        self.page_w_mm = self.pagesize[0] / mm
        self.page_h_mm = self.pagesize[1] / mm
        self.usable_w, self.usable_h = USABLE[paper]
        self.project = project_name
        self.c = canvas.Canvas(path, pagesize=self.pagesize)
        self.c.setTitle(f"{project_name} - Printable Patterns")
        self.page_num = 0

    # ---------- page management ----------
    def new_page(self):
        if self.page_num > 0:
            self._footer()
            self.c.showPage()
        self.page_num += 1

    def save(self):
        self._footer()
        self.c.showPage()
        self.c.save()

    def _footer(self):
        self.c.setFillColorRGB(*GRAY)
        self.c.setFont("Helvetica", 8)
        self.c.drawString(12 * mm, 8 * mm,
                          f"{self.project} - print at 100% scale ({self.paper} paper)")
        self.c.drawRightString((self.page_w_mm - 12) * mm, 8 * mm,
                               f"Page {self.page_num}")

    def fits(self, w, h):
        """Check whether a w x h mm part fits the printable area."""
        return (w <= self.usable_w and h <= self.usable_h) or \
               (h <= self.usable_w and w <= self.usable_h)

    # ---------- text ----------
    def part_label(self, x, y, text, size=13):
        self.c.setFillColorRGB(*ACCENT)
        self.c.setFont("Helvetica-Bold", size)
        self.c.drawString(x * mm, y * mm, text)

    def note(self, x, y, lines, size=9):
        self.c.setFillColorRGB(*GRAY)
        self.c.setFont("Helvetica", size)
        for i, ln in enumerate(lines):
            self.c.drawString(x * mm, (y - i * 4.2) * mm, ln)

    def title_block(self, instruction_lines):
        """Standard page-1 header: project title + printing instructions."""
        self.part_label(12, self.page_h_mm - 15, self.project.upper() +
                        " - PRINTABLE PATTERNS", size=16)
        self.note(12, self.page_h_mm - 22, instruction_lines)

    # ---------- line styles ----------
    def _cut(self):
        self.c.setStrokeColorRGB(*CUT)
        self.c.setLineWidth(1.3)
        self.c.setDash()

    def _guide(self):
        self.c.setStrokeColorRGB(*GRAY)
        self.c.setLineWidth(0.8)
        self.c.setDash(3, 3)

    # ---------- standard fixtures ----------
    def calibration_bar(self, x, y):
        self._cut()
        self.c.setLineWidth(1)
        self.c.line(x * mm, y * mm, (x + 100) * mm, y * mm)
        for t in range(0, 101, 10):
            h = 4 if t % 50 == 0 else 2.5
            self.c.line((x + t) * mm, y * mm, (x + t) * mm, (y + h) * mm)
        self.note(x, y - 5, [
            "CALIBRATION: this bar must measure exactly 10 cm (100 mm).",
            "If not, set the printer to 100% / Actual Size (not 'Fit to page').",
        ])

    def punch(self, x, y, r=2.0):
        """Hole Punch mark: small circle with crosshair."""
        self._cut()
        self.c.circle(x * mm, y * mm, r * mm, stroke=1, fill=0)
        self.c.setLineWidth(0.5)
        self.c.line((x - r - 1.5) * mm, y * mm, (x + r + 1.5) * mm, y * mm)
        self.c.line(x * mm, (y - r - 1.5) * mm, x * mm, (y + r + 1.5) * mm)

    # ---------- shapes (cut lines) ----------
    def rect(self, x, y, w, h):
        self._cut()
        self.c.rect(x * mm, y * mm, w * mm, h * mm, stroke=1, fill=0)

    def rounded_rect(self, x, y, w, h, radius=10):
        self._cut()
        self.c.roundRect(x * mm, y * mm, w * mm, h * mm, radius * mm,
                         stroke=1, fill=0)

    def circle(self, cx, cy, r):
        self._cut()
        self.c.circle(cx * mm, cy * mm, r * mm, stroke=1, fill=0)

    def donut(self, cx, cy, r_outer, r_inner, starter_punch=True):
        """Ring shape. Adds a starter punch inside the inner hole so the
        ChompSaw can be fed from there to cut the interior circle."""
        self.circle(cx, cy, r_outer)
        self.circle(cx, cy, r_inner)
        if starter_punch:
            self.punch(cx, cy + max(r_inner - 4, 0))

    def polygon(self, points, close=True):
        """Straight-sided part. points = [(x, y), ...] in mm."""
        self._cut()
        p = self.c.beginPath()
        p.moveTo(points[0][0] * mm, points[0][1] * mm)
        for (x, y) in points[1:]:
            p.lineTo(x * mm, y * mm)
        if close:
            p.close()
        self.c.drawPath(p, stroke=1, fill=0)

    def path(self, segments, close=True):
        """Mixed straight/curved outline for wedges, cradle notches, gears...

        segments is a list of tuples:
          ("move", x, y)                        - start point (first segment)
          ("line", x, y)                        - straight cut to (x, y)
          ("arc", cx, cy, r, start_deg, extent) - arc around center (cx, cy);
              positive extent = counterclockwise. The pen draws a straight
              connector to the arc's start point if it isn't already there.
        """
        self._cut()
        p = self.c.beginPath()
        for seg in segments:
            kind = seg[0]
            if kind == "move":
                p.moveTo(seg[1] * mm, seg[2] * mm)
            elif kind == "line":
                p.lineTo(seg[1] * mm, seg[2] * mm)
            elif kind == "arc":
                _, cx, cy, r, start, extent = seg
                p.arcTo((cx - r) * mm, (cy - r) * mm,
                        (cx + r) * mm, (cy + r) * mm,
                        startAng=start, extent=extent)
        if close:
            p.close()
        self.c.drawPath(p, stroke=1, fill=0)

    def notched_edge_points(self, p1, p2, notch_radius):
        """Helper for cradle notches: given an edge from p1 to p2 and a
        notch radius, returns (center, entry_point, exit_point, entry_angle)
        for a semicircular notch centered on the edge midpoint.

        Use with path(): line to entry_point, then
        ("arc", cx, cy, r, entry_angle, -180) dips the notch into the part
        on the right-hand side of the p1->p2 direction.
        """
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        entry = (mx - notch_radius * ux, my - notch_radius * uy)
        exit_ = (mx + notch_radius * ux, my + notch_radius * uy)
        entry_angle = math.degrees(math.atan2(entry[1] - my, entry[0] - mx))
        return (mx, my), entry, exit_, entry_angle

    # ---------- guides ----------
    def guide_line(self, x1, y1, x2, y2):
        self._guide()
        self.c.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)
        self.c.setDash()

    def guide_rect(self, x, y, w, h):
        self._guide()
        self.c.rect(x * mm, y * mm, w * mm, h * mm, stroke=1, fill=0)
        self.c.setDash()
