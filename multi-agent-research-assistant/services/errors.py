class RetrievalError(Exception):
    """A retrieval tool failed (network down, rate limit, bad response).

    Tools raise this with a human-readable message; the Research Agent catches it
    per tool so one failing source never crashes the whole run.
    """
