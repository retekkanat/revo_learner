"""Prepared responses and in-memory clients for offline application tests."""

from __future__ import annotations

import json

from botocore.exceptions import ClientError

from support_assistant.bedrock import ConverseResult
from support_assistant.schemas import Passage


def converse_response(text: str = "Ready.", *, stop_reason: str = "end_turn", content: list | None = None,
                      input_tokens: int = 20, output_tokens: int = 5, request_id: str = "req-1") -> dict:
    """Return a Converse response in the shape the API documents."""
    return {
        "output": {"message": {"role": "assistant", "content": content or [{"text": text}]}},
        "stopReason": stop_reason,
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens,
                  "totalTokens": input_tokens + output_tokens},
        "metrics": {"latencyMs": 321},
        "ResponseMetadata": {"RequestId": request_id, "HTTPStatusCode": 200},
    }


def client_error(code: str, status: int, operation: str = "Converse") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": f"{code} for the test"},
                        "ResponseMetadata": {"RequestId": "req-error", "HTTPStatusCode": status}}, operation)


class ScriptedRuntime:
    """A `bedrock-runtime` stand-in that returns or raises a fixed sequence of outcomes."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[dict] = []

    def converse(self, **request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeEventStream:
    """An event stream that records whether the application closed it."""

    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.closed = False

    def __iter__(self):
        for event in self.events:
            if self.closed:
                return
            yield event

    def close(self) -> None:
        self.closed = True


class StreamingRuntime:
    def __init__(self, events: list[dict]) -> None:
        self.stream = FakeEventStream(events)

    def converse_stream(self, **request):
        return {"ResponseMetadata": {"RequestId": "req-stream"}, "stream": self.stream}


def stream_events(pieces: list[str], *, complete: bool = True) -> list[dict]:
    events = [{"messageStart": {"role": "assistant"}}]
    events += [{"contentBlockDelta": {"delta": {"text": piece}, "contentBlockIndex": 0}} for piece in pieces]
    if complete:
        events += [{"contentBlockStop": {"contentBlockIndex": 0}}, {"messageStop": {"stopReason": "end_turn"}},
                   {"metadata": {"usage": {"inputTokens": 30, "outputTokens": 40, "totalTokens": 70},
                                 "metrics": {"latencyMs": 900}}}]
    return events


class ScriptedModel:
    """A stand-in for `BedrockClient` that returns prepared Converse results in order.

    Use it to test loop limits, dispatch and stopping with known responses.
    These results do not predict a live model's behaviour.
    """

    def __init__(self, messages: list[dict], stop_reasons: list[str]) -> None:
        self.messages = list(messages)
        self.stop_reasons = list(stop_reasons)
        self.calls = 0
        self.seen: list[list[dict]] = []
        self.systems: list[str | None] = []

    def converse(self, messages, **kwargs):
        self.calls += 1
        self.seen.append([dict(message) for message in messages])
        self.systems.append(kwargs.get("system"))
        return ConverseResult(message=self.messages.pop(0), stop_reason=self.stop_reasons.pop(0),
                              usage={"inputTokens": 1, "outputTokens": 1}, latency_ms=1,
                              request_id=f"req-{self.calls}", elapsed_ms=1, attempts=1, model_id="test")


def tool_use_message(name: str, value: dict, tool_use_id: str = "tool-1") -> dict:
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": tool_use_id, "name": name, "input": value}}]}


def text_message(text: str) -> dict:
    return {"role": "assistant", "content": [{"text": text}]}


class FakeS3:
    """Enough of the S3 client for idempotent writes: head, put and get by key."""

    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}
        self.puts = 0

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        return {"Metadata": self.objects[Key]["Metadata"]}

    def put_object(self, Bucket, Key, Body, ContentType, Metadata):
        self.puts += 1
        self.objects[Key] = {"Body": Body, "Metadata": Metadata}


class FakeDynamo:
    """Enough of the DynamoDB client to honour the conditional write on `case_id`."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.writes = 0

    def put_item(self, TableName, Item, ConditionExpression, ExpressionAttributeValues,
                 ReturnValuesOnConditionCheckFailure):
        key = Item["case_id"]["S"]
        old = self.items.get(key)
        if old is not None and old["content_sha256"]["S"] == ExpressionAttributeValues[":sha"]["S"]:
            error = ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "failed"}}, "PutItem")
            error.response["Item"] = old
            raise error
        self.writes += 1
        self.items[key] = Item


class FakeRetriever:
    """Return prepared passages for a question and record the filter the application set."""

    def __init__(self, passages: list[Passage]) -> None:
        self.passages = passages
        self.filters: list[dict | None] = []

    def retrieve(self, query, *, top_k=5, metadata_filter=None, run_id=None):
        self.filters.append(metadata_filter)
        return list(self.passages)


def passage(doc_id: str, score: float, *, audience: str = "customer", status: str = "current",
            rank: int = 1) -> Passage:
    return Passage(doc_id=doc_id, text=f"Text of {doc_id}.", score=score, rank=rank,
                   location=f"s3://bucket/curated/documents/{doc_id.replace('_', '-')}-x.md",
                   metadata={"doc_id": doc_id, "audience": audience, "status": status})


def json_lines(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
