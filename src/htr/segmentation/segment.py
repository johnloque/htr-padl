"""Segmentation d'une double page : reliure → 2 pages → redressement → 7 colonnes → 10 lignes → crops.

    uv run python -m htr.segmentation.segment [--input gold/photos] [--only "1491_W_1 (1)"]

Sorties (une entrée par photo) :
- data/rows/<photo>/rNN_left.jpg, rNN_right.jpg, rNN.jpg (gauche + droite côte à côte)
- data/cells/<photo>/rNN/<colonne>.jpg
- data/debug/<photo>/overview.jpg, page_left.jpg, page_right.jpg, rows.jpg (planche de contrôle)
- data/segmentation/<photo>.json : statut, drapeaux, coins, colonnes, séparateurs de lignes
- data/segmentation/report.csv : une ligne par photo

Si data/corners/<photo>.json existe (saisi avec `click_corners`), les coins manuels remplacent la détection.
Une page dont le nombre de colonnes ou de lignes diffère de l'attendu est signalée (statut `flagged`)
et ses crops ne sont pas exportés.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import yaml
from skimage.filters import threshold_sauvola

ROOT = Path(__file__).resolve().parents[3]
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class SegmentationError(Exception):
    pass


# ---------------------------------------------------------------- primitives

def binarize(gray: np.ndarray, cfg: dict) -> np.ndarray:
    th = threshold_sauvola(gray, window_size=cfg["sauvola_window"], k=cfg["sauvola_k"])
    return ((gray < th) * 255).astype(np.uint8)


def line_masks(binary: np.ndarray, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Masques des traits longs horizontaux et verticaux."""
    C = cfg["close_len"]
    rect = lambda w, h: cv2.getStructuringElement(cv2.MORPH_RECT, (w, h))
    h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, rect(cfg["h_open_len"], 1))
    h = cv2.morphologyEx(h, cv2.MORPH_CLOSE, rect(C, 1))
    v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, rect(1, cfg["v_open_len"]))
    v = cv2.morphologyEx(v, cv2.MORPH_CLOSE, rect(1, C))
    return h, v


def find_gutter(gray: np.ndarray, hmask: np.ndarray, cfg: dict) -> int:
    """Reliure. Les séparateurs horizontaux sont décalés d'une page à l'autre : à la pliure, le profil
    vertical des traits juste à gauche cesse d'être corrélé à celui juste à droite. On prend le minimum
    de cette corrélation, puis on recale sur la colonne la plus sombre à proximité (ombre de la pliure,
    points de couture), après avoir effacé les traits imprimés fins par fermeture morphologique."""
    H, W = hmask.shape
    y0, y1 = (int(H * f) for f in cfg["coverage_band"])
    hb = cv2.blur((hmask > 0).astype(np.float32), (9, 3))[y0:y1]
    d, wdt = int(cfg["offset_frac"] * W), 6
    x0, x1 = (int(W * f) for f in cfg["search_band"])
    corr = np.ones(W)
    for x in range(max(x0, d + wdt), min(x1, W - d - wdt)):
        a, b = hb[:, x - d - wdt:x - d].mean(axis=1), hb[:, x + d:x + d + wdt].mean(axis=1)
        corr[x] = -1 if a.std() < 1e-3 or b.std() < 1e-3 else np.corrcoef(a, b)[0, 1]
    corr = np.convolve(corr, np.ones(5) / 5, mode="same")
    g = x0 + 3 + int(np.argmin(corr[x0 + 3:x1 - 3]))
    r = int(cfg["refine_frac"] * W)
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    prof = cv2.GaussianBlur(closed[y0:y1].astype(np.float32).mean(axis=0).reshape(1, -1), (0, 0), 3).ravel()
    lo, hi = max(0, g - r), min(W, g + r)
    return lo + int(np.argmin(prof[lo:hi]))


@dataclass
class Seg:
    """Segment de trait ajusté : pour un horizontal y = a·x + b, pour un vertical x = a·y + b."""
    a: float
    b: float
    lo: float  # étendue le long du trait
    hi: float

    def at(self, t: float) -> float:
        return self.a * t + self.b


