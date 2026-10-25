"""Generate procedural leather / paper textures for the Wang Leather site."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import os

OUT = os.path.join(os.path.dirname(__file__), 'img')
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261025)


def fbm(w, h, octaves=(4, 8, 16, 32, 64), weights=(.42, .26, .16, .10, .06)):
    acc = np.zeros((h, w), dtype=np.float32)
    for oct_, wt in zip(octaves, weights):
        small = rng.normal(0, 1, (max(2, h // oct_), max(2, w // oct_))).astype(np.float32)
        small = (small - small.min()) / (np.ptp(small) + 1e-6)
        up = np.array(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0
        acc += wt * up
    acc = (acc - acc.min()) / (np.ptp(acc) + 1e-6)
    return acc


def leather(w, h, base, grain_amt=9.0, mottle=16.0, seed=0, sheen=True):
    rnd = np.random.default_rng(seed)
    g = fbm(w, h)
    fine = rnd.normal(0, 1, (h, w)).astype(np.float32)
    fine = np.array(Image.fromarray(((fine.clip(-2.5, 2.5) / 5 + .5) * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0
    # pebble cells: sparse soft blobs
    cells = np.zeros((h, w), dtype=np.float32)
    for _ in range(int(w * h / 2600)):
        cx, cy = rnd.integers(0, w), rnd.integers(0, h)
        r = rnd.integers(2, 7)
        cells[max(0, cy - r):cy + r, max(0, cx - r):cx + r] += 1
    cells = np.array(Image.fromarray((np.clip(cells, 0, 1) * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2.2)), dtype=np.float32) / 255.0

    hh, ww = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = ww / w, hh / h
    if sheen:
        light = np.exp(-(((nx - .28) ** 2) / .18 + ((ny - .18) ** 2) / .22)) * .5
        light += np.exp(-(((nx - .8) ** 2) / .3 + ((ny - .85) ** 2) / .35)) * .12
    else:
        light = np.zeros((h, w), dtype=np.float32)

    lum = ((g - .5) * mottle + (fine - .5) * grain_amt + (cells - .25) * 10 + light * 26)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for i, c in enumerate(base):
        arr[..., i] = c + lum * (1.0 if i == 1 else .92) + (lum * .18 if i == 2 else 0)

    # vignette
    d = np.sqrt(((nx - .5) * 1.05) ** 2 + ((ny - .5) * .95) ** 2)
    vig = np.clip(1.12 - d * .55, .55, 1.12)
    arr *= vig[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def paper(w, h, seed=3):
    rnd = np.random.default_rng(seed)
    g = fbm(w, h, (6, 12, 24, 48), (.45, .3, .17, .08))
    base = np.array([241, 235, 223], dtype=np.float32)
    arr = base[None, None, :] + (g[..., None] - .5) * 22
    # fibers
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img, 'RGBA')
    for _ in range(900):
        x, y = rnd.integers(0, w), rnd.integers(0, h)
        ln = rnd.integers(4, 26)
        a = rnd.normal(0, .5)
        dx, dy = np.cos(a) * ln, np.sin(a) * ln
        d.line([x, y, x + dx, y + dy], fill=(120, 105, 84, rnd.integers(4, 12)), width=1)
    return img.filter(ImageFilter.GaussianBlur(.35))


def save(im, name, q=90):
    im.save(os.path.join(OUT, name), quality=q, optimize=True, progressive=True)
    print('saved', name, im.size)


if __name__ == '__main__':
    save(leather(1800, 1200, (56, 37, 24), 18, 30, 11), 'leather-dark.jpg', 90)
    save(leather(1400, 1000, (132, 86, 48), 16, 24, 23), 'leather-caramel.jpg', 90)
    save(leather(1400, 1000, (78, 32, 27), 16, 24, 31), 'leather-oxblood.jpg', 90)
    save(leather(1400, 1000, (50, 58, 47), 16, 24, 37), 'leather-olive.jpg', 90)
    save(paper(1800, 1200), 'paper.jpg', 86)

    # grain overlay, neutral, multiply-blended by CSS
    g = fbm(1200, 1200, (3, 6, 12, 24, 48), (.3, .28, .2, .14, .08))
    grain = np.clip(238 + (g - .5) * 34, 150, 255).astype(np.uint8)
    save(Image.fromarray(np.dstack([grain] * 3)), 'grain.jpg', 82)

