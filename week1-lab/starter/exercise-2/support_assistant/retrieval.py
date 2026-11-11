"""Retrieve passages and compare results with a local keyword search.

The managed knowledge base parses the curated documents, splits them into
chunks and creates embeddings for hybrid search. `Retrieve` returns ranked
passages with scores and source locations, even if none answers the question.
The application checks every citation in a generated answer against the
passages it supplied. Week 2 adds a filter for the caller's access, a relevance
threshold and a check of each cited document's status.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field

from botocore.exceptions import ClientError

from . import config
from .ingest import DOCUMENT_PREFIX, METADATA_PREFIX, WaitTimeout, parse_document, wait_for
from .ledger import Ledger, wait_ms
from .schemas import Citation, Passage

# ---------------------------------------------------------------- keyword baseline

STOP_WORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its my of on or so that the "
    "their there this to was what when where which will with you your me we our not any".split()
)
TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return [word for word in TOKEN.findall(text.lower()) if word not in STOP_WORDS]


@dataclass
class KeywordBaseline:
    """A deterministic BM25 keyword ranking over whole documents. It runs locally and costs nothing."""

    documents: dict[str, str]
    k1: float = 1.5
    b: float = 0.75
    _terms: dict[str, Counter] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._terms = {doc_id: Counter(tokens(text)) for doc_id, text in self.documents.items()}
        self._length = {doc_id: sum(counts.values()) for doc_id, counts in self._terms.items()}
        self._average = sum(self._length.values()) / max(len(self._length), 1)
        frequency: Counter = Counter()
        for counts in self._terms.values():
            frequency.update(counts.keys())
        total = len(self._terms)
        self._idf = {term: math.log(1 + (total - df + 0.5) / (df + 0.5)) for term, df in frequency.items()}

    def rank(self, query: str, top_k: int = config.TOP_K) -> list[tuple[str, float]]:
        """Return the top documents and their scores, highest first; ties break by identifier."""
        scores = {}
        for doc_id, counts in self._terms.items():
            score = 0.0
            for term in set(tokens(query)):
                if term in counts:
                    tf = counts[term]
                    norm = tf + self.k1 * (1 - self.b + self.b * self._length[doc_id] / self._average)
                    score += self._idf[term] * tf * (self.k1 + 1) / norm
            if score > 0:
                scores[doc_id] = round(score, 4)
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]


def load_corpus() -> dict[str, str]:
    """Return every curated document's text by identifier, read from `data/documents/`."""
    corpus = {}
    for path in sorted((config.DATA_DIR / "documents").glob("*.md")):
        parsed, _ = parse_document(path, config.reference_date())
        if parsed is not None:
            corpus[parsed.metadata.doc_id] = parsed.data.decode("utf-8")
    return corpus


# ------------------------------------------------------------- the knowledge base


