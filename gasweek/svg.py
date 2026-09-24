"""an svg chart with nothing but string formatting: fee over time on a log axis,
plus the hour-of-day medians as bars underneath."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from .fees import BlockFee
from .stats import bucket, by_hour, gwei, median, percentile

W, H = 960, 520
H_BLOB = 640  # taller when the blob fee panel is drawn
INK, MUTED, GRID, ACCENT, BAND, BG = "#1c1917", "#78716c", "#e7e5e4", "#0f766e", "#99f6e4", "#fafaf9"
FONT = "font-family='ui-sans-serif, system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif'"

LOG_TICKS = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(rows: list[BlockFee], tz_hours: float = 0.0, title: str | None = None, source: str | None = None) -> str:
    if not rows:
        raise ValueError("no rows to draw")
    blob_rows = [r for r in rows if r.blob_fee_gwei is not None]
    height = H_BLOB if len(blob_rows) > len(rows) // 2 else H
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{height}' viewBox='0 0 {W} {height}' {FONT}>",
           f"<rect width='{W}' height='{height}' fill='{BG}'/>"]
    tz = "utc" if not tz_hours else f"utc{tz_hours:+g}"
    start = datetime.fromtimestamp(rows[0].timestamp, tz=timezone.utc)
    end = datetime.fromtimestamp(rows[-1].timestamp, tz=timezone.utc)
    hours_span = (rows[-1].timestamp - rows[0].timestamp) / 3600
    span = f"last {round(hours_span / 24)} days" if hours_span >= 47 else f"last {round(hours_span)} hours"
    out.append(f"<text x='24' y='34' font-size='20' fill='{INK}'>{_esc(title or 'ethereum base fee, ' + span)}</text>")
    out.append(f"<text x='24' y='54' font-size='12' fill='{MUTED}'>{start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} utc, "
               f"{len(rows):,} blocks, median {gwei(median([r.base_fee_gwei for r in rows]))} gwei</text>")

    # panel 1: time series, 30 minute buckets, p25-p75 band + median line, log y
    x0, x1, y0, y1 = 64, W - 24, 72, 312
    buckets = bucket(rows, 1800)
    lo = min(percentile(v, 5) for _, v in buckets)
    hi = max(percentile(v, 95) for _, v in buckets)
    lo, hi = max(lo, 1e-4) / 1.3, hi * 1.3
    lg0, lg1 = math.log10(lo), math.log10(hi)

    def yy(v: float) -> float:
        v = min(max(v, lo), hi)
        return y1 - (math.log10(v) - lg0) / (lg1 - lg0) * (y1 - y0)

    t0, t1 = buckets[0][0], buckets[-1][0]

    def xx(t: int) -> float:
        return x0 + (t - t0) / max(1, t1 - t0) * (x1 - x0)

    for tick in LOG_TICKS:
        if lo <= tick <= hi:
            y = yy(tick)
            out.append(f"<line x1='{x0}' y1='{y:.1f}' x2='{x1}' y2='{y:.1f}' stroke='{GRID}'/>")
            out.append(f"<text x='{x0 - 8}' y='{y + 4:.1f}' font-size='11' text-anchor='end' fill='{MUTED}'>{gwei(tick)}</text>")
    day = 86400
    first_midnight = (t0 // day + 1) * day
    t = first_midnight
    while t <= t1:
        x = xx(t)
        out.append(f"<line x1='{x:.1f}' y1='{y0}' x2='{x:.1f}' y2='{y1}' stroke='{GRID}'/>")
        label = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%a %d")
        out.append(f"<text x='{x + 4:.1f}' y='{y1 + 16}' font-size='11' fill='{MUTED}'>{label}</text>")
        t += day
    upper = " ".join(f"{xx(t):.1f},{yy(percentile(v, 75)):.1f}" for t, v in buckets)
    lower = " ".join(f"{xx(t):.1f},{yy(percentile(v, 25)):.1f}" for t, v in reversed(buckets))
    out.append(f"<polygon points='{upper} {lower}' fill='{BAND}' opacity='0.6'/>")
    line = " ".join(f"{xx(t):.1f},{yy(median(v)):.1f}" for t, v in buckets)
    out.append(f"<polyline points='{line}' fill='none' stroke='{ACCENT}' stroke-width='1.8'/>")
    out.append(f"<text x='{x1}' y='{y0 - 8}' font-size='11' text-anchor='end' fill='{MUTED}'>"
               "gwei, log scale, median of 30 min with p25 to p75 band</text>")

    # panel 2: hour of day
    hx0, hx1, hy0, hy1 = 64, W - 24, 360, 470
    hours = {h: median(v) for h, v in by_hour(rows, tz_hours).items() if v}
    top = max(hours.values()) if hours else 1
    slot = (hx1 - hx0) / 24
    cheapest = min(hours, key=hours.get) if hours else None
    priciest = max(hours, key=hours.get) if hours else None
    out.append(f"<text x='{hx0}' y='{hy0 - 12}' font-size='12' fill='{INK}'>median base fee by hour of day ({tz})</text>")
    for h in range(24):
        v = hours.get(h)
        if v is None:
            continue
        bar_h = (hy1 - hy0) * v / top
        fill = ACCENT if h in (cheapest, priciest) else BAND
        x = hx0 + h * slot + 2
        out.append(f"<rect x='{x:.1f}' y='{hy1 - bar_h:.1f}' width='{slot - 4:.1f}' height='{bar_h:.1f}' fill='{fill}'/>")
        out.append(f"<text x='{x + (slot - 4) / 2:.1f}' y='{hy1 + 14}' font-size='10' text-anchor='middle' fill='{MUTED}'>{h:02d}</text>")
        if h in (cheapest, priciest):
            out.append(f"<text x='{x + (slot - 4) / 2:.1f}' y='{hy1 - bar_h - 4:.1f}' font-size='10' text-anchor='middle' "
                       f"fill='{INK}'>{gwei(v)}</text>")
    if cheapest is not None and priciest is not None and hours[cheapest] > 0:
        ratio = hours[priciest] / hours[cheapest]
        out.append(f"<text x='{hx1}' y='{hy0 - 12}' font-size='12' text-anchor='end' fill='{MUTED}'>"
                   f"cheapest {cheapest:02d}:00 ({gwei(hours[cheapest])}), priciest {priciest:02d}:00 "
                   f"({gwei(hours[priciest])}), {ratio:.1f}x apart</text>")
    # panel 3: blob base fee, same log treatment, 30 minute medians (post-cancun rows only)
    if height == H_BLOB:
        bx0, bx1, by0, by1 = 64, W - 24, 512, 600
        bbuckets = [(t, [r.blob_fee_gwei for r in rows if r.blob_fee_gwei is not None and t <= r.timestamp < t + 1800])
                    for t, _ in buckets]
        bbuckets = [(t, v) for t, v in bbuckets if v]
        if bbuckets:
            blo = max(min(min(v) for _, v in bbuckets), 1e-6) / 1.3
            bhi = max(max(v) for _, v in bbuckets) * 1.3
            blg0, blg1 = math.log10(blo), math.log10(bhi)

            def by(v: float) -> float:
                v = min(max(v, blo), bhi)
                return by1 - (math.log10(v) - blg0) / max(1e-9, blg1 - blg0) * (by1 - by0)

            out.append(f"<text x='{bx0}' y='{by0 - 10}' font-size='12' fill='{INK}'>blob base fee (gwei, log scale, 30 min medians)</text>")
            for tick in LOG_TICKS:
                if blo <= tick <= bhi:
                    y = by(tick)
                    out.append(f"<line x1='{bx0}' y1='{y:.1f}' x2='{bx1}' y2='{y:.1f}' stroke='{GRID}'/>")
                    out.append(f"<text x='{bx0 - 8}' y='{y + 4:.1f}' font-size='11' text-anchor='end' fill='{MUTED}'>{gwei(tick)}</text>")
            bline = " ".join(f"{xx(t):.1f},{by(median(v)):.1f}" for t, v in bbuckets)
            out.append(f"<polyline points='{bline}' fill='none' stroke='{ACCENT}' stroke-width='1.6' opacity='0.85'/>")
    credit = source or "source: eth_feeHistory from a public rpc, github.com/AlinaSchan/gasweek"
    out.append(f"<text x='24' y='{height - 12}' font-size='11' fill='{MUTED}'>{_esc(credit)}</text>")
    out.append("</svg>")
    return "\n".join(out)
