import os

# Must be set before app.services.orchestrator is first imported anywhere in the
# test session — it builds the job store at import time and would otherwise try
# a real (network-dependent) Firestore connection.
os.environ.setdefault("JOB_STORE", "memory")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
