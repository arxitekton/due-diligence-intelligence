from cdd.extract import ExtractorUnavailable, capabilities


def test_capabilities_returns_bool_dict_and_never_raises():
    caps = capabilities()
    assert isinstance(caps, dict)
    assert set(caps) >= {"html", "pdf", "edgar", "fetch"}
    assert all(isinstance(v, bool) for v in caps.values())


def test_extractor_unavailable_is_runtime_error():
    assert issubclass(ExtractorUnavailable, RuntimeError)


def test_html_clean_raises_or_works_without_crashing_import():
    # importing the module must never fail even if bs4 is absent
    from cdd.extract import html_clean  # noqa: F401


def test_capabilities_reports_new_backends():
    from cdd.extract import capabilities
    caps = capabilities()
    for key in ("gleif", "companies_house", "gdelt", "sanctions_xml"):
        assert key in caps and isinstance(caps[key], bool)