def ensure_kb_role(iam, account_id: str, role_name: str, bucket: str, lab: int = 5) -> str:
    """Create the knowledge base's service role, which may read only the curated zone.

    The role needs the documents and their metadata files, which both sit under
    `curated/`; the raw, cleansed and rejected zones stay out of its reach.
    """
    region = config.region()
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"}, "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"aws:SourceAccount": account_id},
                      "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{region}:{account_id}:knowledge-base/*"}}}]}
    access = {"Version": "2012-10-17", "Statement": [
        {"Sid": "ListCuratedDocuments", "Effect": "Allow", "Action": "s3:ListBucket",
         "Resource": f"arn:aws:s3:::{bucket}", "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}}},
        {"Sid": "ReadCuratedZone", "Effect": "Allow", "Action": "s3:GetObject",
         "Resource": f"arn:aws:s3:::{bucket}/curated/*",
         "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}}}]}
    try:
        arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "NoSuchEntity":
            raise
        arn = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust),
                              Description="Kestrel knowledge base service role for the AWS FDE course",
                              Tags=config.tag_list(lab))["Role"]["Arn"]
    iam.put_role_policy(RoleName=role_name, PolicyName="read-curated-documents", PolicyDocument=json.dumps(access))
    return arn


def find_knowledge_base(agent, name: str) -> str | None:
    for page in agent.get_paginator("list_knowledge_bases").paginate():
        for summary in page["knowledgeBaseSummaries"]:
            if summary["name"] == name:
                return summary["knowledgeBaseId"]
    return None


def ensure_knowledge_base(agent, name: str, role_arn: str, *, lab: int = 5,
                          timeout: float = config.KB_WAIT_SECONDS) -> str:
    """Create the managed knowledge base with the managed embedding model, once, and wait for it."""
    kb_id = find_knowledge_base(agent, name)
    if kb_id is None:
        def create() -> tuple[bool, object]:
            try:
                response = agent.create_knowledge_base(
                    name=name, roleArn=role_arn, description="Kestrel Telecom support documents (Exercise 5)",
                    knowledgeBaseConfiguration={"type": "MANAGED",
                                                "managedKnowledgeBaseConfiguration": {"embeddingModelType": "MANAGED"}},
                    tags=config.tags(lab))
                return True, response["knowledgeBase"]["knowledgeBaseId"]
            except ClientError as error:
                # Retry while a newly created role is becoming available to the service.
                message = error.response["Error"]["Message"].lower()
                if error.response["Error"]["Code"] == "ValidationException" and "role" in message:
                    return False, "role not yet usable"
                raise
        kb_id = wait_for(create, timeout=120, interval=10, what="knowledge base creation")
    wait_for(lambda: _kb_status(agent, kb_id), timeout=timeout, interval=config.POLL_INTERVAL_SECONDS,
             what=f"knowledge base {name}")
    return kb_id


def _kb_status(agent, kb_id: str) -> tuple[bool, str]:
    status = agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
    if status == "FAILED":
        raise RuntimeError("The knowledge base reports FAILED; read its failureReasons in the console.")
    return status == "ACTIVE", status


def data_source_configuration(bucket: str, account_id: str) -> dict:
    """The S3 connector settings: the curated documents, and their metadata files under their own prefix.

    The connector needs the bucket owner's account number even when the bucket is
    in the same account; the code passes it at run time and never prints it. The
    documents are text only, so media extraction is switched off.
    """
    return {
        "type": "MANAGED_KNOWLEDGE_BASE_CONNECTOR",
        "managedKnowledgeBaseConnectorConfiguration": {
            "mediaExtractionConfiguration": {
                "imageExtractionConfiguration": {"imageExtractionStatus": "DISABLED"},
            },
            "connectorParameters": {
                "type": "S3",
                "version": "1",
                "connectionConfiguration": {"bucketName": bucket, "bucketOwnerAccountId": account_id},
                "filterConfiguration": {"inclusionPrefixes": [DOCUMENT_PREFIX]},
                "metadataFilesPrefix": METADATA_PREFIX,
            },
        },
    }


def ensure_data_source(agent, kb_id: str, name: str, bucket: str, account_id: str, *,
                       timeout: float = config.KB_WAIT_SECONDS) -> str:
    """Connect the curated prefix with Default chunking. Chunking cannot be changed afterwards.

    A data source that failed to connect is deleted and created again, because a
    failed data source cannot be repaired in place.
    """
    ds_id = None
    for page in agent.get_paginator("list_data_sources").paginate(knowledgeBaseId=kb_id):
        for summary in page["dataSourceSummaries"]:
            if summary["name"] == name:
                ds_id = summary["dataSourceId"]
    if ds_id is not None:
        current = agent.get_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)["dataSource"]["status"]
        if current == "FAILED":
            agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)
            wait_for(lambda: (_data_source_gone(agent, kb_id, ds_id), "DELETING"), timeout=timeout,
                     interval=config.POLL_INTERVAL_SECONDS, what=f"removal of the failed data source {name}")
            ds_id = None
    if ds_id is None:
        ds_id = agent.create_data_source(
            knowledgeBaseId=kb_id, name=name, dataDeletionPolicy="DELETE",
            dataSourceConfiguration=data_source_configuration(bucket, account_id))["dataSource"]["dataSourceId"]

    def status() -> tuple[bool, str]:
        state = agent.get_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)["dataSource"]
        if state["status"] == "FAILED":
            raise RuntimeError(f"The data source reports FAILED: {config.redact(str(state.get('failureReasons')))}")
        return state["status"] == "AVAILABLE", state["status"]

    wait_for(status, timeout=timeout, interval=config.POLL_INTERVAL_SECONDS, what=f"data source {name}")
    return ds_id


def _data_source_gone(agent, kb_id: str, ds_id: str) -> bool:
    try:
        agent.get_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            return True
        raise
    return False


