"""Config flow for Mimo ASR."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import DOMAIN, NAME, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mimo ASR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        # 检查是否已有实例，防止重复配置[reference:10]
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

        # 创建配置条目[reference:11]
        return self.async_create_entry(
            title=NAME,
            data=user_input
        )
