"""Drawing helpers for the dashboard (gauge, trend chart, bar chart, header banner).

Each function returns a 'scene': a plain list of drawing primitives. draw_items() paints a
scene onto a Tkinter Canvas. Keeping the geometry in pure functions makes it easy to test."""
import math

COL = dict(navy="#101a2c", teal="#39d6bd", teal_d="#087f8c", ink="#172337", grey="#65758c",
           grid="#dce5f0", cold="#eaf2fc", ok="#e4f8ef", warn_bg="#fff2d9", crit_bg="#ffe7e5",
           amber="#e3a008", red="#e34d59", green="#19a974", blue="#4598df", purple="#8b5cf6",
           over="#bdc9d8")


def temp_color(value, t):
    """Colour for a temperature value using the configurable thresholds."""
    if value >= t["temp_critical"]:
        return COL["red"]
    if value >= t["temp_warning"]:
        return COL["amber"]
    if value < t["temp_min"]:
        return COL["blue"]
    return COL["green"]


class Scene(list):
    def line(self, coords, fill="#000000", width=1, dash=None):
        self.append(dict(kind="line", coords=list(coords), fill=fill, width=width, dash=dash))

    def rect(self, x0, y0, x1, y1, fill="", outline="", width=1):
        self.append(dict(kind="rect", coords=[x0, y0, x1, y1], fill=fill, outline=outline, width=width))

    def oval(self, x0, y0, x1, y1, fill="", outline="", width=1):
        self.append(dict(kind="oval", coords=[x0, y0, x1, y1], fill=fill, outline=outline, width=width))

    def text(self, x, y, text, fill="#000000", size=9, bold=False, anchor="center"):
        self.append(dict(kind="text", coords=[x, y], text=text, fill=fill, size=size, bold=bold, anchor=anchor))

    def arc(self, bbox, start, extent, outline, width):
        self.append(dict(kind="arc", coords=list(bbox), start=start, extent=extent, outline=outline, width=width))


def draw_items(canvas, items):
    """Paint a scene onto a Tkinter Canvas (clears it first)."""
    canvas.delete("all")
    for it in items:
        k = it["kind"]
        if k == "line":
            opts = dict(fill=it["fill"], width=it["width"])
            if it.get("dash"):
                opts["dash"] = it["dash"]
            canvas.create_line(*it["coords"], **opts)
        elif k == "rect":
            canvas.create_rectangle(*it["coords"], fill=it["fill"], outline=it["outline"], width=it["width"])
        elif k == "oval":
            canvas.create_oval(*it["coords"], fill=it["fill"], outline=it["outline"], width=it["width"])
        elif k == "text":
            canvas.create_text(*it["coords"], text=it["text"], fill=it["fill"], anchor=it["anchor"],
                               font=("Helvetica", it["size"], "bold" if it["bold"] else "normal"))
        elif k == "arc":
            canvas.create_arc(*it["coords"], start=it["start"], extent=it["extent"], style="arc",
                              outline=it["outline"], width=it["width"])


