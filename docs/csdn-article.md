> 写给想省事下载 B 站视频、又想看懂实现细节的同行。
> 全文代码约 3900 行，Apache-2.0 开源，macOS / Linux 都有现成安装包。
> 项目地址：https://github.com/oldsixxiaolv/bilifetch

---

## 一、先说问题

在 macOS 上想下个 B 站视频，常见选择是：

| 方案 | 问题 |
|---|---|
| 网页右键「另存为」 | 大多只能拿到 480P，多 P 视频得一个个点 |
| 各种在线解析站 | 要上传链接、有广告、有隐私风险、速度看服务器脸色 |
| Java 版 GUI 工具 | 要自己装 JRE，还要补 `ffmpeg`，命令行和图形两套 UI |
| yt-dlp 之类 | 强，但 B 站需要额外配置，且没有「浏览、勾选、再批量下」的界面 |

于是我写了一个：**`BiliFetch`** —— 图形界面和命令行**共用同一套下载逻辑**，`brew install --cask bilifetch` 一条命令就能装，图标是一只小狐狸。

![BiliFetch 主界面](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot.png)

**它能做什么**

- 番剧整季、普通视频分 P、合集、收藏夹、`b23.tv` 短链，都支持
- **扫码登录**后能拿 1080P / 4K / 杜比（未登录 B 站只给 480P）
- 点「浏览…」先把内容列成清单，**勾选后再下**；番剧会把花絮、二创默认折叠
- 断点续传、并发分段、CDN 自动挑最快镜像、`ffmpeg` 无损合并
- macOS 一个 `.app` 双击即用（**用户机器不需要装 Python**），Linux 一个 `.deb`

![浏览预览](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-collection.png)

![扫码登录](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-login.png)

---

## 二、几个有意思的技术点

这一节挑三个「踩坑时间最长、收获最大」的讲，代码都能在仓库里对上。

### 1. CDN 镜像探测：串行探速差点让我白等 11 秒

B 站一个番剧的播放地址，展开出来是 **9 个域名 × 主/备地址 = 18 个候选镜像**，实测速度能差 40 倍。选错镜像，整个下载全程慢。

我最初的实现是**串行**探：挨个下载一小段测速，取最快的。问题在于候选里有一半是坏的或者极慢的，而每个坏镜像要等到超时（连接 5s + 读取 6s）才判死：

```
下载开始前花在探速上：11.6 秒
```

更糟的是，**探速期间点「停止」几乎没有反应** —— 请求正卡在等响应头，取消标志根本没机会被看到。

改成**并行探**就干净了：

```python
# 所有候选一起测，整体耗时 ≈ 单个候选的耗时
pool = ThreadPoolExecutor(max_workers=min(12, len(urls)))
futures = [pool.submit(probe, u) for u in urls]
for fut in as_completed(futures):
    res = fut.result()
    if res and res[0] > best_speed:
        best_speed, best = res[0], res[1]
    if best_speed > 5e6:      # 5 MB/s 单连接就够快，不用等其它镜像
        break
```

```python
def probe(u):
    resp = self.session.get(u, headers=self._range_headers(referer, 0, 256 * 1024),
                            stream=True, timeout=(2.5, 2.5))
    t = time.time()            # 计时从「收到响应头之后」开始
    n = sum(len(c) for c in resp.iter_content(1 << 16))
    return (n / max(time.time() - t, 0.01), u)
```

两个细节值得说：

1. **计时从收到响应头之后开始算**。连接和 TLS 握手那几百毫秒不该算进传输速度，否则快的镜像会被误判成慢的。
2. **探速用很短的超时**（2.5 秒）。探速只需要个相对快慢，不值得等满。

效果：**下载启动延迟 11.6s → 0.53s**，顺带把「停止」的响应也救回来了。

> 教训：用户说「慢」的时候，慢的往往不在主流程上。我一开始一直在怀疑下载本身，直到给核心层打点（分段起止、探速起止、取消时刻），一眼就看到「下载还没开始，卡在探速」。

