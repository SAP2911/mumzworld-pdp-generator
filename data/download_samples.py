"""
Generates 15 synthetic test images for the eval harness using PIL.
Run once before executing evals: python data/download_samples.py

Images are simple colored rectangles with product text overlays —
sufficient to verify pipeline logic and demonstrate uncertainty handling.
Replace with real product photos for a production-quality demo.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).parent / "sample_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def make_product_image(
    filename: str,
    lines: list[str],
    bg_color: tuple[int, int, int],
    text_color: tuple[int, int, int] = (30, 30, 30),
    size: tuple[int, int] = (500, 500),
) -> None:
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)

    # Border to simulate product frame
    draw.rectangle([20, 20, size[0] - 20, size[1] - 20], outline=text_color, width=2)

    # Try to load a font, fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        small_font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        small_font = font

    y = 60
    for i, line in enumerate(lines):
        f = font if i == 0 else small_font
        draw.text((50, y), line, fill=text_color, font=f)
        y += 40

    img.save(OUTPUT_DIR / filename, quality=90)


# ── Tier 1: Easy (clear product images) ──────────────────────────────────────
make_product_image(
    "stroller_clear.jpg",
    ["STROLLER", "Model: UltraLite X1", "0-36 months", "Max 15 kg", "5-point harness", "One-hand fold"],
    (240, 240, 245),
)
make_product_image(
    "bottle_branded.jpg",
    ["NaturalStart™", "Anti-Colic Feeding Bottle", "125 ml | Slow Flow", "BPA-Free Silicone", "Age: 0+ months"],
    (210, 235, 255),
)
make_product_image(
    "carrier_in_use.jpg",
    ["ErgoBaby Carrier", "Ergonomic Hip Seat", "3-18 months | Up to 20 kg", "Breathable mesh", "4 carry positions"],
    (255, 228, 210),
)
make_product_image(
    "toy_blocks.jpg",
    ["Wooden Learning Blocks", "12 pcs | Non-toxic paint", "Age: 6 months+", "EN 71 Certified", "Develops fine motor skills"],
    (255, 248, 180),
)
make_product_image(
    "car_seat_labeled.jpg",
    ["SafeRide Pro Car Seat", "Group 0+/1 | 0-18 kg", "ECE R129 i-Size", "Side Impact Protection", "ISOFIX + Support Leg"],
    (210, 255, 215),
)

# ── Tier 2: Medium (partial/ambiguous images) ─────────────────────────────────
make_product_image(
    "stroller_partial.jpg",
    ["[Rear view only]", "Stroller chassis visible", "Wheels + storage basket", "Brand/model not visible"],
    (215, 215, 220),
)
make_product_image(
    "product_box.jpg",
    ["[PRODUCT BOX ONLY]", "Digital Baby Monitor", "2.4 GHz FHSS", "Range: 300m", "Temperature Sensor"],
    (240, 238, 205),
)
make_product_image(
    "multiple_products.jpg",
    ["[Multiple items in frame]", "Stroller + Diaper Bag", "Shown together", "Primary: Stroller"],
    (230, 225, 255),
)
make_product_image(
    "arabic_packaging.jpg",
    ["عربة أطفال", "ماركة: ليتل ستار", "٠-٣٦ شهراً", "قابلة للطي", "حزام أمان خماسي"],
    (255, 248, 228),
    text_color=(60, 40, 10),
)
make_product_image(
    "lifestyle_blurry.jpg",
    ["[lifestyle photo]", "Baby in carrier", "Background blurred", "Product partially visible"],
    (185, 185, 190),
)

# ── Tier 3: Adversarial (edge cases) ─────────────────────────────────────────
make_product_image(
    "landscape.jpg",
    ["Desert landscape", "Sand dunes at sunset", "No product present", "[NOT A PRODUCT IMAGE]"],
    (210, 180, 120),
    text_color=(100, 70, 20),
)
make_product_image(
    "product_blurry.jpg",
    ["##BLUR##", "###blur###", "##BLUR##", "Image degraded"],
    (160, 158, 162),
    text_color=(100, 100, 100),
)
make_product_image(
    "kitchen_appliance.jpg",
    ["KitchenPro Coffee Maker", "1200W | 12-Cup Capacity", "Auto Shut-Off", "NOT a baby product"],
    (245, 210, 210),
    text_color=(120, 30, 30),
)
make_product_image(
    "box_only.jpg",
    ["[Sealed Shipping Box]", "Contents unknown", "No product visible", "Box dimensions: 40x30x25cm"],
    (232, 218, 195),
)
Image.new("RGB", (500, 500), (0, 0, 0)).save(OUTPUT_DIR / "black.jpg")

created = list(OUTPUT_DIR.glob("*.jpg"))
print(f"Generated {len(created)} test images in {OUTPUT_DIR}")
for f in sorted(created):
    print(f"  {f.name}")
