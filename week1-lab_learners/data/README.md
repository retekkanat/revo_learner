# Kestrel Telecom dataset

This folder contains the Kestrel Telecom dataset used throughout the course. Kestrel is a fictional UK broadband provider. Its documents supply the assistant's answers, and its case records supply the case-lookup tool.

The folder also contains user roles and access rules, a goodwill-credit approval scenario, evaluation questions with reference answers, and the dated model prices used by the cost ledger. The exercises use the same files so you can compare their results.

The lab code reads these files and never changes them. The dataset includes defects such as those found in support records. The exercises ask you to find and handle them. If you change a file, run `check_data.py` before you commit, because the labs depend on those defects.

## Synthetic data

Kestrel Telecom, its plans, its staff, its customers, its cases and its documents are invented for this course. No real company, person, street or product is described. Phone numbers use only the range 01632 960000 to 01632 960999, which is reserved for fiction. Email addresses use only the reserved domains `kestrel.example` and `example.com`. Addresses are reduced to nine service areas written `KT-01` to `KT-09`, which aren't real postcodes. The dataset contains no account identifiers, credentials or access keys.

The one exception is `pricing.json`, which records real published Amazon Bedrock prices. Its `synthetic` field is `false` for that reason.

## Files

| File | What it holds | Where the course uses it |
| --- | --- | --- |
| `kestrel-company.md` | A one-page profile of Kestrel: plans, support teams, service levels and the four user roles. It isn't part of the corpus. | Day 1, to introduce the system, and as background for every exercise. |
| `documents/` | 25 short support documents that the assistant answers from. | Exercise 4 ingestion; Exercise 5 knowledge base, cited answers and prompt versions; Week 2 Day 6 retrieval comparison and answering only from evidence; Week 2 Day 8 knowledge base behind the gateway; Week 3 Day 13 evaluation. |
| `cases.json` | 40 support case records. | Exercise 2 structured output; Exercise 3 tools and injection cases; Exercise 4 data contract; Exercise 5 caller scope; Week 2 memory; Week 3 identity and policy. |
| `users.json` | Four users, one for each role, with the scopes that map to tool permissions and Cedar policies. | Exercise 5 caller scope; Week 3 sign-in, scoped tool calls and Cedar policies. |
| `approval-case.json` | One goodwill credit request that needs a supervisor's approval. | Day 9 durable workflow. |
| `questions.json` | 30 questions with reference answers, supporting documents, expected tool calls and assertions. | Exercise 5 retrieval measurement and prompt versions; Week 3 Day 13 AgentCore Evaluations ground truth. |
| `pricing.json` | Dated Bedrock prices for the Claude models that the course can use, through the EU inference profiles, read from the pricing page. | Exercise 2 usage ledger; Week 3 Day 14 cost attribution. |
| `check_data.py` | A standard-library script that validates every file against the schemas below and confirms that the dataset still contains its defects. | Before every commit that changes this folder, and in the lab builder's checks. |

## Conventions

The dataset describes Kestrel as it stands on its reference date, 31 October 2026. Every file that has a `reference_date` field uses that date, and the freshness check measures document age from it.

- **Timestamps** are UTC instants in ISO 8601 form, `YYYY-MM-DDTHH:MM:SSZ`. On and after 25 October 2026 UK time is the same as UTC, so a time such as 18:00 in a note is also the UK time.
- **Dates** are `YYYY-MM-DD`.
- **Money** in prose is written in pounds, such as £45.00. Money in JSON fields is an integer number of pence, in fields that end in `_pence`. Prices in `pricing.json` are US dollars per million tokens, as the AWS page shows them.
- **Identifiers** inside the data are snake_case and stable: `case_1001`, `cust_1001`, `kd_01`, `kq_01`, `user_customer_01`, `appr_0001` and the outage reference `inc_0457`.
- **Filenames** are kebab-case. A document's filename carries its identifier with a hyphen, so `documents/kd-07-refund-rules.md` holds the document whose identifier is `kd_07`. The identifier is also written inside the file, so the lab code never has to derive it from the name.

## Document corpus

The `documents/` folder holds 25 Markdown documents of 190 to 350 words each, so most fit in one or two chunks under the knowledge base's default chunking strategy. Every document starts with the same header:

```markdown
# Refund rules

Last reviewed: 2026-07-27
Document id: kd_07
Owner team: billing
Audience: customer
Status: current

The body starts here.
```

