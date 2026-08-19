"""Support for Mimo speech to text service."""
from __future__ import annotations

import asyncio
import base64
import logging
import math
import struct
from array import array
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
    CONF_API_KEY,
    CONF_SILENCE_SECONDS,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_SILENCE_SECONDS,
    DEFAULT_REQUEST_TIMEOUT,
    MIMO_API_BASE,
    MIMO_ASR_MODEL,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    FRAME_BYTES,
    SPEECH_RMS_THRESHOLD,
    SPEECH_START_SECONDS,
    MIN_COMMAND_SECONDS,
    MAX_AUDIO_SECONDS,
    SILENCE_PAD_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2  # 16-bit
_FRAME_SECONDS = FRAME_BYTES / (_SAMPLE_RATE * _SAMPLE_WIDTH)


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


def _frame_rms(frame: bytes) -> float:
    """计算 16-bit PCM 帧的均方根（能量）。"""
    samples = array("h")
    samples.frombytes(frame)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


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

        options = self._config_entry.options
        silence_seconds = float(
            options.get(CONF_SILENCE_SECONDS, DEFAULT_SILENCE_SECONDS)
        )
        request_timeout = float(
            options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
        )

        # 流式消费音频（实际为 PCM 裸流），逐帧做能量检测
        chunks: list[bytes] = []
        pending = bytearray()
        frames: list[bool] = []  # 每帧是否为语音
        first_speech_frame: int | None = None
        last_speech_frame: int | None = None
        speech_seconds = 0.0
        trailing_silence_seconds = 0.0
        stop_early = False

        try:
            async for chunk in stream:
                chunks.append(chunk)
                pending.extend(chunk)
                while len(pending) >= FRAME_BYTES:
                    frame = bytes(pending[:FRAME_BYTES])
                    del pending[:FRAME_BYTES]
                    frame_index = len(frames)
                    is_speech = _frame_rms(frame) >= SPEECH_RMS_THRESHOLD
                    frames.append(is_speech)

                    if is_speech:
                        trailing_silence_seconds = 0.0
                        speech_seconds += _FRAME_SECONDS
                        if first_speech_frame is None:
                            first_speech_frame = frame_index
                        last_speech_frame = frame_index
                    else:
                        trailing_silence_seconds += _FRAME_SECONDS

                    if len(frames) * _FRAME_SECONDS >= MAX_AUDIO_SECONDS:
                        _LOGGER.debug("Audio reached max duration cap, stopping early")
                        stop_early = True
                        break

                    if (
                        first_speech_frame is not None
                        and speech_seconds >= SPEECH_START_SECONDS
                        and (frame_index - first_speech_frame + 1) * _FRAME_SECONDS
                        >= MIN_COMMAND_SECONDS
                        and trailing_silence_seconds >= silence_seconds
                    ):
                        _LOGGER.debug(
                            "Trailing silence %.2fs detected after %.2fs of speech, "
                            "ending recognition early (frame %d/%d)",
                            trailing_silence_seconds,
                            speech_seconds,
                            frame_index + 1,
                            len(frames),
                        )
                        stop_early = True
                        break

                if stop_early:
                    break
        except asyncio.CancelledError:
            _LOGGER.debug("Speech recognition cancelled")
            raise
        finally:
            if hasattr(stream, "aclose"):
                await stream.aclose()

        if first_speech_frame is None:
            _LOGGER.debug(
                "No speech detected in %d frames, skipping API call",
                len(frames),
            )
            return SpeechResult("", SpeechResultState.SUCCESS)

        # 裁剪首尾静音，各保留少量余量，避免切掉辅音起始/收尾
        pad_frames = round(SILENCE_PAD_SECONDS / _FRAME_SECONDS)
        assert last_speech_frame is not None
        start_frame = max(0, first_speech_frame - pad_frames)
        end_frame = min(len(frames), last_speech_frame + 1 + pad_frames)

        audio_data = b"".join(chunks)
        audio_data = audio_data[start_frame * FRAME_BYTES : end_frame * FRAME_BYTES]

        _LOGGER.debug(
            "Collected %d bytes PCM (frames %d-%d of %d), %.2fs of speech",
            len(audio_data),
            start_frame,
            end_frame,
            len(frames),
            speech_seconds,
        )

        # 根据元数据添加 WAV 头部
        wav_header = create_wav_header(
            metadata.sample_rate.value, 1, 16, len(audio_data)
        )
        wav_audio = wav_header + audio_data
        audio_base64 = base64.b64encode(wav_audio).decode("utf-8")

        client = await self._async_get_client()

        lang = metadata.language
        if lang == "zh-CN":
            lang = "zh"

        try:
            completion = await client.with_options(
                timeout=request_timeout, max_retries=1
            ).chat.completions.create(
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
        except asyncio.CancelledError:
            _LOGGER.debug("API request cancelled")
            raise
        except Exception as err:
            _LOGGER.exception("Error during speech recognition: %s", err)
            return SpeechResult("", SpeechResultState.ERROR)

        if completion.choices and completion.choices[0].message.content:
            result_text = completion.choices[0].message.content
            _LOGGER.info("Speech recognition successful: %s", result_text)
            return SpeechResult(result_text, SpeechResultState.SUCCESS)
        else:
            _LOGGER.error("No text in response: %s", completion)
            return SpeechResult("", SpeechResultState.ERROR)
