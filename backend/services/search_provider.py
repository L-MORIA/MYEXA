"""Shared contract for the search providers.

The backend talks to more than one search backend: Exa is the primary one and
a local SearXNG instance is the fallback used when the primary is
unreachable. Both implement the same interface, so the application layer can
switch between them without knowing which one answered.
"""


class ProviderError(RuntimeError):
    """Base class for provider failures (network, HTTP status, bad answer)."""


class ProviderUnavailable(ProviderError):
    """Raised when every configured provider failed.

    It is a ``ProviderError`` because it carries a provider failure message —
    the application shows that reason to the user instead of a bare "no
    results".
    """


class SearchProvider:
    """Interface of a search provider.

    ``search`` returns a list of result dicts in the MYEXA format:
    ``url``, ``title``, ``highlights``, ``highlight_scores``, ``score``,
    ``published_date``, ``language``. Providers raise ``ProviderError``
    subclasses on failure — they never return an empty list to signal an
    error, because "nothing found" and "the backend is down" are different
    answers for the user.
    """

    name = "provider"

    def is_configured(self) -> bool:
        """Return True when the provider may be used at all."""
        return True

    def search(self, query: str, num_results: int = 10, language: str = "en",
               country: str = None) -> list[dict]:
        raise NotImplementedError
