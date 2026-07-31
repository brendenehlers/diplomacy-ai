import pytest
from diplomacy_ai.provider import OpenAIProvider, ProviderError


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
    prov = OpenAIProvider(completion_fn=fake)
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
    prov = OpenAIProvider(completion_fn=fake, retries=2, backoff_base=0)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.data["reasoning"] == "ok" and calls["n"] == 2


async def test_backoff_sleeps_between_attempts(monkeypatch):
    sleeps = []
    async def fake_sleep(seconds): sleeps.append(seconds)
    monkeypatch.setattr("diplomacy_ai.provider.asyncio.sleep", fake_sleep)

    async def fake(**kwargs):
        raise RuntimeError("rate limited")
    prov = OpenAIProvider(completion_fn=fake, retries=2, backoff_base=2.0)
    with pytest.raises(ProviderError):
        await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    # Sleeps after attempt 0 and 1 (not after the final attempt): 2**0, 2**1
    assert sleeps == [1.0, 2.0]


async def test_model_id_passed_through_verbatim():
    seen = {}
    async def fake(**kwargs):
        seen.update(kwargs)
        return _Resp('{"reasoning": "ok"}')
    prov = OpenAIProvider(completion_fn=fake)
    c = await prov.complete(model="anthropic:anthropic/claude-sonnet-4", system="s",
                            user="u", schema=SCHEMA, schema_name="t",
                            temperature=0.5, timeout=10)
    assert seen["model"] == "anthropic:anthropic/claude-sonnet-4"
    assert c.meta["model"] == "anthropic:anthropic/claude-sonnet-4"


async def test_temperature_omitted_when_none():
    seen = {}
    async def fake(**kwargs):
        seen.update(kwargs)
        return _Resp('{"reasoning": "ok"}')
    prov = OpenAIProvider(completion_fn=fake)
    await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                        schema_name="t", temperature=None, timeout=10)
    assert "temperature" not in seen


async def test_temperature_sent_when_set():
    seen = {}
    async def fake(**kwargs):
        seen.update(kwargs)
        return _Resp('{"reasoning": "ok"}')
    prov = OpenAIProvider(completion_fn=fake)
    await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                        schema_name="t", temperature=0.3, timeout=10)
    assert seen["temperature"] == 0.3


class _Usage:
    def __init__(self, **fields):
        self.prompt_tokens = fields.pop("prompt_tokens", 10)
        self.completion_tokens = fields.pop("completion_tokens", 20)
        for k, v in fields.items():
            setattr(self, k, v)


async def test_reads_cost_from_usage():
    async def fake(**kwargs):
        return _Resp('{"reasoning": "ok"}', usage=_Usage(cost=0.0042))
    prov = OpenAIProvider(completion_fn=fake)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.meta["cost"] == 0.0042
    assert c.meta["prompt_tokens"] == 10 and c.meta["completion_tokens"] == 20


async def test_cost_is_none_when_usage_omits_it():
    async def fake(**kwargs):
        return _Resp('{"reasoning": "ok"}', usage=_Usage())
    prov = OpenAIProvider(completion_fn=fake)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.meta["cost"] is None


def test_missing_api_key_raises_provider_error(monkeypatch):
    monkeypatch.delenv("NGROK_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="NGROK_API_KEY"):
        OpenAIProvider()


async def test_malformed_json_raises_provider_error():
    async def fake(**kwargs):
        return _Resp("not json")
    prov = OpenAIProvider(completion_fn=fake, retries=1)
    with pytest.raises(ProviderError):
        await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
