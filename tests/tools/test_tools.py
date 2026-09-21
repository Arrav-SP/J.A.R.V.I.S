"""Unit tests for the JARVIS Tool Subsystem."""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.config.settings import Settings
from app.core.orchestrator import Orchestrator
from app.tools.registry import ToolRegistry
from app.tools.schemas import BaseTool, ToolDefinition, ToolParameter, ToolResult
from app.tools.web.search import WebSearchTool
from app.tools.web.weather import WeatherTool


class DummyEchoTool(BaseTool):
    """Simple test tool."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo",
            description="Echoes back the provided message.",
            parameters=[
                ToolParameter(name="msg", type_name="string", description="Text to echo", required=True)
            ],
        )

    def run(self, msg: str = "hello", **kwargs: object) -> str:
        if msg == "trigger_error":
            raise ValueError("Intentional dummy error")
        return f"echo: {msg}"


def test_tool_parameter_and_definition_schema() -> None:
    """Verify tool parameter and definition JSON Schema generation."""
    tool = DummyEchoTool()
    schema = tool.definition.to_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "echo"
    assert "msg" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["required"] == ["msg"]


def test_tool_execution_success_and_error() -> None:
    """Verify BaseTool.execute handles success and error encapsulation with timing."""
    tool = DummyEchoTool()

    res_ok = tool.execute(msg="test_ok")
    assert res_ok.success is True
    assert res_ok.data == "echo: test_ok"
    assert res_ok.execution_time_ms >= 0.0

    res_err = tool.execute(msg="trigger_error")
    assert res_err.success is False
    assert "Intentional dummy error" in str(res_err.error)


def test_tool_registry_lifecycle() -> None:
    """Verify ToolRegistry register, lookup, execution, and unregister."""
    registry = ToolRegistry()
    tool = DummyEchoTool()

    registry.register(tool)
    assert "echo" in registry.list_tools()
    assert registry.get_tool("echo") is tool

    schemas = registry.get_openai_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"

    res = registry.execute("echo", msg="from_registry")
    assert res.success is True
    assert res.data == "echo: from_registry"

    unreg_res = registry.execute("non_existent_tool")
    assert unreg_res.success is False
    assert "not registered" in str(unreg_res.error)

    assert registry.unregister("echo") is True
    assert "echo" not in registry.list_tools()


def test_weather_tool_wttr_success() -> None:
    """Verify WeatherTool correctly parses wttr.in JSON payload."""
    fake_wttr_json = {
        "current_condition": [
            {
                "temp_C": "28",
                "FeelsLikeC": "31",
                "weatherDesc": [{"value": "Partly cloudy"}],
                "humidity": "75",
                "windspeedKmph": "14",
                "precipMM": "0.2",
            }
        ],
        "nearest_area": [
            {
                "areaName": [{"value": "Vellore"}],
                "country": [{"value": "India"}],
            }
        ],
        "weather": [
            {
                "maxtempC": "34",
                "mintempC": "25",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_wttr_json).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    tool = WeatherTool()
    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = tool.execute(location="Vellore")
        assert res.success is True
        data = res.data
        assert data["location"] == "Vellore"
        assert data["temperature_c"] == 28.0
        assert data["feels_like_c"] == 31.0
        assert data["condition"] == "Partly cloudy"
        assert "28.0°C" in data["summary"]
        assert "Partly cloudy" in data["summary"]


def test_weather_tool_open_meteo_fallback() -> None:
    """Verify WeatherTool falls back to Open-Meteo if wttr.in fails."""
    geo_json = {
        "results": [
            {"name": "Vellore", "country": "India", "latitude": 12.9184, "longitude": 79.1325}
        ]
    }
    forecast_json = {
        "current": {
            "temperature_2m": 26.5,
            "apparent_temperature": 29.0,
            "relative_humidity_2m": 80,
            "wind_speed_10m": 12.0,
            "weather_code": 80,
            "precipitation": 1.5,
        },
        "daily": {
            "temperature_2m_max": [32.0],
            "temperature_2m_min": [24.0],
        },
    }

    geo_resp = MagicMock()
    geo_resp.read.return_value = json.dumps(geo_json).encode("utf-8")
    geo_resp.__enter__.return_value = geo_resp

    w_resp = MagicMock()
    w_resp.read.return_value = json.dumps(forecast_json).encode("utf-8")
    w_resp.__enter__.return_value = w_resp

    tool = WeatherTool()

    # Simulate wttr failing, then geocoding and forecast succeeding
    with patch.object(tool, "_fetch_wttr", side_effect=RuntimeError("wttr server down")):
        with patch("urllib.request.urlopen", side_effect=[geo_resp, w_resp]):
            res = tool.execute(location="Vellore")
            assert res.success is True
            assert res.data["location"] == "Vellore"
            assert res.data["temperature_c"] == 26.5
            assert res.data["condition"] == "Slight rain showers"


def test_web_search_tool_success() -> None:
    """Verify WebSearchTool parses DuckDuckGo HTML results."""
    fake_html = """
    <html>
        <tr>
            <td>
                <a class='result-link' href='https://example.com/ipl'>KKR wins IPL 2024 Final</a>
                <td class='result-snippet'>Kolkata Knight Riders beat SRH by 8 wickets to lift trophy.</td>
            </td>
        </tr>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_html.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    tool = WebSearchTool()
    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = tool.execute(query="who won IPL 2024")
        assert res.success is True
        assert res.data["count"] >= 1
        assert "KKR" in res.data["summary"]


def test_orchestrator_weather_tool_routing() -> None:
    """Verify Orchestrator intercepts weather query, runs tool, and injects telemetry into context."""
    orchestrator = Orchestrator(settings=Settings())

    fake_weather_data = {
        "summary": "Current weather in Vellore, India: 27.5°C, Light rain shower. Humidity: 85%, Wind: 10 km/h.",
        "location": "Vellore",
        "temperature_c": 27.5,
    }

    with patch.object(orchestrator.weather_tool, "execute", return_value=ToolResult(success=True, data=fake_weather_data)):
        response = orchestrator.process_message("What is the forecast for Vellore, Tamil Nadu?")
        assert "27.5°C" in response or "Vellore" in response
        assert len(response) > 10


def test_orchestrator_search_tool_routing() -> None:
    """Verify Orchestrator intercepts search query, runs search tool, and includes findings."""
    orchestrator = Orchestrator(settings=Settings())

    fake_search_data = {
        "summary": "[1] KKR Championship: Kolkata Knight Riders won the 2024 IPL final.",
        "results": [{"title": "KKR", "snippet": "Won title", "url": "http://ipl.com"}],
    }

    with patch.object(orchestrator.search_tool, "execute", return_value=ToolResult(success=True, data=fake_search_data)):
        response = orchestrator.process_message("Search who won the IPL 2024 final")
        assert "Kolkata Knight Riders" in response or "KKR" in response or "live search" in response.lower()
