"""The Bedrock client: Converse and ConverseStream calls with response validation.

The client sends a request with the model from `config.py`, inspects the stop
reason, the content block types, the usage, the latency and the request
identifier, and writes one ledger row for every attempt. It turns off the SDK's
own retries so that every attempt is visible. The application retries only the
configured temporary errors.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    EventStreamError,
    ReadTimeoutError,
)
from pydantic import BaseModel, ValidationError

from . import config
from .ledger import Ledger, wait_ms

# Errors that AWS's troubleshooting guidance says to retry with backoff and jitter.
# An access denial, a validation error or a missing resource is never retried,
# because those errors require a change to the request or its permissions.
# A timeout is not retried automatically: the original request may still be
# running, so another attempt could incur an additional charge.
RETRYABLE_CODES = frozenset(
    {"ThrottlingException", "ServiceUnavailableException", "InternalServerException", "ModelNotReadyException"}
)
USABLE_STOP_REASONS = frozenset({"end_turn", "tool_use", "stop_sequence"})


class BedrockCallError(RuntimeError):
    """A call that did not produce a usable response, after any retries."""

    def __init__(self, code: str, message: str, *, attempts: int, retryable: bool,
                 request_id: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.attempts = attempts
        self.retryable = retryable
        self.request_id = request_id


@dataclass
class ConverseResult:
    """What one successful Converse call returned, and what the client checked."""

    message: dict
    stop_reason: str
    usage: dict
    latency_ms: int | None
    request_id: str
    elapsed_ms: int
    attempts: int
    model_id: str

    def blocks(self, kind: str) -> list:
        """Return the content blocks of one type, such as `text` or `toolUse`."""
        return [block[kind] for block in self.message.get("content", []) if kind in block]

    def text(self) -> str:
        """Return the text of the answer, after checking that text blocks exist."""
        pieces = self.blocks("text")
        if not pieces:
            raise ValueError(f"The response holds no text block (stop reason {self.stop_reason}).")
        return "".join(pieces)

    @property
    def complete(self) -> bool:
        return self.stop_reason in USABLE_STOP_REASONS


@dataclass
class StreamResult:
    """The text and completion status of a streamed request."""

    text: str
    complete: bool
    stop_reason: str | None
    usage: dict | None
    latency_ms: int | None
    request_id: str | None
    chunks: int
    interrupted_reason: str | None = None


def make_runtime_client(*, read_timeout: float | None = None, connect_timeout: float | None = None):
    """Create a `bedrock-runtime` client with SDK retries off and explicit timeouts."""
    return boto3.client(
        "bedrock-runtime",
        region_name=config.region(),
        config=Config(
            retries={"total_max_attempts": 1, "mode": "standard"},
            read_timeout=read_timeout or config.READ_TIMEOUT_SECONDS,
            connect_timeout=connect_timeout or config.CONNECT_TIMEOUT_SECONDS,
        ),
    )


def result_from_response(response: dict, *, elapsed_ms: int, attempts: int, model_id: str) -> ConverseResult:
    """Extract the message, stop reason, usage, latency and request identifier.

    Read the message and content blocks from `output.message`, the stop reason
    from `stopReason`, and token counts from `usage`. Bedrock reports latency in
    `metrics.latencyMs`. The response metadata contains the request identifier
    that AWS Support uses to trace the call.
    """
    # TODO Exercise 1.4:
    # Read the message from `response["output"]["message"]` and the stop reason from `stopReason`.
    # Read `usage` (use an empty dict if it is missing) and `metrics.latencyMs`.
    # Read the request identifier from `response["ResponseMetadata"]["RequestId"]`.
    # Return a `ConverseResult` with these values and the arguments passed in.
    raise NotImplementedError("TODO Exercise 1.4: complete result_from_response()")


def should_retry(code: str) -> bool:
    """Return whether this error code is in the configured retryable set."""
    # TODO Exercise 1.7:
    # Return True only for an error code in `RETRYABLE_CODES`.
    raise NotImplementedError("TODO Exercise 1.7: complete should_retry()")


def backoff_delay(attempt: int, rng: Callable[[], float] = random.random) -> float:
    """Return the wait before the next attempt: exponential backoff with full jitter."""
    # TODO Exercise 1.7:
    # Work out the ceiling: `BACKOFF_BASE_SECONDS * 2 ** (attempt - 1)`, capped at `BACKOFF_CAP_SECONDS`.
    # Return `rng()` times the ceiling, which is exponential backoff with full jitter.
    raise NotImplementedError("TODO Exercise 1.7: complete backoff_delay()")


def _error_parts(error: ClientError) -> tuple[str, str, int | None, str | None]:
    response = error.response
    return (
        response.get("Error", {}).get("Code", "Unknown"),
        config.redact(response.get("Error", {}).get("Message", "")),
        response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        response.get("ResponseMetadata", {}).get("RequestId"),
    )


@dataclass
class BedrockClient:
    """Send Converse requests and record every attempt in the ledger."""

    ledger: Ledger = field(default_factory=Ledger)
    client: object = None
    model_id: str = config.MODEL_ID
    max_attempts: int = config.MAX_ATTEMPTS
    sleep: Callable[[float], None] = time.sleep
    rng: Callable[[], float] = random.random
    read_timeout: float = config.READ_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = make_runtime_client(read_timeout=self.read_timeout)

    def with_read_timeout(self, seconds: float) -> "BedrockClient":
        """Return a client that shares this ledger and model but waits `seconds` for a response."""
        return BedrockClient(ledger=self.ledger, model_id=self.model_id, max_attempts=self.max_attempts,
                             sleep=self.sleep, rng=self.rng, read_timeout=seconds)

    def _request(self, messages: list[dict], system: str | None, max_tokens: int, temperature: float | None,
                 tool_config: dict | None, output_config: dict | None) -> dict:
        request: dict = {"modelId": self.model_id, "messages": messages,
                         "inferenceConfig": {"maxTokens": max_tokens}}
        if temperature is not None:
            request["inferenceConfig"]["temperature"] = temperature
        if system:
            request["system"] = [{"text": system}]
        if tool_config:
            request["toolConfig"] = tool_config
        if output_config:
            request["outputConfig"] = output_config
        return request

    def converse(
        self,
        messages: list[dict],
        *,
        system: str | None = None,
        max_tokens: int = config.MAX_TOKENS,
        temperature: float | None = config.TEMPERATURE,
        tool_config: dict | None = None,
        output_config: dict | None = None,
        run_id: str | None = None,
        validate: Callable[[ConverseResult], str | None] | None = None,
    ) -> ConverseResult:
        """Send a request, retry configured temporary errors, and return a checked result.

        `validate` lets the caller refuse a response that arrived but cannot be
        used; it returns a reason, or None to accept. A refused response is
        recorded with the status `rejected` and raised as `BedrockCallError`.
        """
        request = self._request(messages, system, max_tokens, temperature, tool_config, output_config)
        attempt = 0
        while True:
            attempt += 1
            started = time.perf_counter()
            try:
                response = self.client.converse(**request)
            except ClientError as error:
                code, message, http_status, request_id = _error_parts(error)
                retry = should_retry(code) and attempt < self.max_attempts
                self.ledger.record(
                    operation="converse", status="failed", model_id=self.model_id, attempt=attempt,
                    run_id=run_id, request_id=request_id, error_code=code, http_status=http_status,
                    will_retry=retry, elapsed_ms=wait_ms(started), note=message[:200],
                )
                if retry:
                    self.sleep(backoff_delay(attempt, self.rng))
                    continue
                raise BedrockCallError(code, message, attempts=attempt, retryable=should_retry(code),
                                       request_id=request_id) from error
            except (ReadTimeoutError, ConnectTimeoutError) as error:
                self.ledger.record(
                    operation="converse", status="timed_out", model_id=self.model_id, attempt=attempt,
                    run_id=run_id, error_code=type(error).__name__, elapsed_ms=wait_ms(started),
                    note="No response before the client timeout. The request may have run, so it is not retried.",
                )
                raise BedrockCallError(type(error).__name__, str(error), attempts=attempt, retryable=False) from error
            except EndpointConnectionError as error:
                self.ledger.record(
                    operation="converse", status="failed", model_id=self.model_id, attempt=attempt,
                    run_id=run_id, error_code="EndpointConnectionError", elapsed_ms=wait_ms(started),
                    note="The endpoint could not be reached.",
                )
                raise BedrockCallError("EndpointConnectionError", str(error), attempts=attempt,
                                       retryable=False) from error

            result = result_from_response(response, elapsed_ms=wait_ms(started), attempts=attempt,
                                          model_id=self.model_id)
            reason = None
            if not result.complete:
                reason = f"stop reason {result.stop_reason}: the answer is incomplete"
            elif validate is not None:
                reason = validate(result)
            self.ledger.record(
                operation="converse", status="rejected" if reason else "succeeded", model_id=self.model_id,
                usage=result.usage, attempt=attempt, run_id=run_id, request_id=result.request_id,
                stop_reason=result.stop_reason, latency_ms=result.latency_ms, elapsed_ms=result.elapsed_ms,
                note=reason,
            )
            if reason:
                raise BedrockCallError("RejectedOutput", reason, attempts=attempt, retryable=False,
                                       request_id=result.request_id)
            return result

    def stream(
        self,
        messages: list[dict],
        *,
        system: str | None = None,
        max_tokens: int = config.MAX_TOKENS,
        deadline_seconds: float | None = None,
        max_chunks: int | None = None,
        on_text: Callable[[str], None] | None = None,
        run_id: str | None = None,
    ) -> StreamResult:
        """Stream an answer, stop it at a deadline or a chunk limit, and record the attempt.

        A stream that the application stops has no `messageStop` and no
        `metadata` event, so its usage is unknown and its text is incomplete.
        """
        request = self._request(messages, system, max_tokens, config.TEMPERATURE, None, None)
        started = time.perf_counter()
        try:
            response = self.client.converse_stream(**request)
        except ClientError as error:
            code, message, http_status, request_id = _error_parts(error)
            self.ledger.record(operation="converse_stream", status="failed", model_id=self.model_id,
                               run_id=run_id, request_id=request_id, error_code=code, http_status=http_status,
                               elapsed_ms=wait_ms(started), note=message[:200])
            raise BedrockCallError(code, message, attempts=1, retryable=should_retry(code),
                                   request_id=request_id) from error
        request_id = response["ResponseMetadata"]["RequestId"]
        events = response["stream"]
        pieces: list[str] = []
        stop_reason = usage = latency = interrupted = None
        chunks = 0
        try:
            for event in events:
                if "contentBlockDelta" in event:
                    piece = event["contentBlockDelta"]["delta"].get("text", "")
                    pieces.append(piece)
                    chunks += 1
                    if on_text:
                        on_text(piece)
                    interrupted = should_interrupt(chunks, time.perf_counter() - started,
                                                   max_chunks=max_chunks, deadline_seconds=deadline_seconds)
                    if interrupted:
                        events.close()
                        break
                elif "messageStop" in event:
                    stop_reason = event["messageStop"]["stopReason"]
                elif "metadata" in event:
                    usage = event["metadata"].get("usage")
                    latency = (event["metadata"].get("metrics") or {}).get("latencyMs")
        except EventStreamError as error:
            code = error.response.get("Error", {}).get("Code", "EventStreamError")
            self.ledger.record(operation="converse_stream", status="failed", model_id=self.model_id,
                               run_id=run_id, request_id=request_id, error_code=code,
                               elapsed_ms=wait_ms(started), note="The stream failed before it completed.")
            raise BedrockCallError(code, str(error), attempts=1, retryable=should_retry(code),
                                   request_id=request_id) from error
        status, recorded_usage, note = stream_outcome(interrupted, stop_reason, usage)
        self.ledger.record(operation="converse_stream", status=status, model_id=self.model_id,
                           usage=recorded_usage, run_id=run_id, request_id=request_id,
                           stop_reason=stop_reason, latency_ms=latency, elapsed_ms=wait_ms(started),
                           note=note, chunks=chunks)
        return StreamResult(text="".join(pieces), complete=status == "succeeded", stop_reason=stop_reason,
                            usage=recorded_usage, latency_ms=latency, request_id=request_id,
                            chunks=chunks, interrupted_reason=interrupted)


def should_interrupt(chunks: int, elapsed_seconds: float, *, max_chunks: int | None,
                     deadline_seconds: float | None) -> str | None:
    """Return an interruption reason if a limit is reached, or None to continue."""
    # TODO Exercise 1.6:
    # Return a reason when `chunks` has reached `max_chunks` (if a limit is set).
    # Return a reason when `elapsed_seconds` is past `deadline_seconds` (if a deadline is set).
    # Otherwise return None, so the stream keeps reading.
    raise NotImplementedError("TODO Exercise 1.6: complete should_interrupt()")


def stream_outcome(interrupted: str | None, stop_reason: str | None,
                   usage: dict | None) -> tuple[str, dict | None, str | None]:
    """Return the ledger status, usage and note for a streamed attempt.

    If the client interrupts the stream before receiving usage metadata,
    record its usage and cost as unknown.
    """
    # TODO Exercise 1.6:
    # An interrupted stream returns ("interrupted", None, note): its usage is unknown, never zero.
    # A stream that ended with a usable stop reason and a usage block returns ("succeeded", usage, None).
    # Anything else returns ("rejected", usage, note) with the stop reason in the note.
    raise NotImplementedError("TODO Exercise 1.6: complete stream_outcome()")


# --------------------------------------------------------------- structured answers

JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(text: str) -> dict:
    """Return the one JSON object in a model's text, ignoring a Markdown code fence."""
    match = JSON_OBJECT.search(text)
    if not match:
        raise ValueError("The answer holds no JSON object.")
    return json.loads(match.group(0))


