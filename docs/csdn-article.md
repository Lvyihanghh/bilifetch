> 网页右键「另存为」只能拿 480P，多 P 视频还得一个个点。
> 自己写了个 B 站下载器：macOS 双击就能用，不用装 Python，图标是只小狐狸 🦊

![主界面](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot.png)

**能干嘛**

- 番剧整季、分 P、合集、收藏夹、`b23.tv` 短链，都能下
- 扫码登录后能拿 **1080P / 4K / 杜比**（不登录只给 480P）
- 先列出内容让你**勾选**，再批量下；花絮、二创默认折叠
- 断点续传，下一半关掉再打开接着下
- macOS 一个 `.app`、Linux 一个 `.deb`

---

## 一、装

**macOS**

下载 [Releases](https://github.com/oldsixxiaolv/bilifetch/releases) 里的 `BiliFetch-1.0.0-macOS.dmg`，打开后把 **BiliFetch.app** 拖到右边的 **Applications** 图标上。

以后在「应用程序」里就能看到那只小狐狸，双击打开。

> 第一次双击如果提示「无法验证开发者」：**右键点 BiliFetch.app → 打开 → 再点「打开」**。这是没做公证，不是文件坏了。

**Linux**

```bash
sudo apt install ./bilifetch_1.0.0_all.deb
sudo apt install python3-pyqt5 ffmpeg
```

**命令行也有一份**（图形界面和它是同一套逻辑）

```bash
bilifetch 'https://www.bilibili.com/bangumi/play/ep1633643'
```

---

## 二、用（三步）

**第 1 步**：把 B 站链接粘到输入框，点 **「浏览…」**。

**第 2 步**：软件会把里面的内容列成清单，勾你要的。

![浏览预览](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-collection.png)

**第 3 步**：点 **「确认下载」**，下面能看到进度和速度。

![下载中](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-empty.png)

文件默认存在 `~/Downloads/BiliFetch`，点右下角「打开输出目录」直接去看。

---

## 三、几个常见问题

**Q：画质只有 480P？**
右上角点「扫码登录」，用手机 B 站 App 扫一下，登录后自动解锁 1080P 及以上。登录状态会一直保留，除非你主动点「退出登录」。

**Q：二维码扫不上？**
点「刷新二维码」换一张（有效期 180 秒）。

![扫码登录](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-login.png)

**Q：只想听声音，不要画面？**
在浏览窗口里勾「只下音频」。

**Q：下到一半不想下了？**
点「停止」，会很快停下；之后可以重新开始，也可以「清空」队列。

**Q：会不会偷偷上传我的链接？**
不会。所有请求都直接打到 B 站和它的 CDN，没有第三方服务器。

---

## 四、拿去

| | |
|---|---|
| 下载 | https://github.com/oldsixxiaolv/bilifetch/releases/tag/v1.0.0 |
| 源码 | https://github.com/oldsixxiaolv/bilifetch |
| macOS 一键装 | `brew install --cask bilifetch` |

Apache-2.0 开源，觉得好用麻烦点个 ⭐️，有问题欢迎提 Issue。

> 仅供学习研究，请遵守 B 站用户协议；番剧的 DRM 加密内容下不了。
