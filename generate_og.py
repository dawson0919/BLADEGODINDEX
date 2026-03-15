"""Generate OG image (1200x630) for Facebook/LINE/Twitter sharing.
Uses hero-bg.png as background with text overlay.
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 630
BASE_DIR = os.path.dirname(__file__)
BG_PATH = os.path.join(BASE_DIR, "dashboard", "assets", "hero-bg.png")
LOGO_PATH = os.path.join(BASE_DIR, "dashboard", "assets", "logo.png")
OUT = os.path.join(BASE_DIR, "dashboard", "assets", "og.png")

# Load hero-bg.png and resize/crop to 1200x630
bg = Image.open(BG_PATH).convert("RGBA")
bg_w, bg_h = bg.size

# Scale to cover 1200x630, then center-crop
scale = max(W / bg_w, H / bg_h)
new_w, new_h = int(bg_w * scale), int(bg_h * scale)
bg = bg.resize((new_w, new_h), Image.LANCZOS)
left = (new_w - W) // 2
top = (new_h - H) // 2
bg = bg.crop((left, top, left + W, top + H))

# Darken slightly for text readability
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
img.paste(bg, (0, 0))

# Add dark overlay for text contrast
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 120))
img = Image.alpha_composite(img, overlay)

# Add gradient overlay: darker at top and bottom for text areas
gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
grad_draw = ImageDraw.Draw(gradient)
for y in range(150):
    alpha = int(160 * (1 - y / 150))
    grad_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
for y in range(H - 120, H):
    alpha = int(140 * ((y - (H - 120)) / 120))
    grad_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
img = Image.alpha_composite(img, gradient)

# Convert to RGB for drawing text
img = img.convert("RGB")
draw = ImageDraw.Draw(img)


# Try to load a nice font, fall back to default
def get_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/msjhbd.ttc",   # Microsoft JhengHei Bold
        "C:/Windows/Fonts/msjh.ttc",      # Microsoft JhengHei
        "C:/Windows/Fonts/msyh.ttc",      # Microsoft YaHei
        "C:/Windows/Fonts/arial.ttf",
    ]
    if not bold:
        candidates = [c.replace("bd.", ".") for c in candidates] + candidates
    for f in candidates:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default()


font_title = get_font(78, bold=True)
font_sub = get_font(36)
font_en = get_font(28)
font_tag = get_font(22)

# Logo + Title centered
logo = None
if os.path.exists(LOGO_PATH):
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.resize((80, 80), Image.LANCZOS)

title = "刀神指標"
bbox = draw.textbbox((0, 0), title, font=font_title)
tw = bbox[2] - bbox[0]

if logo:
    logo_gap = 16
    total_w = 80 + logo_gap + tw
    logo_x = (W - total_w) // 2
    title_x = logo_x + 80 + logo_gap
    # Paste logo
    img.paste(logo, (logo_x, 60), logo)
    draw = ImageDraw.Draw(img)  # refresh draw after paste
else:
    title_x = (W - tw) // 2

# Title with subtle shadow
draw.text((title_x + 2, 72), title, fill="#000000", font=font_title)
draw.text((title_x, 70), title, fill="#f5c518", font=font_title)

# English subtitle
sub_en = "Blade God Index"
bbox2 = draw.textbbox((0, 0), sub_en, font=font_sub)
sw = bbox2[2] - bbox2[0]
draw.text(((W - sw) // 2 + 1, 171), sub_en, fill="#000000", font=font_sub)
draw.text(((W - sw) // 2, 170), sub_en, fill="#e8eaf0", font=font_sub)

# Tagline
tagline = "美股市場情緒量化儀表板  |  9 項免費即時指標"
bbox3 = draw.textbbox((0, 0), tagline, font=font_en)
tgw = bbox3[2] - bbox3[0]
draw.text(((W - tgw) // 2, 230), tagline, fill="#9ca3af", font=font_en)

# Zone bar (colored rectangles) — positioned lower
bar_y = 480
bar_h = 44
zones = [
    ("#ef4444", "極度恐慌"),
    ("#f97316", "恐懼"),
    ("#eab308", "中性"),
    ("#22c55e", "貪婪"),
    ("#3b82f6", "極度貪婪"),
]
bar_w = 170
bar_gap = 10
total_bar = len(zones) * bar_w + (len(zones) - 1) * bar_gap
bar_x = (W - total_bar) // 2

for i, (color, label) in enumerate(zones):
    x = bar_x + i * (bar_w + bar_gap)
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    # Semi-transparent effect via slightly darker fill
    draw.rounded_rectangle([x, bar_y, x + bar_w, bar_y + bar_h], radius=8,
                           fill=(r, g, b))
    lbbox = draw.textbbox((0, 0), label, font=font_tag)
    lw = lbbox[2] - lbbox[0]
    lh = lbbox[3] - lbbox[1]
    draw.text((x + (bar_w - lw) // 2, bar_y + (bar_h - lh) // 2 - 2),
              label, fill="#ffffff", font=font_tag)

# Score range labels
draw.text((bar_x, bar_y + bar_h + 6), "0", fill="#9ca3af", font=font_tag)
end_label = "100"
ebbox = draw.textbbox((0, 0), end_label, font=font_tag)
draw.text((bar_x + total_bar - (ebbox[2] - ebbox[0]), bar_y + bar_h + 6),
          end_label, fill="#9ca3af", font=font_tag)

# Bottom URL
url = "blade-god-index-production.up.railway.app"
ubbox = draw.textbbox((0, 0), url, font=font_tag)
uw = ubbox[2] - ubbox[0]
draw.text(((W - uw) // 2, H - 35), url, fill="#6b7280", font=font_tag)

img.save(OUT, "PNG", quality=95)
print(f"OG image saved: {OUT} ({os.path.getsize(OUT) // 1024} KB)")
