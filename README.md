# 多运营商多号码话费流量智能监控系统

本项目是一个功能强大的多运营商（中国电信 / 中国联通）套餐用量监控及 Web 数据展示平台。它支持通过模拟 API 接口以及会话保活机制，定时拉取手机的话费余额、通话语音、流量套餐使用进度，并配备了高颜值、现代感十足的 Glassmorphism（磨砂玻璃拟物化）暗黑风 Web 仪表盘。

---

## 🌟 项目特性

- **高颜值大屏 Web UI**：采用现代化的暗黑磨砂玻璃（Glassmorphism）风格设计，配备动态环形图进度条，自适应手机、平板与桌面端。
- **多运营商支持**：
  - **中国电信**：支持账号/密码直接配置，利用 RSA 算法进行本地加密模拟登录，自动更新及缓存 Token。
  - **中国联通**：支持网页/App端 Cookie 导入模式及验证码登录模式，内置请求级会话保活与自动重连检测机制。
- **多维度流量明细**：区分“通用流量”与“专用/定向流量”，并能精细化解析出各个子流量包的已用与总量。
- **青龙定时任务与多通道推送**：内置定时任务脚本 `telecom_monitor.py` 与推送模块 `notify.py`，支持 Bark、钉钉机器人、企业微信、飞书、Server酱、PushDeer、邮件 SMTP、Telegram 等十几种主流通知渠道。
- **轻量易部署**：提供本地 Python 脚本一键启动、Docker / Docker-Compose 容器化快速部署方案。

---

## 📸 界面预览

*主页大屏提供卡片式管理，支持多个手机号多运营商混合排列，一目了然：*
- 🎨 精美渐变色彩环展示通用、定向流量使用比例。
- 📊 流量包明细折叠展开，支持人性化数据单位转换（自动转换 KB / MB / GB）。
- ⚙️ 一键删除、修改、新增或重新导入凭证。

---

## ⚙️ 快速部署说明

### 选项一：本地运行 (Windows / Linux)

#### 1. 准备环境
确保本地已安装 Python 3.8 或以上版本。

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 启动服务
- **Windows**: 双击运行目录下的 `start.bat`。
- **Linux/Mac**: 赋予权限后运行 `start.sh`：
  ```bash
  chmod +x start.sh
  ./start.sh
  ```
启动后可使用浏览器访问：`http://localhost:10000`

---

### 选项二：Docker 容器化部署

#### 1. 使用 Docker Hub 镜像 / 本地构建
你可以直接在本地构建镜像：
```bash
docker build -t multi-carrier-monitor .
```

#### 2. 运行容器
将本地配置文件夹挂载出来以持久化登录凭据：
```bash
docker run -d \
  --name carrier-monitor \
  -p 10000:10000 \
  -v ./config:/app/config \
  -e WHITELIST_NUM= \
  --restart unless-stopped \
  multi-carrier-monitor
```

#### 3. 使用 Docker Compose 部署
推荐使用 Docker Compose 进行管理。在项目目录下创建 `docker-compose.yml`：

```yaml
version: '3.8'
services:
  carrier-monitor:
    build: .
    container_name: carrier-monitor
    ports:
      - "10000:10000"
    volumes:
      - ./config:/app/config
    environment:
      - WHITELIST_NUM=  # 登录白名单，多号码用英文逗号分隔。留空代表不设限制
      - DEBUG=False
    restart: unless-stopped
```

启动命令：
```bash
docker-compose up -d
```

---

### 选项三：青龙面板部署 (定时推送)

如果你习惯使用青龙面板运行定时任务，可以通过以下配置添加定时监控：

1. **拉取任务**：
   在青龙面板中，新建订阅或拉库任务：
   ```bash
   ql repo https://github.com/YourUsername/ChinaTelecomMonitor_OpenSource.git "telecom_monitor" "" "telecom_class|unicom_class|notify"
   ```
2. **定时规则 (Cron)**：
   建议设置为每天 3-4 次，例如早上 `0 9,13,19,22 * * *`。
3. **环境变量**：
   - `TELECOM_USER`: 电信账号密码拼接（例如 `18912345678yourpassword`）。
   - `TELECOM_FLUX_PACKAGE`: `true` (默认) 表示推送流量包明细，`false` 表示仅推送概要。
   - `TELECOM_ONLY_WARN`: `true` 表示仅在流量超标/非均匀使用时推送警告，`false` (默认) 表示每次都推送。
   - 各推送渠道环境变量（如 `BARK_PUSH`、`DD_BOT_TOKEN`、`TG_BOT_TOKEN` 等，请参考 `notify.py` 内的注释进行配置）。

---

## 🍪 联通 Cookie 抓取与导入指南

由于联通模拟登录风控较严，本项目对中国联通号码推荐采用 **Cookie 导入方案**。抓取及导入步骤如下：

### 步骤 1：准备浏览器环境
1. 打开电脑上的 Chrome、Edge 或 Safari 浏览器。
2. 按下键盘上的 `F12`（或右键 -> 选择“检查”/“审查元素”），切换到 **Network (网络)** 面板。

### 步骤 2：登录联通营业厅
1. 浏览器访问联通手机端营业厅接口页面：[中国联通余量查询接口](https://mxx.client.10010.com/servicequerybusiness/operationservice/queryOcsPackageFlowLeftContentRevisedInJune) 或者是 [联通触屏版官网](https://m.client.10010.com/)。
2. 进行常规短信验证码登录。

### 步骤 3：截获 Cookie 字符串
1. 登录成功后，在开发者工具 Network 面板的 Filter 过滤框中输入 `queryOcsPackage`。
2. 在下方抓到的请求列表中，点击任意一个请求（如 `queryOcsPackageFlowLeftContentRevisedInJune`）。
3. 找到 **Headers** 标签页，往下滚动找到 **Request Headers (请求头)**。
4. 复制 `cookie:` 右侧的整段文本（它通常包含了 `servicequerybusiness=...; SHAREJSESSIONID=...; clientid=...` 等内容）。

### 步骤 4：导入系统
1. 打开本监控系统网页端（`http://localhost:10000`）。
2. 点击右上角的 **“添加账户”**，选择运营商为 **“中国联通”**。
3. 在输入框中填写您的**联通手机号**，并将刚才复制的 **Cookie 字符串** 完整粘贴到 Cookie 输入框中，点击保存导入。
4. 系统将自动在后台进行会话保活（默认每 5 分钟自动检测并请求一次以延长 Cookie 有效期）。

---

## 📝 许可证

本项目基于 MIT 协议开源。
感谢以下项目在开发过程中提供的技术参考：
- `ChinaTelecomMonitor` Go语言实现版本
- `boxjs`
