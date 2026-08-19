# Mimo Speech-To-Text 集成 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![ha_version](https://img.shields.io/badge/Home%20Assistant-2025.2+-blue.svg)](https://www.home-assistant.io/)
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

## 🎚️ 识别参数

插件内置能量检测（VAD），会实时监听尾静音，**在检测到语音结束后立即调用 API**，而不是被动等待 Home Assistant 管道关闭音频流——即使你的拾音设备不提供 VAD 概率，识别也能在说完话后约半秒内结束。发送前会自动裁剪首尾静音，全程无语音时不消耗 API 额度。

在 **设置 → 设备与服务 → Mimo Speech-To-Text → 配置** 中可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 结束静音时长 | 0.5 秒 | 语音后静音达到该时长即结束识别。调小响应更快但可能截断句中停顿；调大更稳妥但等待更久 |
| API 请求超时 | 15 秒 | Mimo API 单次请求超时上限，防止管道卡死 |

## 🔧 支持参数

| 项目 | 支持情况 |
|------|----------|
| 语言 | `zh`, `zh-CN`, `en` |
| 音频格式 | WAV |
| 采样率 | 16 kHz |
| 声道 | 单声道 |
| 码率 | 16-bit PCM |

> ⚠️ 注意：Home Assistant 默认会使用 Opus/OGG 格式，本集成已声明仅支持 WAV/PCM，管道会自动转换，无需手动配置。

## ❓ 故障排除

### 1. 语音识别失败，日志显示 “No text in response”
- 检查 API Key 是否有效，余额是否充足。
- 确认音频文件未损坏且大小在限制内（Base64 编码后 < 10 MB）。

### 2. 提示 “Unsupported language”
- 当前只支持 `zh`, `zh-CN`, `en`，请在语音助手设置中确认语言。

### 3. 无法加载集成
- 检查 `custom_components/mimo_asr` 目录结构是否正确。
- 重启 HA 后重试。

### 4. 识别结果被截断或等待太久
- 在集成配置中调整 **结束静音时长**：被截断则调大（如 0.8s），等待太久则调小（如 0.3s）。
- 开启 debug 日志观察 VAD 行为（提前结束、裁剪帧范围）。

### 5. 获取更多调试日志
在 `configuration.yaml` 中添加：
```yaml
logger:
  default: warning
  logs:
    custom_components.mimo_asr: debug