@dataclass
class StructuredOutcome:
    """A validated record, or the reason the answer was refused."""

    record: BaseModel | None
    rejected_reason: str | None
    request_id: str | None


def validate_structured(text: str, model: type[BaseModel]) -> tuple[BaseModel | None, str | None]:
    """Validate the JSON answer and return a record or validation errors."""
    # TODO Exercise 1.5:
    # Parse the one JSON object in `text` with `parse_json_object()`.
    # Validate it with `model.model_validate()` and return (record, None).
    # On a `ValidationError`, return (None, reason) and name every failing field in the reason.
    # On any other `ValueError`, such as JSON that is cut off, return (None, reason).
    raise NotImplementedError("TODO Exercise 1.5: complete validate_structured()")


def native_output_config(model: type[BaseModel], name: str) -> dict:
    """Return the `outputConfig` that asks Bedrock for native structured output."""
    return {"textFormat": {"type": "json_schema", "structure": {"jsonSchema": {
        "schema": json.dumps(model.model_json_schema()), "name": name,
        "description": f"A {name} record for Kestrel Telecom.",
    }}}}


def request_structured(client: BedrockClient, prompt: str, model: type[BaseModel], *,
                       system: str | None = None, max_tokens: int = config.MAX_TOKENS,
                       native: bool = False, run_id: str | None = None) -> StructuredOutcome:
    """Ask for a JSON answer and validate it. An invalid answer is recorded and never used.

    The application checks every answer against its schema and field validators,
    including answers produced with native structured output.
    """
    def validate(result: ConverseResult) -> str | None:
        return validate_structured(result.text(), model)[1]

    output_config = None
    if native:
        output_config = native_output_config(model, model.__name__)
        if client.read_timeout < config.STRUCTURED_OUTPUT_READ_TIMEOUT_SECONDS:
            client = client.with_read_timeout(config.STRUCTURED_OUTPUT_READ_TIMEOUT_SECONDS)
    try:
        result = client.converse([{"role": "user", "content": [{"text": prompt}]}], system=system,
                                 max_tokens=max_tokens, output_config=output_config, run_id=run_id,
                                 validate=validate)
    except BedrockCallError as error:
        if error.code == "RejectedOutput":
            return StructuredOutcome(None, error.message, error.request_id)
        raise
    return StructuredOutcome(validate_structured(result.text(), model)[0], None, result.request_id)
