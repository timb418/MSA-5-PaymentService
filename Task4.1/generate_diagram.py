#!/usr/bin/env python3
"""
OrchestrPay — Payment Process BPMN diagram.
Uses matplotlib for precise, clean layout with zero text overlap.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

# ── Canvas ────────────────────────────────────────────────────────────────────
FIG_W, FIG_H = 28, 13
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "blue":   "#BBDEFB",   # normal service task
    "yellow": "#FFF9C4",   # pivot / timer
    "purple": "#E1BEE7",   # waiting user task
    "green":  "#C8E6C9",   # success tasks
    "red":    "#FFCDD2",   # compensation tasks
    "pink":   "#F8BBD0",   # security alert
    "gw":     "#FFE0B2",   # gateway fill
    "start":  "#2E7D32",   # start event
    "end_ok": "#1B5E20",   # end success
    "end_er": "#B71C1C",   # end refunded
    "lane_a": "#F0F8FF",   # swim lane A background
    "lane_b": "#FAF0FF",   # swim lane B background
    "lane_c": "#FFF5F5",   # swim lane C background
}

# Edge colors
E = {
    "main":  "#1B5E20",
    "timer": "#E65100",
    "comp":  "#C62828",
    "alert": "#880E4F",
    "def":   "#424242",
}

# ── Layout constants ───────────────────────────────────────────────────────────
TW, TH = 2.4, 1.1     # task width / height
GS = 0.6               # gateway half-diagonal
RS = 0.35              # event radius
FS = 8.5               # task label font size
FG = 7.0               # gateway label font size
FE = 7.0               # edge label font size

# Row Y centres
R_A = 10.5   # happy path
R_B =  6.5   # manual review
R_C =  2.5   # compensation

# ── Node positions  {id: (x, y)} ─────────────────────────────────────────────
POS = {
    # Row A
    "start":       ( 0.7,  R_A),
    "create":      ( 2.6,  R_A),
    "debit":       ( 5.3,  R_A),
    "fraud_check": ( 8.0,  R_A),
    "fraud_gw":    (10.7,  R_A),
    "merge_gw":    (13.1,  R_A),
    "transfer":    (15.6,  R_A),
    "update_ok":   (18.5,  R_A),
    "notify_ok":   (21.4,  R_A),
    "end_ok":      (24.0,  R_A),
    # Row B
    "manual_review":(10.7, R_B),
    "cutoff":      (12.2,  R_B - 1.5),
    "manual_gw":   (13.1,  R_B),
    # Row C
    "credit":      (13.1,  R_C),
    "cancel":      (15.6,  R_C),
    "update_fail": (18.0,  R_C),
    "notify_fail": (20.3,  R_C),
    "fraud_flag":  (22.6,  R_C),
    "notify_sec":  (24.7,  R_C),
    "end_refunded":(26.8,  R_C),
}

# ── Geometry helpers ──────────────────────────────────────────────────────────
def p(nid): return POS[nid]
def px(nid): return POS[nid][0]
def py(nid): return POS[nid][1]

def r(nid):    return (px(nid) + TW/2,  py(nid))
def l(nid):    return (px(nid) - TW/2,  py(nid))
def t(nid):    return (px(nid),          py(nid) + TH/2)
def b(nid):    return (px(nid),          py(nid) - TH/2)
def rg(nid):   return (px(nid) + GS,    py(nid))
def lg(nid):   return (px(nid) - GS,    py(nid))
def tg(nid):   return (px(nid),          py(nid) + GS)
def bg(nid):   return (px(nid),          py(nid) - GS)
def re(nid):   return (px(nid) + RS,    py(nid))
def le(nid):   return (px(nid) - RS,    py(nid))
def te(nid):   return (px(nid),          py(nid) + RS)
def be(nid):   return (px(nid),          py(nid) - RS)
def rc(nid):   return (px(nid) + 0.22,  py(nid))  # timer circle right
def bc(nid):   return (px(nid),          py(nid) - 0.22)


# ── Drawing functions ─────────────────────────────────────────────────────────

def draw_lane(y_ctr, label, color, height=3.8):
    """Horizontal swim lane background."""
    bg = FancyBboxPatch(
        (0.15, y_ctr - height/2), FIG_W - 0.3, height,
        boxstyle="round,pad=0.0", linewidth=0.8,
        facecolor=color, edgecolor="#BBBBBB", alpha=0.4, zorder=0
    )
    ax.add_patch(bg)
    ax.text(0.32, y_ctr, label, ha="left", va="center",
            fontsize=7, color="#666666", style="italic",
            rotation=90, zorder=1)


def draw_task(nid, label, color, bold=False, width=TW):
    x, y = POS[nid]
    lw = 2.0 if bold else 1.0
    rect = FancyBboxPatch(
        (x - width/2, y - TH/2), width, TH,
        boxstyle="round,pad=0.08",
        facecolor=color, edgecolor="#333333", linewidth=lw, zorder=3
    )
    ax.add_patch(rect)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=FS, family="DejaVu Sans",
            multialignment="center", zorder=4,
            linespacing=1.3)


def draw_gateway(nid, label, color=C["gw"]):
    x, y = POS[nid]
    diamond = plt.Polygon(
        [[x, y+GS], [x+GS, y], [x, y-GS], [x-GS, y]],
        facecolor=color, edgecolor="#333333", linewidth=1.2, zorder=3
    )
    ax.add_patch(diamond)
    ax.text(x, y, "✕", ha="center", va="center",
            fontsize=9, color="#555555", zorder=5)
    ax.text(x, y - GS - 0.22, label, ha="center", va="top",
            fontsize=FG - 0.5, family="DejaVu Sans",
            multialignment="center", color="#333333", zorder=4)


def draw_start(nid):
    x, y = POS[nid]
    c = plt.Circle((x, y), RS, facecolor=C["start"],
                    edgecolor="white", linewidth=2, zorder=3)
    ax.add_patch(c)
    ax.text(x, y - RS - 0.2, "START", ha="center", va="top",
            fontsize=FG, family="DejaVu Sans",
            color=C["start"], fontweight="bold")


def draw_end(nid, label, color):
    x, y = POS[nid]
    outer = plt.Circle((x, y), RS,
                        facecolor=color, edgecolor=color, linewidth=3, zorder=3)
    inner = plt.Circle((x, y), RS * 0.65,
                        facecolor="white", edgecolor="white", linewidth=1, zorder=4)
    dot   = plt.Circle((x, y), RS * 0.30,
                        facecolor=color, edgecolor=color, zorder=5)
    ax.add_patch(outer); ax.add_patch(inner); ax.add_patch(dot)
    ax.text(x, y - RS - 0.2, label, ha="center", va="top",
            fontsize=FG, family="DejaVu Sans",
            color=color, fontweight="bold", multialignment="center")


def draw_timer(nid):
    x, y = POS[nid]
    c = plt.Circle((x, y), 0.25, facecolor=C["yellow"],
                    edgecolor="#888888", linewidth=1, linestyle="--", zorder=3)
    ax.add_patch(c)
    ax.text(x, y, "T", ha="center", va="center",
            fontsize=9, fontweight="bold", color="#E65100", zorder=4)
    ax.text(x, y - 0.42, "CUT-OFF\n20 мин", ha="center", va="top",
            fontsize=5.8, color="#E65100", multialignment="center")


def arrow(p1, p2, via=None, label="", col=E["def"],
          lbl_frac=0.5, lbl_dy=0.2, lw=1.4):
    """Draw polyline with arrowhead at p2, optional label."""
    pts = [p1] + (via or []) + [p2]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    ax.plot(xs, ys, color=col, linewidth=lw, zorder=2, solid_capstyle="round")
    # Arrowhead
    dx, dy = pts[-1][0]-pts[-2][0], pts[-1][1]-pts[-2][1]
    ln = np.hypot(dx, dy)
    if ln > 0:
        ax.annotate("", xy=p2,
                    xytext=(p2[0] - dx/ln*0.01, p2[1] - dy/ln*0.01),
                    arrowprops=dict(arrowstyle="-|>", color=col,
                                    lw=lw, mutation_scale=12),
                    zorder=2)
    # Label
    if label:
        # Place label at fraction along the polyline
        total = sum(np.hypot(pts[i+1][0]-pts[i][0],
                             pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))
        target = total * lbl_frac
        acc = 0.0
        mx, my = pts[0]
        for i in range(len(pts)-1):
            seg = np.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
            if acc + seg >= target:
                t = (target - acc) / seg if seg > 0 else 0
                mx = pts[i][0] + t*(pts[i+1][0]-pts[i][0])
                my = pts[i][1] + t*(pts[i+1][1]-pts[i][1])
                break
            acc += seg
        ax.text(mx, my + lbl_dy, label, ha="center", va="bottom",
                fontsize=FE, color=col, family="DejaVu Sans",
                multialignment="center",
                bbox=dict(facecolor="white", edgecolor="none",
                          pad=1.0, alpha=0.92),
                zorder=6)


# ═════════════════════════════════════════════════════════════════════════════
#  DRAW SWIM LANES
# ═════════════════════════════════════════════════════════════════════════════
draw_lane(R_A, "① Счастливый путь (Happy Path)", C["lane_a"], height=3.5)
draw_lane(R_B, "② Ручная проверка (Manual Review)", C["lane_b"], height=3.5)
draw_lane(R_C, "③ Компенсация (Compensation)", C["lane_c"], height=3.5)

# ═════════════════════════════════════════════════════════════════════════════
#  DRAW NODES
# ═════════════════════════════════════════════════════════════════════════════

# ── Row A ──────────────────────────────────────────────────────────────────
draw_start("start")
draw_task("create",      "CREATE_PAYMENT\nСоздать платёж в БД",      C["blue"])
draw_task("debit",       "DEBIT_ACCOUNT\nЗарезервировать\nсредства", C["blue"])
draw_task("fraud_check", "FRAUD_CHECK\nАнтифрод-проверка",           C["blue"])
draw_gateway("fraud_gw", "Результат\nантифрода")
draw_gateway("merge_gw", "Одобрено\n(merge)")
draw_task("transfer",    "TRANSFER_FUNDS\nПеревод контрагенту\n★ PIVOT POINT",
          C["yellow"], bold=True)
draw_task("update_ok",   "UPDATE_STATUS\n→ COMPLETED",               C["green"])
draw_task("notify_ok",   "NOTIFY_CLIENT\nSUCCESS",                   C["green"])
draw_end("end_ok",  "COMPLETED ✔", C["end_ok"])

# ── Row B ──────────────────────────────────────────────────────────────────
draw_task("manual_review",
          "WAIT_MANUAL_REVIEW\nОжидание решения\nоператора  (max 20 мин)",
          C["purple"])
draw_timer("cutoff")
draw_gateway("manual_gw", "Решение\nоператора")

# ── Row C ──────────────────────────────────────────────────────────────────
draw_task("credit",      "CREDIT_ACCOUNT\nВозврат средств",          C["red"])
draw_task("cancel",      "CANCEL_PAYMENT\nОтмена платежа",           C["red"])
draw_task("update_fail", "UPDATE_STATUS\n→ REFUNDED",                C["red"])
draw_task("notify_fail", "NOTIFY_CLIENT\nFAILURE",                   C["red"])
draw_gateway("fraud_flag", "Мошен-\nничество?")
draw_task("notify_sec",  "NOTIFY_SECURITY\nАлерт службе\nбезопасности [!]",
          C["pink"], bold=True, width=2.4)
draw_end("end_refunded", "REFUNDED ↩", C["end_er"])

# ═════════════════════════════════════════════════════════════════════════════
#  DRAW ARROWS
# ═════════════════════════════════════════════════════════════════════════════

# ── Row A: main happy path ─────────────────────────────────────────────────
arrow(re("start"),    l("create"))
arrow(r("create"),    l("debit"))
arrow(r("debit"),     l("fraud_check"))
arrow(r("fraud_check"), lg("fraud_gw"))

# fraud_gw → merge_gw  (APPROVED, staying on Row A)
arrow(rg("fraud_gw"), lg("merge_gw"), label="Разрешено", col=E["main"], lbl_dy=0.18)

# merge_gw → transfer → update → notify → end
arrow(rg("merge_gw"), l("transfer"),   col=E["main"])
arrow(r("transfer"),  l("update_ok"),  col=E["main"])
arrow(r("update_ok"), l("notify_ok"),  col=E["main"])
arrow(r("notify_ok"), le("end_ok"),    col=E["main"])

# ── Row A→B: fraud_gw → manual_review ─────────────────────────────────────
arrow(bg("fraud_gw"), t("manual_review"),
      label="Ручная\nпроверка", col=E["timer"],
      lbl_dy=0.18, lbl_frac=0.4)

# ── Row A→C: fraud_gw → credit (DENIED) ───────────────────────────────────
arrow(bg("fraud_gw"), t("credit"),
      via=[(px("fraud_gw"), py("credit") + TH/2 + 0.15)],
      label="Запрет", col=E["comp"],
      lbl_dy=0.18, lbl_frac=0.35)

# ── Row B: manual review → manual_gw ─────────────────────────────────────
arrow(r("manual_review"), lg("manual_gw"))

# Timer boundary: manual_review → cutoff (dashed attachment line)
mx_attach = px("manual_review") + TW/2 * 0.4
my_attach  = py("manual_review") - TH/2
ax.plot([mx_attach, px("cutoff")], [my_attach, py("cutoff") + 0.25],
        color=E["timer"], lw=1.0, linestyle="dashed", zorder=2)
ax.text(px("cutoff") - 0.55, (my_attach + py("cutoff") + 0.25)/2,
        "таймаут", ha="right", fontsize=5.5, color=E["timer"])

# cutoff → merge_gw (auto-approve): goes right then up
arrow((px("cutoff") + 0.25, py("cutoff")),
      bg("merge_gw"),
      via=[(px("merge_gw"), py("cutoff"))],
      label="авто-одобрение\n(cut-off)", col=E["timer"],
      lbl_dy=0.15, lbl_frac=0.65)

# manual_gw → merge_gw (APPROVED by operator) — goes up to Row A
arrow(tg("manual_gw"), bg("merge_gw"),
      label="Одобрено\nоператором", col=E["main"],
      lbl_dy=0.15, lbl_frac=0.5)

# manual_gw → credit (DENIED by operator) — goes down to Row C
arrow(bg("manual_gw"), t("credit"),
      via=[(px("manual_gw"), R_C + TH/2 + 0.15)],
      label="Отклонено\nоператором", col=E["comp"],
      lbl_dy=0.15, lbl_frac=0.4)

# ── Row C: compensation chain ─────────────────────────────────────────────
arrow(r("credit"),      l("cancel"),      col=E["comp"])
arrow(r("cancel"),      l("update_fail"), col=E["comp"])
arrow(r("update_fail"), l("notify_fail"), col=E["comp"])
arrow(r("notify_fail"), lg("fraud_flag"), col=E["comp"])

# fraud_flag → notify_sec (YES, fraud)
arrow(rg("fraud_flag"), l("notify_sec"),
      label="Да\n(мошен-во)", col=E["alert"],
      lbl_dy=0.18, lbl_frac=0.5)

# fraud_flag → end_refunded (NO)
arrow(bg("fraud_flag"),
      (px("end_refunded"), py("end_refunded") + RS),
      via=[(px("fraud_flag"), R_C - 1.2), (px("end_refunded"), R_C - 1.2)],
      label="Нет", col=E["comp"],
      lbl_dy=0.12, lbl_frac=0.6)

# notify_sec → end_refunded
arrow(r("notify_sec"), le("end_refunded"), col=E["alert"])

# ═════════════════════════════════════════════════════════════════════════════
#  LEGEND & TITLE
# ═════════════════════════════════════════════════════════════════════════════

legend_items = [
    mpatches.Patch(color=C["blue"],   label="Service Task — сервисная операция"),
    mpatches.Patch(color=C["yellow"], label="★ Pivot Point — точка невозврата (TRANSFER_FUNDS)"),
    mpatches.Patch(color=C["purple"], label="User Task — ожидание решения оператора"),
    mpatches.Patch(color=C["green"],  label="Success — операции успешного пути"),
    mpatches.Patch(color=C["red"],    label="Compensation — компенсирующие операции"),
    mpatches.Patch(color=C["pink"],   label="Security Alert — уведомление о мошенничестве [!]"),
    mpatches.Patch(color=E["main"],   label="─── Успешный поток"),
    mpatches.Patch(color=E["timer"],  label="─── Таймер / ручная проверка"),
    mpatches.Patch(color=E["comp"],   label="─── Компенсация / отказ"),
]
ax.legend(handles=legend_items, loc="upper left",
          bbox_to_anchor=(0.015, 0.16),
          fontsize=7, framealpha=0.95,
          title="Легенда", title_fontsize=7.5,
          ncol=3, columnspacing=1.2, handlelength=1.2)

ax.set_title(
    "OrchestrPay — Процесс обработки платежа (BPMN)\n"
    "Saga-оркестрация: Payment Service → FraudCheck Service → Notification Service",
    fontsize=13, fontweight="bold", pad=14
)

# ── Save ──────────────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(script_dir, "payment-process.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight",
            facecolor="white", edgecolor="none")
plt.close(fig)
print(f"Diagram saved: {out_path}")
