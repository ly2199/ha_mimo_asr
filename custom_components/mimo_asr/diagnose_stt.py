"""Diagnose STT entities."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry

_LOGGER = logging.getLogger(__name__)

async def diagnose_stt(hass: HomeAssistant):
    """Diagnose STT entities."""
    _LOGGER.info("=== STT诊断开始 ===")
    
    # 检查所有STT实体
    registry = entity_registry.async_get(hass)
    stt_entities = []
    
    for entity in registry.entities.values():
        if entity.domain == "stt":
            stt_entities.append(entity)
    
    _LOGGER.info("找到 %d 个STT实体:", len(stt_entities))
    for entity in stt_entities:
        _LOGGER.info("  - %s (ID: %s)", entity.entity_id, entity.unique_id)
        
        # 获取实体对象
        entity_obj = hass.data["stt"].get(entity.entity_id)
        if entity_obj:
            _LOGGER.info("    支持的语言: %s", entity_obj.supported_languages)
            _LOGGER.info("    支持格式: %s", entity_obj.supported_formats)
            _LOGGER.info("    支持编解码器: %s", entity_obj.supported_codecs)
        else:
            _LOGGER.warning("    无法获取实体对象")
    
    # 检查语音助手配置
    _LOGGER.info("\n语音助手配置检查:")
    
    # 尝试获取默认管道
    from homeassistant.components.assist_pipeline import async_get_pipeline
    try:
        pipeline = await async_get_pipeline(hass, hass.config.language)
        if pipeline:
            _LOGGER.info("  当前管道: %s", pipeline.name)
            _LOGGER.info("  STT服务: %s", pipeline.stt_engine)
            _LOGGER.info("  TTS服务: %s", pipeline.tts_engine)
        else:
            _LOGGER.warning("  没有找到管道")
    except Exception as e:
        _LOGGER.error("  获取管道失败: %s", e)
    
    _LOGGER.info("=== STT诊断结束 ===")