| Header line | Meaning |
| --- | --- |
| `# <title>` | The document's title, on the first line. |
| `Last reviewed: <date>` | The date someone last confirmed the document. The Exercise 4 freshness check compares it with the reference date. |
| `Document id: <kd_NN>` | The stable identifier that citations, `questions.json` and the dataset manifest use. |
| `Owner team: <team>` | The team responsible for the document: `customer_care`, `technical_support` or `billing`. |
| `Audience: <audience>` | `customer` for published documents, or `internal` for staff procedures. Retrieval for a customer must filter out internal documents. |
| `Status: <status>` | `current` for a document that Kestrel still uses, or `superseded` for one that a newer document has replaced. The assistant must not answer from a superseded document. |

Ingestion writes these header values to metadata files for the knowledge base. The application can then filter retrieval by fields such as audience and status.

| Id | File | Title | Owner team | Audience |
| --- | --- | --- | --- | --- |
| `kd_01` | `kd-01-contacting-support.md` | Contacting Kestrel support | `customer_care` | `customer` |
| `kd_02` | `kd-02-broadband-plans.md` | Kestrel broadband plans | `customer_care` | `customer` |
| `kd_03` | `kd-03-business-500-plan.md` | Business 500 plan | `customer_care` | `customer` |
| `kd_04` | `kd-04-speed-guarantee.md` | Speed guarantee | `technical_support` | `customer` |
| `kd_05` | `kd-05-fair-use-policy.md` | Fair use policy | `technical_support` | `customer` |
| `kd_06` | `kd-06-billing-dates-and-payment.md` | Billing dates and payment | `billing` | `customer` |
| `kd_07` | `kd-07-refund-rules.md` | Refund rules | `billing` | `customer` |
| `kd_08` | `kd-08-router-setup.md` | Setting up the KR-3 router | `technical_support` | `customer` |
| `kd_09` | `kd-09-wifi-troubleshooting.md` | Improving your Wi-Fi | `technical_support` | `customer` |
| `kd_10` | `kd-10-engineer-visits.md` | Engineer visits | `technical_support` | `customer` |
| `kd_11` | `kd-11-moving-home.md` | Moving home | `customer_care` | `customer` |
| `kd_12` | `kd-12-cancellation.md` | Cancelling your plan | `customer_care` | `customer` |
| `kd_13` | `kd-13-outage-procedure.md` | Outage procedure for support staff | `technical_support` | `internal` |
| `kd_14` | `kd-14-reporting-a-fault.md` | Reporting a fault | `technical_support` | `customer` |
| `kd_15` | `kd-15-service-levels-and-compensation.md` | Service levels and compensation | `technical_support` | `customer` |
| `kd_16` | `kd-16-goodwill-credits.md` | Goodwill credits: authority and evidence | `billing` | `internal` |
| `kd_17` | `kd-17-complaints.md` | Making a complaint | `customer_care` | `customer` |
| `kd_18` | `kd-18-account-security-and-privacy.md` | Account security and privacy | `customer_care` | `customer` |
| `kd_19` | `kd-19-price-changes.md` | Price changes | `billing` | `customer` |
| `kd_20` | `kd-20-installation-and-activation.md` | New connections and activation | `customer_care` | `customer` |
| `kd_21` | `kd-21-case-handling-standards.md` | Case handling standards | `customer_care` | `internal` |
| `kd_22` | `kd-22-priority-support.md` | Priority support | `customer_care` | `customer` |
| `kd_23` | `kd-23-digital-voice-home-phone.md` | Digital voice home phone | `technical_support` | `customer` |
| `kd_24` | `kd-24-traffic-management-policy.md` | Traffic management policy | `technical_support` | `customer` |
| `kd_25` | `kd-25-missed-payments.md` | Missed payments | `billing` | `customer` |

Documents refer to each other by title, as published support pages do, never by identifier.

## Case records: `cases.json`

The file is one JSON object. Its `cases` array holds 40 records in the order that a case export produced them.

| Top-level field | Type | Meaning |
| --- | --- | --- |
| `synthetic` | Boolean | Always `true`. |
| `dataset` | String | `kestrel_support_cases`. |
| `dataset_version` | String | The version of this file, `1.0`. |
| `reference_date` | Date | `2026-10-31`. |
| `cases` | Array of case records | The 40 records described below. |

Every field in a case record is required, and a record must have no other fields.

