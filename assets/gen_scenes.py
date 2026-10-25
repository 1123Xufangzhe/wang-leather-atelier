"""Compose photographic-looking scene images (leather swatches, stitch macro)."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(__file__)
IMG = os.path.join(BASE, 'img')
rng = np.random.default_rng(41)


def fbm(w, h, octaves=(3, 7, 15, 30, 60), weights=(.38, .26, .16, .12, .08)):
    acc = np.zeros((h, w), dtype=np.float32)
    for o, wt in zip(octaves, weights):
        s = rng.normal(0, 1, (max(2, h // o), max(2, w // o))).astype(np.float32)
        s = (s - s.min()) / (np.ptp(s) + 1e-6)
        up = np.array(Image.fromarray((s * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC),
                      dtype=np.float32) / 255.0
        acc += wt * up
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)


def leather_plate(w, h, rgb, seed=1, contrast=26.0, fine_amt=13.0):
    """Return RGB image of leather with visible grain."""
    global rng
    rng = np.random.default_rng(seed)
    g = fbm(w, h)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    fine = np.array(Image.fromarray(((fine.clip(-2.4, 2.4) / 4.8 + .5) * 255).astype(np.uint8)),
                    dtype=np.float32) / 255.0
    pebble = rng.normal(0, 1, (h, w)).astype(np.float32)
    pebble = np.array(Image.fromarray(((pebble.clip(-2.4, 2.4) / 4.8 + .5) * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2.2)), dtype=np.float32) / 255.0
    lum = (g - .5) * contrast + (fine - .5) * fine_amt + (pebble - .5) * 22
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for i, c in enumerate(rgb):
        arr[..., i] = c + lum * (1.0 if i == 1 else .94)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def shade(im, top, bottom, edge=90):
    """Simple top-light gradient over the image."""
    w, h = im.size
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    arr = np.asarray(im, dtype=np.float32)
    light = 1.10 - yy * 0.28
    arr = arr * light[..., None]
    # edge darkening
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    ex = np.minimum(xx, 1 - xx)
    ey = np.minimum(yy, 1 - yy)
    d = np.minimum(ex, ey)
    arr *= (0.55 + 0.45 * np.clip(d * 6, 0, 1))[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def rounded_mask(size, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=r, fill=255)
    return m


def shadow_for(piece, blur=22, opacity=115):
    a = piece.split()[3].filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new('RGBA', piece.size, (26, 15, 7, 0))
    sh.putalpha(a.point(lambda v: int(v * opacity / 255)))
    return sh


def make_swatch(rgb, w=400, h=540, seed=5, stitch=True):
    plate = leather_plate(w, h, rgb, seed=seed, contrast=20, fine_amt=16)
    plate = shade(plate, None, None)
    mask = rounded_mask((w, h), 10)
    piece = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    piece.paste(plate, (0, 0), mask)
    d = ImageDraw.Draw(piece)
    if stitch:
        pad = 17
        d.rounded_rectangle([pad, pad, w - pad - 1, h - pad - 1], radius=6,
                            outline=(242, 229, 202, 205), width=2)
        x = pad + 6
        while x < w - pad - 12:
            d.line([x, pad, min(x + 15, w - pad), pad], fill=(246, 235, 210, 235), width=2)
            d.line([x, h - pad - 1, min(x + 15, w - pad), h - pad - 1], fill=(246, 235, 210, 235), width=2)
            x += 27
        y = pad + 6
        while y < h - pad - 12:
            d.line([pad, y, pad, min(y + 15, h - pad)], fill=(246, 235, 210, 235), width=2)
            d.line([w - pad - 1, y, w - pad - 1, min(y + 15, h - pad)], fill=(246, 235, 210, 235), width=2)
            y += 27
    return piece


def swatches():
    W, H = 1600, 1100
    canvas = Image.new('RGB', (W, H), (238, 231, 216))
    # warm backdrop with soft light
    paper = Image.open(os.path.join(IMG, 'paper.jpg')).convert('RGB').resize((W, H), Image.LANCZOS)
    canvas = Image.blend(canvas, paper, 0.75)

    specs = [
        ((176, 118, 66), -10, 250, 620, 5),
        ((118, 44, 35), 7, 470, 590, 9),
        ((78, 84, 62), -5, 690, 640, 13),
        ((198, 158, 104), 12, 910, 585, 17),
        ((40, 29, 22), -9, 1130, 620, 21),
    ]
    for rgb, ang, cx, cy, seed in specs:
        piece = make_swatch(rgb, seed=seed).rotate(ang, expand=True, resample=Image.BICUBIC)
        sh = shadow_for(piece, 22, 115)
        px, py = cx - piece.size[0] // 2, cy - piece.size[1] // 2
        canvas = canvas.convert('RGBA')
        canvas.alpha_composite(sh, (px, py + 22))
        canvas.alpha_composite(piece, (px, py))
        canvas = canvas.convert('RGB')

    # uneven light + vignette
    arr = np.asarray(canvas, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    dx, dy = (xx / W - .42), (yy / H - .38)
    light = 1.08 - np.sqrt(dx ** 2 + dy ** 2) * .45
    arr = arr * np.clip(light, .62, 1.1)[..., None]
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.3))
    canvas.save(os.path.join(IMG, 'swatches.jpg'), quality=88, optimize=True)
    print('swatches ok', canvas.size)


def stitch_macro():
    W, H = 1600, 1050
    leather = leather_plate(W, H, (148, 92, 52), seed=33, contrast=30, fine_amt=15)
    leather = shade(leather, None, None).convert('RGBA')
    # background plate slightly out of focus
    bg = leather.filter(ImageFilter.GaussianBlur(2.4))
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    canvas.paste(bg, (0, 0))

    d = ImageDraw.Draw(canvas, 'RGBA')
    # lower panel (second layer) starting at 58% height
    cut = int(H * 0.60)
    lower = leather.crop((0, 0, W, H - cut))
    lower = lower.filter(ImageFilter.GaussianBlur(0.5))
    dark = Image.new('RGBA', (W, H - cut), (28, 15, 7, 46))
    canvas.paste(lower, (0, cut))
    canvas.alpha_composite(dark, (0, cut))
    d.line([0, cut, W, cut], fill=(18, 9, 3, 210), width=7)
    d.line([0, cut + 7, W, cut + 7], fill=(96, 58, 30, 120), width=3)

    # seam groove on upper panel
    gy = int(H * 0.50)
    d.line([0, gy, W, gy], fill=(70, 42, 22, 150), width=12)
    d.line([0, gy - 4, W, gy - 4], fill=(205, 158, 105, 70), width=2)

    # stitches across the groove
    x = -10
    while x < W:
        ln = rng.integers(38, 50)
        ang = rng.normal(0, 0.02)
        y = gy + rng.integers(-2, 3)
        dx, dy = np.cos(ang), np.sin(ang)
        x2, y2 = x + dx * ln, y + dy * ln
        # shadow under thread
        d.line([x + 4, y + 7, x2 + 4, y2 + 7], fill=(38, 20, 8, 150), width=14)
        # thread body: two strands
        d.line([x, y, x2, y2], fill=(226, 208, 172, 255), width=12)
        d.line([x + 1, y - 2, x2 + 1, y2 - 2], fill=(246, 234, 208, 255), width=4)
        d.line([x + 1, y + 3, x2 + 1, y2 + 3], fill=(186, 162, 124, 220), width=3)
        x += ln + rng.integers(10, 16)

    # fine dust / specular
    arr = np.asarray(canvas.convert('RGB'), dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    d2 = np.sqrt(((xx / W - .5) * 1.05) ** 2 + ((yy / H - .5)) ** 2)
    arr *= np.clip(1.16 - d2 * .5, .55, 1.16)[..., None]
    arr = np.clip(arr, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.35))
    img.save(os.path.join(IMG, 'stitch-macro.jpg'), quality=89, optimize=True)
    print('stitch macro ok')


if __name__ == '__main__':
    swatches()
    stitch_macro()


