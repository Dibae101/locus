"""Pipeline planner: DAG build, cycle detection, static type-check (Stage 4.1/4.2).

Builds the pipeline graph from a Locusfile, detects cycles, orders stages into
execution waves (independent stages share a wave and may run in parallel), and
STATIC-CHECKS every dependency edge's artifact-type compatibility before any stage
runs. A major-version mismatch fails the plan; a minor mismatch warns. Provenance
conformance is gated per mode.

Requirements: 5.1-5.6, 6.3-6.6, 7.7, 7.8.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from locus.artifacts import Compat
from locus.errors import ConformanceError, CycleError, PlanError, TypeMismatchError
from locus.image import ResolvedImage
from locus.locusfile import Locusfile, StageSpec

ImageResolver = Callable[[str], ResolvedImage]


@dataclass
class PlannedStage:
    spec: StageSpec
    image: ResolvedImage


@dataclass
class PipelinePlan:
    stages: dict[str, PlannedStage]
    waves: list[list[str]]  # ordered groups of stage ids; within a wave = parallelizable
    warnings: list[str] = field(default_factory=list)
    terminal: str = ""


class PipelinePlanner:
    """Plans a composed pipeline, failing fast on cycles or type mismatches."""

    def plan(
        self,
        lf: Locusfile,
        resolver: ImageResolver,
        *,
        mode: str = "strict",
    ) -> PipelinePlan:
        specs = lf.normalized_pipeline()
        if not specs:
            raise PlanError("pipeline has no stages")
        by_id = {s.id: s for s in specs}
        self._validate_refs(specs, by_id)

        images = {s.id: resolver(s.image) for s in specs}
        waves = self._topo_waves(specs, by_id)
        warnings = self._typecheck_edges(specs, by_id, images)
        self._gate_conformance(specs, images, mode)

        terminal = self._terminal_stage(specs, by_id)
        planned = {s.id: PlannedStage(spec=s, image=images[s.id]) for s in specs}
        return PipelinePlan(stages=planned, waves=waves, warnings=warnings, terminal=terminal)

    @staticmethod
    def _validate_refs(specs: list[StageSpec], by_id: dict[str, StageSpec]) -> None:
        ids = {s.id for s in specs}
        if len(ids) != len(specs):
            raise PlanError("duplicate stage ids in pipeline")
        for s in specs:
            for dep in s.needs:
                if dep not in ids:
                    raise PlanError(f"stage {s.id!r} depends on unknown stage {dep!r}")

    def _topo_waves(
        self, specs: list[StageSpec], by_id: dict[str, StageSpec]
    ) -> list[list[str]]:
        """Kahn-style layering; raises CycleError if not fully consumed."""
        remaining = {s.id: set(s.needs) for s in specs}
        waves: list[list[str]] = []
        while remaining:
            ready = sorted(sid for sid, deps in remaining.items() if not deps)
            if not ready:
                raise CycleError(self._find_cycle(by_id))
            waves.append(ready)
            for sid in ready:
                del remaining[sid]
            for deps in remaining.values():
                deps.difference_update(ready)
        return waves

    @staticmethod
    def _find_cycle(by_id: dict[str, StageSpec]) -> list[str]:
        # DFS to surface one cycle for the error message.
        color: dict[str, int] = {}
        stack: list[str] = []

        def visit(node: str) -> list[str] | None:
            color[node] = 1
            stack.append(node)
            for dep in by_id[node].needs:
                if color.get(dep, 0) == 1:
                    return stack[stack.index(dep):] + [dep]
                if color.get(dep, 0) == 0:
                    found = visit(dep)
                    if found:
                        return found
            stack.pop()
            color[node] = 2
            return None

        for sid in by_id:
            if color.get(sid, 0) == 0:
                found = visit(sid)
                if found:
                    return found
        return list(by_id)

    def _typecheck_edges(
        self,
        specs: list[StageSpec],
        by_id: dict[str, StageSpec],
        images: dict[str, ResolvedImage],
    ) -> list[str]:
        warnings: list[str] = []
        for s in specs:
            for dep in s.needs:
                emitted = images[dep].manifest.emits
                accepts = images[s.id].manifest.accepts
                if not accepts:
                    # Consumer declares no accepted types: treat as wildcard root-style.
                    continue
                best = max(
                    (emitted.compatible_with(a) for a in accepts),
                    key=_compat_rank,
                )
                if best is Compat.INCOMPATIBLE:
                    raise TypeMismatchError(
                        producer=dep,
                        consumer=s.id,
                        emitted=emitted.tag(),
                        accepted=[a.tag() for a in accepts],
                    )
                if best is Compat.MINOR_DIFF:
                    warnings.append(
                        f"minor artifact-version difference on edge {dep} -> {s.id} "
                        f"({emitted.tag()})"
                    )
        return warnings

    @staticmethod
    def _gate_conformance(
        specs: list[StageSpec], images: dict[str, ResolvedImage], mode: str
    ) -> None:
        if mode != "strict":
            return
        for s in specs:
            if not images[s.id].manifest.provenance_conformant:
                raise ConformanceError(s.id)

    @staticmethod
    def _terminal_stage(specs: list[StageSpec], by_id: dict[str, StageSpec]) -> str:
        depended_on = {dep for s in specs for dep in s.needs}
        leaves = [s.id for s in specs if s.id not in depended_on]
        if len(leaves) != 1:
            raise PlanError(
                f"pipeline must have exactly one terminal stage, found {len(leaves)}: {leaves}"
            )
        return leaves[0]


def _compat_rank(c: Compat) -> int:
    return {Compat.OK: 2, Compat.MINOR_DIFF: 1, Compat.INCOMPATIBLE: 0}[c]
