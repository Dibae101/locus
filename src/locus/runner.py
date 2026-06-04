"""Single-image run via the process backend (Layer 2, Stage 3.3).

Loads a Locusfile, resolves the (single) image, runs its capability in-process
through the Layer 1 engine, materializes the result as a ``LocusArtifact`` in the run
workspace, and returns a ``RunOutput``. Multi-stage composition is added in Stage 4.

Requirements: 1.3, 3.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from locus.artifacts import LocusArtifact
from locus.builtins import resolve_builtin
from locus.errors import ImageNotFoundError
from locus.image import ResolvedImage, StageContext
from locus.locusfile import Locusfile, StageSpec
from locus.workspace import RunWorkspace

if TYPE_CHECKING:
    from locus.executor import PipelineRunOutput


@dataclass
class RunOutput:
    frame: pd.DataFrame
    artifact: LocusArtifact
    engine_mode: str
    workspace: RunWorkspace


def resolve_image(ref: str) -> ResolvedImage:
    image = resolve_builtin(ref)
    if image is None:
        raise ImageNotFoundError(ref)
    return image


def run_single(lf: Locusfile, *, workspace: RunWorkspace | None = None) -> RunOutput:
    stages = lf.normalized_pipeline()
    if len(stages) != 1:
        raise ValueError("run_single expects exactly one stage; use run_pipeline for pipelines")
    stage = stages[0]
    ws = workspace or RunWorkspace()
    return _run_stage(stage, lf, ws)


def run_pipeline(
    lf: Locusfile,
    *,
    workspace: RunWorkspace | None = None,
    runtime: str = "process",
) -> PipelineRunOutput:
    """Plan and execute a (possibly multi-stage) pipeline."""
    from locus.backends import select_backend
    from locus.executor import StageExecutor
    from locus.planner import PipelinePlanner

    ws = workspace or RunWorkspace()
    planner = PipelinePlanner()
    plan = planner.plan(lf, resolve_image, mode=lf.mode)
    backend = select_backend(runtime)
    result: PipelineRunOutput = StageExecutor(lf, workspace=ws, backend=backend).execute(plan)
    return result


def _run_stage(stage: StageSpec, lf: Locusfile, ws: RunWorkspace) -> RunOutput:
    image = resolve_image(stage.image)
    source = stage.source or lf.source
    ctx = StageContext(
        stage_id=stage.id,
        source=source,
        config=stage.config,
        grounding_threshold=float(
            (lf.llm or {}).get("grounding_threshold", 0.7)
            if isinstance(lf.llm, dict)
            else 0.7
        ),
        workspace_dir=str(ws.path),
    )
    frame, engine_mode = image.capability.run([], ctx)
    artifact = ws.write_table(stage.id, frame, image.manifest.emits, engine_mode=engine_mode)
    return RunOutput(frame=frame, artifact=artifact, engine_mode=engine_mode, workspace=ws)
