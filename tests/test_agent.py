from diplomacy_ai.agent import PowerAgent
from diplomacy_ai.models import PowerView, InMessage

VIEW = PowerView(
    power_name="FRANCE", phase="S1901M", board_text="b",
    own_units=["A PAR"], own_centers=["PAR"],
    legal_orders={"PAR": ["A PAR H"]},
)


def _agent(provider):
    return PowerAgent(power_name="FRANCE", model="m", persona="bold",
                      provider=provider, temperature=0.5, timeout=10, end_year=1910)


async def test_negotiate_parses_and_sanitizes_messages(make_provider):
    prov = make_provider([{
        "reasoning": "think",
        "messages": [
            {"to": "england", "body": "ally?"},
            {"to": "GLOBAL", "body": "hello all"},
            {"to": "FRANCE", "body": "to self"},
            {"to": "ATLANTIS", "body": "bad"},
            {"to": "ENGLAND", "body": "   "},
        ],
    }])
    res = await _agent(prov).negotiate(VIEW, [], round_num=1, total_rounds=3)
    assert res.reasoning == "think"
    sent = {(m.to, m.body) for m in res.messages}
    assert sent == {("ENGLAND", "ally?"), ("GLOBAL", "hello all")}


async def test_negotiate_degrades_on_provider_error(make_provider):
    prov = make_provider([None])
    res = await _agent(prov).negotiate(VIEW, [InMessage("ENGLAND", "hi", "private")], 1, 3)
    assert res.messages == []
    assert res.meta.get("error") is True


async def test_decide_orders_parses_orders(make_provider):
    prov = make_provider([{"reasoning": "r", "orders": ["A PAR H", "  ", "A PAR - BUR"]}])
    res = await _agent(prov).decide_orders(VIEW)
    assert res.orders == ["A PAR H", "A PAR - BUR"]


async def test_decide_orders_degrades_to_hold_on_error(make_provider):
    prov = make_provider([None])
    res = await _agent(prov).decide_orders(VIEW)
    assert res.orders == [] and res.meta.get("error") is True


async def test_decide_orders_passes_rejected_to_prompt(make_provider):
    prov = make_provider([{"reasoning": "r", "orders": ["A PAR H"]}])
    await _agent(prov).decide_orders(VIEW, rejected=["A PAR - MOS"])
    assert "A PAR - MOS" in prov.calls[0]["user"]
