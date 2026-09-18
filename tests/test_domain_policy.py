from harvester.domain_policy import DomainPolicy

def test_gov_allowed():
    p = DomainPolicy(["*.gov"], ["*.facebook.com"])
    assert p.is_allowed("https://tea.texas.gov/x")
    assert p.is_allowed("texas.gov")
    assert not p.is_allowed("https://facebook.com/gov")
    assert not p.is_allowed("https://example.com")

def test_state_us_pattern():
    p = DomainPolicy(["*.state.*.us"])
    assert p.is_allowed("www.sos.state.tx.us")

def test_seed_extra_host():
    p = DomainPolicy(["*.gov"], extra_allowed_hosts=["www.fldoe.org"])
    assert p.is_allowed("https://www.fldoe.org/budget.pdf")
