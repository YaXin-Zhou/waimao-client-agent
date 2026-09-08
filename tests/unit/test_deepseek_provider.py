from src.infrastructure.deepseek_provider import DeepSeekConfig, DeepSeekProvider


def test_provider_builds_structured_json_request_without_exposing_transport_details():
    captured = {}

    def fake_request(payload):
        captured.update(payload)
        return {
            "choices": [{"message": {"content": '{"company_type": "distributor"}'}}]
        }

    provider = DeepSeekProvider(
        DeepSeekConfig(
            api_key="test-key",
            base_url="https://api.example",
            model="deepseek-v4-flash",
        ),
        request=fake_request,
    )

    result = provider.generate_json("Classify this company")

    assert result == {"company_type": "distributor"}
    assert captured["model"] == "deepseek-v4-flash"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["response_format"] == {"type": "json_object"}


def test_provider_loads_local_env_values_without_printing_secrets(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=secret-value\n"
        "DEEPSEEK_BASE_URL=https://api.example\n"
        "DEEPSEEK_MODEL=deepseek-v4-pro\n",
        encoding="utf-8",
    )

    config = DeepSeekConfig.from_env_file(env_file)

    assert config.api_key == "secret-value"
    assert config.base_url == "https://api.example"
    assert config.model == "deepseek-v4-pro"
