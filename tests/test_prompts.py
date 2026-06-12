from diplomacy_ai.models import PowerView, InMessage
from diplomacy_ai.prompts import (
    negotiation_prompt, orders_prompt, NEGOTIATION_SCHEMA, ORDERS_SCHEMA,
)

VIEW = PowerView(
    power_name="FRANCE", phase="S1901M", board_text="FRANCE: units [A PAR]",
    own_units=["A PAR"], own_centers=["PAR"],
    legal_orders={"PAR": ["A PAR H", "A PAR - BUR"]},
)


def test_negotiation_prompt_includes_power_round_and_inbox():
    inbox = [InMessage(sender="ENGLAND", body="ally?", scope="private")]
    system, user = negotiation_prompt(
        VIEW, "cautious", inbox, round_num=2, total_rounds=3, end_year=1910)
    assert "FRANCE" in system and "cautious" in system
    assert "1910" in system and "18 supply" in system
    assert "round 2 of 3" in user.lower()
    assert "ENGLAND" in user and "ally?" in user
    assert "A PAR - BUR" in user


def test_negotiation_prompt_handles_empty_inbox():
    system, user = negotiation_prompt(VIEW, "", [], round_num=1, total_rounds=3, end_year=1910)
    assert "no messages" in user.lower()


def test_orders_prompt_lists_legal_orders_and_rejected():
    system, user = orders_prompt(VIEW, "bold", end_year=1910, rejected=["A PAR - MOS"])
    assert "A PAR - BUR" in user
    assert "A PAR - MOS" in user
    assert "rejected" in user.lower()


def test_schemas_are_well_formed():
    assert NEGOTIATION_SCHEMA["required"] == ["reasoning", "messages"]
    assert ORDERS_SCHEMA["required"] == ["reasoning", "orders"]
