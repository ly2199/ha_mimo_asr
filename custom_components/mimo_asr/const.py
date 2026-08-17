"""Constants for Mimo ASR integration."""
DOMAIN = "mimo_asr"
NAME = "Mimo Speech-To-Text"

CONF_API_KEY = "api_key"

# Mimo API 配置
MIMO_API_BASE = "https://api.xiaomimimo.com/v1"
MIMO_ASR_MODEL = "mimo-v2.5-asr"

# 支持的语言 (BCP47 格式)[reference:7]
SUPPORTED_LANGUAGES = ["zh", "zh-CN", "en"]
DEFAULT_LANGUAGE = "zh"
