"""Outreach, timing, suppression and simulator building blocks (PROMPT.md §6.5-7)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from wiqaya.common import calendar as cal
from wiqaya.governance.suppress import SUPPRESSED, is_suppression_safe, suppress, suppress_records
from wiqaya.outreach.render import render, validate_llm_output
from wiqaya.simulate.engine import channel_sequence, crn


def test_suppress_dataframe() -> None:
    df = pd.DataFrame({"segment": ["a", "b"], "n": [5, 40], "rate": [0.5, 0.25]})
    out = suppress(df)
    assert out.loc[0, "rate"] == SUPPRESSED and out.loc[0, "n"] == SUPPRESSED
    assert out.loc[1, "rate"] == 0.25


def test_suppress_records_and_safety_check() -> None:
    rows = [{"segment": "x", "n": 3, "reach": 66.7}, {"segment": "y", "n": 30, "reach": 10.0}]
    assert not is_suppression_safe(rows)
    out = suppress_records(rows)
    assert out[0]["reach"] == SUPPRESSED and out[0]["suppressed"]
    assert is_suppression_safe(out)


def test_quiet_hours_and_friday() -> None:
    assert not cal.can_send(datetime(2026, 11, 3, 22, 0))[0]
    assert not cal.can_send(datetime(2026, 11, 6, 12, 0))[0]  # Friday midday
    assert cal.can_send(datetime(2026, 11, 3, 10, 0))[0]


def test_ramadan_send_after_iftar() -> None:
    assert not cal.can_send(datetime(2027, 2, 15, 12, 0))[0]
    when, notes = cal.next_send_time(datetime(2027, 2, 15, 12, 0))
    assert when.hour >= 19 and any("Ramadan" in n for n in notes)


def test_national_day_closed() -> None:
    from datetime import date

    assert not cal.clinic_open(date(2026, 12, 2))


def test_render_arabic_is_rtl_with_gloss() -> None:
    r = render(pathway="household_bundle", audience="adult", channel="whatsapp", language="ar",
               values={"recipient_first_name": "مريم", "n_members": "4", "member_names": "A & B",
                       "clinic_name": "Primary Care Centre – Khalifa City 1", "slot_options": "05/11 08:30"},
               send_from=datetime(2026, 11, 1, 10, 0))  # fmt: skip
    assert r.rtl and r.review_status == "machine_draft" and r.english_gloss
    assert "{" not in r.text


def test_llm_fence_rejects_new_numbers_and_blocklist() -> None:
    orig = "Your check is on 05/11."
    assert validate_llm_output(orig, "Your routine check is on 05/11.", 200, "en")
    assert not validate_llm_output(orig, "Your check is on 06/11.", 200, "en")
    assert not validate_llm_output(orig, "Your diabetes check is on 05/11.", 200, "en")


def test_chw_after_two_non_responses() -> None:
    assert channel_sequence(["sms", "chw_script"]) == ["sms", "sms", "chw_script"]
    assert channel_sequence(["whatsapp", "sms", "call_script", "chw_script"]) == ["whatsapp", "sms", "chw_script"]


def test_common_random_numbers_are_policy_independent() -> None:
    assert crn(1, "p-1", 0) == crn(1, "p-1", 0)
    assert crn(1, "p-1", 0) != crn(1, "p-1", 1)
    assert 0 <= crn(5, "x", 3) < 1