### 2. PyQt 信号里装字节数：超过 2GB 会**静默回绕成负数**

界面上的进度条一直显示 **-12%**，进度条画不出来，但下载其实在正常跑。

原因很隐蔽：`pyqtSignal(str, int, int)` 里我传的是字节数，而 **C++ 的 int 是 32 位有符号**，超过 2³¹-1 会被静默回绕：

```python
emit(2_147_483_648)   # 收到 -2147483648
emit(2_460_000_000)   # 收到 -1834967296
```

而登录后 1080P/4K 的长视频流**正好超过 2GB** —— 本地用几十 MB 的测试视频永远复现不出来。

修法就一行：信号参数改成 `float`（53 位尾数，精确到 2^53），算出来的百分比再夹一层 `max(0, min(100, pct))`。

### 3. 退出时崩溃：QThread 在运行中被析构，Qt 直接 abort

点「下载中退出」，进程直接 SIGABRT 消失，崩溃报告里没有一行 Python 栈。查下来是 Qt 的硬规则：

> **运行中的 `QThread` 被析构 → Qt 立刻 abort。**

这类坑一共踩了四个：

| 症状 | 真因 | 修法 |
|---|---|---|
| 退出必崩 | 线程还在跑就被销毁 | 退出前 cancel + 等线程真正结束 |
| 停止后没法重新开始 | 线程的 `quit()` 要靠 GUI 线程处理队列信号才触发，而 GUI 线程正阻塞在 `wait()` 上 → 死锁 | 让线程自己退：`QThread.currentThread().quit()` |
| 停止后没法清空 | 旧线程的 `finished` 回调把**新线程的引用**抹了 | 回调带上线程对象，核对 `thread is self.thread` 再动状态 |
| 关掉浏览窗口就崩 | 抓图线程是窗口的子对象，窗口销毁时它还在跑 | 等不干净就 `setParent(None)` 并继续持有引用，等它自己结束再删 |

还有个更隐蔽的：**取消标志只在两次网络读之间检查**，请求卡在 socket 读取上时要等**读超时（60 秒）**才生效。改法是取消时直接把正在读的连接 `close()` 掉，阻塞的读立刻抛错：

```python
def cancel(self):
    with self._active_lock:
        resp_list = list(self._active)
    # 放到后台线程关：close() 可能和正在读的线程抢锁，
    # 放在界面线程里做会把界面卡住
    threading.Thread(target=self._close_all, args=(resp_list,), daemon=True).start()
```

停止延迟：**60 秒 → 1.1 秒**。

---

## 三、界面也花了不少功夫

界面是自己画的（`QPainter` + `QSS`），目标就俩：**别卡、别丑**。

- **合并成一张主卡**：链接输入框和「保存到 / 画质 / 高级」放一张卡里，中间一条分隔线。原来拆成两张卡，看着像两个功能凑在一起。
- **队列和日志合并成一张卡**，用分段切换，右上角按钮跟着换（队列页是「停止/清空」，日志页是「复制/清空」）。这样就不会出现一个永远空着的大黑框。
- **淡入动画踩了个 PyQt 的坑**：给自绘控件套 `QGraphicsOpacityEffect`，Qt 会把控件重定向到 effect 自己的 pixmap，和控件 `paintEvent` 里的 `QPainter` 抢同一个绘制设备，控制台刷 136 条 `A paint device can only be painted by one painter at a time`，界面还会画花。改成自己盖一层半透明遮罩渐隐就干净了。
- **二维码被裁掉**：登录框里二维码原图 424×424，而承载它的标签只有 260×260 —— `QLabel` 对超尺寸的 pixmap 是「按原样画、超出部分裁掉」，**不会自动缩小**。手机上扫到的是残缺码，表现为「扫码没反应」。缩放 + `setDevicePixelRatio(2.0)` 解决，Retina 上还不糊。

![下载中](https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot-empty.png)