| Field | Type | Rule | Personal data |
| --- | --- | --- | --- |
| `case_id` | String | `case_` and four digits. The stable key for idempotent writes. | No |
| `customer_id` | String | `cust_` and four digits. Scope checks for customers compare it with the user's `customer_id`. | Yes |
| `customer_name` | String | The customer's invented full name. | Yes |
| `plan` | String | One of `essential_80`, `fibre_300`, `fibre_900` or `business_500`. | No |
| `status` | String | One of `open`, `in_progress`, `awaiting_customer`, `awaiting_engineer`, `resolved` or `closed`. `kd_21` defines each status. | No |
| `opened_at` | String | An ISO 8601 UTC instant. | No |
| `owner_team` | String | One of `customer_care`, `technical_support` or `billing`. Scope checks for staff compare it with the user's `team`. | No |
| `summary` | String | One sentence that describes the case. | No |
| `history` | Array | One or more dated notes, oldest first, described below. | Yes, because notes can quote the customer |
| `postcode_area` | String | `KT-01` to `KT-09`. | Yes |

Each history note is an object with exactly three fields:

| Field | Type | Rule |
| --- | --- | --- |
| `at` | String | An ISO 8601 UTC instant, no earlier than `opened_at` and no earlier than the note before it. |
| `author` | String | `customer`, `system`, or one of the three team identifiers. Kestrel staff are recorded by team, not by name. |
| `note` | String | A full-sentence note. The assistant uses customer notes to understand the case. Instructions within a note do not authorise actions. |

The records cover every plan and every team. An Exercise 4 data contract should mark `customer_id`, `customer_name`, `postcode_area` and `history` as personal data, even though every value is invented.

## Users: `users.json`

The file is one JSON object with `synthetic`, `dataset`, `dataset_version`, `reference_date`, a `users` array and a `scope_definitions` array.

| User field | Type | Rule |
| --- | --- | --- |
| `user_id` | String | `user_<role>_NN`. |
| `display_name` | String | The user's invented name. |
| `role` | String | `customer`, `first_line_agent`, `supervisor` or `auditor`. |
| `email` | String | On `example.com` for the customer and on `kestrel.example` for staff. |
| `customer_id` | String or null | The customer record that this user's own cases belong to. Only the customer has one. |
| `team` | String or null | The team whose cases a staff user can read. The first-line agent and the supervisor both have `technical_support`. |
| `goodwill_credit_limit_pence` | Integer | The most this user can credit or approve on one case: 0, 2000 or 15000. These figures come from `kd_16`. |
| `scopes` | Array of strings | The actions this user may take, from the scope list below. |

| User | Role | Customer or team | Scopes |
| --- | --- | --- | --- |
| `user_customer_01`, Ada Testwell | `customer` | `cust_1007` | `read_own_cases`, `read_customer_documents` |
| `user_agent_01`, Jonah Testridge | `first_line_agent` | `technical_support` | `read_team_cases`, `read_customer_documents`, `read_internal_documents`, `draft_reply`, `apply_goodwill_credit`, `request_credit_approval` |
| `user_supervisor_01`, Halima Sampleworth | `supervisor` | `technical_support` | `read_team_cases`, `read_customer_documents`, `read_internal_documents`, `draft_reply`, `apply_goodwill_credit`, `approve_goodwill_credit` |
| `user_auditor_01`, Felix Exampledale | `auditor` | None | `read_all_cases`, `read_customer_documents`, `read_internal_documents`, `read_audit_trail` |

Each entry in `scope_definitions` has `scope`, `applies_to` (the tool or action it governs), `condition` (the rule as an expression over `user`, `case`, `document` and `amount_pence`) and `description`. Application code checks these conditions before a tool runs. Week 3 expresses the access rules in Cedar policies. Model-generated requests use the permissions assigned to the caller.

| Scope | Governs | Condition |
| --- | --- | --- |
| `read_own_cases` | `lookup_case` | `case.customer_id == user.customer_id` |
| `read_team_cases` | `lookup_case` | `case.owner_team == user.team` |
| `read_all_cases` | `lookup_case` | Always allowed |
| `read_customer_documents` | Retrieval | `document.audience == "customer"` |
| `read_internal_documents` | Retrieval | `document.audience == "internal"` |
| `draft_reply` | `draft_reply` | The user can look up the case |
| `apply_goodwill_credit` | `apply_goodwill_credit` | The amount is within the user's limit and the user can look up the case |
| `request_credit_approval` | `request_credit_approval` | The amount is above the user's limit and the user can look up the case |
| `approve_goodwill_credit` | `approve_goodwill_credit` | The amount is within the user's limit and the user's team owns the case |
| `read_audit_trail` | `read_audit_trail` | Always allowed |

Week 1 has only the two tools in the exercise register, `lookup_case` and `draft_reply`. The credit actions arrive with the Week 2 workflow and the Week 3 policies.

## Approval case: `approval-case.json`

The file describes approval request `appr_0001`: a first-line agent asks the technical support supervisor to approve a £45.00 goodwill credit on `case_1028`, the third fault in seven weeks for customer `cust_1020`. The earlier faults are `case_1010` and `case_1020`.