def fit_segments(mask: np.ndarray, horizontal: bool, min_len: float) -> list[Seg]:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    segs = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        length, thick = (w, h) if horizontal else (h, w)
        if length < min_len or thick > 0.08 * length + 6:
            continue
        ys, xs = np.nonzero(labels[y:y + h, x:x + w] == i)
        xs, ys = xs + x, ys + y
        t, u = (xs, ys) if horizontal else (ys, xs)
        a, b = np.polyfit(t.astype(float), u.astype(float), 1)
        segs.append(Seg(a, b, float(t.min()), float(t.max())))
    return segs


def intersect(h: Seg, v: Seg) -> tuple[float, float]:
    # y = ha·x + hb ; x = va·y + vb
    y = (h.a * v.b + h.b) / (1 - h.a * v.a)
    return v.a * y + v.b, y


def merge_collinear(segs: list[Seg], ref: float, tol: float) -> list[Seg]:
    """Fusionne les morceaux d'un même trait (même position en `ref`, pente voisine)."""
    out: list[Seg] = []
    for sg in sorted(segs, key=lambda s: s.at(ref)):
        if out and abs(out[-1].at(ref) - sg.at(ref)) < tol and abs(out[-1].a - sg.a) < 0.02:
            m = out[-1]
            w1, w2 = m.hi - m.lo, sg.hi - sg.lo
            out[-1] = Seg((m.a * w1 + sg.a * w2) / (w1 + w2), (m.b * w1 + sg.b * w2) / (w1 + w2),
                          min(m.lo, sg.lo), max(m.hi, sg.hi))
        else:
            out.append(sg)
    return out


def refine_hline(hmask: np.ndarray, a: float, b: float, x0: float, x1: float, tol: float) -> Seg:
    """Recale une droite y = a·x + b sur le trait horizontal le plus marqué à ± tol."""
    band = cv2.dilate(hmask, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))) > 0
    H, W = band.shape
    xs = np.linspace(max(0, x0), min(W - 1, x1), 300)
    best = (-1.0, a, b)
    for da in np.linspace(-0.01, 0.01, 21):
        for db in np.arange(-tol, tol + 1):
            # rotation autour du milieu pour découpler pente et décalage
            aa, bb = a + da, b + db - da * (x0 + x1) / 2
            ys = np.round(aa * xs + bb).astype(int)
            ok = (ys >= 0) & (ys < H)
            if ok.sum() < len(xs) * 0.8:
                continue
            score = band[ys[ok], xs[ok].astype(int)].mean()
            if score > best[0]:
                best = (score, aa, bb)
    return Seg(best[1], best[2], x0, x1)


