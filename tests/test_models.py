import dataclasses
import pytest
from diplomacy_ai.models import (
    OutMessage, InMessage, NegotiationResult, OrderResult, Completion, PowerView,
)


def test_outmessage_is_frozen():
    m = OutMessage(to="FRANCE", body="hi")
    assert m.to == "FRANCE" and m.body == "hi"
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.body = "changed"


def test_results_default_to_empty_meta():
    n = NegotiationResult(reasoning="r", messages=[OutMessage("GLOBAL", "yo")])
    o = OrderResult(reasoning="r", orders=["A PAR H"])
    assert n.meta == {} and o.meta == {}


def test_powerview_holds_legal_orders_by_location():
    v = PowerView(
        power_name="FRANCE", phase="S1901M", board_text="...",
        own_units=["A PAR"], own_centers=["PAR"],
        legal_orders={"PAR": ["A PAR H", "A PAR - BUR"]},
    )
    assert v.legal_orders["PAR"][1] == "A PAR - BUR"
    assert Completion(data={"x": 1}, meta={}).data["x"] == 1