| Field | Type | Meaning |
| --- | --- | --- |
| `synthetic`, `reference_date` | Boolean, date | As in the other files. |
| `approval_id` | String | `appr_0001`. |
| `case_id`, `customer_id`, `related_case_ids`, `owner_team` | Strings | The case under review, its customer, the customer's earlier related cases and the team that owns the case. |
| `submitted_at`, `requested_by`, `approver_role` | Strings | When the request was made, by which user, and which role decides it. |
| `policy_document` | String | `kd_16`, the goodwill credit policy that the decision applies. |
| `request` | Object | `type`, `amount_pence` (4500), `currency`, `reason`, `requester_limit_pence` (2000) and `approver_limit_pence` (15000). |
| `evidence_available` | Array | Five items, each with `evidence_id`, `kind`, `source`, `summary` and `establishes`. |
| `evidence_missing` | Array | Items that the goodwill credit policy requires and the case doesn't yet contain, each with `evidence_id`, `description`, `why_needed` and `supplied_by`. |
| `supplementary_evidence` | Array | The missing items as they arrive later, each with `evidence_id`, `arrives_at`, `source` and `summary`. A lab feeds them in after the workflow has asked for them. |
| `decision_states` | Array | Each state has `state`, `decided_by`, `next_states` and `meaning`. |
| `initial_state` | String | `submitted`. |

The file contains the request and evidence for the Day 9 approval exercise. It omits the expected decision; learners assess the request against the goodwill credit policy.

| State | Decided by | Next states |
| --- | --- | --- |
| `submitted` | system | `under_review` |
| `under_review` | supervisor | `approved`, `rejected`, `more_evidence_requested` |
| `more_evidence_requested` | supervisor | `under_review`, `rejected` |
| `approved` | supervisor | `applied` |
| `rejected` | supervisor | None |
| `applied` | billing | None |

## Question set: `questions.json`

The file is one JSON object with `synthetic`, `dataset`, `dataset_version`, `reference_date`, `tools` (`["lookup_case", "draft_reply"]`) and a `questions` array of 30 entries. Each question is one session for evaluation purposes.

| Field | Type | Rule |
| --- | --- | --- |
| `question_id` | String | `kq_01` to `kq_30`. |
| `asked_by` | String | The `user_id` of the person asking. Scope is judged against this user. |
| `question` | String | The question as the user would type it. |
| `reference_answer` | String | The expected response in full sentences. It names every supporting document by identifier. |
| `supporting_documents` | Array of document ids | The documents that support the reference answer. It is empty only for `no_evidence` questions. Retrieval hit rate is measured against this list. |
| `misleading_documents` | Array of document ids | Documents that retrieval is likely to return but that must not be used to answer. The list is often empty. |
| `case_id` | String or null | The case the question is about, when it needs a case lookup. |
| `expected_tools` | Array of tool names | The tool calls that the reference assistant makes, in order. It is empty when the application answers from retrieval alone, because retrieval isn't a model tool in Week 1. `draft_reply` always follows `lookup_case`. |
| `assertions` | Array of one to three strings | Sentences that a judge can check against a response. |
| `category` | String | One of the five categories below. |

| Category | Meaning |
| --- | --- |
| `answerable` | The corpus, and the case when there is one, support a single correct answer. |
| `no_evidence` | No document answers the question, and the correct response says so without guessing. |
| `contradicted` | The supporting documents disagree, and the correct response says so instead of choosing one. |
| `out_of_date` | Retrieval is likely to return a document that is no longer current. |
| `out_of_scope` | The question asks about a case that the asking user may not see. |

Use `asked_by` to run each evaluation question as its specified user, with that user's access rules. Use `case_id` to check that `lookup_case` requested the correct case and to assess a draft against the case history. If a response cites a document in `misleading_documents`, count it as a failure even when its wording otherwise appears correct.

For AgentCore Evaluations on Day 13, in Week 3, map `reference_answer` to the expected response and `assertions` to the session assertions. `expected_tools` records the expected sequence of tool calls, also called the tool trajectory.

For an `out_of_scope` question, the expected sequence is `["lookup_case"]`: the tool checks case ownership when called. A model may instead decline before requesting the tool. In either case, the assertions require the response to disclose no information about the restricted case.

## Price register: `pricing.json`

