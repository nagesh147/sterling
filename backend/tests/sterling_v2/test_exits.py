from app.engines.sterling_v2.exits import TrailState, atr_trailing


def test_trailing_ratchets_up_long():
    st = TrailState(stop=98.0)
    s1 = atr_trailing(prev_high=102, prev_low=99, entry=100, atr0=1.0, side=1,
                      state=st, trail_mult=1.5, be_at_r=1.0)
    assert st.moved_be is True and s1 >= 100.0  # pulled to BE
    s2 = atr_trailing(prev_high=110, prev_low=108, entry=100, atr0=1.0, side=1, state=st)
    assert s2 > s1  # ratchets up


def test_trailing_never_loosens():
    st = TrailState(stop=98.0)
    atr_trailing(110, 108, 100, 1.0, 1, st)
    high_stop = st.stop
    atr_trailing(101, 100, 100, 1.0, 1, st)  # price pulls back
    assert st.stop == high_stop  # stop does not move down


def test_trailing_ratchets_down_short():
    st = TrailState(stop=102.0)
    s1 = atr_trailing(prev_high=101, prev_low=98, entry=100, atr0=1.0, side=-1, state=st)
    assert st.moved_be is True and s1 <= 100.0  # pulled to BE for a short
    s2 = atr_trailing(prev_high=92, prev_low=90, entry=100, atr0=1.0, side=-1, state=st)
    assert s2 < s1  # short stop ratchets DOWN, never up
