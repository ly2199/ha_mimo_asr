"""Support for Mimo speech to text service."""
from __future__ import annotations

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

        # 客户端延迟初始化，使用 executor 避免阻塞事件循环
        self._client: AsyncOpenAI | None = None

        self._attr_name = "Mimo Speech to Text"
        self._attr_unique_id = f"{config_entry.entry_id}"

        _LOGGER.debug("Mimo ASR entity initialized")

    async def _async_get_client(self) -> AsyncOpenAI:
        """异步获取客户端，在 executor 中创建以避免阻塞事件循环。"""
        if self._client is None:
            _LOGGER.debug("Creating AsyncOpenAI client in executor")
            api_key = self._api_key

            def _create_client():
                return AsyncOpenAI(
                    api_key=api_key,
                    base_url=MIMO_API_BASE,
                )

            self._client = await self.hass.async_add_executor_job(_create_client)
        return self._client

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
        """Return a list of supported formats.
        Mimo supports wav and mp3, but HA STT only supports WAV and OGG.
        We only support WAV to ensure compatibility.
        """
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

        # 1. 语言检查
        if metadata.language not in SUPPORTED_LANGUAGES:
            _LOGGER.error("Unsupported language: %s", metadata.language)
            return SpeechResult("", SpeechResultState.ERROR)

        # 2. 严格检查格式：仅支持 WAV
        if metadata.format != AudioFormats.WAV:
            _LOGGER.error(
                "Unsupported format: %s. Only WAV is supported. "
                "Please ensure your audio source provides WAV format.",
                metadata.format,
            )
            return SpeechResult("", SpeechResultState.ERROR)

        # 3. 收集音频数据
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        if not audio_data:
            _LOGGER.error("Received empty audio stream.")
            return SpeechResult("", SpeechResultState.ERROR)

        _LOGGER.debug("Collected %d bytes of audio data.", len(audio_data))

        # 4. Base64 编码
        try:
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        except Exception as err:
            _LOGGER.error("Failed to base64 encode audio: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)

        # 5. 构造 Data URL（严格按照 Mimo 官方示例）
        data_url = f"data:audio/wav;base64,{audio_base64}"

        # 6. 获取客户端（非阻塞）
        client = await self._async_get_client()

        # 7. 语言映射
        lang = metadata.language
        if lang == "zh-CN":
            lang = "zh"

        # 8. 调用 Mimo API
        try:
            completion = await client.chat.completions.create(
                model=MIMO_ASR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": data_url
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