def header(w=4000, h=82):
    """High-contrast engineering dashboard banner with a battery mark and status motif."""
    s = Scene()
    s.rect(0, 0, w, h, fill=COL["navy"])
    # Subtle technical grid on the right, clipped to the requested canvas size.
    grid_start = min(760, max(320, w - 300))
    grid_end = max(grid_start, w - 18)
    for x in range(grid_start, grid_end, 42):
        s.line([x, 0, x, h], "#1b2b43", 1)
    for y in (int(h*.22), int(h*.5), int(h*.78)):
        s.line([grid_start, y, grid_end, y], "#1b2b43", 1)
    s.line([0, h - 3, w, h - 3], COL["teal"], 3)
    # Battery icon scales vertically for compact header test canvases.
    iy0, iy1 = max(5, int(h*.27)), min(h-7, int(h*.73))
    s.rect(22, iy0, 69, iy1, fill="", outline="#d9fff8", width=2)
    s.rect(69, iy0 + 5, 75, iy1 - 5, fill="#d9fff8", outline="#d9fff8")
    for i in range(3):
        s.rect(28 + i * 12, iy0 + 5, 37 + i * 12, iy1 - 5, fill=COL["teal"])
    s.text(91, int(h*.38), "BATTERY THERMAL MANAGEMENT", "#ffffff", 17 if h >= 70 else 13, True, "w")
    s.text(92, int(h*.68), "SYSTEM MONITOR  /  THERMAL ANALYTICS  /  COOLING OPTIMIZATION", "#9fb2c9", 9 if h >= 70 else 7, True, "w")
    # Keep the console label inside even on narrower test canvases.
    if w >= 1250:
        px = w - 600
        s.rect(px, int(h*.3), px+180, int(h*.7), fill="#1b2c42", outline="#2c455f", width=1)
        s.oval(px+12, int(h*.43), px+24, int(h*.57), fill=COL["teal"], outline=COL["teal"])
        s.text(px+33, int(h*.5), "MONITORING CONSOLE", "#e3fff9", 9, True, "w")
    for i, frac in enumerate((.70, .78, .86, .94)):
        x, y = int(w*frac), int(h*(.28 if i % 2 == 0 else .68))
        if x < w - 5:
            s.line([max(grid_start, x-14), y, x, y], "#31516a", 2)
            s.oval(x-3, y-3, x+3, y+3, fill=COL["teal"], outline=COL["teal"])
    return s


def gauge(w, h, value, t, lo=0.0, hi=80.0, title="Battery temperature"):
    """Half-circle temperature gauge with cold / normal / warning / critical zones."""
    s = Scene()
    s.rect(0, 0, w, h, fill="#ffffff")
    s.rect(0, 0, w, 31, fill="#f6f9fd")
    s.line([0, 31, w, 31], COL["grid"], 1)
    s.text(16, 16, title.upper(), COL["navy"], 9, True, "w")
    cx, cy = w / 2, h - 48
    r = min(w / 2 - 26, cy - 38)
    bbox = (cx - r, cy - r, cx + r, cy + r)
    span = hi - lo
    for a, b, colr in ((lo, t["temp_min"], COL["blue"]), (t["temp_min"], t["temp_warning"], COL["green"]),
                       (t["temp_warning"], t["temp_critical"], COL["amber"]), (t["temp_critical"], hi, COL["red"])):
        a, b = max(a, lo), min(b, hi)
        if b > a:
            s.arc(bbox, 180 - 180 * (a - lo) / span, -180 * (b - a) / span, colr, 16)
    s.text(cx - r, cy + 12, f"{lo:g}", COL["grey"], 8, False, "n")
    s.text(cx + r, cy + 12, f"{hi:g}", COL["grey"], 8, False, "n")
    if value is None:
        s.text(cx, cy - r / 2, "No data", COL["grey"], 11)
        return s
    frac = min(max((value - lo) / span, 0.0), 1.0)
    ang = math.pi * (1 - frac)
    s.line([cx, cy, cx + (r - 10) * math.cos(ang), cy - (r - 10) * math.sin(ang)], COL["navy"], 3)
    s.oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=COL["navy"], outline="#ffffff", width=2)
    s.text(cx, cy + 26, f"{value:.1f} °C", temp_color(value, t), 16, True, "n")
    return s


