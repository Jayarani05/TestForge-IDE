import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _analyze(repository):
    return client.post(
        "/repository/analyze",
        json={"path": str(repository)},
    )


def test_repository_analysis_recommends_configured_pytest(
    tmp_path,
):
    (tmp_path / "requirements.txt").write_text(
        "pytest==8.3.0\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_orders.py").write_text(
        "def test_order():\n    assert True\n",
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] == "pytest"
    assert result["supported_test_frameworks"] == ["pytest"]
    assert result["supported_test_languages"] == ["Python"]
    assert result["framework_recommendation_evidence"] == [
        "Existing test file: tests/test_orders.py"
    ]


def test_repository_analysis_uses_pyproject_framework_configuration(
    tmp_path,
):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = \"-ra\"\n",
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] == "pytest"
    assert "pytest" in result["supported_test_frameworks"]
    assert "Python" in result["supported_test_languages"]
    assert result["framework_recommendation_evidence"] == [
        "Detected configured framework: Pytest"
    ]


def test_repository_analysis_recommends_configured_playwright(
    tmp_path,
):
    package_json = {
        "name": "browser-project",
        "devDependencies": {
            "@playwright/test": "^1.63.0",
        },
    }
    (tmp_path / "package.json").write_text(
        json.dumps(package_json),
        encoding="utf-8",
    )
    (tmp_path / "playwright.config.ts").write_text(
        "export default {};\n",
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] == "playwright"
    assert result["supported_test_frameworks"] == ["playwright"]
    assert "Existing automation file: playwright.config.ts" in (
        result["framework_recommendation_evidence"]
    )


def test_repository_analysis_does_not_recommend_unsupported_junit(
    tmp_path,
):
    (tmp_path / "pom.xml").write_text(
        "<project><dependencies><dependency>junit</dependency></dependencies></project>",
        encoding="utf-8",
    )
    (tmp_path / "src" / "test" / "java").mkdir(parents=True)
    (tmp_path / "src" / "test" / "java" / "OrderTest.java").write_text(
        "class OrderTest {}",
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] is None
    assert result["framework_recommendation_evidence"] == []
    assert result["supported_test_frameworks"] == []


def test_repository_analysis_returns_no_recommendation_without_evidence(
    tmp_path,
):
    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] is None
    assert result["framework_recommendation_evidence"] == []
    assert result["supported_test_frameworks"] == []


def test_repository_analysis_avoids_arbitrary_choice_when_test_frameworks_conflict(
    tmp_path,
):
    (tmp_path / "requirements.txt").write_text(
        "pytest==8.3.0\nselenium==4.20.0\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_unit.py").write_text(
        "def test_unit():\n    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "automation").mkdir()
    (tmp_path / "automation" / "selenium_tests.py").write_text(
        "from selenium import webdriver\n",
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] is None
    assert result["framework_recommendation_evidence"] == []


def test_repository_analysis_detects_selenium_support(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "selenium-project",
                "devDependencies": {
                    "selenium-webdriver": "^4.20.0",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "browser.test.js").write_text(
        'const { Builder } = require("selenium-webdriver");\n',
        encoding="utf-8",
    )

    response = _analyze(tmp_path)

    assert response.status_code == 200
    result = response.json()
    assert result["recommended_test_framework"] == "selenium"
    assert "selenium" in result["supported_test_frameworks"]
    assert "JavaScript" in result["supported_test_languages"]
