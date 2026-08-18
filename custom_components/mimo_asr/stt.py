"""Support for Mimo speech to text service."""
from __future__ import annotations

import base64
import logging
import struct
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


def create_wav_header(sample_rate: int, channels: int, bits_per_sample: int, data_size: int) -> bytes:
    """生成标准 WAV 文件头 (44 字节)。"""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    fmt_chunk_size = 16
    audio_format = 1  # PCM

    header = b""
    # RIFF 块
    header += b"RIFF"
    header += struct.pack("<I", 36 + data_size)  # 总长度 (不包括 RIFF 和 size 字段)
    header += b"WAVE"
    # fmt 块
    header += b"fmt "
    header += struct.pack("<I", fmt_chunk_size)
    header += struct.pack("<H", audio_format)
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", block_align)
    header += struct.pack("<H", bits_per_sample)
    # data 块
    header += b"data"
    header += struct.pack("<I", data_size)
    return header


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
        return SUPPORTED_LANGUAGES

    @property
    def default_language(self) -> str:
        return DEFAULT_LANGUAGE

    @property
    def supported_formats(self) -> list[AudioFormats]:
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        _LOGGER.debug(
            "Processing audio stream. Language: %s, Format: %s, Codec: %s",
            metadata.language,
            metadata.format,
            metadata.codec,
        )

        if metadata.language not in SUPPORTED_LANGUAGES:
            _LOGGER.error("Unsupported language: %s", metadata.language)
            return SpeechResult("", SpeechResultState.ERROR)

        if metadata.format != AudioFormats.WAV:
            _LOGGER.error("Unsupported format: %s. Only WAV is supported.", metadata.format)
            return SpeechResult("", SpeechResultState.ERROR)

        # 收集音频数据（实际为 PCM 裸流）
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        if not audio_data:
            _LOGGER.error("Received empty audio stream.")
            return SpeechResult("", SpeechResultState.ERROR)

        _LOGGER.debug("Collected %d bytes of PCM audio data.", len(audio_data))

        # 根据元数据添加 WAV 头部
        sample_rate = metadata.sample_rate.value  # 16000
        channels = 1  # 根据 supported_channels
        bits_per_sample = 16  # 根据 supported_bit_rates

        wav_header = create_wav_header(sample_rate, channels, bits_per_sample, len(audio_data))
        wav_audio = wav_header + audio_data

        _LOGGER.debug("Created WAV audio of %d bytes (header %d + data %d).",
                      len(wav_audio), len(wav_header), len(audio_data))

        try:
            audio_base64 = base64.b64encode(wav_audio).decode("utf-8")
        except Exception as err:
            _LOGGER.error("Failed to base64 encode audio: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)

        client = await self._async_get_client()

        lang = metadata.language
        if lang == "zh-CN":
            lang = "zh"

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
                                    "data": audio_base64,
                                    "format": "wav"
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
