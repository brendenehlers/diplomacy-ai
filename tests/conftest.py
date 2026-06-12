import pytest
from diplomacy_ai.models import Completion
from diplomacy_ai.provider import ProviderError


class FakeProvider:
    """Returns queued payloads (dicts) in order; a payload of None raises."""
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._payloads.pop(0)
        if payload is None:
            raise ProviderError("boom")
        return Completion(data=payload, meta={"model": kwargs["model"]})


@pytest.fixture
def make_provider():
    return lambda payloads: FakeProvider(payloads)
