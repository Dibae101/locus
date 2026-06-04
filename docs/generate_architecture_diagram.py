"""
Generates the Locus layered architecture diagram as a PNG (and SVG).

Run:
    python docs/generate_architecture_diagram.py

Requires matplotlib (see docs/requirements-diagram.txt).
Outputs: docs/architecture.png, docs/architecture.svg

Layout is explicit-coordinate (not auto-layout) so the layered bands stack
deterministically and connectors never cross boxes:
  - Main stack (left):  USER -> LAYER 2 -> LAYER 1   (top to bottom)
  - Right sidebar:      LOCUS HUB (beside L2), OPTIONAL EXTERNAL (beside L1)
"""

import matplotlib

matplotlib.use("Agg")
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.pyplot as plt

# ---- palette -------------------------------------------------------------
C_BG = "#ffffff"
C_TXT = "#1f2933"
C_MUTED = "#52606d"
C_USER, C_USER_E = "#e8eef7", "#3b6cb7"
C_L2, C_L2_E = "#e9f3ec", "#2e8b57"
C_L1, C_L1_E = "#fdf0e3", "#c07d1f"
C_HUB, C_HUB_E = "#efe9f7", "#7a4fb5"
C_EXT, C_EXT_E = "#fdeaea", "#c0504d"
C_BOX = "#ffffff"

fig, ax = plt.subplots(figsize=(16, 11), dpi=150)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")
fig.patch.set_facecolor(C_BG)

# ---- geometry ------------------------------------------------------------
STACK_X, STACK_W = 4, 60          # main vertical stack
SIDE_X, SIDE_W = 68, 28           # right sidebar


def band(x, y, w, h, fc, ec, label, sub=None):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0",
        linewidth=2.2, edgecolor=ec, facecolor=fc, zorder=1))
    ax.text(x + 1.5, y + h - 1.8, label, fontsize=12.5, fontweight="bold",
            color=ec, zorder=3, va="top", ha="left")
    if sub:
        ax.text(x + 1.5, y + h - 4.0, sub, fontsize=8.3, color=C_MUTED,
                zorder=3, va="top", ha="left", style="italic")


def box(x, y, w, h, text, ec, fc=C_BOX, fs=8.8, bold=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.6",
        linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=4))
    ax.text(x + w / 2, y + h / 2, text, fontsize=fs, color=C_TXT, zorder=5,
            ha="center", va="center", fontweight="bold" if bold else "normal")


def arrow(x1, y1, x2, y2, color, dashed=False, lw=2.0, both=False):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="<|-|>" if both else "-|>", mutation_scale=15,
        linewidth=lw, color=color, zorder=6,
        linestyle="--" if dashed else "-",
        shrinkA=0, shrinkB=0))


def label(x, y, text, color, fs=8.2):
    ax.text(x, y, text, fontsize=fs, color=color, ha="center", va="center",
            zorder=7, bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                ec="none", alpha=0.9))


# ---- title ---------------------------------------------------------------
ax.text(50, 98.5, "Locus — Layered Architecture", fontsize=19,
        fontweight="bold", color=C_TXT, ha="center", va="top")
ax.text(50, 95.0,
        "Unstructured corpus  ->  validated, source-grounded tabular data",
        fontsize=10.5, color=C_MUTED, ha="center", va="top", style="italic")

# ---- USER band -----------------------------------------------------------
uy, uh = 82.5, 11
band(STACK_X, uy, STACK_W, uh, C_USER, C_USER_E, "USER'S MACHINE",
     "local · no daemon / no Linux VM required")
uby = uy + 0.8
box(7, uby, 18, 4.0, "Locus CLI\n(pip install locus)", C_USER_E, bold=True)
box(27, uby, 17, 4.0, "Locusfile\n(YAML)", C_USER_E)
box(46, uby, 15, 4.0, ".env\n(local keys)", C_USER_E)

# ---- LAYER 2 band --------------------------------------------------------
l2y, l2h = 55, 26
band(STACK_X, l2y, STACK_W, l2h, C_L2, C_L2_E,
     "LAYER 2 — locus-image-runtime",
     "packaging · distribution · CLI · composition · serving")
r1 = l2y + 14
box(6, r1, 13, 6, "Pull &\nlocal cache", C_L2_E)
box(21, r1, 14, 6, "Compose\npipeline (DAG)", C_L2_E)
box(37, r1, 13, 6, "Author·build\n· publish", C_L2_E)
box(52, r1, 10, 6, "Serve UI\n· export", C_L2_E)
r2 = l2y + 4.5
box(6, r2, 22, 7, "Stage interchange contract\ntyped Locus_Artifact +\nstatic type-check (fail fast)", C_L2_E, fs=8.0)
box(30, r2, 19, 7, "Cross-stage\nprovenance propagation\n(managed lineage)", C_L2_E, fs=8.0)
box(51, r2, 11, 7, "Run\nworkspace +\nLineage_Store", C_L2_E, fs=8.0)

