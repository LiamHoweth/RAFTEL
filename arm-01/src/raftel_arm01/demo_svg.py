"""Render a static XY trace of recorded logical BenchSort outcomes."""

from collections import Counter
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from raftel_arm01.config import Config
from raftel_arm01.models import ObjectPose, Position
from raftel_arm01.tasks.sorter import Result

_BIN_COLORS = ("#b44848", "#168065", "#376bc3")
_OUTCOME_COLORS = {"skipped": "#9d570c", "failed": "#9e284e", "pending": "#65758b"}


def _add(parent: Element, tag: str, **attributes: str | int | float) -> Element:
    return SubElement(
        parent,
        tag,
        {
            key.replace("_", "-"): f"{value:.2f}" if isinstance(value, float) else str(value)
            for key, value in attributes.items()
        },
    )


def _xml_text(value: str) -> str:
    # ElementTree escapes markup, but XML 1.0 also forbids controls and unpaired surrogates.
    return "".join(
        char
        if 0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or ord(char) >= 0x10000
        else "\ufffd"
        for char in value
    )


def _text(parent: Element, x: int, y: int, value: str, style: str = "") -> Element:
    element = _add(parent, "text", x=x, y=y)
    if style:
        element.set("class", style)
    element.text = _xml_text(value)
    return element


def _line(parent: Element, x1: float, y1: float, x2: float, y2: float, **style: str) -> None:
    _add(parent, "line", x1=x1, y1=y1, x2=x2, y2=y2, **style)


def _bin(parent: Element, x: float, y: float, color: str) -> None:
    _add(parent, "rect", x=x - 7, y=y - 7, width=14, height=14, rx=3, fill="#fff", stroke=color)
    _add(parent, "rect", x=x - 3, y=y - 3, width=6, height=6, rx=1, fill=color)


def _start(parent: Element, x: float, y: float, outcome: str, color: str) -> None:
    fill = "#fff"
    if outcome == "skipped":
        points = f"{x:.2f},{y - 6:.2f} {x + 6:.2f},{y:.2f} {x:.2f},{y + 6:.2f} {x - 6:.2f},{y:.2f}"
        _add(parent, "polygon", points=points, fill=fill, stroke=color, stroke_width=2)
    elif outcome == "failed":
        _add(parent, "circle", cx=x, cy=y, r=7, fill=fill)
        _line(parent, x - 4, y - 4, x + 4, y + 4, stroke=color, stroke_width="2")
        _line(parent, x - 4, y + 4, x + 4, y - 4, stroke=color, stroke_width="2")
    elif outcome == "pending":
        _add(parent, "circle", cx=x, cy=y, r=5, fill=fill, stroke=color, stroke_width=2)
    else:
        _add(parent, "circle", cx=x, cy=y, r=5, fill=color, stroke=fill, stroke_width=1.4)


