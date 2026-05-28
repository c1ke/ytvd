# YTVD — YouTube Video Downloader

一个基于 yt-dlp 的自托管视频下载网站，支持 YouTube、TikTok、Twitter 等 1000+ 网站。

## 功能特性

- 🎬 解析视频信息，选择分辨率格式下载
- 🎵 一键提取 MP3 音频
- 📊 实时下载进度（速度 / ETA）
- 📁 文件管理：下载、删除
- 🔐 后台管理密码保护
- 🌍 8 种语言切换
- 🎨 黑色 / 暖白 两种主题
- 📢 4 处广告位支持
- 🔗 友情链接管理
- 🍪 YouTube Cookie 支持（会员视频）

---

## 部署教程

### 环境要求

- Debian / Ubuntu Linux
- Python 3.9+
- ffmpeg（合并音视频必须）

### 第一步：安装系统依赖

```bash
apt update
apt install -y python3.11-venv python3-pip ffmpeg
```

### 第二步：上传项目文件

将项目文件上传到服务器，推荐路径：

```
/www/wwwroot/你的域名/
```

目录结构：
```
your-domain/
├── app.py
├── requirements.txt
├── ytvd.service
├── templates/
│   └── index.html
├── downloads/       ← 自动创建
└── config/          ← 自动创建
```

### 第三步：创建虚拟环境并安装依赖

```bash
cd /www/wwwroot/你的域名
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 第四步：配置并启动系统服务

编辑 `ytvd.service`，将 `your-domain.com` 替换为你的实际目录路径：

```ini
WorkingDirectory=/www/wwwroot/你的域名
ExecStart=/www/wwwroot/你的域名/venv/bin/python app.py
```

复制服务文件并启动：

```bash
cp ytvd.service /etc/systemd/system/ytvd.service
systemctl daemon-reload
systemctl enable ytvd
systemctl start ytvd
systemctl status ytvd
```

默认监听端口：**5000**

---

## 宝塔面板绑定域名

1. **新建站点**
   - 宝塔 → 网站 → 添加站点
   - 域名填写你的域名，PHP 选**纯静态**

2. **配置反向代理**
   - 网站设置 → 反向代理 → 添加反向代理
   - 目标 URL：`http://127.0.0.1:5000`
   - 发送域名：`$host`
   - 勾选启用 → 保存

3. **申请 SSL 证书**
   - 网站设置 → SSL → Let's Encrypt → 申请
   - 开启强制 HTTPS

4. **DNS 解析**
   - 去域名商控制台添加 A 记录
   - 主机记录：`@` 或 `www` 或子域名
   - 记录值：服务器 IP

完成后访问 `https://你的域名` 即可。

---

## 修改端口

默认端口 5000，如需修改编辑 `app.py` 最后一行：

```python
app.run(debug=False, host="0.0.0.0", port=5000)  # 改这里
```

同时修改宝塔反向代理的目标 URL 端口。

---

## 后台管理

访问网站后点击 **Admin** → 输入密码登录

**默认密码：`admin123`**

> ⚠️ 部署后请立即登录后台修改密码！

后台功能：
- 🎨 Logo 与品牌设置（渐变文字或图片）
- 🔗 友情链接管理
- 🍪 YouTube Cookie（用于下载会员/私有视频）
- 📢 广告位 HTML 设置（页眉/页脚/左侧/右侧）
- 📁 文件管理
- 🔑 修改密码

---

## YouTube Cookie 使用方法

用于下载需要登录的视频（会员视频、私有视频等）：

1. 安装浏览器扩展：**Get cookies.txt LOCALLY**
2. 登录 YouTube 账号
3. 点击扩展 → Export cookies for this tab
4. 复制全部内容
5. 后台管理 → YouTube Cookies → 粘贴 → 勾选启用 → 保存

---

## 一键卸载

```bash
systemctl stop ytvd
systemctl disable ytvd
rm /etc/systemd/system/ytvd.service
systemctl daemon-reload
rm -rf /www/wwwroot/你的域名
```

---

## 注意事项

1. **ffmpeg 必须安装**，否则下载的视频没有声音（视频流和音频流无法合并）
2. 视频下载受**服务器所在地区**限制，部分 YouTube 视频在某些地区不可用
3. `config/` 目录包含密码哈希和 Cookie，**不要上传到 GitHub**（已在 .gitignore 中排除）
4. `downloads/` 目录会占用磁盘空间，定期清理
5. 生产环境建议配合 Nginx/宝塔反向代理使用，不要直接暴露 5000 端口

---

## License

MIT
