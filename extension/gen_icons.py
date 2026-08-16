"""One-off script that generated extension/icons/icon{16,48,128}.png.

Not run automatically anywhere (no build step for this extension, matching
the rest of the app -- see extension/README.md); kept in the repo so the
icons can be regenerated/tweaked later without hunting for how they were
made. Requires Pillow (`pip install pillow`), same dependency the rest of
this project doesn't otherwise need at runtime -- dev-only.

Design: a simple copper-accent circle (matches static/css/variables.css's
--accent: #a06a2f) with a white musical note, echoing this app's own
copper/teal "warm analog" palette without trying to be a pixel-perfect
logo.
"""
from PIL import Image, ImageDraw

ACCENT = (160, 106, 47, 255)  # #a06a2f
ACCENT_HOVER = (138, 87, 38, 255)  # #8a5726, used for a subtle rim
WHITE = (255, 255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    # Supersample at 4x and downscale for clean anti-aliased edges at small
    # sizes (16px in particular has no room for jagged circle edges).
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = big * 0.04
    draw.ellipse([margin, margin, big - margin, big - margin], fill=ACCENT, outline=ACCENT_HOVER, width=max(1, int(big * 0.02)))

    # A simple white musical eighth-note: a filled note head + stem + flag,
    # built from primitive shapes rather than a font glyph (no guaranteed
    # font available in this environment, and a hand-drawn glyph scales
    # more predictably down to 16px anyway).
    cx, cy = big * 0.42, big * 0.62
    head_r = big * 0.13
    draw.ellipse([cx - head_r, cy - head_r, cx + head_r, cy + head_r], fill=WHITE)

    stem_x = cx + head_r * 0.85
    stem_top = big * 0.18
    stem_width = big * 0.045
    draw.rectangle([stem_x - stem_width / 2, stem_top, stem_x + stem_width / 2, cy], fill=WHITE)

    # Flag: a simple curved-looking triangle off the top of the stem.
    flag = [
        (stem_x + stem_width / 2, stem_top),
        (stem_x + big * 0.22, stem_top + big * 0.10),
        (stem_x + stem_width / 2, stem_top + big * 0.22),
    ]
    draw.polygon(flag, fill=WHITE)

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    import os

    out_dir = os.path.join(os.path.dirname(__file__), "icons")
    os.makedirs(out_dir, exist_ok=True)
    for size in (16, 48, 128):
        icon = draw_icon(size)
        icon.save(os.path.join(out_dir, f"icon{size}.png"))
        print(f"wrote icons/icon{size}.png")
