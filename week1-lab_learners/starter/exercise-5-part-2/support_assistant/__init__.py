"""Support Assistant v1 for the fictional Kestrel Telecom course scenario.

The package generates answers from support documents, looks up cases and saves
proposed replies for supervisory approval. It uses a Claude model through
Amazon Bedrock. The dispatcher checks the caller's access before executing a
tool request. The package provides no tools to change accounts, issue credits
or send messages to customers.
"""

CHECKPOINT = "starter/exercise-5-part-2"

# The submodules, imported in dependency order so that `from support_assistant import config` works.
from . import config, ledger, schemas, bedrock, tools, loop, ingest, retrieval, assistant, prompts  # noqa: E402,F401
