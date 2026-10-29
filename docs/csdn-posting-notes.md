# CSDN 发布辅助（发之前看这个）

## 一、标题候选（CSDN 标题党一点，点击率高，但别太夸张）

1. **用 Python + PyQt5 重写一个 B 站下载器：图形界面 + 命令行，一次打包 macOS/Linux 通吃**
2. **我给自己的 B 站下载器换了个小狐狸图标，顺手修好了 4 个 PyQt 的“地狱级”坑**
3. **B 站下载器（macOS/Linux）：扫码登录、4K、断点续传，打包即用不用装 Python**
4. **从零写一个 B 站下载器 GUI：3900 行 Python，讲讲我踩过的 5 个坑**
5. **写了个跨平台 B 站下载器：小狐狸图标 + 边下边播的进度条 + 一键装到「应用程序」**

> 推荐 1（技术味最足，适合长期搜索流量）或 3（最直白，适合第一次推）。

## 二、摘要（填 CSDN 的「文章简介」栏，200 字内）

用 Python + PyQt5 重写的 B 站视频下载器：图形界面和命令行共用同一套下载逻辑，支持番剧整季、分 P、合集、扫码登录拿 1080P/4K、断点续传与并发分段下载。macOS 一个 .app 双击即用（用户无需装 Python），Linux 提供 .deb。文中分享了 CDN 并行探速、PyQt 信号整数溢出、QThread 退出崩溃等 5 个真实踩坑与解法。

## 三、标签 / 分类

- 分类建议：**Python** 或 **其他编程语言**（别选「人工智能」，不贴）
- 标签：`Python`、`PyQt5`、`B站`、`视频下载`、`macOS`、`Linux`、`GUI`、`开源项目`、`ffmpeg`、`GUI开发`

## 四、图片上传清单

正文里的图片用的是仓库相对路径，**发到 CSDN 前需要先在编辑器里上传、再替换成 CSDN 的图片链接**。本地文件在：

| 插入位置 | 本地文件 |
|---|---|
| 主界面 | `docs/screenshot.png` |
| 浏览预览 | `docs/screenshot-collection.png` |
| 下载中（进度条） | `docs/screenshot-empty.png` |
| 扫码登录 | `docs/screenshot-login.png` |
| 应用图标（可选，封面用） | `dist/BiliFetch-app-icon.png` |

> 建议另外裁一张 16:9 的封面图（从 `docs/screenshot.png` 上半部分裁），CSDN 的文章封面会显示得更大。

**不用裁图的话**，也可以直接用外链（Markdown 会自动代理）：

```
https://raw.githubusercontent.com/oldsixxiaolv/bilifetch/main/docs/screenshot.png
```

## 五、一句话推广文案（朋友圈 / 微博 / X）

**短版（60 字内）**
> 写了个跨平台 B 站下载器：小狐狸图标、扫码登录拿 4K、断点续传，macOS 双击即用不用装 Python。开源了 ⭐️

**长版（150 字内）**
> B 站下载器重写计划第 N 版：Python + PyQt5，图形界面和命令行共用一套逻辑，番剧整季/分 P/合集都支持，扫码登录能拿 1080P/4K，分段并发 + 断点续传 + 自动挑最快 CDN。macOS 一个 .app 双击即用，Linux 有 .deb。踩坑记录都写在文章里了，欢迎试。

**技术向（发技术群/朋友圈）**
> 分享三个 PyQt 的坑：① 信号里传 int，超过 2GB 会静默回绕成负数（进度条显示 -12%）；② 给自绘控件套 QGraphicsOpacityEffect 会和 QPainter 抢绘制设备；③ 运行中的 QThread 被析构直接 abort，退出必崩。都在文章里写了怎么定位和修。

## 六、发布后的检查清单

- [ ] 四张图都换成 CSDN 自己的链接（别用 raw.githubusercontent 外链，CDN 可能不稳）
- [ ] 校验和那两行没有提「上传到某账号」这类信息（只写仓库地址即可）
- [ ] 命令行示例至少挑一条**自己跑过**再发
- [ ] 文末「已知限制」保留（番剧 DRM 不支持等）—— 少写一句限制，评论区就多一条「骗人」的评论
- [ ] 仓库地址用的是 `oldsixxiaolv/bilifetch`（发布版所在的那个号）
