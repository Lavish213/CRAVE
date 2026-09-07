from app.services.search.query_interpreter import interpret_search_query


def test_extracts_supported_context_without_destroying_food_intent():
    result = interpret_search_query("cheap vegan ramen near me")

    assert result.lookup_query == "ramen"
    assert result.price_tier == 1
    assert result.required_categories == ("Vegan",)
    assert result.context == ("near_me",)
    assert result.uncertain is False


def test_unsupported_allergy_is_fail_closed_and_visible():
    result = interpret_search_query("nut free Thai food")

    assert result.lookup_query == "Thai food"
    assert result.hard_constraints == ("nut_free",)
    assert result.unsupported_hard_constraints == ("nut_free",)
    assert result.uncertain is True


def test_exact_place_name_is_left_untouched():
    result = interpret_search_query("Nido's Backyard")

    assert result.lookup_query == "Nido's Backyard"
    assert result.price_tier is None
    assert result.required_categories == ()


def test_context_only_query_has_a_stable_lookup_fallback():
    result = interpret_search_query("cheap date night near me")

    assert result.lookup_query == "restaurant"
    assert result.context == ("date_night", "near_me")
    assert result.uncertain is True


def test_unenforced_time_context_is_visible_and_uncertain():
    result = interpret_search_query("ramen open late")

    assert result.lookup_query == "ramen"
    assert result.context == ("open_late",)
    assert result.uncertain is True


def test_non_vegan_is_not_inverted_into_positive_vegan_filter():
    result = interpret_search_query("non-vegan ramen")

    assert result.lookup_query == "non-vegan ramen"
    assert result.required_categories == ()
    assert "vegan" not in result.hard_constraints
    assert result.uncertain is True


def test_not_vegan_is_not_inverted_into_positive_vegan_filter():
    result = interpret_search_query("not vegan ramen")

    assert result.lookup_query == "not vegan ramen"
    assert result.required_categories == ()
    assert "vegan" not in result.hard_constraints
    assert result.uncertain is True
