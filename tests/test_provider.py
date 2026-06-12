import pytest
from diplomacy_ai.provider import LiteLLMProvider, ProviderError


class _Msg:
    def __init__(self, content): self.content = content


class _Choice:
    def __init__(self, content): self.message = _Msg(content)


class _Resp:
    def __init__(self, content, usage=None):
        self.choices = [_Choice(content)]
        self.usage = usage


SCHEMA = {"type": "object", "properties": {"reasoning": {"type": "string"}},
          "required": ["reasoning"], "additionalProperties": False}


async def test_parses_json_content():
    async def fake(**kwargs):
        return _Resp('{"reasoning": "hello"}')
    prov = LiteLLMProvider(completion_fn=fake)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.data["reasoning"] == "hello"
    assert c.meta["model"] == "m" and "latency" in c.meta


async def test_retries_then_succeeds():
    calls = {"n": 0}
    async def fake(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("rate limited")
        return _Resp('{"reasoning": "ok"}')
    prov = LiteLLMProvider(completion_fn=fake, retries=2, backoff_base=0)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.data["reasoning"] == "ok" and calls["n"] == 2


async def test_backoff_sleeps_between_attempts(monkeypatch):
    sleeps = []
    async def fake_sleep(seconds): sleeps.append(seconds)
    monkeypatch.setattr("diplomacy_ai.provider.asyncio.sleep", fake_sleep)

    async def fake(**kwargs):
        raise RuntimeError("rate limited")
    prov = LiteLLMProvider(completion_fn=fake, retries=2, backoff_base=2.0)
    with pytest.raises(ProviderError):
        await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    # Sleeps after attempt 0 and 1 (not after the final attempt): 2**0, 2**1
    assert sleeps == [1.0, 2.0]


async def test_malformed_json_raises_provider_error():
    async def fake(**kwargs):
        return _Resp("not json")
    prov = LiteLLMProvider(completion_fn=fake, retries=1)
    with pytest.raises(ProviderError):
        await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