def temperature_chart(w, h, temps, t, predicted=None, title="Temperature history, °C (measured)"):
    """Line chart of measured temperatures with coloured safety bands and an optional estimate."""
    s = Scene()
    s.rect(0, 0, w, h, fill="#ffffff")
    s.rect(0, 0, w, 30, fill="#f6f9fd")
    s.line([0, 30, w, 30], COL["grid"], 1)
    s.text(14, 15, title.upper(), COL["navy"], 9, True, "w")
    temps = list(temps)[-30:]
    if not temps:
        s.text(w / 2, h / 2, "No temperature readings yet", COL["grey"], 11)
        return s
    x0, x1, y0, y1 = 46, w - 20, 34, h - 34
    vals = temps + ([predicted] if predicted is not None else [])
    ymin = min(vals + [t["temp_min"]]) - 3
    ymax = max(vals + [t["temp_critical"]]) + 3
    span = ymax - ymin
    Y = lambda v: y1 - (v - ymin) / span * (y1 - y0)

    for lo, hi, colr in ((ymin, t["temp_min"], COL["cold"]), (t["temp_min"], t["temp_warning"], COL["ok"]),
                         (t["temp_warning"], t["temp_critical"], COL["warn_bg"]), (t["temp_critical"], ymax, COL["crit_bg"])):
        lo, hi = max(lo, ymin), min(hi, ymax)
        if hi > lo:
            s.rect(x0, Y(hi), x1, Y(lo), fill=colr)
    for i in range(5):
        v = ymin + span * i / 4
        s.line([x0, Y(v), x1, Y(v)], COL["grid"], 1)
        s.text(x0 - 6, Y(v), f"{v:.0f}", COL["grey"], 8, False, "e")
    s.line([x0, y0, x0, y1], COL["grey"], 1)
    s.line([x0, y1, x1, y1], COL["grey"], 1)
    for v, colr, label in ((t["temp_warning"], COL["amber"], "Warn"), (t["temp_critical"], COL["red"], "Critical")):
        s.line([x0, Y(v), x1, Y(v)], colr, 1, (5, 3))
        s.text(x0 + 6, Y(v) - 7, f"{label} {v:g}", colr, 8, True, "w")

    slots = len(temps) + (1 if predicted is not None else 0)
    step = (x1 - x0 - 30) / max(slots - 1, 1)
    X = (lambda i: x0 + 15 + i * step) if slots > 1 else (lambda i: (x0 + x1) / 2)
    pts = [(X(i), Y(v)) for i, v in enumerate(temps)]
    if len(pts) > 1:
        s.line([c for p in pts for c in p], COL["navy"], 2)
    for (px, py), v in zip(pts, temps):
        s.oval(px - 3.5, py - 3.5, px + 3.5, py + 3.5, fill=temp_color(v, t), outline="#ffffff", width=1)
    if predicted is not None:
        px, py = X(len(temps)), Y(predicted)
        s.line([pts[-1][0], pts[-1][1], px, py], COL["purple"], 2, (4, 3))
        s.oval(px - 5, py - 5, px + 5, py + 5, fill="#ffffff", outline=COL["purple"], width=2)
        # keep the label on the side away from the dashed line
        ty = max(py - 14, 24) if predicted >= temps[-1] else min(py + 16, y1 - 6)
        s.text(px + 4, ty, f"Estimate {predicted:.1f}", COL["purple"], 8, True, "e")
    tick = max(1, math.ceil(len(temps) / 10))
    for i in range(0, len(temps), tick):
        s.text(X(i), y1 + 12, str(i + 1), COL["grey"], 8)
    s.text((x0 + x1) / 2, h - 8, "reading number (oldest to latest)", COL["grey"], 8)
    return s


def bar_chart(w, h, rows, title):
    """Horizontal bars. rows = list of (label, value, colour)."""
    s = Scene()
    s.rect(0, 0, w, h, fill="#ffffff")
    s.text(14, 14, title, COL["navy"], 10, True, "w")
    s.rect(w - 250, 8, w - 240, 18, fill=COL["teal"])
    s.text(w - 236, 13, "within limit", COL["grey"], 8, False, "w")
    s.rect(w - 150, 8, w - 140, 18, fill=COL["over"])
    s.text(w - 136, 13, "over limit", COL["grey"], 8, False, "w")
    if not rows:
        s.text(w / 2, h / 2, "No cooling cases yet - click Load Demo CFD Cases", COL["grey"], 11)
        return s
    left, right, top = 170, 60, 30
    rh = min(24, (h - top - 6) / len(rows))
    vmax = max(v for _, v, _ in rows) or 1
    for i, (label, val, colr) in enumerate(rows):
        y = top + i * rh
        bw = (w - left - right) * val / vmax
        s.text(left - 8, y + rh / 2, label, COL["ink"], 8, False, "e")
        s.rect(left, y + 3, left + bw, y + rh - 3, fill=colr)
        s.text(left + bw + 6, y + rh / 2, f"{val:.2f}", COL["ink"], 8, True, "w")
    return s