| Field | Meaning |
| --- | --- |
| `source` | The page URL, the date it was read (`read_on`), the table that was read, how it was read, and the model pages that confirmed the inference profile identifiers. |
| `region`, `region_name`, `inference_type` | `eu-west-2`, Europe (London), and `geo_cross_region`, which is the table that prices the `eu.` inference profiles. |
| `currency`, `unit` | `USD` and `per_million_tokens`. |
| `course_model` | The inference profile that the labs call, which is the one the usage ledger prices by default. |
| `comparison_model` | The larger model that Day 2 compares with the course model. It must be in the Active stage. |
| `models` | One entry for each model, with `model_name`, `inference_profile_id`, `lifecycle`, `input`, `output`, `cache_write_5m`, `cache_write_1h`, `cache_read`, `batch_input`, `batch_output` and `long_context`. A `null` price means that the page showed N/A or no such row. |
| `managed_knowledge_bases` | The managed knowledge base prices, with `source_url`, `read_on`, `section`, `currency`, `retrieve_per_1000_requests`, `storage_per_gb_month`, `agentic_retrieve_per_1000_requests`, `agentic_underlying_retrieve_per_1000_requests`, `managed_parsing_embeddings_reranking` and `notes`. The usage ledger reads `retrieve_per_1000_requests` for each Retrieve call. |
| `global_cross_region_for_comparison` | The lower prices that the page lists for the global profiles, for comparison only. |
| `notes` | What the reader must know before using the figures. |

| Model | Inference profile | Input | Output | Cache read |
| --- | --- | --- | --- | --- |
| Claude Haiku 4.5, the course model | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | $1.10 | $5.50 | $0.11 |
| Claude Sonnet 4.6, the Day 2 comparison model | `eu.anthropic.claude-sonnet-4-6` | $3.30 | $16.50 | $0.33 |
| Claude Sonnet 4.5 | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` | $3.30 | $16.50 | $0.33 |
| Claude Haiku 5.5 | `eu.anthropic.claude-haiku-5-5` | $0.11 | $0.55 | $0.011 |
| Claude Sonnet 5.5 | `eu.anthropic.claude-sonnet-5-5` | $2.20 | $11.00 | $0.11 |

The course uses Claude Haiku 4.5 and compares it with Claude Sonnet 4.6 on Day 2. The register also includes prices for three other models. Check each model's availability and lifecycle before using it; the register records these details as checked on 31 October 2026.

A managed knowledge base costs $1.00 for every 1,000 Retrieve calls and $5.00 for each GB of raw data stored each month. Agentic retrieval costs $4.00 for every 1,000 calls, plus $1.00 for every 1,000 Retrieve calls it makes. The managed parser, embedding model and reranker cost nothing extra.

The prices were read from <https://aws.amazon.com/bedrock/pricing/> on 31 October 2026, in prices per million tokens. Recheck them before each cohort and update `read_on`.

## Check the dataset

Run the check from the `week1/labs` folder:

```bash
uv run python data/check_data.py
```

The script needs only Python 3.12 or later, so `python3 data/check_data.py` works too. It exits with status 0 when the dataset passes and 1 when it doesn't. It prints the size of each file and how many defects of each kind the dataset contains, but not where they are.

The script checks the following:

- Every document has the header above, an identifier that matches its filename, a known owner team, audience and status, and a body of 150 to 400 words.
- Every document more than 365 days old on the reference date is marked `superseded`, every `superseded` document is that old, and no document is dated after the reference date.
- No document mentions what the `no_evidence` questions ask about.
- `cases.json` has 40 records with the fields and values described above, each customer has one name and one area, and every plan and team has at least five valid cases. The script counts the records that break the contract, the case identifiers that appear more than once, and the case notes that address an assistant.
- `users.json` has one user for each role, known scopes, a defined condition for every scope, and a customer whose cases exist.
- `approval-case.json` refers to a valid case owned by the approver's team, asks for an amount above the requester's limit and within the approver's, defines every state it names, supplies every missing evidence item later, and contains no expected outcome.
- `questions.json` has 30 questions in the stated categories. Only the `no_evidence` questions lack a supporting document. Each reference answer names its supporting documents, no question cites a superseded document as support, customers cite only customer documents, and tool lists are valid. Every case question is inside the asking user's scope, except the `out_of_scope` questions, which are outside it.
- `pricing.json` names the pricing page, a read date and `eu-west-2`, gives positive prices for the five EU inference profiles, names an Active course model and an Active comparison model, and gives a positive Retrieve price and storage price for managed knowledge bases.
- No file contains a phone number outside 01632 960000 to 01632 960999, an email domain other than `kestrel.example` or `example.com`, text shaped like a UK postcode, a link to another site except the AWS pages that `pricing.json` cites, a 12-digit number, an access key or an ARN.

Instructors have two more options, `--staff` and `--self-test`, which need a staff-only file that the learner package doesn't include.
