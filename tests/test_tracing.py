# SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import patch

from retasc.tracing import init_tracing


@patch("retasc.tracing.TracerProvider")
@patch("retasc.tracing.OTLPSpanExporter")
@patch("retasc.tracing.BatchSpanProcessor")
@patch("retasc.tracing.Resource")
def test_init_tracing_with_valid_config(
    mock_resource, mock_batch, mock_span_exporter, mock_provider, monkeypatch
):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://example.com")
    monkeypatch.setenv("OTEL_EXPORTER_SERVICE_NAME", "example_service")

    init_tracing()

    mock_provider.assert_called_once_with(resource=mock_resource.create.return_value)
    mock_span_exporter.assert_called_once_with(endpoint="https://example.com")
    mock_provider.return_value.add_span_processor.assert_called_once_with(
        mock_batch.return_value
    )


@patch("retasc.tracing.TracerProvider")
def test_init_tracing_with_invalid_config_name(mock_provider, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://example.com")
    monkeypatch.delenv("OTEL_EXPORTER_SERVICE_NAME", raising=False)
    init_tracing()
    mock_provider.assert_not_called()


@patch("retasc.tracing.TracerProvider")
def test_init_tracing_with_invalid_config_endpoint(mock_provider, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_SERVICE_NAME", "example_service")
    init_tracing()
    mock_provider.assert_not_called()
