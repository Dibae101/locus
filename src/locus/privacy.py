"""Runtime privacy disclosure (Layer 2, Stage 10.2).

Classifies each image in a pipeline by privacy class and produces a disclosure. When
any stage calls an external LLM provider, the runtime must present a consent notice
before data leaves the user's environment and must NOT present a blanket
"data stays local" claim.

Requirements: 12.1, 12.2, 12.3.
"""

from __future__ import annotations

from dataclasses import dataclass

from locus.manifest import PrivacyClass
from locus.planner import PipelinePlan


@dataclass
class PrivacyDisclosure:
    stages_local: list[str]
    stages_external: list[str]

    @property
    def has_external(self) -> bool:
        return bool(self.stages_external)

    @property
    def all_local(self) -> bool:
        return not self.stages_external

    def summary(self) -> str:
        if self.all_local:
            return "All stages run locally; no data leaves your environment."
        # Must NOT make a blanket local claim when an external stage exists (Req 12.3).
        names = ", ".join(self.stages_external)
        return (
            f"WARNING: stage(s) [{names}] call an external provider; "
            f"data will leave your environment for those stages."
        )

    def consent_prompt(self) -> str | None:
        """The consent text shown before any external egress (Req 12.1)."""
        if self.all_local:
            return None
        names = ", ".join(self.stages_external)
        return (
            f"Stage(s) [{names}] will transmit your data to an external LLM provider. "
            f"Proceed? [y/N]"
        )


def classify_pipeline(plan: PipelinePlan) -> PrivacyDisclosure:
    """Classify each stage by its image's privacy class (Req 12.2)."""
    local: list[str] = []
    external: list[str] = []
    for stage_id, planned in plan.stages.items():
        if planned.image.manifest.privacy_class is PrivacyClass.CALLS_EXTERNAL:
            external.append(stage_id)
        else:
            local.append(stage_id)
    return PrivacyDisclosure(stages_local=sorted(local), stages_external=sorted(external))
