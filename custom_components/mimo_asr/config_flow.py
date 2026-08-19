"""Config flow for Mimo ASR."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    NAME,
    CONF_API_KEY,
    CONF_SILENCE_SECONDS,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_REQUEST_TIMEOUT,
    SILENCE_SECONDS_MIN,
    SILENCE_SECONDS_MAX,
    REQUEST_TIMEOUT_MIN,
    REQUEST_TIMEOUT_MAX,
    MIMO_API_BASE,
    MIMO_ASR_MODEL,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mimo ASR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # 检查是否已有实例，防止重复配置
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_API_KEY): str,
                }),
                errors=errors,
                description_placeholders={
                    "docs_url": "https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition"
                }
            )

        # 可选：测试 API Key 是否有效
        # 使用 aiohttp 进行简单的 API 测试，避免引入 openai 库的阻塞问题
        # 注意：这里只做基本的连接测试，不进行完整的语音识别
        session = async_get_clientsession(self.hass)
        try:
            # 简单测试：调用模型列表或使用一个最小的请求
            # 由于 Mimo API 没有直接的验证端点，我们尝试用最小的请求来测试
            import json
            headers = {
                "Authorization": f"Bearer {user_input[CONF_API_KEY]}",
                "Content-Type": "application/json",
            }
            # 使用一个最小的请求来测试 API Key 是否有效
            test_payload = {
                "model": MIMO_ASR_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": "test"
                    }
                ],
                "max_tokens": 1
            }
            async with session.post(
                f"{MIMO_API_BASE}/chat/completions",
                headers=headers,
                json=test_payload,
                timeout=10
            ) as resp:
                if resp.status == 401:
                    errors["base"] = "invalid_auth"
                    _LOGGER.error("Invalid API Key")
                elif resp.status != 200:
                    # 其他错误不阻止配置，但记录日志
                    _LOGGER.warning("API test returned status %d", resp.status)
        except Exception as err:
            # 网络错误等不阻止配置，让用户继续
            _LOGGER.warning("API test failed: %s", err)

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_API_KEY): str,
                }),
                errors=errors,
                description_placeholders={
                    "docs_url": "https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition"
                }
            )

        # 创建配置条目
        return self.async_create_entry(
            title=NAME,
            data=user_input
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MimoASROptionsFlow(config_entry)


class MimoASROptionsFlow(config_entries.OptionsFlow):
    """Handle options for Mimo ASR."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SILENCE_SECONDS,
                    default=float(options.get(
                        CONF_SILENCE_SECONDS, DEFAULT_SILENCE_SECONDS
                    )),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(
                        min=SILENCE_SECONDS_MIN,
                        max=SILENCE_SECONDS_MAX,
                        min_included=True,
                        max_included=True,
                    ),
                ),
                vol.Optional(
                    CONF_REQUEST_TIMEOUT,
                    default=int(options.get(
                        CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
                    )),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=REQUEST_TIMEOUT_MIN,
                        max=REQUEST_TIMEOUT_MAX,
                        min_included=True,
                        max_included=True,
                    ),
                ),
            }),
        )
