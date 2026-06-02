# runfreecloud_renew（CloakBrowser 版）

> 基于 [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) 的 run.freecloud.ltd 自动签到 & 续费脚本。  
> 通过 GitHub Actions 每日定时运行，支持按需录屏调试、WxPusher 推送通知、自动清理旧 Runs。

---

## 目录

- [功能一览](#功能一览)
- [改版背景](#改版背景)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [GitHub Secrets 配置](#github-secrets-配置)
- [定时任务说明](#定时任务说明)
- [录屏开关说明](#录屏开关说明)
- [自动清理旧 Runs](#自动清理旧-runs)
- [Artifacts 说明](#artifacts-说明)
- [WxPusher 推送配置（可选）](#wxpusher-推送配置可选)
- [V2Ray / Xray 代理配置](#v2ray--xray-代理配置)
  - [代理内核说明](#代理内核说明)
  - [配置方法](#配置方法)
- [业务逻辑说明](#业务逻辑说明)
- [常见问题](#常见问题)

---

## 功能一览

| 功能 | 说明 |
|------|------|
| ✅ 自动登录 | OCR 自动识别图形验证码，模拟人工输入，支持最多 3 次重试 |
| ✅ 自动签到 | 点击"我要签到"，自动解答数学验证题，处理 layui 弹窗确认 |
| ✅ 自动续费 | 检测服务到期日，剩余 ≤ 2 天时自动走完续费支付全流程 |
| ✅ CF 自动通过 | CloakBrowser 源码级指纹伪装，无需手动处理 Cloudflare 验证 |
| ✅ WxPusher 推送 | 签到完成后推送积分余额、到期时间、是否续费等信息 |
| ✅ 全程截图 | 关键步骤自动截图，上传至 Artifacts，保留 3 天 |
| ✅ 按需录屏 | 手动触发时可选择开启录屏，定时任务默认不录屏节省空间 |
| ✅ 自动清理 | 每次运行结束后自动删除旧 Runs，只保留最近 2 个 |
| ✅ Xray 代理内核 | 使用 Xray-core v25.5.16 提供本地 SOCKS5 代理，规避 Actions IP 封锁 |

---

## 改版背景

原版使用 `pydoll` 驱动 Chromium，Cloudflare 已能从底层检测 pydoll 的自动化特征，导致验证无法通过，脚本失效。

本版本改用 **CloakBrowser**，核心优势：

- **源码级指纹伪装**：在 Chromium 源码层面修改自动化标识，而非通过 JS 注入（JS 注入方案已被 CF 识别），从根本上规避检测
- **geoip 自动匹配**：根据代理 IP 自动匹配浏览器时区、语言，消除与 IP 地理位置不符的指纹矛盾
- **Playwright 兼容 API**：同步调用风格，逻辑清晰，易于维护和调试
- **自带 Chromium 二进制**：通过 `ensure_binary()` 一键下载，CI 环境无需额外安装 chromium

---

## 项目结构

```
runfreecloud_renew/
├── sign_cloakbrowser.py          # 主脚本（登录 / 签到 / 续费）
├── requirements.txt              # Python 依赖
├── README.md                     # 本文件
└── .github/
    └── workflows/
        └── v2ray-sign.yml        # GitHub Actions 工作流
```

---

## 快速开始

### 1. Fork 本仓库

点击右上角 **Fork**，将本仓库 fork 到你自己的 GitHub 账号下。

### 2. 配置 Secrets

进入仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

按照下一节的表格依次添加所需的 Secret。

### 3. 手动触发测试

进入 **Actions** → **RUN签到 (CloakBrowser)** → **Run workflow**

首次建议选择 `enable_recording: true` 开启录屏，方便排查问题。

### 4. 查看结果

运行完成后，在该次运行页面底部的 **Artifacts** 区域下载截图和录屏（如已开启）查看执行过程。

### 5. 等待自动运行

配置完成后，每天 UTC 01:30（北京时间 09:30）自动执行一次，无需人工干预。

---

## GitHub Secrets 配置

| Secret 名 | 是否必填 | 说明 |
|-----------|:-------:|------|
| `EMAIL` | ✅ | run.freecloud.ltd 登录邮箱 |
| `PASSWORD` | ✅ | 登录密码 |
| `V2RAY_CONFIG` | ✅ | Xray/V2Ray 完整配置 JSON（见下方说明） |
| `WXPUSHER_TOKEN` | ⬜ | WxPusher AppToken，不填则跳过微信推送 |
| `WXPUSHER_UID` | ⬜ | WxPusher 用户 UID，不填则跳过微信推送 |

> `GITHUB_TOKEN` 无需配置，GitHub Actions 自动提供，用于清理旧 Runs。

---

## 定时任务说明

工作流中的触发配置：

```yaml
on:
  schedule:
    - cron: '30 1 * * *'   # UTC 每天 01:30，即北京时间 09:30
  workflow_dispatch:        # 支持手动触发
```

如需修改运行时间，编辑 `v2ray-sign.yml` 中的 `cron` 字段。  
Cron 表达式格式：`分 时 日 月 周`，时区为 UTC。

> GitHub Actions 的定时任务在高峰期可能延迟 10～30 分钟，属正常现象。

---

## 录屏开关说明

录屏功能通过触发方式区分，**无需修改代码**：

| 触发方式 | 录屏行为 |
|---------|---------|
| `schedule` 定时触发 | 🚫 始终不录屏（节省存储和运行时间） |
| `workflow_dispatch` 手动触发 | 出现下拉选项，可自由选择 |

手动触发时的下拉选项：

```
是否录屏（仅手动触发时有效）
  ├─ false（默认）  →  不录屏，只上传截图
  └─ true           →  开启录屏，额外上传 recording.mp4
```

**实现原理**：

`workflow_dispatch` 输入 `enable_recording` 在 `schedule` 触发时不存在，对应环境变量为空字符串，shell 判断 `[ "$ENABLE_RECORDING" = "true" ]` 为假，因此定时任务绝不会触发录屏逻辑。

---

## 自动清理旧 Runs

每次运行结束后（`if: always()`），工作流自动执行清理步骤：

1. 使用内置 `GITHUB_TOKEN`（无需额外配置 Secret）调用 GitHub API
2. 按 `run_number` 倒序获取该 workflow 的全部运行记录
3. 跳过最新的 2 个，其余全部删除

```
runs（按时间倒序）
  ├─ run #105  ← 保留
  ├─ run #104  ← 保留
  ├─ run #103  ← 删除
  ├─ run #102  ← 删除
  └─ ...       ← 删除
```

> 如需修改保留数量，编辑 `v2ray-sign.yml` 中清理步骤的 `.[2:]` 部分，数字即为保留个数。

---

## Artifacts 说明

每次运行结束后，根据配置上传以下 Artifacts，保留 **3 天**：

| Artifact 名 | 内容 | 上传条件 |
|------------|------|---------|
| `screenshots-{run号}` | 全程关键步骤截图（`.png`） | 每次都上传 |
| `recording-{run号}` | 录屏视频（`recording.mp4`）+ ffmpeg 日志 | 仅手动触发且选择录屏时上传 |

截图命名规律（按执行顺序）：

```
{时间戳}_02_login_success.png       登录成功
{时间戳}_02_already_signed.png      今日已签到（重复运行时）
{时间戳}_03_sign_complete.png       签到完成
{时间戳}_03b_service_page.png       服务列表页（续费检查）
{时间戳}_04a_checked.png            勾选服务（触发续费时）
{时间戳}_04b_after_renew_click.png  点击续费后
{时间戳}_04c_after_xfsubmit.png     提交续费页
{时间戳}_04d_after_payamount.png    账单支付页
{时间戳}_04e_after_paynow.png       确认支付后
{时间戳}_04f_renew_complete.png     续费完成
{时间戳}_99_error.png               异常截图（出错时）
```

---

## WxPusher 推送配置（可选）

配置后，每次签到完成自动推送结果到微信。

**推送示例（正常签到）：**

```
✅ 签到成功
账户余额剩余 120 积分
到期时间 2025-08-01
不用续期，等到 2025-07-30 再续期
```

**推送示例（自动续费）：**

```
✅ 签到成功
账户余额剩余 80 积分
到期时间 2025-09-01
✅ 已自动续期
```

**推送示例（异常）：**

```
❌ 登录失败，请检查账号密码或网络
```

**获取 Token 和 UID：**

1. 访问 [wxpusher.zjiecode.com](https://wxpusher.zjiecode.com) 注册账号
2. 创建应用 → 获得 `AppToken`，填入 Secret `WXPUSHER_TOKEN`
3. 用微信扫码关注该应用 → 获得你的 `UID`，填入 Secret `WXPUSHER_UID`

---

## V2Ray / Xray 代理配置

### 代理内核说明

工作流使用 **[Xray-core](https://github.com/XTLS/Xray-core) v25.5.16** 作为代理内核，在 GitHub Actions 运行环境中提供本地 SOCKS5 代理服务。

| 项目 | 值 |
|------|---|
| 代理内核 | Xray-core v25.5.16 |
| 本地监听协议 | SOCKS5（无认证） |
| 本地监听地址 | `127.0.0.1:10808` |
| 浏览器代理配置 | `socks5://127.0.0.1:10808` |
| 支持出站协议 | vmess / vless / trojan / shadowsocks 等所有 Xray 协议 |

**工作流中的启动方式：**

```bash
# 下载 Xray-core v25.5.16
curl -sL https://github.com/XTLS/Xray-core/releases/download/v25.5.16/Xray-linux-64.zip -o xray.zip
unzip xray.zip && chmod +x xray

# 写入配置并后台启动
echo "$V2RAY_CONFIG" > config.json
./xray run -c config.json &

# 验证代理是否生效
curl -s --socks5 127.0.0.1:10808 ifconfig.me
```

### 配置方法

`V2RAY_CONFIG` Secret 填入完整的 Xray 配置 JSON，最低要求：入站为 `socks` 协议监听 `10808` 端口。

**配置示例（VMess）：**

```json
{
  "inbounds": [
    {
      "port": 10808,
      "protocol": "socks",
      "settings": {
        "auth": "noauth",
        "udp": true
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "vmess",
      "settings": {
        "vnext": [
          {
            "address": "your.server.com",
            "port": 443,
            "users": [
              {
                "id": "your-uuid-here",
                "alterId": 0
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls"
      }
    }
  ]
}
```

> 支持 vmess / vless / trojan / shadowsocks 等所有 Xray 协议，入站保持 `socks:10808` 即可。

---

## 业务逻辑说明

### 登录流程

1. 导航至登录页，等待 Cloudflare 验证自动通过（最多 45 秒）
2. 模拟人工输入邮箱、密码（随机打字延迟 50～120ms）
3. OCR 识别 base64 内联图形验证码（ddddocr），过滤非数字字符后填入
4. 点击登录按钮，检测 URL 是否跳转至 `/clientarea`
5. 失败自动重试，最多 3 次

### 签到流程

1. 导航至签到插件页（`addons?_plugin=5`）
2. 检测"今日已签到"文案，已签到则跳过
3. 点击"我要签到"，弹出数学验证题
4. 正则提取算式（支持 `+` `-` `*` `/`），计算后填入答案
5. 点击"验证答案"，等待 layui 弹窗逐个确认（验证成功弹窗 → 签到成功弹窗）
6. 签到完成后刷新页面，读取最新积分余额

### 续费流程

1. 导航至服务列表页（`service?groupid=305`）
2. 从表格"到期"列读取到期日期
3. 计算剩余天数，**≤ 2 天**才触发续费（否则跳过）
4. 勾选服务 → 点续费按钮 → 提交续费 → 账单页支付 → 弹窗确认支付
5. 续费成功后重新读取最新到期日，更新推送内容

---

## 常见问题

**Q：定时任务一直没有运行？**

A：仓库需要有近期 push 活动，否则 GitHub 会暂停定时任务。进入 Actions 页面，若看到提示可手动启用。也可以偶尔手动触发一次来保持活跃。

---

**Q：日志显示"CF 验证超时"怎么办？**

A：代理节点 IP 可能被 Cloudflare 标记。建议更换延迟更低、更干净的代理节点，并更新 `V2RAY_CONFIG` Secret。

---

**Q：验证码识别失败怎么处理？**

A：ddddocr 偶发识别错误属正常，脚本会自动重试最多 3 次。若连续失败，请下载 Artifacts 中的截图，确认登录页验证码样式是否发生变化。

---

**Q：如何只签到，不自动续费？**

A：在 `sign_cloakbrowser.py` 的 `main()` 函数中，将 `renewed, expiry_str, remain = renew(page)` 一行注释掉，并在其下方添加：

```python
renewed, expiry_str, remain = False, None, None
```

---

**Q：续费积分不够怎么办？**

A：脚本不会在积分不足时强行续费，支付失败后会在截图中留下记录。请确保通过每日签到积累足够的积分。

---

**Q：如何修改只保留的 Runs 数量？**

A：编辑 `v2ray-sign.yml` 中清理步骤的这一行：

```bash
--jq '.workflow_runs | sort_by(.run_number) | reverse | .[2:] | .[].id'
```

将 `.[2:]` 中的 `2` 改为你想保留的数量即可。

---

**Q：录屏文件在哪里看？**

A：手动触发时选择 `enable_recording: true`，运行结束后在该次运行页面底部 **Artifacts** 区域下载 `recording-{run号}`，包含 `recording.mp4` 和 `ffmpeg.log`，保留 3 天。

---

## License

MIT