# ---- LAYER 1 band --------------------------------------------------------
l1y, l1h = 22, 28
band(STACK_X, l1y, STACK_W, l1h, C_L1, C_L1_E,
     "LAYER 1 — unstructured-to-tabular-etl  (engine, in every image)",
     "raw corpus -> validated, source-grounded table")
stages = [
    ("Ingest", "files·URLs·\nAPIs·DBs"),
    ("Parse", "normalize ->\nInterm. Rep."),
    ("Extract", "determ. default\n· LLM opt-in"),
    ("Clean", "coerce · dedup\n/ entity res."),
    ("Ground", "faithfulness\n+ flag/reject"),
    ("Emit", "table +\nlineage"),
]
sw, gap = 8.6, 1.2
sx = 5.5
sy = l1y + 11
stage_cx = []
for i, (t, sub) in enumerate(stages):
    x = sx + i * (sw + gap)
    box(x, sy, sw, 8, f"{t}\n\n{sub}", C_L1_E, fs=8.0, bold=False)
    stage_cx.append(x + sw / 2)
    if i < len(stages) - 1:
        arrow(x + sw, sy + 4, x + sw + gap, sy + 4, C_L1_E, lw=1.5)
# review feedback row beneath the engine flow
box(16, l1y + 2.5, 36, 5, "Human-in-the-loop review & correction feedback",
    C_L1_E, fc="#fbe7cf", fs=8.6)
# dashed feedback loop Ground -> review -> Emit
arrow(stage_cx[4], sy, stage_cx[4], l1y + 7.5, C_L1_E, dashed=True, lw=1.4)
arrow(stage_cx[5], l1y + 7.5, stage_cx[5], sy, C_L1_E, dashed=True, lw=1.4)

# ---- right sidebar: HUB (beside L2) + EXTERNAL (beside L1) ----------------
hy, hh = 63, 12
band(SIDE_X, hy, SIDE_W, hh, C_HUB, C_HUB_E, "LOCUS HUB",
     "Harbor registry · public + private")
box(SIDE_X + 2, hy + 1.2, SIDE_W - 4, 5.0,
    "Versioned images +\nmanifests (OCI artifacts,\nnamespaces, RBAC)", C_HUB_E, fs=8.0)

ey, eh = 30, 12
band(SIDE_X, ey, SIDE_W, eh, C_EXT, C_EXT_E, "OPTIONAL EXTERNAL",
     "only if user adds an LLM key")
box(SIDE_X + 2, ey + 1.2, SIDE_W - 4, 5.0,
    "LLM provider via LiteLLM\n(consent shown before\ndata leaves)", C_EXT_E, fs=8.0)

# ---- cross-layer connectors (no box crossings) ---------------------------
# USER -> LAYER 2
arrow(15, uy, 15, l2y + l2h, C_USER_E, lw=2.4)
label(15, (uy + l2y + l2h) / 2, "run", C_USER_E)
# LAYER 2 -> LAYER 1
arrow(33, l2y, 33, l1y + l1h, C_L2_E, lw=2.4)
label(33, (l2y + l1y + l1h) / 2, "runs engine", C_L2_E)
# LAYER 2 <-> HUB  (horizontal, into sidebar)
arrow(STACK_X + STACK_W, hy + hh / 2, SIDE_X, hy + hh / 2, C_HUB_E,
      dashed=True, lw=2.0, both=True)
label((STACK_X + STACK_W + SIDE_X) / 2, hy + hh / 2 + 2.2, "OCI\npull/push",
      C_HUB_E, fs=7.6)
# LAYER 1 (Extract/Ground) -> EXTERNAL (horizontal)
arrow(STACK_X + STACK_W, ey + eh / 2, SIDE_X, ey + eh / 2, C_EXT_E,
      dashed=True, lw=2.0)
label((STACK_X + STACK_W + SIDE_X) / 2, ey + eh / 2 + 2.2, "opt-in\n+ consent",
      C_EXT_E, fs=7.6)

# ---- legend --------------------------------------------------------------
ax.plot([], [], color=C_MUTED, linestyle="-", linewidth=2,
        label="data / control flow")
ax.plot([], [], color=C_MUTED, linestyle="--", linewidth=2,
        label="optional / opt-in path")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.01), ncol=2,
          frameon=False, fontsize=9.5)

plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.04)
plt.savefig("docs/architecture.png", dpi=150, facecolor=C_BG,
            bbox_inches="tight")
plt.savefig("docs/architecture.svg", facecolor=C_BG, bbox_inches="tight")
print("wrote docs/architecture.png and docs/architecture.svg")
