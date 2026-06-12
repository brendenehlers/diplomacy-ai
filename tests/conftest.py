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


from diplomacy_ai.models import NegotiationResult, OrderResult


class FakeAgent:
    """Scripted agent. `order_scripts` is a list of order-lists returned in sequence
    (first = initial, second = repair). `messages` returned every negotiate call."""
    def __init__(self, power_name, order_scripts=None, messages=None):
        self.power_name = power_name
        self._order_scripts = list(order_scripts or [[]])
        self._messages = messages or []
        self.order_calls = []

    async def negotiate(self, view, inbox, round_num, total_rounds):
        return NegotiationResult(reasoning="r", messages=list(self._messages))

    async def decide_orders(self, view, rejected=None):
        self.order_calls.append(rejected)
        orders = self._order_scripts.pop(0) if self._order_scripts else []
        return OrderResult(reasoning="r", orders=orders)
