from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from schemas.results import ArtifactRef
from tools.formatting import save_artifact_json


class ArtifactService:
    def save_json(self, run_id: str, payload: dict[str, Any], artifact_type: str = "json") -> ArtifactRef:
        path = save_artifact_json(run_id, payload)
        artifact_id = Path(path).stem
        ref = ArtifactRef(
            artifact_id=artifact_id,
            artifact_path=path,
            artifact_type=artifact_type,
        )
        public_base_url = os.getenv("MCP_PUBLIC_BASE_URL", "").rstrip("/")
        if public_base_url:
            ref.artifact_url = f"{public_base_url}/artifacts/{artifact_id}"
        return ref

