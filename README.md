# Mimo Speech-To-Text 集成 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![ha_version](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg)](https://www.home-assistant.io/)
[![GitHub release](https://img.shields.io/github/v/release/ly2199/ha_mimo_asr)](https://github.com/ly2199/ha_mimo_asr/releases)

使用 Mimo ASR 服务为 Home Assistant 提供语音识别（STT）能力，让您的语音助手更智能、更精准。

## ✨ 特性

- 基于 [Mimo ASR](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition) 云端识别引擎
- 支持中英文语音识别
- 低延迟、高准确率
- 完美集成 Home Assistant 语音助手（Assist Pipeline）
- 仅需 API Key，配置简单

## 📋 前提条件

- Home Assistant 2024.1 或更高版本
- 有效的 [Mimo API Key](https://mimo.mi.com/)（需注册并获取）

## 📦 安装

### 方法一：通过 HACS（推荐）

1. 确保你已经安装了 [HACS](https://hacs.xyz/)。
2. 在 HACS 中点击右上角菜单 → **Custom repositories**。
3. 添加仓库地址：`https://github.com/ly2199/ha_mimo_asr`，类别选择 **Integration**。
4. 点击 **Install** 安装。
5. 重启 Home Assistant。

### 方法二：手动安装

1. 下载本仓库所有文件，放入 `custom_components/mimo_asr/` 目录。
2. 重启 Home Assistant。

## ⚙️ 配置

1. 进入 **设置** → **设备与服务** → **添加集成**。
2. 搜索 **Mimo Speech-To-Text**，点击进入。
3. 输入你的 **API Key**（从 Mimo 平台获取）。
4. 点击确认，完成配置。

> 目前只支持单个实例，重复添加会被拦截。

## 🗣️ 在语音助手中使用

配置完成后，你需要将本 STT 引擎设置为默认语音助手的识别器：

1. 进入 **设置** → **语音助手**。
2. 选择或新建一个语音助手（如 `conversation`）。
3. 在 **语音转文本 (STT)** 下拉菜单中选择 **Mimo Speech to Text**。
4. 保存设置。

现在，当你说出语音指令时，HA 会使用 Mimo 进行识别。

## 🔧 支持参数

| 项目 | 支持情况 |
|------|----------|
| 语言 | `zh`, `zh-CN`, `en` |
| 音频格式 | WAV, MP3 |
| 采样率 | 16 kHz |
| 声道 | 单声道 |
| 码率 | 16-bit PCM |

> ⚠️ 注意：Home Assistant 默认会使用 Opus/OGG 格式，如果遇到兼容性问题，请确保你的音频源输出为 WAV 或 MP3。

## ❓ 故障排除

### 1. 语音识别失败，日志显示 “No text in response”
- 检查 API Key 是否有效，余额是否充足。
- 确认音频文件未损坏且大小在限制内（Base64 编码后 < 10 MB）。

### 2. 提示 “Unsupported language”
- 当前只支持 `zh`, `zh-CN`, `en`，请在语音助手设置中确认语言。

### 3. 无法加载集成
- 检查 `custom_components/mimo_asr` 目录结构是否正确。
- 重启 HA 后重试。

### 4. 获取更多调试日志
在 `configuration.yaml` 中添加：
```yaml
logger:
  default: warning
  logs:
    custom_components.mimo_asr: debug
