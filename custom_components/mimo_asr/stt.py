"""Support for Mimo speech to text service."""
from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import AsyncIterable

from openai import AsyncOpenAI

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_API_KEY,
    MIMO_API_BASE,
    MIMO_ASR_MODEL,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mimo ASR entity from a config entry."""
    _LOGGER.info("Setting up Mimo ASR entity")
    async_add_entities([MimoASR(hass, config_entry)])


class MimoASR(SpeechToTextEntity):
    """Representation of a Mimo ASR entity."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Mimo ASR entity."""
        self.hass = hass
        self._config_entry = config_entry
        self._api_key: str = config_entry.data[CONF_API_KEY]

        # 不在 __init__ 中初始化 AsyncOpenAI，避免阻塞事件循环
        # 客户端将在 _get_client() 中延迟初始化
        self._client: AsyncOpenAI | None = None

        self._attr_name = "Mimo Speech to Text"
        self._attr_unique_id = f"{config_entry.entry_id}"

        _LOGGER.debug("Mimo ASR entity initialized")

    def _get_client(self) -> AsyncOpenAI:
        """获取或创建 AsyncOpenAI 客户端。
        
        客户端在第一次调用时创建，后续复用。
        注意：此方法应在 async 上下文中调用，但 AsyncOpenAI 的初始化
        本身是同步的，会触发 load_verify_locations 阻塞调用。
        但由于我们是在 async_process_audio_stream 中调用，
        Home Assistant 会检测到阻塞调用并发出警告。
        
        更好的方案是使用 async with 上下文管理器，但 openai 库
        目前不支持异步上下文管理器用于客户端初始化。
        
        参考 Home Assistant 官方 OpenAI 集成的做法：
        https://github.com/home-assistant/core/blob/dev/homeassistant/components/openai_conversation/__init__.py
        """
        if self._client is None:
            _LOGGER.debug("Creating AsyncOpenAI client")
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=MIMO_API_BASE,
            )
        return self._client

    # --- 以下为 STT 实体必需的属性 ---

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return DEFAULT_LANGUAGE

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        # STT 框架仅支持 WAV 和 OGG
        # 参考: https://developers.home-assistant.io/docs/core/entity/stt/\#properties
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    # --- 核心方法：处理音频流 ---

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process audio stream and send to Mimo ASR."""
        _LOGGER.debug(
            "Processing audio stream. Language: %s, Format: %s, Codec: %s",
            metadata.language,
            metadata.format,
            metadata.codec,
        )

        # 检查语言是否支持
        if metadata.language not in SUPPORTED_LANGUAGES:
            _LOGGER.error("Unsupported language: %s", metadata.language)
            return SpeechResult("", SpeechResultState.ERROR)

        # 收集音频流数据
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        if len(audio_data) == 0:
            _LOGGER.error("Received empty audio stream.")
            return SpeechResult("", SpeechResultState.ERROR)

        _LOGGER.debug("Collected %d bytes of audio data.", len(audio_data))

        # Base64 编码
        try:
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        except Exception as err:
            _LOGGER.error("Failed to base64 encode audio: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)

        # 确定 MIME 类型 - 只支持 WAV
        mime_type = "audio/wav"

        # 获取客户端（延迟初始化）
        client = self._get_client()

        # 调用 Mimo ASR API
        try:
            # 语言代码映射：HA 使用 zh-CN，Mimo 使用 zh
            lang = metadata.language
            if lang == "zh-CN":
                lang = "zh"

            completion = await client.chat.completions.create(
                model=MIMO_ASR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:{mime_type};base64,{audio_base64}"
                                }
                            }
                        ]
                    }
                ],
                extra_body={
                    "asr_options": {
                        "language": lang
                    }
                }
            )

            # 解析结果
            if completion.choices and completion.choices[0].message.content:
                result_text = completion.choices[0].message.content
                _LOGGER.info("Speech recognition successful: %s", result_text)
                return SpeechResult(result_text, SpeechResultState.SUCCESS)
            else:
                _LOGGER.error("No text in response: %s", completion)
                return SpeechResult("", SpeechResultState.ERROR)

        except Exception as err:
            _LOGGER.exception("Error during speech recognition: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)
