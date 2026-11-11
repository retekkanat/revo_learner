# Kestrel data contract

In Exercise 4, the workbook copies this template to `work/evidence/<your initials>/data-contract.md`. Complete that copy before you load any data. `schemas.py` implements version 1.0 of the required fields, formats and validation rules. Use this document to explain the data owners, access rules and storage decisions behind that schema.

A change to the accepted fields or validation rules requires a new contract version. Do not change the contract while an ingestion run is in progress.

- Contract version: 1.0
- Date: [write here]
- Owner of the contract: [write here]

## Data requirements

Describe Kestrel's support data by answering each question in one or two sentences.

1. Purpose: which assistant tasks need this data? [write here]
2. Readers: which people and applications read the data? [write here]
3. Sources: where does each kind of record come from? [write here]
4. Access: which records can each user role read? [write here]
5. Storage and processing: where does each kind of record go, and why there? [write here]

## Case records

| Field | Type | Required | Allowed values or rule | Owner | Personal data |
| --- | --- | --- | --- | --- | --- |
| `case_id` | String | Yes | `case_` and four digits; the stable key | [write here] | No |
| `customer_id` | String | Yes | `cust_` and four digits | [write here] | [write here] |
| `customer_name` | String | Yes | Not empty | [write here] | [write here] |
| `plan` | String | Yes | [write here] | [write here] | No |
| `status` | String | Yes | [write here] | [write here] | No |
| `opened_at` | String | Yes | [write here] | [write here] | No |
| `owner_team` | String | Yes | [write here] | [write here] | No |
| `summary` | String | Yes | Not empty | [write here] | [write here] |
| `history` | List of notes | Yes | At least one note; notes in time order | [write here] | [write here] |
| `postcode_area` | String | Yes | `KT-01` to `KT-09` | [write here] | [write here] |

A record with a field that is not in this table is rejected.

## Document metadata

| Field | Type | Required | Allowed values or rule | Owner |
| --- | --- | --- | --- | --- |
| `doc_id` | String | Yes | `kd_` and two digits, matching the file name | [write here] |
| `title` | String | Yes | The first line of the document | [write here] |
| `last_reviewed` | Date | Yes | [write here] | [write here] |
| `owner_team` | String | Yes | [write here] | [write here] |
| `audience` | String | Yes | [write here] | [write here] |
| `status` | String | Yes | [write here] | [write here] |

## Rules for rejected records and duplicates

Describe how ingestion handles each of these cases: an invalid record, an identical duplicate, and two records with the same key but different content.

[write here]

## Document review dates

Record the maximum document age allowed by the freshness check, measured from the dataset's reference date. Explain how the assistant handles a document older than that limit.

[write here]

## Chunking and the knowledge base

The chunking strategy cannot be changed after the data source is created, so record it here before you create one.

- Chunking strategy: [write here]
- Embedding model: [write here]
- Parser: [write here]
- Prefix the knowledge base reads: [write here]

## Contract changes

Identify who approves a new contract version. Describe how records loaded under the previous version are handled after the change.

[write here]