def start_ingestion(agent, kb_id: str, ds_id: str) -> str:
    """Start an ingestion job for the data source and return its identifier."""
    return agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)["ingestionJob"]["ingestionJobId"]


def wait_for_ingestion(agent, kb_id: str, ds_id: str, job_id: str, *,
                       timeout: float = config.INGESTION_WAIT_SECONDS) -> dict:
    """Wait for one ingestion job with a limit. A wait that passes its limit is recorded as TIMED_OUT."""
    started = time.perf_counter()

    def status() -> tuple[bool, dict]:
        current = agent.get_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id,
                                          ingestionJobId=job_id)["ingestionJob"]
        if current["status"] == "FAILED":
            raise RuntimeError(f"The ingestion job failed: {config.redact(str(current.get('failureReasons')))}")
        return current["status"] == "COMPLETE", current

    try:
        finished = wait_for(status, timeout=timeout, interval=min(config.POLL_INTERVAL_SECONDS, timeout), what="ingestion job")
    except WaitTimeout as error:
        return {"ingestion_job_id": job_id, "status": "TIMED_OUT", "error": str(error),
                "elapsed_seconds": round(time.perf_counter() - started, 1)}
    return {"ingestion_job_id": job_id, "status": finished["status"], "statistics": finished.get("statistics", {}),
            "warnings": [config.redact(str(reason)) for reason in finished.get("failureReasons", [])],
            "elapsed_seconds": round(time.perf_counter() - started, 1)}


def sync(agent, kb_id: str, ds_id: str, *, timeout: float = config.INGESTION_WAIT_SECONDS) -> dict:
    """Start an ingestion job and wait for it with a limit. Return the job's statistics and timing.

    A job can finish as COMPLETE and still report failure reasons, such as a role
    that cannot read a prefix; they are returned as `warnings` so the quality
    report shows them.
    """
    return wait_for_ingestion(agent, kb_id, ds_id, start_ingestion(agent, kb_id, ds_id), timeout=timeout)


# ------------------------------------------------------------------------ Retrieve


def passage_from_result(result: dict, rank: int) -> Passage:
    """Turn one `Retrieve` result into a passage with its document identifier and location."""
    metadata = result.get("metadata") or {}
    location = result.get("location") or {}
    uri = (location.get("s3Location") or {}).get("uri") or location.get("customDocumentLocation", {}).get("id")
    doc_id = metadata.get("doc_id")
    if not doc_id and uri:
        match = re.search(r"/(kd-\d{2})-", uri)
        doc_id = match.group(1).replace("-", "_") if match else None
    return Passage(doc_id=doc_id or "unknown", text=(result.get("content") or {}).get("text", ""),
                   score=result.get("score"), location=uri, rank=rank, metadata=metadata)


@dataclass
class Retriever:
    """Call `Retrieve` on the managed knowledge base and record each call in the ledger."""

    kb_id: str
    client: object
    ledger: Ledger = field(default_factory=Ledger)

    def retrieve(self, query: str, *, top_k: int = config.TOP_K, metadata_filter: dict | None = None,
                 run_id: str | None = None) -> list[Passage]:
        search: dict = {"numberOfResults": top_k}
        if metadata_filter:
            search["filter"] = metadata_filter
        started = time.perf_counter()
        try:
            response = self.client.retrieve(knowledgeBaseId=self.kb_id, retrievalQuery={"text": query},
                                            retrievalConfiguration={"managedSearchConfiguration": search})
        except ClientError as error:
            self.ledger.record(operation="retrieve", status="failed", run_id=run_id,
                               error_code=error.response["Error"]["Code"], elapsed_ms=wait_ms(started),
                               request_id=error.response.get("ResponseMetadata", {}).get("RequestId"),
                               note=config.redact(error.response["Error"]["Message"])[:200])
            raise
        passages = [passage_from_result(result, rank)
                    for rank, result in enumerate(response.get("retrievalResults", []), start=1)]
        self.ledger.record(operation="retrieve", status="succeeded", run_id=run_id,
                           request_id=response["ResponseMetadata"]["RequestId"], elapsed_ms=wait_ms(started),
                           note=f"{len(passages)} passages", top_score=passages[0].score if passages else None)
        return passages


def distinct_documents(passages: list[Passage]) -> list[str]:
    """Return the document identifiers of the passages, in rank order, without repeats."""
    seen: list[str] = []
    for passage in passages:
        if passage.doc_id not in seen:
            seen.append(passage.doc_id)
    return seen


