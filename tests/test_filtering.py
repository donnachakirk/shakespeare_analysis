from shakespeare_geo.filtering import (
    build_character_lexicon,
    llm_settlement_rejection_reason,
    postfilter_rejection_reason,
    prefilter_rejection_reason,
)


def test_prefilter_rejects_character_deity_and_landmark_phrase():
    lexicon = build_character_lexicon(["FRIAR JOHN", "ROMEO"])

    assert (
        prefilter_rejection_reason("Friar John", "Friar John", lexicon)
        == "pre_character_name"
    )
    assert prefilter_rejection_reason("God", "God", lexicon) == "pre_deity"
    assert (
        prefilter_rejection_reason("Capel's monument", "Capel's monument", lexicon)
        == "pre_possessive_landmark"
    )


def test_llm_filter_rejects_non_settlement_country():
    reason = llm_settlement_rejection_reason(
        entity_kind="place",
        place_granularity="country",
        is_real_world="true",
        should_keep="true",
    )
    assert reason == "llm_not_settlement"


def test_postfilter_accepts_city_and_rejects_country():
    assert (
        postfilter_rejection_reason(
            geocode_class="place",
            geocode_type="city",
            geocode_addresstype="city",
        )
        is None
    )

    assert (
        postfilter_rejection_reason(
            geocode_class="boundary",
            geocode_type="administrative",
            geocode_addresstype="country",
        )
        == "post_not_settlement_type"
    )


def test_postfilter_accepts_administrative_city_relation():
    assert (
        postfilter_rejection_reason(
            geocode_class="boundary",
            geocode_type="administrative",
            geocode_addresstype="city",
        )
        is None
    )
