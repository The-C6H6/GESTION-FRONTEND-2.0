from esiqie_dictamenes.core.services import build_demo_services


def test_demo_services_do_not_share_mutable_repositories_between_sessions():
    first = build_demo_services()
    second = build_demo_services()

    assert first.dictamen_repository is not second.dictamen_repository
    assert first.auth_repository is not second.auth_repository
