"""OpenCode 1.18.26 model catalog parser."""

from __future__ import annotations

import json

from pydantic import ValidationError

from agenty.runtime.protocol import (
    EvidenceLevel,
    RuntimeIdentity,
    RuntimeModelCatalog,
    RuntimeModelDescriptor,
    RuntimeModelRef,
)


class InvalidOpenCodeModelCatalog(ValueError):
    pass


class OpenCodeModelCatalogParser:
    """Parse repeated `qualified-id` plus JSON records from models --verbose."""

    evidence_source = "opencode 1.18.26 models --verbose"

    def parse(
        self,
        output: str,
        runtime: RuntimeIdentity,
    ) -> RuntimeModelCatalog:
        decoder = json.JSONDecoder()
        cursor = 0
        descriptors: list[RuntimeModelDescriptor] = []

        while True:
            cursor = self._skip_whitespace(output, cursor)
            if cursor >= len(output):
                break
            line_end = output.find("\n", cursor)
            if line_end < 0:
                raise InvalidOpenCodeModelCatalog(
                    "model identity is not followed by JSON metadata"
                )
            qualified_id = output[cursor:line_end].strip()
            cursor = self._skip_whitespace(output, line_end + 1)
            try:
                metadata, cursor = decoder.raw_decode(output, cursor)
            except json.JSONDecodeError as exc:
                raise InvalidOpenCodeModelCatalog(
                    f"invalid metadata for {qualified_id!r}: {exc.msg}"
                ) from exc
            descriptors.append(
                self._descriptor(qualified_id, metadata, runtime)
            )

        if not descriptors:
            raise InvalidOpenCodeModelCatalog("model catalog is empty")
        try:
            return RuntimeModelCatalog(
                runtime=runtime,
                models=tuple(descriptors),
            )
        except ValidationError as exc:
            raise InvalidOpenCodeModelCatalog(str(exc)) from exc

    def _descriptor(
        self,
        qualified_id: str,
        metadata: object,
        runtime: RuntimeIdentity,
    ) -> RuntimeModelDescriptor:
        if not isinstance(metadata, dict):
            raise InvalidOpenCodeModelCatalog("model metadata must be an object")
        provider_id = metadata.get("providerID")
        model_id = metadata.get("id")
        if not isinstance(provider_id, str) or not isinstance(model_id, str):
            raise InvalidOpenCodeModelCatalog(
                "model metadata requires providerID and id"
            )
        if qualified_id != f"{provider_id}/{model_id}":
            raise InvalidOpenCodeModelCatalog(
                f"model identity does not match metadata: {qualified_id!r}"
            )
        variants = metadata.get("variants", {})
        if not isinstance(variants, dict):
            raise InvalidOpenCodeModelCatalog("model variants must be an object")
        display_name = metadata.get("name")
        if display_name is not None and not isinstance(display_name, str):
            raise InvalidOpenCodeModelCatalog("model name must be text")
        return RuntimeModelDescriptor(
            runtime=runtime,
            model=RuntimeModelRef(
                model_type="language",
                provider_id=provider_id,
                model_id=model_id,
            ),
            display_name=display_name,
            supported_efforts=tuple(variants),
            evidence=EvidenceLevel.PROBE_VERIFIED,
            evidence_source=self.evidence_source,
        )

    @staticmethod
    def _skip_whitespace(text: str, cursor: int) -> int:
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        return cursor