def render_svg(
    config: Config, objects: list[ObjectPose], result: Result, placements: dict[str, Position]
) -> str:
    """Project actual mock inputs and confirmed placements onto the arm_base XY plane."""
    sorted_ids = set(result.sorted_ids)
    routes = [(obj, placements[obj.identifier]) for obj in objects if obj.identifier in sorted_ids]
    positions = [obj.position for obj in objects]
    positions.extend(bin_.position for bin_ in config.bins)
    positions.extend(destination for _, destination in routes)
    positions.append(Position(0, 0, 0))
    # Normalize before subtracting numeric extremes so the plot stays finite for rejected inputs.
    extent = max(0.01, max(max(abs(pos.x), abs(pos.y)) for pos in positions))
    xs = [pos.x / extent for pos in positions]
    ys = [pos.y / extent for pos in positions]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    zoom = min(472 / max(max_x - min_x, 0.05), 250 / max(max_y - min_y, 0.05))
    center_x, center_y = (max_x + min_x) / 2, (max_y + min_y) / 2

    def project(pos: Position) -> tuple[float, float]:
        return (
            309 + zoom * (pos.x / extent - center_x),
            313 - zoom * (pos.y / extent - center_y),
        )

    root = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": "0 0 944 566",
            "width": "944",
            "height": "566",
            "role": "img",
            "aria-labelledby": "benchsort-title benchsort-description",
        },
    )
    SubElement(root, "title", id="benchsort-title").text = "ARM-01 BenchSort logical simulation"
    SubElement(root, "desc", id="benchsort-description").text = (
        f"XY plot with {len(objects)} starting object poses and {len(result.sorted_ids)} "
        "confirmed mock placements. Straight lines associate sorted starts with destinations."
    )
    SubElement(root, "style").text = """
      text { font-family: system-ui, 'Segoe UI', sans-serif; fill: #172539; font-size: 13px; }
      .headline { font-size: 31px; font-weight: 700; }
      .label { font-size: 16px; font-weight: 650; }
      .muted { fill: #47596e; }
      .small { font-size: 11px; }
      .total { font-size: 32px; font-weight: 700; }
      .count { text-anchor: end; font-weight: 700; }
    """
    _add(root, "rect", width=944, height=566, rx=22, fill="#eef3f9")
    _text(root, 32, 51, "ARM-01 BenchSort", "headline")
    _text(root, 33, 77, "Logical simulation · Recorded start poses and mock placements", "muted")
    _add(root, "rect", x=24, y=104, width=570, height=438, rx=15, fill="#fff", stroke="#d5dfe9")
    _add(root, "rect", x=610, y=104, width=310, height=438, rx=15, fill="#fff", stroke="#d5dfe9")
    _text(root, 44, 134, "XY projection", "label")
    _text(root, 44, 154, "arm_base frame · metres", "small muted")
    _add(root, "rect", x=44, y=167, width=530, height=292, rx=9, fill="#f6f9fc", stroke="#dce4ee")

    origin_x, origin_y = project(positions[-1])
    _line(root, 52, origin_y, 565, origin_y, stroke="#d4dee9", stroke_dasharray="4 4")
    _line(root, origin_x, 175, origin_x, 451, stroke="#d4dee9", stroke_dasharray="4 4")
    _add(root, "circle", cx=origin_x, cy=origin_y, r=3, fill="#53667c")
    _text(root, 551, round(origin_y - 6), "+X", "small muted")
    _text(root, round(origin_x + 7), 183, "+Y", "small muted")

    colors = dict(zip((bin_.category for bin_ in config.bins), _BIN_COLORS, strict=True))
    outcomes = {
        identifier: outcome
        for outcome, identifiers in (
            ("sorted", result.sorted_ids),
            ("skipped", result.skipped_ids),
            ("failed", result.failed_ids),
            ("pending", result.pending_ids),
        )
        for identifier in identifiers
    }
    counts: Counter[str] = Counter()
    for obj, destination in routes:
        bin_ = config.bin_at(destination)
        color = "#65758b"
        if bin_ is not None:
            counts[bin_.category] += 1
            color = colors[bin_.category]
        _line(
            root,
            *project(obj.position),
            *project(destination),
            stroke=color,
            opacity="0.36",
            stroke_width="1.5",
        )
    for bin_ in config.bins:
        group = _add(root, "g")
        SubElement(group, "title").text = _xml_text(f"{bin_.category} bin · {bin_.position}")
        _bin(group, *project(bin_.position), colors[bin_.category])
    for obj in objects:
        outcome = outcomes[obj.identifier]
        color = _OUTCOME_COLORS.get(outcome, colors.get(obj.category, "#65758b"))
        group = _add(root, "g")
        title = f"{obj.identifier} · {obj.category} · {outcome} · start {obj.position}"
        SubElement(group, "title").text = _xml_text(title)
        _start(group, *project(obj.position), outcome, color)

    _add(root, "path", d="M 467 504 v -4 h 78 v 4", fill="none", stroke="#53667c")
    _text(root, 467, 492, f"{extent * (78 / zoom):.3g} m", "small muted")
    _text(root, 44, 487, "Lines connect sorted starts to mock placements.", "muted")
    _text(root, 44, 508, "They show routing decisions only.", "muted")

    _text(root, 632, 134, "Run outcome", "label")
    _text(root, 632, 177, f"{len(result.sorted_ids)} / {len(objects)}", "total")
    run_state = "aborted run" if result.aborted else "all observations processed"
    _text(root, 633, 199, f"Confirmed mock placements · {run_state}", "small muted")
    for y, status, label, number in (
        (229, "sorted", "Sorted start", len(result.sorted_ids)),
        (255, "skipped", "Skipped", len(result.skipped_ids)),
        (281, "failed", "Failed", len(result.failed_ids)),
        (307, "pending", "Pending", len(result.pending_ids)),
    ):
        _start(root, 639, y - 4, status, _OUTCOME_COLORS.get(status, "#47596e"))
        _text(root, 655, y, label)
        _text(root, 896, y, str(number), "count")

    _line(root, 632, 327, 898, 327, stroke="#d5dfe9")
    _text(root, 632, 355, "Confirmed by bin", "label")
    for y, bin_ in zip((386, 420, 454), config.bins, strict=True):
        _bin(root, 639, y - 4, colors[bin_.category])
        category = " ".join(bin_.category.split())
        label = category if len(category) <= 18 else f"{category[:16]}…"
        element = _text(root, 655, y, label)
        SubElement(element, "title").text = _xml_text(category)
        _text(root, 896, y, str(counts[bin_.category]), "count")
    _text(root, 632, 508, "Squares mark configured bin centres.", "muted")

    indent(root)
    return tostring(root, encoding="unicode") + "\n"
