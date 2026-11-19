"""Band, strip and tile arithmetic of the Large-image engine (engine design sections 2.2-2.5). Pure Python; no image.

Every banded pass reads a plane in full-width row bands (or full-height column strips for column passes) and writes only the
band's core rows; the halo rows it reads are real image rows, and the image's own border rule (reflection, clamping) applies
only at the true image border. A band height is ALWAYS one of the registered heights (gate G1 proved band-invariance at exactly
these heights; anything else is a programming error, not an adaptation), and band starts fall on multiples of ALIGN rows (288,
the least common multiple of every pooling factor of the finish), so pooled grids see whole cells.

The x4 model's margin tiling (ClaudeUpscaleModelTiled, node_pack/claude_creative/__init__.py margin_tiled_upscale) is
reproduced here as geometry: the same tile starts, cores, input crops and blend ramps, so a banded run adds the same products
in the same order (tile rows outer, tiles inner) to every output pixel."""
from dataclasses import dataclass

BAND_HEIGHTS = (288, 576, 1152, 2304)       # registered band heights (G1); the last band of a plane is the remainder
PROCESS_COUNTS = (4, 2, 1)                  # registered finish process counts; shrinking stays inside this set
ALIGN = 288                                 # band starts are multiples of this (LCM of the finish's pooling factors 2-48)


@dataclass(frozen=True)
class Band:
    index: int
    start: int          # first core row
    stop: int           # one past the last core row
    read_start: int     # first row read (core minus halo, clipped to the image)
    read_stop: int      # one past the last row read

    @property
    def rows(self):
        return self.stop - self.start

    @property
    def core_offset(self):
        """Index of the first core row inside the rows read."""
        return self.start - self.read_start


def check_band_height(h):
    if h not in BAND_HEIGHTS:
        raise AssertionError(f'band height {h} is not a registered height {BAND_HEIGHTS}')
    return h


def check_process_count(n):
    if n not in PROCESS_COUNTS:
        raise AssertionError(f'process count {n} is not a registered count {PROCESS_COUNTS}')
    return n


def shrink_processes(n):
    """The next registered process count below n (at least 1)."""
    check_process_count(n)
    lower = [c for c in PROCESS_COUNTS if c < n]
    return max(lower) if lower else 1


def band_height_for(width, bytes_per_row_px, budget_bytes, halo=0):
    """The largest registered band height whose rows (core plus 2 x halo) fit the budget; the smallest when none does (the
    band budget then names the overrun; it is counted, never silently changed to an unregistered height)."""
    for h in sorted(BAND_HEIGHTS, reverse=True):
        if (h + 2 * halo) * width * bytes_per_row_px <= budget_bytes:
            return h
    return BAND_HEIGHTS[0]


def bands(total, height, halo=0):
    """Row bands of a plane of `total` rows: cores of `height` rows (the last is the remainder) starting at multiples of
    `height` (so of ALIGN), each read with `halo` real rows above and below, clipped to the image."""
    check_band_height(height)
    if total <= 0:
        return []
    out = []
    for i, s in enumerate(range(0, total, height)):
        e = min(total, s + height)
        out.append(Band(i, s, e, max(0, s - halo), min(total, e + halo)))
    return out


def strips(total, width, halo=0):
    """Column strips (full height) for column passes: the same rule along x. Any width is allowed for a strip: a column
    pass is exact for any split because each column is processed whole."""
    if width <= 0:
        raise ValueError('strip width must be positive')
    return [Band(i, s, min(total, s + width), max(0, s - halo), min(total, s + width + halo))
            for i, s in enumerate(range(0, total, width))]


def covers(parts, total):
    """True when the cores tile [0, total) exactly once, in order."""
    pos = 0
    for b in parts:
        if b.start != pos or b.stop <= b.start:
            return False
        pos = b.stop
    return pos == total


# --- the x4 model's margin tiling, as geometry ---------------------------------------------------------------------------

def dat_starts(n, tile=512, margin=64, blend=16):
    """margin_tiled_upscale's tile starts along one axis of n input pixels."""
    core = tile - 2 * margin
    step = core - blend
    if n <= tile:
        return [0]
    s = list(range(0, n - core, step)) + [n - core]
    return sorted(set(max(0, min(n - core, v)) for v in s))


@dataclass(frozen=True)
class DatTile:
    y: int
    x: int
    cy0: int
    cy1: int
    cx0: int
    cx1: int
    iy0: int
    iy1: int
    ix0: int
    ix1: int
    lo_y: bool          # the ramp is flat at the low end (image border or one tile)
    hi_y: bool
    lo_x: bool
    hi_x: bool


def dat_tile_rows(H, W, tile=512, margin=64, blend=16):
    """[[DatTile]]: the classic tiles in the classic order (y outer, x inner), grouped by tile row. One tile when the image
    fits in one tile (the classic then evaluates it whole)."""
    if tile <= 2 * margin + blend:
        raise ValueError('tile must exceed 2 * margin + blend')
    core = tile - 2 * margin
    rows = []
    for y in dat_starts(H, tile, margin, blend):
        row = []
        for x in dat_starts(W, tile, margin, blend):
            cy0, cy1 = (0, H) if H <= tile else (y, y + core)
            cx0, cx1 = (0, W) if W <= tile else (x, x + core)
            row.append(DatTile(y, x, cy0, cy1, cx0, cx1, max(0, cy0 - margin), min(H, cy1 + margin), max(0, cx0 - margin),
                               min(W, cx1 + margin), cy0 == 0 or H <= tile, cy1 == H or H <= tile, cx0 == 0 or W <= tile,
                               cx1 == W or W <= tile))
        rows.append(row)
    return rows


def dat_final_rows(rows, H, scale=4):
    """For each tile row i: the output rows [lo, hi) that are final once tile rows 0..i are added (no later tile touches
    them). Their union is [0, H * scale), in order. This is where a banded accumulator flushes `acc / wsum`."""
    out, done = [], 0
    for i, r in enumerate(rows):
        nxt = rows[i + 1][0].cy0 * scale if i + 1 < len(rows) else H * scale
        out.append((done, nxt))
        done = nxt
    return out


def dat_live_rows(rows, scale=4):
    """The most output rows the banded accumulator holds at once (its band, for the memory model's 2560-row term)."""
    most, done = 0, 0
    for i, r in enumerate(rows):
        hi = r[0].cy1 * scale
        most = max(most, hi - done)
        if i + 1 < len(rows):
            done = rows[i + 1][0].cy0 * scale
    return most


# --- seams ----------------------------------------------------------------------------------------------------------------

def join_rows(parts):
    """The rows where one band's core meets the next: where a seam detector looks (engine design section 5, Q3b)."""
    return [b.start for b in parts[1:]]
