"""Foundation-model fine-tuning via TerraTorch — Phase 2 real implementation.

Wraps the three backbones the brief calls out: Prithvi-EO-2.0 (300M / 600M),
Clay v1.5, and TerraMind.  Each fine-tunes a semantic-segmentation head on
user labels and exports the result to ONNX for fast inference via the
existing :mod:`terrascope.core.ml.inference` session cache.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    pass

Backbone = Literal[
    "prithvi_eo_v2_300",
    "prithvi_eo_v2_600",
    "clay_v1_5",
    "terramind",
]

# Bands each backbone expects.  Users supply rasters with matching band order.
BACKBONE_BANDS: dict[str, tuple[str, ...]] = {
    "prithvi_eo_v2_300": ("BLUE", "GREEN", "RED", "NIR_NARROW", "SWIR_1", "SWIR_2"),
    "prithvi_eo_v2_600": ("BLUE", "GREEN", "RED", "NIR_NARROW", "SWIR_1", "SWIR_2"),
    "clay_v1_5": ("BLUE", "GREEN", "RED", "NIR", "SWIR_1", "SWIR_2"),
    "terramind": ("BLUE", "GREEN", "RED", "NIR_NARROW", "SWIR_1", "SWIR_2"),
}


@dataclass(slots=True)
class FoundationFinetuneConfig:
    """Parameters for one fine-tune run."""

    backbone: Backbone = "prithvi_eo_v2_300"
    n_classes: int = 2
    max_epochs: int = 20
    batch_size: int = 8
    learning_rate: float = 1e-4
    patch_size: int = 224
    accelerator: str = "auto"  # "auto" / "gpu" / "cpu"


def finetune(
    cfg: FoundationFinetuneConfig,
    train_rasters: list[Path],
    train_masks: list[Path],
    *,
    out_dir: Path,
    val_rasters: list[Path] | None = None,
    val_masks: list[Path] | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> Path:
    """Fine-tune a TerraTorch backbone on user-supplied rasters + masks.

    Each ``train_rasters[i]`` is a multi-band scene; each ``train_masks[i]``
    is a single-band integer raster with the same georeferencing where each
    pixel is a class id (0 = background / nodata).

    Returns the path to a ``best.ckpt`` Lightning checkpoint.  Convert to
    ONNX with :func:`export_finetuned_to_onnx` for production inference.
    """
    from lightning import Trainer
    from lightning.pytorch.callbacks import ModelCheckpoint
    from lightning.pytorch.loggers import CSVLogger
    from terratorch.datamodules import GenericNonGeoSegmentationDataModule
    from terratorch.tasks import SemanticSegmentationTask

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bands = list(BACKBONE_BANDS[cfg.backbone])

    datamodule = GenericNonGeoSegmentationDataModule(
        train_image_files=[str(p) for p in train_rasters],
        train_label_files=[str(p) for p in train_masks],
        val_image_files=[str(p) for p in (val_rasters or [])],
        val_label_files=[str(p) for p in (val_masks or [])],
        num_classes=cfg.n_classes,
        batch_size=cfg.batch_size,
        bands=bands,
        img_size=cfg.patch_size,
    )

    task = SemanticSegmentationTask(
        model_args={
            "backbone": cfg.backbone,
            "decoder": "UperNetDecoder",
            "num_classes": cfg.n_classes,
            "bands": bands,
        },
        loss="ce",
        lr=cfg.learning_rate,
        optimizer="AdamW",
    )

    checkpoint_cb = ModelCheckpoint(
        dirpath=str(out_dir),
        filename="best",
        save_top_k=1,
        monitor="val_loss",
        mode="min",
    )
    logger = CSVLogger(save_dir=str(out_dir), name="logs")

    trainer = Trainer(
        max_epochs=cfg.max_epochs,
        accelerator=cfg.accelerator,
        callbacks=[checkpoint_cb, _ProgressBridge(progress_cb)] if progress_cb else [checkpoint_cb],
        logger=logger,
        enable_progress_bar=False,
    )
    trainer.fit(task, datamodule=datamodule)
    return out_dir / "best.ckpt"


def export_finetuned_to_onnx(
    checkpoint_path: Path,
    out_path: Path,
    *,
    patch_size: int = 224,
    n_input_bands: int = 6,
    opset: int = 17,
) -> Path:
    """Export a fine-tuned task checkpoint to ONNX.

    ONNX input is a float32 tensor of shape ``(N, n_input_bands, patch_size, patch_size)``;
    output is the class-probability tensor produced by the UperNet decoder.
    """
    import torch
    from terratorch.tasks import SemanticSegmentationTask

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    task = SemanticSegmentationTask.load_from_checkpoint(str(checkpoint_path))
    task.eval()
    dummy = torch.randn(1, n_input_bands, patch_size, patch_size)
    torch.onnx.export(
        task.model,
        (dummy,),  # tuple form is required in modern torch.onnx
        str(out_path),
        input_names=["input"],
        output_names=["logits"],
        opset_version=opset,
        dynamic_axes={"input": {0: "N"}, "logits": {0: "N"}},
    )
    return out_path


# --------------------------------------------------------------------------- #
# Backwards-compat shim — old code calls this; keep it green.                 #
# --------------------------------------------------------------------------- #
def finetune_prithvi(
    datamodule,  # type: ignore[no-untyped-def]
    *,
    n_classes: int,
    variant: str = "prithvi_eo_v2_300",
    max_epochs: int = 20,
    logger=None,  # type: ignore[no-untyped-def]
):  # type: ignore[no-untyped-def]
    """Legacy single-call wrapper.  Prefer :func:`finetune`."""
    from lightning import Trainer
    from terratorch.tasks import SemanticSegmentationTask

    task = SemanticSegmentationTask(
        model_args=dict(
            backbone=variant,
            decoder="UperNetDecoder",
            num_classes=n_classes,
            bands=list(BACKBONE_BANDS[variant]),
        ),
        loss="ce",
        lr=1e-4,
        optimizer="AdamW",
    )
    Trainer(max_epochs=max_epochs, logger=logger, accelerator="auto").fit(
        task, datamodule=datamodule
    )
    return task


# --------------------------------------------------------------------------- #
class _ProgressBridge:
    """Tiny Lightning callback that forwards epoch progress to a callback."""

    def __init__(self, cb: Callable[[float], None]) -> None:
        self.cb = cb

    def on_train_epoch_end(self, trainer, pl_module) -> None:  # type: ignore[no-untyped-def]
        self.cb((trainer.current_epoch + 1) / max(trainer.max_epochs, 1))
