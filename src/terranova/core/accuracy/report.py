"""PDF report rendering for an :class:`AccuracyReport`.

Uses reportlab Platypus for the document layout and matplotlib for the
confusion-matrix heatmap.  The matplotlib import is deferred so a default
install of the plugin does not need matplotlib unless the user actually
generates a report.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .metrics import AccuracyReport


def render_pdf(
    report: "AccuracyReport",
    out_path: Path,
    *,
    title: str = "Terranova — Accuracy report",
    subtitle: str | None = None,
    class_names: dict[int, str] | None = None,
) -> Path:
    """Render a one-page A4 PDF summarising an accuracy assessment.

    Sections:

    - Header (title + subtitle + timestamp)
    - Summary table (OA, kappa, n samples)
    - Confusion matrix heatmap
    - Per-class table (user's, producer's, F1)

    Parameters
    ----------
    report
        The result of :func:`accuracy.metrics.assess`.
    out_path
        Destination PDF.
    class_names
        Optional mapping of class id → display name.  Falls back to the
        integer id when missing.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --------------------------- confusion matrix heatmap --- #
    fig, ax = plt.subplots(figsize=(5.5, 4.5), dpi=150)
    cm = report.confusion_matrix
    # Use Crameri batlow (CVD-friendly).  Fall back to viridis if cmcrameri
    # is missing — matplotlib has it built in since 3.4.
    try:
        import cmcrameri  # noqa: F401

        cmap = plt.get_cmap("cmc.batlow")
    except ImportError:
        cmap = plt.get_cmap("viridis")

    im = ax.imshow(cm, cmap=cmap, aspect="auto")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pixels")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Reference")
    labels = [class_names.get(c, str(c)) if class_names else str(c) for c in report.class_labels]
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)

    # Cell value annotations — readable when total isn't too large.
    if cm.max() > 0:
        thresh = cm.max() / 2.0
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(
                    j,
                    i,
                    f"{cm[i, j]}",
                    ha="center",
                    va="center",
                    color="white" if cm[i, j] > thresh else "black",
                    fontsize=8,
                )
    fig.tight_layout()
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", bbox_inches="tight")
    plt.close(fig)
    img_buf.seek(0)

    # --------------------------- PDF assembly --------------- #
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="Terranova",
    )
    styles = getSampleStyleSheet()
    story: list = []

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    if subtitle:
        story.append(Paragraph(subtitle, styles["Heading3"]))
    story.append(
        Paragraph(
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    # Summary table
    summary = Table(
        [
            ["Overall accuracy", f"{report.overall_accuracy * 100:.1f}%"],
            ["Kappa", f"{report.kappa:.3f}"],
            ["Number of samples", f"{report.n_samples}"],
            ["Number of classes", f"{len(report.class_labels)}"],
        ],
        colWidths=[60 * mm, 50 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ECEEF1")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#8A93A0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DCE2")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary)
    story.append(Spacer(1, 6 * mm))

    # Confusion matrix image
    story.append(Paragraph("<b>Confusion matrix</b>", styles["Heading3"]))
    story.append(Image(img_buf, width=150 * mm, height=110 * mm))
    story.append(Spacer(1, 4 * mm))

    # Per-class table.  UA and PA are accuracies (0-1) so render as
    # percentages; F1 is a unitless score so stays as a 3-dp decimal.
    rows = [["Class", "User's", "Producer's", "F1"]]
    for i, lbl in enumerate(report.class_labels):
        name = class_names.get(lbl, str(lbl)) if class_names else str(lbl)
        rows.append(
            [
                name,
                _fmt_pct(report.users_accuracy[i]),
                _fmt_pct(report.producers_accuracy[i]),
                _fmt(report.f1_per_class[i]),
            ]
        )
    per_class = Table(rows, colWidths=[40 * mm, 30 * mm, 30 * mm, 30 * mm])
    per_class.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1C2A4A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DCE2")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#8A93A0")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(Paragraph("<b>Per-class accuracy</b>", styles["Heading3"]))
    story.append(per_class)

    doc.build(story)
    return out_path


def _fmt(v: float) -> str:
    import numpy as np

    if np.isnan(v):
        return "—"
    return f"{v:.3f}"


def _fmt_pct(v: float) -> str:
    """Format an accuracy in [0,1] as a percentage with one decimal."""
    import numpy as np

    if np.isnan(v):
        return "—"
    return f"{v * 100:.1f}%"
