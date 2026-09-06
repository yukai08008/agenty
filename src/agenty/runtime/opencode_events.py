"""OpenCode 1.18.26 raw JSON to public RuntimeEvent normalization."""

from __future__ import annotations

import json

from agenty.runtime.adapters import RuntimeTurnAdapterError
from agenty.runtime.protocol import (
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
)


class OpenCodeEventNormalizer:
    runtime_kind = "opencode"
    runtime_version = "1.18.26"

    def normalize_json_line(
        self,
        line: str,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        *,
        line_number: int,
    ) -> RuntimeEvent:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise self.invalid_output(
                "OpenCode emitted malformed JSON",
                line_number=line_number,
            ) from exc
        if not isinstance(raw, dict):
            raise self.invalid_output(
                "OpenCode JSON event must be an object",
                line_number=line_number,
            )
        return self.normalize(raw, runtime, request, line_number=line_number)

    def normalize(
        self,
        raw: dict,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        *,
        line_number: int = 1,
    ) -> RuntimeEvent:
        self._validate_runtime(runtime)
        session_id = raw.get("sessionID")
        if session_id is not None and (
            not isinstance(session_id, str) or not session_id.strip()
        ):
            raise self.invalid_output(
                "OpenCode event has an invalid sessionID",
                line_number=line_number,
            )

        event_type = raw.get("type")
        event_names = {
            "step_start": OutputEvent.STEP_STARTED,
            "step_finish": OutputEvent.STEP_FINISHED,
            "text": OutputEvent.TEXT_EMITTED,
            "reasoning": OutputEvent.REASONING_EMITTED,
            "error": OutputEvent.RUNTIME_ERROR_EMITTED,
        }
        part = raw.get("part")
        if event_type == "tool_use":
            tool_state = part.get("state") if isinstance(part, dict) else None
            status = (
                tool_state.get("status") if isinstance(tool_state, dict) else None
            )
            name = (
                OutputEvent.TOOL_FAILED
                if status == "error"
                else OutputEvent.TOOL_COMPLETED
            )
        else:
            name = event_names.get(event_type)
        if name is None:
            raise self.invalid_output(
                f"OpenCode emitted unknown event type: {event_type!r}",
                line_number=line_number,
            )

        payload = {}
        if name in {OutputEvent.TEXT_EMITTED, OutputEvent.REASONING_EMITTED}:
            text = part.get("text") if isinstance(part, dict) else None
            if isinstance(text, str):
                payload["text"] = text
        if name in {OutputEvent.TOOL_COMPLETED, OutputEvent.TOOL_FAILED}:
            if isinstance(part, dict) and isinstance(part.get("tool"), str):
                payload["tool"] = part["tool"]
        if name is OutputEvent.RUNTIME_ERROR_EMITTED:
            payload.update(self.error_details(raw))

        return RuntimeEvent(
            name=name,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id=session_id,
            payload=payload,
            raw_event=raw,
        )

    def error_details(self, raw: dict) -> dict:
        error = raw.get("error")
        if isinstance(error, str):
            return {"message": error}
        if isinstance(error, dict):
            data = error.get("data")
            details = {}
            if isinstance(error.get("name"), str):
                details["error_type"] = error["name"]
            if isinstance(data, dict):
                if isinstance(data.get("message"), str):
                    details["message"] = data["message"]
                if isinstance(data.get("statusCode"), int):
                    details["status_code"] = data["statusCode"]
                if isinstance(data.get("isRetryable"), bool):
                    details["retryable"] = data["isRetryable"]
            if "message" not in details and isinstance(error.get("message"), str):
                details["message"] = error["message"]
            if "message" not in details and "error_type" in details:
                details["message"] = details["error_type"]
            if details:
                return details
        return {"message": "OpenCode runtime error"}

    def invalid_output(self, message: str, **details) -> RuntimeTurnAdapterError:
        return RuntimeTurnAdapterError(
            RuntimeFailure(
                code=RuntimeFailureCode.INVALID_OUTPUT,
                message=message,
                details=details,
            )
        )

    def _validate_runtime(self, runtime: RuntimeIdentity) -> None:
        if (
            runtime.runtime_kind != self.runtime_kind
            or runtime.runtime_version != self.runtime_version
        ):
            raise self.invalid_output(
                "OpenCode event normalizer requires its exact runtime version",
                expected_kind=self.runtime_kind,
                expected_version=self.runtime_version,
                actual_kind=runtime.runtime_kind,
                actual_version=runtime.runtime_version,
            )
