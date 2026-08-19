"""Constants for Mimo ASR integration."""
DOMAIN = "mimo_asr"
NAME = "Mimo Speech-To-Text"

CONF_API_KEY = "api_key"
CONF_SILENCE_SECONDS = "silence_seconds"
CONF_REQUEST_TIMEOUT = "request_timeout"

# Mimo API 配置
MIMO_API_BASE = "https://api.xiaomimimo.com/v1"
MIMO_ASR_MODEL = "mimo-v2.5-asr"

# 支持的语言 (BCP47 格式)
# 参考: https://developers.home-assistant.io/docs/core/entity/stt/\#properties
SUPPORTED_LANGUAGES = ["zh", "zh-CN", "en"]
DEFAULT_LANGUAGE = "zh"

# 识别参数默认值及范围
DEFAULT_SILENCE_SECONDS = 0.5
SILENCE_SECONDS_MIN = 0.3
SILENCE_SECONDS_MAX = 1.5

DEFAULT_REQUEST_TIMEOUT = 15
REQUEST_TIMEOUT_MIN = 5
REQUEST_TIMEOUT_MAX = 60

# 能量 VAD 参数（16kHz / 16bit / 单声道 PCM）
FRAME_BYTES = 320  # 10ms 一帧 (16000Hz * 2字节 * 0.01s)
SPEECH_RMS_THRESHOLD = 300  # 帧 RMS 达到该值视为语音
SPEECH_START_SECONDS = 0.3  # 累计语音达到该时长才进入"指令中"状态
MIN_COMMAND_SECONDS = 1.0  # 首个语音帧起总时长达到该值后才允许静音提前结束
MAX_AUDIO_SECONDS = 30.0  # 音频最长保留时长，超出强制截断
SILENCE_PAD_SECONDS = 0.2  # 裁剪后首尾保留的静音余量