def detect_corners(binary: np.ndarray, cfg: dict, side: str) -> np.ndarray:
    """4 coins (TL, TR, BR, BL) du tableau d'une page, à l'échelle de travail.

    Les traits verticaux du tableau sont continus de l'en-tête au bas de page : les plus à gauche et
    à droite donnent les bords latéraux, leurs extrémités une première estimation des bords haut et bas,
    recalée ensuite sur le trait horizontal le plus proche.
    """
    H, W = binary.shape
    hmask, vmask = line_masks(binary, cfg["lines"])
    vs = merge_collinear(fit_segments(vmask, False, 0.1 * H), H / 2, 0.006 * W)
    if not vs:
        raise SegmentationError("aucun trait vertical")
    longest = max(v.hi - v.lo for v in vs)
    long_vs = [v for v in vs if v.hi - v.lo >= 0.6 * longest]
    # un trait du tableau commence et finit avec les autres (exclut la tranche du livre, etc.)
    lo_med, hi_med = np.median([v.lo for v in long_vs]), np.median([v.hi for v in long_vs])
    tol = 0.04 * H
    table = [v for v in long_vs if abs(v.lo - lo_med) < 3 * tol and abs(v.hi - hi_med) < 3 * tol]
    if len(table) < cfg["table"]["columns_per_page"] // 2:
        raise SegmentationError(f"{len(table)} traits verticaux de tableau seulement")
    ref = H / 2
    left, right = min(table, key=lambda v: v.at(ref)), max(table, key=lambda v: v.at(ref))
    # côté reliure, le trait de bord se courbe et se perd dans la pliure : on prend le bord de la découpe
    # (qui déborde un peu sur l'autre page), parallèle au trait fiable le plus proche ; le gabarit de
    # colonnes retrouvera ensuite le vrai bord dans la page redressée
    if side == "left":
        right = Seg(right.a, (W - 1) - right.a * ref, right.lo, right.hi)
    else:
        left = Seg(left.a, 0 - left.a * ref, left.lo, left.hi)
    # pente des bords haut/bas : médiane des pentes des longs traits horizontaux (fiable) ;
    # décalage : médiane sur les extrémités des traits verticaux du tableau
    hs = fit_segments(hmask, True, 0.2 * W)
    slope = float(np.median([h.a for h in hs])) if hs else 0.0
    ta = ba = slope
    tb = float(np.median([v.lo - slope * v.at(v.lo) for v in table]))
    bb = float(np.median([v.hi - slope * v.at(v.hi) for v in table]))
    x0, x1 = left.at(ref), right.at(ref)
    top = refine_hline(hmask, ta, tb, x0, x1, int(tol / 2))
    bottom = refine_hline(hmask, ba, bb, x0, x1, int(tol / 2))
    return np.array([intersect(top, left), intersect(top, right), intersect(bottom, right),
                     intersect(bottom, left)], dtype=np.float32)


