"""
王氏手工皮艺 — 产品实物图渲染器 v3
程序化「摄影棚」渲染：SDF 高度场 → 法线光照 → 皮革颗粒 / 车缝 / 烫印 → 统一取景与投影。

用法：
  python render_products.py            # 全部 7 款
  python render_products.py tote belt  # 只渲染指定款式（快速迭代用）
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = 1600
OUT = 1000
CX = CY = W / 2.0
YY, XX = np.mgrid[0:W, 0:W].astype(np.float32)
THREAD = np.array([226, 213, 186], np.float32)
BRASS = np.array([176, 141, 88], np.float32)

OUTDIR = os.path.join(os.path.dirname(__file__), 'img', 'works')


# ------------------------------------------------------------------ utils
def gb(a, r):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0


def pnorm(a):
    return (a - a.min()) / (np.ptp(a) + 1e-6)


def fbm(w, h, octaves, weights, seed):
    r = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    for o, wt in zip(octaves, weights):
        s = r.normal(0, 1, (max(2, h // o), max(2, w // o))).astype(np.float32)
        s = (s - s.min()) / (np.ptp(s) + 1e-6)
        up = np.asarray(Image.fromarray((s * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255.0
        acc += wt * up
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)


def sd_round_rect(cx, cy, w, h, r):
    dx = np.abs(XX - (CX + cx)) - (w / 2 - r)
    dy = np.abs(YY - (CY + cy)) - (h / 2 - r)
    ax, ay = np.maximum(dx, 0), np.maximum(dy, 0)
    return np.sqrt(ax * ax + ay * ay) + np.minimum(np.maximum(dx, dy), 0) - r


def sd_seg(ax, ay, bx, by):
    pax, pay = XX - ax, YY - ay
    bax, bay = bx - ax, by - ay
    t = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay + 1e-9), 0, 1)
    dx, dy = pax - bax * t, pay - bay * t
    return np.sqrt(dx * dx + dy * dy)


def sd_poly(pts):
    x, y = XX, YY
    n = len(pts)
    area = 0.0
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        area += ax * by - bx * ay
    sgn = 1.0 if area > 0 else -1.0
    dist = np.full((W, W), 1e9, np.float32)
    inside = np.ones((W, W), bool)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        dist = np.minimum(dist, sd_seg(ax, ay, bx, by))
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        inside &= (cross * sgn) > 0
    return np.where(inside, -dist, dist)


def inset_poly(pts, d):
    n = len(pts)
    cxp = sum(p[0] for p in pts) / n
    cyp = sum(p[1] for p in pts) / n
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        ln = np.hypot(ex, ey)
        ex, ey = ex / ln, ey / ln
        nx, ny = -ey, ex
        if (cxp - a[0]) * nx + (cyp - a[1]) * ny < 0:
            nx, ny = -nx, -ny
        lines.append(((a[0] + nx * d, a[1] + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, d1) = lines[i - 1]
        (q, d2) = lines[i]
        det = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(det) < 1e-7:
            out.append(q)
            continue
        rx, ry = q[0] - p[0], q[1] - p[1]
        t = (rx * d2[1] - ry * d2[0]) / det
        out.append((p[0] + d1[0] * t, p[1] + d1[1] * t))
    return out


def pt(x, y):
    return (CX + x, CY + y)


def arc(cx, cy, r, a0, a1, n=56):
    a = np.linspace(np.radians(a0), np.radians(a1), n)
    return [(CX + cx + r * np.cos(t), CY + cy + r * np.sin(t)) for t in a]


def bez(p0, p1, p2, n=64):
    t = np.linspace(0, 1, n)
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
    return list(zip(x + CX, y + CY))


def inset_pts(pts, d):
    return inset_poly([pt(*q) for q in pts], d)


def poly_path(pts, close=True):
    p = [pt(*q) for q in pts]
    return p + [p[0]] if close else p


def rounded_path(cx, cy, w, h, r, n=10):
    hw, hh = w / 2, h / 2
    path = []
    for (sx, sy, a0) in ((hw - r, -hh + r, -90), (hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180)):
        for k in range(n + 1):
            a = np.radians(a0 + 90 * k / n)
            path.append(pt(cx + sx + r * np.cos(a), cy + sy + r * np.sin(a)))
    path.append(path[0])
    return path


def dist_to_path(path):
    dl = np.full((W, W), 1e9, np.float32)
    for i in range(len(path) - 1):
        dl = np.minimum(dl, sd_seg(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]))
    return dl


# ------------------------------------------------------------------ piece
class Piece:
    def __init__(self, wav):
        self.h = np.zeros((W, W), np.float32)
        self.mat = np.zeros((W, W), np.int8)
        self.alb = np.zeros((W, W, 3), np.float32)
        self.groove = np.zeros((W, W), np.float32)
        self.thread = np.zeros((W, W), np.float32)
        self.deboss = np.zeros((W, W), np.float32)
        self.vis = np.ones((W, W), np.float32)
        self.wav = wav

    def slab(self, sdf, base, color, bevel=30.0, metal=False):
        t = np.clip(-sdf / bevel, 0, 1)
        prof = base * np.sqrt(np.maximum(0, 1 - (1 - t) ** 2))
        prof[sdf >= 0] = 0
        upd = prof > self.h
        self.h[upd] = prof[upd]
        self.alb[upd] = color
        self.mat[upd] = 1 if metal else 0

    def tube(self, dline, R, base, color, metal=False):
        u = np.clip(1 - (dline / R) ** 2, 0, 1)
        prof = base * np.sqrt(u)
        upd = prof > self.h
        self.h[upd] = prof[upd]
        self.alb[upd] = color
        self.mat[upd] = 1 if metal else 0

    def ribbon(self, path, width, base, color, bevel=5.0):
        """扁平皮革条：平顶、圆边、圆头。"""
        dl = dist_to_path(path)
        half = width / 2.0
        t = np.clip((half - dl) / bevel, 0, 1)
        prof = base * np.sqrt(np.maximum(0, 1 - (1 - t) ** 2))
        prof[dl > half] = 0
        upd = prof > self.h
        self.h[upd] = prof[upd]
        self.alb[upd] = color
        self.mat[upd] = 0

    def _mask(self, fn):
        im = Image.new('L', (W, W), 0)
        fn(ImageDraw.Draw(im))
        return np.asarray(im, np.float32) / 255.0

    def stitches(self, path, dash=13, gap=8, width=3.4, vis_th=99.0):
        pts = list(path)

        def draw(d):
            on = True
            slant = 0.0
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                seg = np.hypot(bx - ax, by - ay)
                if seg < 1e-6:
                    continue
                ux, uy = (bx - ax) / seg, (by - ay) / seg
                px, py = -uy, ux
                t = 0.0
                while t < seg:
                    if on:
                        l = min(dash, seg - t)
                        o = slant
                        x0, y0 = ax + ux * t + px * o, ay + uy * t + py * o
                        x1, y1 = ax + ux * (t + l) + px * o, ay + uy * (t + l) + py * o
                        d.line([x0, y0, x1, y1], fill=255, width=max(2, int(width)))
                        r = width / 2
                        d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=255)
                        d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=255)
                        slant = -slant
                        t += l
                    else:
                        t += gap
                    on = not on

        self.thread += self._mask(draw)
        self.groove += self._mask(lambda d: d.line(pts, fill=255, width=int(width + 3), joint='curve'))
        self.vis *= (self.h < vis_th).astype(np.float32)

    def seal(self, cx, cy, r, text='王'):
        mask = Image.new('L', (W, W), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([CX + cx - r, CY + cy - r, CX + cx + r, CY + cy + r], outline=255, width=3)
        try:
            font = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', int(r * 1.45))
            bb = d.textbbox((0, 0), text, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            d.text((CX + cx - tw / 2 - bb[0], CY + cy - th / 2 - bb[1] - r * 0.06), text, font=font, fill=255)
        except Exception:
            pass
        m = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255.0
        self.deboss += m

    def render(self, grain):
        cov = (self.h > 0.05).astype(np.float32)
        wav = (self.wav - 0.5) * 1.1
        dome = 1.7 * gb(cov, 38.0)
        self.h = np.maximum(0, self.h + (wav + dome) * cov)

        hs = gb(self.h / (self.h.max() + 1e-6), 1.1) * self.h.max()
        gy, gx = np.gradient(hs)
        k = 2.6
        nx = -gx * k
        ny = -gy * k
        nz = np.ones_like(self.h)

        gry, grx = np.gradient(grain)
        nx += grx * 1.2
        ny += gry * 1.2
        ln = np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx / ln, ny / ln, nz / ln

        L = np.array([-0.46, -0.55, 0.70], np.float32)
        L /= np.linalg.norm(L)
        diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
        F = np.array([0.58, 0.28, 0.48], np.float32)
        F /= np.linalg.norm(F)
        fill = np.clip(nx * F[0] + ny * F[1] + nz * F[2], 0, 1)
        Hh = L + np.array([0, 0, 1], np.float32)
        Hh /= np.linalg.norm(Hh)
        nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)

        metal = self.mat == 1
        shin = np.where(metal, 90.0, 22.0)
        spec = nh ** shin
        spec_k = np.where(metal, 0.80, 0.30)

        grv_s = gb(np.clip(self.groove * self.vis, 0, 1), 1.2)
        ao = 0.58 + 0.42 * np.clip(self.h / (self.h.max() * 0.5 + 1e-6), 0, 1)
        ao *= (1.0 - 0.30 * grv_s)

        amb = 0.36
        col = self.alb * (amb * ao[..., None]
                          + diff[..., None] * np.array([1.0, 0.95, 0.87], np.float32) * 1.0
                          + fill[..., None] * np.array([0.52, 0.60, 0.76], np.float32) * 0.20)
        spec_col = np.where(metal[..., None], np.array([1.0, 0.83, 0.52], np.float32),
                            np.array([1.0, 0.97, 0.90], np.float32))
        col = col + (spec * spec_k)[..., None] * spec_col

        thr = np.clip(self.thread * self.vis, 0, 1)[..., None]
        grv = grv_s[..., None]
        col = col * (1 - 0.26 * grv)
        thread_shade = (0.42 + 0.46 * diff[..., None]) * THREAD * 0.86
        col = col * (1 - thr) + thr * thread_shade

        col = col * (1 - 0.34 * self.deboss[..., None])

        # 皮革颗粒：反照率微起伏 + 低频色差（patina）
        col = col * (0.975 + 0.045 * grain[..., None])
        mott = gb(self.wav, 60.0)
        col = col * (0.94 + 0.12 * mott[..., None])

        # 边缘封边：轮廓处压暗
        edge_band = np.clip((gb(1 - cov, 2.2) - 0.5) * 2.0, 0, 1)
        col = col * (1 - 0.16 * edge_band[..., None])

        # 细微划痕
        col = col * (1 - 0.06 * SCRATCH[..., None])

        # 边缘菲涅尔高光（皮革油脂感）
        fres = np.clip(1 - nz, 0, 1) ** 2
        col = col + (0.30 * fres * (0.35 + 0.65 * diff))[..., None] * np.array([1.0, 0.96, 0.88], np.float32)

        # 高光偏暖、暗部偏冷（摄影调色）
        col = col + (0.02 * diff[..., None]) * np.array([1.0, 0.92, 0.78], np.float32)

        # 影棚光衰减：边缘略暗
        r2 = ((XX - CX) ** 2 + (YY - CY) ** 2) / (W * 0.55) ** 2
        falloff = np.clip(1.0 - 0.16 * r2, 0.80, 1.0)
        col = col * (falloff * cov + (1 - cov))[..., None]

        alpha = np.clip(self.h / 0.9, 0, 1)
        return col, alpha



def make_scratch():
    im = Image.new('L', (W, W), 0)
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(5)
    for _ in range(110):
        x, y = r.uniform(0, W), r.uniform(0, W)
        a = r.normal(0, 0.6)
        ln = r.uniform(24, 160)
        d.line([x, y, x + np.cos(a) * ln, y + np.sin(a) * ln], fill=int(r.integers(40, 120)), width=1)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    return np.asarray(im, np.float32) / 255.0


SCRATCH = make_scratch()
# ------------------------------------------------------------------ scene
def make_grain():
    r1 = np.random.default_rng(31)
    r2 = np.random.default_rng(47)
    r3 = np.random.default_rng(53)
    fine = gb(pnorm(r1.normal(0, 1, (W, W)).astype(np.float32)), 0.8)
    micro = gb(pnorm(r2.normal(0, 1, (W, W)).astype(np.float32)), 2.0)
    mid = gb(pnorm(r3.normal(0, 1, (W, W)).astype(np.float32)), 6.0)
    low = fbm(W, W, (8, 16, 32, 64), (.4, .3, .2, .1), 91)
    g = 0.46 * fine + 0.28 * micro + 0.18 * mid + 0.08 * low
    return pnorm(g)


def compose(rgba, name, fill=0.76):
    prod = rgba.crop(rgba.split()[3].getbbox())
    scale = (OUT * fill) / max(prod.size)
    prod = prod.resize((max(1, round(prod.size[0] * scale)), max(1, round(prod.size[1] * scale))), Image.LANCZOS)
    prod = prod.filter(ImageFilter.GaussianBlur(0.35))

    canvas = Image.new('RGBA', (OUT, OUT), (0, 0, 0, 0))
    px, py = (OUT - prod.size[0]) // 2, (OUT - prod.size[1]) // 2
    a = prod.split()[3]

    soft = a.filter(ImageFilter.GaussianBlur(70)).point(lambda v: int(v * 0.12))
    tight = a.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.20))

    sh1 = Image.new('RGBA', prod.size, (46, 28, 15, 0))
    sh1.putalpha(soft)
    sh2 = Image.new('RGBA', prod.size, (30, 18, 9, 0))
    sh2.putalpha(tight)

    canvas.alpha_composite(sh1, (px + 12, py + 20))
    canvas.alpha_composite(sh2, (px + 4, py + 7))
    canvas.alpha_composite(prod, (px, py))

    arr = np.asarray(canvas, np.float32)
    nz = np.random.default_rng(abs(hash(name)) % 9999).normal(0, 1.7, (OUT, OUT, 1))
    arr[..., :3] = np.clip(arr[..., :3] + nz, 0, 255)
    canvas = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    canvas.save(os.path.join(OUTDIR, name + '.webp'), 'WEBP', quality=92, method=6)
    print('saved', name, canvas.size)


# ------------------------------------------------------------------ products
def tote(grain, wav):
    p = Piece(wav)
    col = np.array([168, 112, 62], np.float32)
    body = [(-330, -290), (330, -290), (308, 310), (-308, 310)]
    p.slab(sd_poly([pt(*q) for q in body]), 8.0, col, 46)
    band = [(-330, -290), (330, -290), (327, -240), (-327, -240)]
    p.slab(sd_poly([pt(*q) for q in band]), 8.6, col * 0.87, 14)

    left = [pt(-230, -292), pt(-230, -392)] + arc(-145, -392, 85, 180, 360) + [pt(-60, -392), pt(-60, -292)]
    right = [pt(230, -292), pt(230, -392)] + arc(145, -392, 85, 360, 180) + [pt(60, -392), pt(60, -292)]
    for path in (left, right):
        p.ribbon(path, 30, 11.5, col * 0.92, bevel=7)

    p.stitches(poly_path(inset_pts(body, 30)), vis_th=10.4)
    p.stitches([pt(-320, -264), pt(320, -264)], dash=12, gap=8, width=3.2, vis_th=10.4)
    p.seal(0, 190, 34)
    return p.render(grain)


def crossbody(grain, wav):
    p = Piece(wav)
    col = np.array([110, 42, 34], np.float32)
    strap = bez((-232, -128), (0, -540), (232, -128))
    p.ribbon(strap, 22, 9.2, col * 0.88, bevel=5)

    p.slab(sd_round_rect(0, 78, 476, 320, 34), 8.0, col, 44)
    p.slab(sd_round_rect(0, -70, 476, 224, 26), 9.8, col * 1.05, 34)
    p.slab(sd_round_rect(0, 18, 34, 28, 5), 11.4, BRASS, 5, metal=True)
    p.slab(sd_round_rect(0, 18, 16, 12, 3), 11.8, BRASS * 0.5, 3, metal=True)

    p.groove += p._mask(lambda d: d.line([pt(-236, 42), pt(236, 42)], fill=255, width=12))
    p.stitches(rounded_path(0, -70, 476 - 36, 224 - 36, 18), vis_th=9.4)
    p.stitches(rounded_path(0, 78, 476 - 40, 320 - 40, 26), vis_th=9.4)
    return p.render(grain)


def wallet(grain, wav):
    p = Piece(wav)
    col = np.array([78, 84, 68], np.float32)
    p.slab(sd_round_rect(0, 0, 600, 368, 24), 8.0, col, 44)
    p.groove += p._mask(lambda d: d.line([pt(0, -178), pt(0, 178)], fill=255, width=6))
    p.stitches(rounded_path(0, 0, 600 - 48, 368 - 48, 16), dash=12, gap=8, width=3.2)
    p.seal(0, 14, 38)
    return p.render(grain)


def cardholder(grain, wav):
    p = Piece(wav)
    col = np.array([183, 137, 85], np.float32)
    p.slab(sd_round_rect(0, 0, 420, 290, 16), 7.4, col, 40)
    p.stitches(rounded_path(0, 0, 420 - 34, 290 - 34, 10), dash=11, gap=8, width=3.0)
    p.stitches([pt(-170, -72), pt(170, -72)], dash=11, gap=9, width=2.8)
    return p.render(grain)


def belt(grain, wav):
    p = Piece(wav)
    col = np.array([136, 88, 50], np.float32)
    p.slab(sd_round_rect(50, 0, 740, 80, 14), 6.2, col, 40)
    outer = sd_round_rect(-320, 0, 84, 112, 10)
    inner = sd_round_rect(-320, 0, 50, 78, 6)
    p.slab(np.maximum(outer, -inner), 8.8, BRASS, 6, metal=True)
    p.tube(sd_seg(CX - 320, CY, CX - 288, CY), 5.0, 9.4, BRASS, metal=True)
    p.tube(sd_seg(CX - 292, CY, CX - 270, CY), 3.4, 6.8, BRASS * 0.8, metal=True)

    p.stitches([pt(-255, -25), pt(390, -25)], dash=12, gap=8, width=3.2)
    p.stitches([pt(-255, 25), pt(390, 25)], dash=12, gap=8, width=3.2)

    hole = np.zeros((W, W), bool)
    for hx in (270, 310, 350, 390):
        hole |= np.hypot(XX - (CX + hx), YY - CY) < 8.5
    p.h[hole] = 0
    p.alb[hole] = 0
    p.thread[hole] = 0
    return p.render(grain)


def journal(grain, wav):
    p = Piece(wav)
    col = np.array([76, 45, 25], np.float32)
    p.slab(sd_round_rect(0, 0, 424, 574, 12), 8.4, col, 44)
    p.slab(sd_round_rect(-190, 0, 44, 574, 12), 8.9, col * 0.74, 14)
    p.ribbon([pt(172, -280), pt(172, 280)], 11, 10.2, np.array([26, 15, 8], np.float32), bevel=4)
    p.stitches(rounded_path(0, 0, 424 - 44, 574 - 44, 8), dash=12, gap=8, width=3.2)
    p.seal(0, 20, 46)
    return p.render(grain)


def keypouch(grain, wav):
    p = Piece(wav)
    col = np.array([92, 36, 28], np.float32)
    p.slab(sd_round_rect(0, 50, 356, 290, 26), 7.6, col, 42)
    p.slab(sd_round_rect(0, -98, 356, 128, 24), 8.6, col * 1.06, 30)
    ring = np.abs(np.hypot(XX - CX, YY - (CY - 200)) - 44) - 6.2
    p.slab(ring, 7.4, BRASS, 5, metal=True)
    p.slab(np.hypot(XX - CX, YY - (CY + 20)) - 12, 8.4, BRASS, 5, metal=True)
    p.groove += p._mask(lambda d: d.line([pt(-176, -34), pt(176, -34)], fill=255, width=10))
    p.stitches(rounded_path(0, 50, 356 - 42, 290 - 42, 14), vis_th=8.2)
    return p.render(grain)


# ------------------------------------------------------------------ main
FILL = {'belt': 0.90, 'journal': 0.80}

PRODUCTS = (('tote', tote), ('crossbody', crossbody), ('wallet', wallet),
            ('cardholder', cardholder), ('belt', belt), ('journal', journal),
            ('keypouch', keypouch))


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    grain = make_grain()
    wav = pnorm(fbm(W, W, (5, 10, 20, 40), (.4, .3, .2, .1), 77))
    only = sys.argv[1:]
    for name, fn in PRODUCTS:
        if only and name not in only:
            continue
        print('rendering', name)
        col, alpha = fn(grain, wav)
        rgb = np.clip(col, 0, 255).astype(np.uint8)
        a = np.clip(alpha * 255, 0, 255).astype(np.uint8)
        compose(Image.fromarray(np.dstack([rgb, a]), 'RGBA'), name, FILL.get(name, 0.76))


if __name__ == '__main__':
    main()







