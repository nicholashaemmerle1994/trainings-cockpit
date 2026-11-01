from __future__ import annotations

import pytest

from trainings_cockpit import fuel


def test_short_session_needs_nothing() -> None:
    assert fuel.carb_rate(30, "locker") == 0
    assert fuel.carb_rate(44, "race") == 0

    plan = fuel.plan(30, "locker")
    assert plan["total"]["carbs"] == 0
    assert plan["schedule"] == []
    assert plan["gels"]["count"] == 0


def test_bands_grow_with_duration() -> None:
    rates = [fuel.carb_rate(minutes, "race") for minutes in (60, 90, 120, 180, 240, 300)]
    assert rates == sorted(rates)
    assert rates[0] < rates[-1]


def test_race_is_higher_than_easy() -> None:
    for minutes in (60, 90, 120, 180, 240):
        assert fuel.carb_rate(minutes, "race") > fuel.carb_rate(minutes, "locker")


def test_cap_is_never_exceeded() -> None:
    for minutes in range(20, 900, 10):
        for mode in fuel.MODES:
            assert fuel.carb_rate(minutes, mode) <= fuel.CARB_CAP


def test_known_values() -> None:
    # 90 min locker: 45 g/h Band × 0,90
    assert fuel.carb_rate(90, "locker") == 40
    # 90 min Wettkampf: 45 g/h Band × 1,10
    assert fuel.carb_rate(90, "race") == 50
    # 2 h liegt schon im nächsten Band (60 g/h)
    assert fuel.carb_rate(120, "locker") == 55
    # 3 h Wettkampf: 75 g/h Band × 1,10 = 82,5 → aufgerundet 85
    assert fuel.carb_rate(180, "race") == 85
    # 4 h Wettkampf läuft in den Deckel
    assert fuel.carb_rate(240, "race") == 90


def test_plan_feeds_what_it_promises() -> None:
    plan = fuel.plan(240, "race", weight_kg=78, temp_c=18)
    hours = plan["input"]["hours"]

    carbs = plan["drink"]["carbs_per_bottle"] * plan["drink"]["bottles"]
    carbs += plan["gels"]["carbs_total"]
    assert carbs == pytest.approx(plan["per_hour"]["carbs"] * hours, abs=40)


def test_drink_and_gels_split_the_hour() -> None:
    drink = fuel.plan(180, "race")["drink"]
    assert drink["carbs_per_hour"] > 0
    assert drink["concentration_pct"] <= fuel.MAX_CONCENTRATION * 100
    assert drink["bottle_ml"] % 50 == 0


def test_short_easy_run_stays_light() -> None:
    plan = fuel.plan(45, "locker")
    assert plan["per_hour"]["carbs"] == 20
    assert plan["gels"]["count"] == 0
    assert plan["total"]["carbs"] < 25


def test_schedule_stays_inside_the_session() -> None:
    plan = fuel.plan(300, "race")
    minutes = [entry["minute"] for entry in plan["schedule"]]
    assert minutes == sorted(minutes)
    assert all(0 <= minute <= 300 - 10 for minute in minutes)
    assert plan["schedule"][0]["kind"] == "trinken"


def test_heat_adds_water_and_salt() -> None:
    cool = fuel.plan(240, "race", temp_c=12)
    hot = fuel.plan(240, "race", temp_c=30)
    assert hot["water"]["ml_per_hour"] > cool["water"]["ml_per_hour"]
    assert hot["sodium"]["mg_per_hour"] > cool["sodium"]["mg_per_hour"]


def test_short_session_has_no_sodium_target() -> None:
    assert fuel.plan(60, "race")["sodium"]["mg_per_hour"] == 0


def test_race_plan_includes_day_before() -> None:
    keys = [item["key"] for item in fuel.plan(240, "race", weight_kg=78)["surrounding"]]
    assert keys == ["vortag", "fruehstueck", "danach"]

    easy = [item["key"] for item in fuel.plan(240, "locker")["surrounding"]]
    assert "vortag" not in easy


def test_high_rate_warns_about_mixed_sugars() -> None:
    notes = " ".join(note["text"] for note in fuel.plan(300, "race")["notes"])
    assert "Fruktose" in notes


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        fuel.plan(120, "rennen")


def test_input_is_clamped() -> None:
    plan = fuel.plan(5, "locker", weight_kg=20, temp_c=80)
    assert plan["input"]["minutes"] == 20
    assert plan["input"]["weight_kg"] == 35
    assert plan["input"]["temp_c"] == 45