def warp(image: np.ndarray, corners: np.ndarray, margin_frac: float) -> tuple[np.ndarray, int]:
    """Redresse le tableau en rectangle, avec une marge pour que les bords restent visibles."""
    tl, tr, br, bl = corners
    w = int(round((np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2))
    h = int(round((np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2))
    m = int(margin_frac * max(w, h))
    dst = np.array([[m, m], [m + w - 1, m], [m + w - 1, m + h - 1], [m, m + h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    out = cv2.warpPerspective(image, M, (w + 2 * m, h + 2 * m), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, m


def peaks(profile: np.ndarray, min_value: float, merge: int) -> list[int]:
    """Centres des plages où le profil dépasse `min_value` (plages proches fusionnées)."""
    above = np.append(profile >= min_value, False)
    out, start = [], None
    for i, v in enumerate(above):
        if v and start is None:
            start = i
        elif not v and start is not None:
            seg = profile[start:i]
            c = start + int(np.argmax(seg))
            if out and c - out[-1][1] <= merge:
                if profile[c] > out[-1][0]:
                    out[-1] = (profile[c], c)
            else:
                out.append((profile[c], c))
            start = None
    return [c for _, c in out]


def detect_columns(vmask: np.ndarray, template: list[float], cfg: dict) -> tuple[list[int], int]:
    """Traits de colonnes ajustés sur le gabarit du formulaire imprimé (positions relatives des 8 traits).

    On cherche l'échelle et le décalage qui alignent le plus de traits candidats sur le gabarit ; un trait
    non détecté est placé à sa position prévue. Renvoie (positions, nombre de traits effectivement vus)."""
    thick = cv2.dilate(vmask, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))) > 0
    prof = thick.mean(axis=0)
    W = vmask.shape[1]
    cands = np.array(peaks(prof, cfg["column_min_coverage"], cfg["merge_px"]), float)
    t = np.array(template, float)
    tol = cfg["column_template_tol"] * W
    best = (-1, 0.0, 0.0, 0.0)
    for i in range(len(t)):
        for j in range(i + 1, len(t)):
            for xi in cands:
                for xj in cands[cands > xi]:
                    scale = (xj - xi) / (t[j] - t[i])
                    if scale < cfg["column_min_width_frac"] * W:
                        continue
                    off = xi - scale * t[i]
                    pred = off + scale * t
                    d = np.abs(cands[None, :] - pred[:, None]).min(axis=1)
                    matched = int((d < tol).sum())
                    err = float(d[d < tol].sum())
                    if matched > best[0] or (matched == best[0] and err < best[3]):
                        best = (matched, off, scale, err)
    matched, off, scale, _ = best
    pred = off + scale * t
    xs = []
    for x in pred:
        d = np.abs(cands - x)
        xs.append(int(cands[d.argmin()]) if len(cands) and d.min() < tol else int(round(x)))
    return xs, matched


def line_response(gray: np.ndarray, cfg: dict) -> np.ndarray:
    """Réponse « trait fin horizontal sombre » : black-hat avec un élément vertical, lissé horizontalement."""
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, cfg["row_blackhat_px"]))
    r = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k).astype(np.float32)
    return cv2.blur(r, (9, 1))


def trace_paths(resp: np.ndarray, x0: int, x1: int, step: int, max_dy: int, penalty: float) -> tuple[np.ndarray, np.ndarray]:
    """Programmation dynamique de gauche à droite : pour chaque ordonnée d'arrivée, le chemin de réponse
    cumulée maximale (pente bornée à max_dy pixels par pas, pénalité par pixel de déplacement).
    Renvoie (scores d'arrivée, chemins [H, n_pas])."""
    xs = np.arange(x0, x1 - step + 1, step)
    S = np.stack([resp[:, x:x + step].mean(axis=1) for x in xs], axis=1)  # H × n
    H, n = S.shape
    V = S[:, 0].copy()
    back = np.zeros((H, n), np.int32)
    for i in range(1, n):
        best = np.full(H, -np.inf)
        arg = np.zeros(H, np.int32)
        for dy in range(-max_dy, max_dy + 1):
            shifted = np.full(H, -np.inf)
            if dy >= 0:
                shifted[dy:] = V[:H - dy] if dy else V
            else:
                shifted[:dy] = V[-dy:]
            shifted -= penalty * abs(dy)
            better = shifted > best
            best[better] = shifted[better]
            arg[better] = dy
        V = best + S[:, i]
        back[:, i] = arg
    paths = np.zeros((H, n), np.int32)
    y = np.arange(H)
    for i in range(n - 1, -1, -1):
        paths[:, i] = y
        y = np.clip(y - back[y, i], 0, H - 1)
    return V / n, paths, xs


def detect_rows(gray: np.ndarray, cols: list[int], margin: int, cfg: dict) -> tuple[list[list[int]], list[str]]:
    """Séparateurs de lignes, chacun donné colonne par colonne (le trait se courbe près de la reliure).

    1. Carte de réponse des traits fins horizontaux ; chemins de réponse maximale suivis de gauche à
       droite par programmation dynamique (absorbe la courbure et les traits en pointillés).
    2. Un séparateur doit être marqué dans TOUTES les colonnes le long de son chemin (les traits fins
       internes aux cases ne traversent pas les colonnes voisines).
    3. Parmi les candidats, on retient n+1 séparateurs consécutifs à pas régulier, les plus bas
       (l'en-tête est au-dessus du premier).
    """
    n = cfg["rows_per_page"]
    H = gray.shape[0]
    resp = line_response(gray, cfg)
    step = cfg["row_dp_step_px"]
    score, paths, xs = trace_paths(resp, cols[0], cols[-1], step, 1, cfg["row_dp_penalty"])
    # seuil de « trait présent » relatif au fond de la page
    on = resp > cfg["row_on_factor"] * np.median(resp[:, cols[0]:cols[-1]] + 1e-3)
    col_idx = np.searchsorted(cols, xs + step // 2) - 1
    # candidats : maxima locaux du score d'arrivée, chemins distincts
    order = np.argsort(-score)
    p_min = H / (n + 2.5)
    taken, weak_bottom, fracs = [], [], {}
    for y in order:
        if score[y] <= 0:
            break
        path = paths[y]
        if any(np.median(np.abs(path - paths[t])) < 0.3 * p_min for t in taken):
            continue
        frac = []
        for c in range(len(cols) - 1):
            sel = col_idx == c
            frac.append(on[path[sel], xs[sel] + step // 2].mean() if sel.any() else 0)
        ok = min(frac) >= cfg["row_min_coverage"]
        # le bord bas du tableau (position connue par les coins) se courbe fortement contre la pliure :
        # on l'accepte s'il est vu dans au moins la moitié des colonnes
        at_bottom = abs(np.median(path) - (H - 1 - margin)) <= 0.3 * p_min
        if not ok and at_bottom and np.mean(np.array(frac) >= cfg["row_min_coverage"]) >= 0.5:
            ok = True
            weak_bottom.append(y)
        if ok:
            taken.append(y)
            fracs[y] = frac
        if len(taken) > 3 * n:
            break
    cands = sorted(taken, key=lambda t: np.median(paths[t]))
    if len(cands) < n + 1:
        raise SegmentationError(f"{len(cands)} séparateurs traversant toutes les colonnes (au moins {n + 1} attendus)")
    meds = np.array([np.median(paths[t]) for t in cands])
    # séquences régulières de n+1 séparateurs ; on préfère celle qui finit au bas du tableau,
    # sinon la plus basse
    bottom = H - 1 - margin
    best, best_key = None, None
    for i in range(len(cands) - n):
        gaps = np.diff(meds[i:i + n + 1])
        cv = gaps.std() / gaps.mean()
        if cv > cfg["row_pitch_cv_max"]:
            continue
        key = (abs(meds[i + n] - bottom) > 0.3 * p_min, -meds[i + n])
        if best_key is None or key < best_key:
            best, best_key = i, key
    if best is None:
        raise SegmentationError("aucune suite régulière de séparateurs")
    pitch = float(np.mean(np.diff(meds[best:best + n + 1])))
    # au-dessus du premier séparateur il y a toujours l'en-tête du tableau
    if meds[best] - margin < cfg["row_header_min_frac"] * pitch:
        raise SegmentationError("pas d'en-tête au-dessus de la première ligne (décalage d'une ligne ?)")
    seps = []
    for t in cands[best:best + n + 1]:
        path = paths[t]
        seps.append([int(np.median(path[col_idx == c])) for c in range(len(cols) - 1)])
    warnings = [] if not best_key[0] else ["le dernier séparateur n'est pas au bas estimé du tableau"]
    if cands[best + n] in weak_bottom:
        # colonnes où le bord bas n'est pas vu : séparateur précédent + pas médian de la colonne
        g = np.median(np.diff(np.array(seps[:-1]), axis=0), axis=0)
        for c, f in enumerate(fracs[cands[best + n]]):
            if f < cfg["row_min_coverage"]:
                seps[-1][c] = int(seps[-2][c] + g[c])
                warnings.append(f"bord bas extrapolé dans la colonne {c + 1}")
    # cohérence par colonne : un pas qui s'écarte trop du pas médian de sa colonne (accroché à une réglure
    # interne, fréquente dans « Observations ») est recalé sur le décalage observé dans les autres colonnes
    arr = np.array(seps, float)
    med = np.median(np.diff(arr, axis=0), axis=0)
    fixes = 0
    for k in range(1, len(arr)):
        gaps = arr[k] - arr[k - 1]
        bad = np.abs(gaps - med) > cfg["row_gap_tol"] * med
        if bad.any() and not bad.all():
            rel = np.median((gaps / med)[~bad])
            for c in np.nonzero(bad)[0]:
                arr[k, c] = arr[k - 1, c] + rel * med[c]
                warnings.append(f"séparateur {k} recalé dans la colonne {c + 1}")
                fixes += 1
    if fixes > cfg["row_max_fixes"]:
        raise SegmentationError(f"{fixes} séparateurs incohérents entre colonnes")
    return arr.round().astype(int).tolist(), warnings


# ---------------------------------------------------------------- photo complète

@dataclass
class PageResult:
    side: str
    corners: list
    corners_source: str
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)  # séparateurs : une liste de y par colonne
    warnings: list = field(default_factory=list)
    table_top: int = 0      # bords du tableau dans la page redressée (= marge)
    table_bottom: int = 0
    flags: list = field(default_factory=list)
    size: tuple = (0, 0)


def segment_page(img: np.ndarray, gray_work: np.ndarray, x_off: int, side: str, cfg: dict,
                 manual: list | None) -> tuple[PageResult, np.ndarray]:
    s = cfg["work_scale"]
    if manual is not None:
        corners_full = np.array(manual, dtype=np.float32)
        source = "manuel"
    else:
        b = binarize(gray_work, cfg["binarization"])
        c = detect_corners(b, cfg, side)
        corners_full = (c + np.array([x_off, 0], dtype=np.float32)) / s
        source = "auto"
    page, margin = warp(img, corners_full, cfg["table"]["warp_margin_frac"])
    pr = PageResult(side, corners_full.round(1).tolist(), source, size=page.shape[:2],
                    table_top=margin, table_bottom=page.shape[0] - 1 - margin)
    # structure à l'échelle de travail, sur la page redressée
    pw = cv2.resize(cv2.cvtColor(page, cv2.COLOR_BGR2GRAY), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    hmask, vmask = line_masks(binarize(pw, cfg["binarization"]), cfg["lines"])
    cols, seen = detect_columns(vmask, cfg["columns_template"][side], cfg["table"])
    pr.columns = [round(x / s) for x in cols]
    expected = cfg["table"]["columns_per_page"] + 1
    if cols[0] < 0 or cols[-1] >= vmask.shape[1]:
        pr.flags.append("tableau hors du cadre redressé")
        return pr, page
    if seen < expected - cfg["table"]["column_max_missing"]:
        pr.flags.append(f"{seen} traits de colonnes sur {expected} retrouvés")
        return pr, page
    if seen < expected:
        pr.warnings.append(f"{expected - seen} trait(s) de colonne placé(s) d'après le gabarit")
    try:
        rows, pr.warnings = detect_rows(pw, cols, int(margin * s), cfg["table"])
        pr.rows = [[round(y / s) for y in sep] for sep in rows]
    except SegmentationError as e:
        pr.flags.append(str(e))
    return pr, page


def draw_page(page: np.ndarray, pr: PageResult) -> np.ndarray:
    dbg = page.copy()
    H, W = dbg.shape[:2]
    for x in pr.columns:
        cv2.line(dbg, (x, 0), (x, H), (255, 0, 0), 5)
    for sep in pr.rows:
        for x0, x1, y in zip(pr.columns[:-1], pr.columns[1:], sep):
            cv2.line(dbg, (x0, y), (x1, y), (0, 0, 255), 6)
    for i, (a, b) in enumerate(zip(pr.rows[:-1], pr.rows[1:]), 1):
        cv2.putText(dbg, f"{i}", (10, (a[0] + b[0]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 255), 6)
    for k, f in enumerate(pr.flags):
        cv2.putText(dbg, f, (20, 80 + 70 * k), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
    return dbg


def save(path: Path, img: np.ndarray, quality: int, max_side: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if max_side and max(img.shape[:2]) > max_side:
        f = max_side / max(img.shape[:2])
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, quality])


def export_crops(photo: str, pages: dict, results: dict, cfg: dict, data: Path):
    """Cellules : bande [séparateur haut, séparateur bas] propre à chaque colonne.
    Demi-ligne : cellules juxtaposées, ramenées à la même hauteur (redresse la courbure par morceaux)."""
    ex, q = cfg["export"], cfg["export"]["jpeg_quality"]
    rows_dir, cells_dir = data / "rows" / photo, data / "cells" / photo
    for d in (rows_dir, cells_dir):
        shutil.rmtree(d, ignore_errors=True)
    full_rows = []
    for i in range(cfg["table"]["rows_per_page"]):
        halves = []
        for side in ("left", "right"):
            page, pr = pages[side], results[side]
            H, W = page.shape[:2]
            strips = []
            for c, name in enumerate(cfg["columns"][side]):
                x0, x1 = pr.columns[c], pr.columns[c + 1]
                y0, y1 = pr.rows[i][c], pr.rows[i + 1][c]
                pad = int(ex["row_pad_frac"] * (y1 - y0))
                y0, y1 = max(0, y0 - pad), min(H, y1 + pad)
                cp = int(ex["cell_pad_frac"] * (x1 - x0))
                save(cells_dir / f"r{i + 1:02d}" / f"{name}.jpg", page[y0:y1, max(0, x0 - cp):min(W, x1 + cp)], q)
                strips.append(page[y0:y1, x0:x1])
            h = int(np.median([s.shape[0] for s in strips]))
            row = np.hstack([cv2.resize(s, (s.shape[1], h), interpolation=cv2.INTER_AREA) for s in strips])
            save(rows_dir / f"r{i + 1:02d}_{side}.jpg", row, q)
            halves.append(row)
        h = max(x.shape[0] for x in halves)
        halves = [cv2.resize(x, (int(x.shape[1] * h / x.shape[0]), h)) for x in halves]
        sep = np.full((h, 12, 3), 255, np.uint8)
        full = np.hstack([halves[0], sep, halves[1]])
        save(rows_dir / f"r{i + 1:02d}.jpg", full, q)
        full_rows.append(full)
    # planche de contrôle : toutes les lignes empilées
    w = 2400
    sheet = []
    for k, r in enumerate(full_rows, 1):
        r = cv2.resize(r, (w, int(r.shape[0] * w / r.shape[1])))
        cv2.putText(r, f"{k}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)
        sheet += [r, np.full((6, w, 3), (0, 0, 200), np.uint8)]
    save(data / "debug" / photo / "rows.jpg", np.vstack(sheet), 85)


def segment_photo(path: Path, cfg: dict, data: Path) -> dict:
    photo = path.stem
    img = cv2.imread(str(path))
    if img is None:
        raise SegmentationError(f"image illisible : {path}")
    s = cfg["work_scale"]
    gray = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    hmask, _ = line_masks(binarize(gray, cfg["binarization"]), cfg["lines"])
    gutter = find_gutter(gray, hmask, cfg["gutter"])
    manual_path = data / "corners" / f"{photo}.json"
    manual = json.loads(manual_path.read_text()) if manual_path.exists() else {}

    results, pages, flags, warnings = {}, {}, [], []
    ov = int(cfg["gutter"]["overlap_frac"] * gray.shape[1])
    for side, sl, x_off in (("left", slice(0, gutter + ov), 0), ("right", slice(gutter - ov, None), gutter - ov)):
        try:
            pr, page = segment_page(img, gray[:, sl], x_off, side, cfg, manual.get(side))
        except SegmentationError as e:
            pr, page = PageResult(side, [], "auto", flags=[f"page {side} : {e}"]), None
        results[side], pages[side] = pr, page
        flags += [f"{side}: {f}" for f in pr.flags]
        warnings += [f"{side}: {w}" for w in pr.warnings]
        if page is not None:
            save(data / "debug" / photo / f"page_{side}.jpg", draw_page(page, pr), 80, 1600)

    # contrôle d'appariement : la ligne i de gauche doit être la ligne i de droite. Ramenés à la hauteur
    # du tableau (bord haut → bord bas), les séparateurs des deux pages doivent coïncider.
    if not flags and all(results[k].rows for k in ("left", "right")):
        rel = {}
        for k in ("left", "right"):
            pr = results[k]
            ys = np.array([np.median(sep) for sep in pr.rows], float)
            top, bot = pr.table_top, pr.table_bottom
            rel[k] = (ys - top) / (bot - top)
        d = float(np.max(np.abs(rel["left"] - rel["right"])))
        if d > cfg["table"]["pair_max_rel_diff"]:
            flags.append(f"lignes gauche/droite non appariées (écart relatif {d:.2f})")

    # vue d'ensemble : reliure + quadrilatères
    ov = img.copy()
    cv2.line(ov, (int(gutter / s), 0), (int(gutter / s), ov.shape[0]), (0, 200, 255), 8)
    for pr in results.values():
        if pr.corners:
            cv2.polylines(ov, [np.array(pr.corners, np.int32)], True, (0, 0, 255), 8)
    save(data / "debug" / photo / "overview.jpg", ov, 80, 1600)

    status = "ok" if not flags else "flagged"
    if status == "ok":
        export_crops(photo, pages, results, cfg, data)
    rec = {"photo": photo, "status": status, "flags": flags, "warnings": warnings, "gutter_x": round(gutter / s),
           "pages": {k: vars(v) for k, v in results.items()}}
    out = data / "segmentation" / f"{photo}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=list), encoding="utf-8")
    return rec


def write_review_page(report: list[dict], data: Path):
    """Page HTML locale (data/debug/index.html) pour relire les crops : vue d'ensemble et planche de lignes."""
    import html
    parts = ["<!doctype html><meta charset='utf-8'><title>Contrôle de la segmentation</title>",
             "<style>body{font:14px system-ui;margin:16px;background:#fafafa;color:#222}"
             "section{margin:0 0 40px}img{max-width:100%;border:1px solid #ccc}"
             ".ok{color:#1a7f37}.flagged,.failed{color:#c00}.warn{color:#9a6700}"
             ".grid{display:grid;grid-template-columns:1fr 2fr;gap:12px;align-items:start}</style>",
             "<h1>Contrôle de la segmentation</h1>",
             "<p>Pour chaque photo : reliure (jaune), tableaux détectés (rouge) et planche des 10 lignes "
             "(page gauche + page droite côte à côte). Vérifier que la ligne <i>i</i> de gauche et de droite "
             "concernent le même malade. Crops : <code>data/rows/</code>, <code>data/cells/</code>.</p>"]
    for r in report:
        ph = html.escape(r["photo"])
        parts.append(f"<section><h2>{ph} — <span class='{r['status']}'>{r['status']}</span></h2>")
        for f in r.get("flags", []):
            parts.append(f"<p class='flagged'>⚠ {html.escape(f)}</p>")
        for w in r.get("warnings", []):
            parts.append(f"<p class='warn'>• {html.escape(w)}</p>")
        rows = f"{ph}/rows.jpg" if (data / "debug" / r["photo"] / "rows.jpg").exists() and r["status"] == "ok" else None
        parts.append(f"<div class='grid'><a href='{ph}/overview.jpg'><img src='{ph}/overview.jpg'></a>"
                     + (f"<a href='{rows}'><img src='{rows}'></a>" if rows else "<p>pas de crops exportés</p>")
                     + "</div></section>")
    (data / "debug" / "index.html").write_text("\n".join(parts), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="gold/photos")
    ap.add_argument("--config", default="configs/segmentation.yaml")
    ap.add_argument("--data", default="data")
    ap.add_argument("--only", nargs="*", help="noms de photos (sans extension)")
    args = ap.parse_args(argv)
    cfg = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    data = ROOT / args.data
    photos = sorted(p for p in (ROOT / args.input).iterdir() if p.suffix.lower() in PHOTO_EXT)
    if args.only:
        photos = [p for p in photos if p.stem in args.only]
    report = []
    for p in photos:
        try:
            rec = segment_photo(p, cfg, data)
        except SegmentationError as e:
            rec = {"photo": p.stem, "status": "failed", "flags": [str(e)]}
        report.append(rec)
        print(f"{rec['photo']}: {rec['status']}" + (f" — {'; '.join(rec['flags'])}" if rec["flags"] else ""))
    with (data / "segmentation" / "report.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["photo", "status", "flags"])
        for r in report:
            w.writerow([r["photo"], r["status"], " | ".join(r["flags"])])
    write_review_page(report, data)
    ok = sum(r["status"] == "ok" for r in report)
    print(f"→ {ok}/{len(report)} photos segmentées sans drapeau ; contrôle : {args.data}/debug/<photo>/")


if __name__ == "__main__":
    main()
