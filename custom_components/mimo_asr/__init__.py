"""The Mimo ASR integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.STT]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Mimo ASR from a config entry."""
    _LOGGER.info("Setting up Mimo ASR integration for entry: %s", config_entry.entry_id)

    # 将配置条目转发到 STT 平台进行设置
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # 将配置数据存入 hass.data 以便其他模块访问（可选）
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    _LOGGER.info("Mimo ASR integration setup completed successfully.")
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Mimo ASR integration")

    # 清理数据
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(config_entry.entry_id, None)

    # 卸载平台
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
