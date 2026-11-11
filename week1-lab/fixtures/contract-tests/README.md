# Contract-test fixtures

These synthetic records contain deliberate violations of the Exercise 4 data contract. In Exercise 1.11, run ingestion planning on them and compare the reported errors with the table below. Planning reads the fixtures locally; it does not write them to your bucket or case table.

| File | Record | Expected validation result |
| --- | --- | --- |
| `cases-contract-tests.json` | `case_9001`, first copy | Accepts it. |
| `cases-contract-tests.json` | `case_9001`, second copy | Counts it as a duplicate of the first, because its content is identical, and writes it once. |
| `cases-contract-tests.json` | `case_9002` | Rejects it: the required field `summary` is missing. |
| `cases-contract-tests.json` | `case_9003` | Rejects it for two reasons: `plan` is not an allowed value and `opened_at` is not an ISO 8601 UTC instant. |
| `cases-contract-tests.json` | `case_9004` | Rejects it: the field `priority` is not in the contract. |
| `cases-contract-tests.json` | `case_9001`, third copy | Rejects it: it has the key of an accepted record but different content, so a person must decide which is right. |
| `documents/kd-91-router-quick-start.html` | `kd-91` | Rejects it: HTML is not a supported document type. |
| `documents/kd-92-partner-terms.md` | `kd_92` | Rejects it: `partner` is not an allowed audience. |
| `documents/kd-93-unreviewed-notice.md` | `kd_93` | Rejects it: the required `Last reviewed` value is missing. |

Every name, identifier and note in these files is invented.