---

## 四、安装

**macOS**

```bash
# 图形界面 + 命令行，一步到位
brew install --cask bilifetch
```

或者手动：下载 [Releases](https://github.com/oldsixxiaolv/bilifetch/releases) 里的 `BiliFetch-1.0.0-macOS.dmg`，把 `BiliFetch.app` 拖进「应用程序」。

> 第一次双击若提示「无法验证开发者」：**右键点 BiliFetch.app → 打开 → 再点「打开」**。这是因为没做公证（notarization），不是文件坏了。

**Linux**

```bash
sudo apt install ./bilifetch_1.0.0_all.deb
sudo apt install python3-pyqt5 ffmpeg   # 图形界面和合并需要
```

**命令行**

```bash
bilifetch 'https://www.bilibili.com/bangumi/play/ep1633643'
bilifetch -c "SESSDATA=你的cookie" -q 80 'BV1xx411c7mD'    # 指定画质
bilifetch --audio-only 'BV1xx411c7mD'                       # 只下音频
```

---

## 五、工程上的一些取舍

- **图形界面和命令行共用 `bilifetch.py` 里的同一套下载逻辑**（`download_episode` / `plan_jobs`），不会出现「图形界面能下、命令行下不了」这种分裂。
- **不引冷门依赖**：只用 `requests` + `PyQt5` + `qrcode`，`ffmpeg` 是外部程序。macOS 用 PyInstaller 打自包含 `.app`，并排除 `numpy/cryptography/matplotlib/pandas/scipy`（`qrcode` 的静态扫描会把它们一起拖进来，白涨 43MB）。
- **Cookie 只进 `session` 的 cookie jar（domain=`.bilibili.com`）**：这样 `requests` 不会用 jar 里的 cookie 覆盖我们设的 header，CDN（`*.bilivideo.com`）也拿不到 B 站 cookie，不至于泄漏出去。
- **打包中间目录一律放 `/tmp`**：工作目录在 exFAT 上时，拷文件会带出 `._xxx` 旁挂文件、权限也被压成 700，这些都会混进安装包。
- 打包完有自检开关，直接在 `.app` 里跑真下载：

```bash
BiliFetch.app/Contents/MacOS/BiliFetch --selftest 'BV1...' /tmp/out
BiliFetch.app/Contents/MacOS/BiliFetch --selftest-exit 'BV1...' /tmp/out   # 下载中关窗口，会不会崩
```

第二条是我被「退出就崩」折磨出来的 —— **PyInstaller 打包最容易在 SSL 证书、隐藏依赖上翻车**，所以必须能在打包后的 `.app` 里真跑一次，而不是只看窗口能打开。

---

## 六、项目地址

| | |
|---|---|
| 仓库 | https://github.com/oldsixxiaolv/bilifetch |
| Release | https://github.com/oldsixxiaolv/bilifetch/releases/tag/v1.0.0 |
| 参考的上游 | [nICEnnnnnnnLee/BilibiliDown](https://github.com/nICEnnnnnnnLee/BilibiliDown)（Apache-2.0，本项目为其 API 流程的独立重写） |

---

## 七、说清楚几件事

- 本项目与哔哩哔哩（Bilibili）无任何隶属关系，「Bilibili」相关名称与标识归其权利人所有。
- 图标为原创生成的狐狸形象，未使用 B 站官方 logo 或吉祥物形象。
- **仅供学习研究，请遵守 B 站用户协议**。请不要用它做批量搬运、离线盗版等用途。
- 已知限制：番剧 DRM 加密内容不支持；某些清晰度需要大会员；个别 CDN 镜像会限速。

如果你觉得这个思路还成，**欢迎点个 Star 或提 Issue** —— 尤其想知道：

1. 你更希望我下一步补什么？（批量导出、字幕处理、音频格式转换、自动断点续传队列？）
2. 有没有你在用、我没覆盖到的链接类型？（直播回放、课堂、付费课程？）

评论区见。