def hit_at(supporting: set[str], ranked: list[str], k: int) -> bool | None:
    """Return whether a supporting document is among the first `k` ranked documents.

    A question with no supporting document has no hit to measure, so the result is None.
    """
    # TODO Exercise 1.12:
    # Return None when there are no supporting documents.
    # Return whether any supporting document is among the first `k` ranked documents.
    raise NotImplementedError("TODO Exercise 1.12: complete hit_at()")


def compare_retrievers(questions: list[dict], baseline: KeywordBaseline, retriever: Retriever,
                       *, top_k: int = config.TOP_K, run_id: str | None = None) -> dict:
    """Ask every question of both retrievers and measure them the same way.

    For each answerable question the measure is whether a supporting document
    appears in the top `top_k` results and at rank one. For each question with
    no supporting document, the knowledge base's top score is recorded, because
    a relevance threshold, which Week 2 adds, is set from these scores.
    """
    rows = []
    for question in questions:
        support = set(question["supporting_documents"])
        base = [doc_id for doc_id, _ in baseline.rank(question["question"], top_k)]
        started = time.perf_counter()
        passages = retriever.retrieve(question["question"], top_k=top_k, run_id=run_id)
        latency = wait_ms(started)
        kb_docs = distinct_documents(passages)
        rows.append({
            "question_id": question["question_id"],
            "answerable": bool(support),
            "baseline_top": base[:3],
            "baseline_hit_top_k": hit_at(support, base, top_k),
            "baseline_hit_rank_1": hit_at(support, base, 1),
            "kb_top": kb_docs[:3],
            "kb_hit_top_k": hit_at(support, kb_docs, top_k),
            "kb_hit_rank_1": hit_at(support, kb_docs, 1),
            "kb_top_score": passages[0].score if passages else None,
            "kb_latency_ms": latency,
        })
    answerable = [row for row in rows if row["answerable"]]

    def rate(key: str) -> float:
        return round(sum(bool(row[key]) for row in answerable) / max(len(answerable), 1), 3)

    return {
        "top_k": top_k,
        "answerable_questions": len(answerable),
        "baseline": {"hit_rate_top_k": rate("baseline_hit_top_k"), "hit_rate_rank_1": rate("baseline_hit_rank_1"),
                     "cost_usd": 0.0},
        "knowledge_base": {"hit_rate_top_k": rate("kb_hit_top_k"), "hit_rate_rank_1": rate("kb_hit_rank_1"),
                           "median_latency_ms": sorted(row["kb_latency_ms"] for row in rows)[len(rows) // 2],
                           "calls": len(rows)},
        "answerable_top_scores": sorted(row["kb_top_score"] for row in answerable if row["kb_top_score"] is not None),
        "no_evidence_top_scores": {row["question_id"]: row["kb_top_score"] for row in rows if not row["answerable"]},
        "rows": rows,
    }


# ------------------------------------------------------------ check the citations

CITATION = re.compile(r"\[(kd_\d{2})\]")


def match_citations(answer: str, supplied: list[Passage]) -> tuple[list[Citation], list[str]]:
    """Find every citation in an answer and check that each names a passage the code supplied.

    Never show a citation that code has not matched to a passage it supplied.
    Each citation's S3 location comes from that passage, never from the model's text.
    """
    cited = list(dict.fromkeys(CITATION.findall(answer)))
    locations = {passage.doc_id: passage.location for passage in supplied}
    problems = [] if cited else ["the answer cites no document"]
    problems += [f"{doc_id} was not among the passages supplied" for doc_id in cited if doc_id not in locations]
    return [Citation(doc_id=doc_id, location=locations.get(doc_id)) for doc_id in cited], problems


def check_citations(answer: str, supplied: list[Passage], manifest: dict[str, dict]) -> tuple[list[Citation], list[str]]:
    """Check every citation in an answer: it must name a supplied passage and a document in the manifest.

    The manifest records where each ingested document came from, so a citation
    that it doesn't list names something the ingestion never loaded. Week 2 adds
    a check of the document's status, so that a superseded document is never cited.
    """
    citations, problems = match_citations(answer, supplied)
    problems += [f"{citation.doc_id} is not in the dataset manifest" for citation in citations
                 if citation.doc_id not in manifest]
    return citations, problems
