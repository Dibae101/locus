"""Stage executor (Layer 2, Stage 4.3).

Executes a ``PipelinePlan`` wave by wave through a runtime backend. Root stages (no
deps) receive the pipeline source; dependent stages receive their upstream stages'
output frames. The terminal stage's output is the final result. Stage caching reuses
a prior output when the input fingerprint + image ref are unchanged.

Requirements: 5.3, 5.4, 5.7, 5.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from locus.artifacts import LocusArtifact
from locus.image import StageContext
from locus.locusfile import Locusfile
from locus.planner import PipelinePlan
from locus.provenance import CrossStageProvenance, RowProvenance
from locus.workspace import RunWorkspace

if TYPE_CHECKING:
    from locus.backends import RuntimeBackend


@dataclass
class PipelineRunOutput:
    frame: pd.DataFrame
    artifact: LocusArtifact
    engine_mode: str
    workspace: RunWorkspace
    warnings: list[str]
    provenance: list[RowProvenance] = field(default_factory=list)


class StageExecutor:
    """Runs a planned pipeline in dependency order."""

    def __init__(
        self,
        lf: Locusfile,
        *,
        workspace: RunWorkspace | None = None,
        backend: RuntimeBackend | None = None,
    ) -> None:
        from locus.backends import ProcessBackend

        self._lf = lf
        self._ws = workspace or RunWorkspace()
        self._backend = backend or ProcessBackend()
        self._outputs: dict[str, tuple[pd.DataFrame, LocusArtifact]] = {}
        self._cache: dict[str, tuple[pd.DataFrame, LocusArtifact]] = {}
        self._provenance = CrossStageProvenance()

    def execute(self, plan: PipelinePlan) -> PipelineRunOutput:
        last_mode = "deterministic"
        permissive = self._lf.mode == "permissive"
        stage_errors: list[str] = []
        for wave in plan.waves:
            for stage_id in wave:
                frame, artifact, mode = self._run_stage(plan, stage_id)
                # Collect any extraction errors a stage surfaced (e.g. an image needing
                # OCR), so the result can explain an empty output (Req 11.x).
                stage_errors.extend(frame.attrs.get("locus_errors", []))
                # Permissive mode: a non-conformant stage's output is lineage-broken
                # (strict mode already failed at plan time) (Req 7.8).
                if permissive and not plan.stages[stage_id].image.manifest.provenance_conformant:
                    frame = self._provenance.mark_lineage_broken(frame)
                    artifact = self._ws.write_table(
                        stage_id, frame, plan.stages[stage_id].image.manifest.emits,
                        engine_mode=mode,
                    )
                self._outputs[stage_id] = (frame, artifact)
                self._provenance.record_stage(stage_id, frame)  # Req 7.5
                last_mode = mode

        frame, artifact = self._outputs[plan.terminal]
        resolved = self._provenance.resolve_terminal(frame)  # Req 7.6
        return PipelineRunOutput(
            frame=frame,
            artifact=artifact,
            engine_mode=last_mode,
            workspace=self._ws,
            warnings=plan.warnings + stage_errors,
            provenance=resolved,
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
        frame, mode = self._backend.run_stage(image, inputs, ctx)
        artifact = self._ws.write_table(stage_id, frame, image.manifest.emits, engine_mode=mode)
        self._cache[fingerprint] = (frame, artifact)
        return frame, artifact, mode
