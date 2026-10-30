from app.repository.analyzer_service import RepositoryAnalyzerService


REPOSITORY_PATH = r"C:\Users\jayar\Downloads\TestForge IDE"


def test_repository_analysis_completes_successfully():
    """Verify that repository analysis returns a valid analysis."""
    service = RepositoryAnalyzerService()

    result = service.analyze_repository(REPOSITORY_PATH)

    assert result is not None
    assert result.repository_path == REPOSITORY_PATH
    assert result.project_name == "TestForge IDE"


def test_invalid_repository_path_is_rejected():
    """Verify that an invalid repository path is rejected."""
    service = RepositoryAnalyzerService()

    invalid_path = r"C:\invalid\repository\path"

    try:
        service.analyze_repository(invalid_path)
        assert False, "Expected repository analysis to fail"
    except FileNotFoundError:
        assert True