def test_syrup_replaces_gels_and_drink() -> None:
    plan = fuel.plan(240, "race", source="syrup")
    assert plan["gels"]["count"] == 0
    assert plan["drink"]["carbs_per_hour"] == 0
    assert plan["drink"]["bottle_ml"] == 500
    assert plan["syrup"] is not None


def test_syrup_amounts_for_four_hours() -> None:
    syrup = fuel.plan(240, "race", weight_kg=78, source="syrup", shot_ml=50)["syrup"]
    # 90 g/h ÷ 0,653 g KH je g Sirup ÷ 1,33 g/ml ≈ 104 ml/h
    assert syrup["ml_per_hour"] == pytest.approx(104, abs=2)
    assert syrup["ml_total"] == pytest.approx(416, abs=10)
    assert syrup["carbs_per_shot"] == pytest.approx(43, abs=1)
    assert syrup["shots"] == 8
    assert syrup["minutes_between"] == 29


def test_syrup_salt_per_shot() -> None:
    syrup = fuel.plan(240, "race", source="syrup", shot_ml=50)["syrup"]
    # 600 mg Natrium je Stunde ≈ 1,52 g Salz, verteilt auf 2,1 Shots
    assert syrup["salt_g_per_hour"] == pytest.approx(1.5, abs=0.1)
    assert syrup["salt_g_per_shot"] == pytest.approx(0.74, abs=0.05)


def test_larger_shot_means_fewer_shots() -> None:
    small = fuel.plan(240, "race", source="syrup", shot_ml=50)["syrup"]
    large = fuel.plan(240, "race", source="syrup", shot_ml=100)["syrup"]

    assert large["shots"] < small["shots"]
    assert large["carbs_per_shot"] == pytest.approx(87, abs=1)


def test_syrup_schedule_uses_shots() -> None:
    plan = fuel.plan(180, "race", source="syrup")
    labels = [entry["label"] for entry in plan["schedule"] if entry["kind"] == "essen"]
    assert labels and all(label.startswith("1 Shot") for label in labels)


def test_short_syrup_session_has_no_shots() -> None:
    plan = fuel.plan(30, "locker", source="syrup")
    assert plan["syrup"]["shots"] == 0
    assert plan["schedule"] == []


def test_unknown_source_raises() -> None:
    with pytest.raises(ValueError):
        fuel.plan(120, "locker", source="cola")


def test_syrup_schedule_has_no_water_entries() -> None:
    plan = fuel.plan(240, "race", source="syrup")
    assert plan["schedule"]
    assert all(entry["kind"] == "essen" for entry in plan["schedule"])


def test_short_run_suggests_a_smaller_shot() -> None:
    plan = fuel.plan(90, "locker", source="syrup", shot_ml=50)
    assert plan["syrup"]["shots"] == 1
    assert plan["syrup"]["suggestion"]["shot_ml"] == 25
    assert "25-ml-Shots" in plan["syrup"]["suggestion"]["text"]


def test_matching_shot_has_no_suggestion() -> None:
    plan = fuel.plan(90, "locker", source="syrup", shot_ml=25)
    assert plan["syrup"]["suggestion"] is None


def test_calibrated_easy_rate_matches_the_first_real_run() -> None:
    # 17 km in 1:51, gefahren mit 73 g Kohlenhydraten = 112 g Sirup
    plan = fuel.plan(111, "locker")
    assert plan["per_hour"]["carbs"] == 40
    assert plan["total"]["carbs"] == pytest.approx(73, abs=3)


def test_portion_can_be_weighed_in_grams() -> None:
    plan = fuel.plan(111, "locker", source="syrup", shot_ml=35 / fuel.SYRUP_DENSITY_G_PER_ML)
    syrup = plan["syrup"]

    assert syrup["shot_g"] == 35
    assert syrup["shot_ml"] == 26
    # 35 g × 0,653 = 22,9 g Kohlenhydrate
    assert syrup["carbs_per_shot"] == 23
    assert syrup["unit"] == "g"
    assert plan["schedule"][0]["label"] == "1 Shot à 35 g"


def test_grams_and_millilitres_are_not_the_same_number() -> None:
    by_grams = fuel.plan(111, "locker", source="syrup", shot_ml=35 / fuel.SYRUP_DENSITY_G_PER_ML)
    by_ml = fuel.plan(111, "locker", source="syrup", shot_ml=35)

    assert by_grams["syrup"]["carbs_per_shot"] == 23
    assert by_ml["syrup"]["carbs_per_shot"] == 30
