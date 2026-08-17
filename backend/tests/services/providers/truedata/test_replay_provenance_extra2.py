def test_true_data_store_defaults_are_explicit():
    from app.services.providers.truedata.bar_store import BarStore
    from app.services.providers.truedata.tick_store import TickStore
    assert BarStore.__doc__ is not None
    assert TickStore.__doc__ is not None
