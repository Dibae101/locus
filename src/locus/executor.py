"""Stage executor (Layer 2, Stage 4.3).

Executes a ``PipelinePlan`` wave by wave through a runtime backend. Root stages (no
deps) receive the pipeline source; dependent stages receive their upstream stages'
output frames. The terminal stage's output is the final result. Stage caching reuses
a prior output when the input fingerprint + image ref are unchanged.

Requirements: 5.3, 5.4, 5.7, 5.8.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from locus.artifacts import LocusArtifact
from locus.image import StageContext
from locus.locusfile import Locusfile
from locus.planner import PipelinePlan
from locus.workspace import RunWorkspace


@dataclass
class PipelineRunOutput:
    frame: pd.DataFrame
    artifact: LocusArtifact
    engine_mode: str
    workspace: RunWorkspace
    warnings: list[str]


class StageExecutor:
    """Runs a planned pipeline in dependency order."""

    def __init__(self, lf: Locusfile, *, workspace: RunWorkspace | None = None) -> None:
        self._lf = lf
        self._ws = workspace or RunWorkspace()
        self._outputs: dict[str, tuple[pd.DataFrame, LocusArtifact]] = {}
        self._cache: dict[str, tuple[pd.DataFrame, LocusArtifact]] = {}

    def execute(self, plan: PipelinePlan) -> PipelineRunOutput:
        last_mode = "deterministic"
        for wave in plan.waves:
            for stage_id in wave:
                frame, artifact, mode = self._run_stage(plan, stage_id)
                self._outputs[stage_id] = (frame, artifact)
                last_mode = mode

        frame, artifact = self._outputs[plan.terminal]
        return PipelineRunOutput(
            frame=frame,
            artifact=artifact,
            engine_mode=last_mode,
            workspace=self._ws,
            warnings=plan.warnings,
        )

    def _run_stage(
        self, plan: PipelinePlan, stage_id: str
    ) -> tuple[pd.DataFrame, LocusArtifact, str]:
        planned = plan.stages[stage_id]
        spec = planned.spec
        image = planned.image

        inputs = [self._outputs[dep][0] for dep in spec.needs]
        source = spec.source or self._lf.source

        # Stage caching (Req 5.8): fingerprint deps' artifacts + image ref.
        fingerprint = self._ws.content_hash(
            image.ref,
            *(self._outputs[dep][1].payload_path for dep in spec.needs),
            source.path if source and source.path else "<none>",
        )
        if fingerprint in self._cache:
            return (*self._cache[fingerprint], image.manifest.engine_modes[0])

        ctx = StageContext(
            stage_id=stage_id,
            source=source,
            config=spec.config,
            workspace_dir=str(self._ws.path),
        )
        frame, mode = image.capability.run(inputs, ctx)
        artifact = self._ws.write_table(stage_id, frame, image.manifest.emits, engine_mode=mode)
        self._cache[fingerprint] = (frame, artifact)
        return frame, artifact, mode
