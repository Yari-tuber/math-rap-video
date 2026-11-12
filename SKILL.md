---
name: math-rap-video
description: 把一个知识点（数学为主，其他学科也行）做成「AI 说唱 + 口诀 + 图形演示」的讲题短视频，像抖音上 Rap&科学 那种：顶部常驻口诀、中间图形跟着唱词一步步演示、底部逐句字幕。歌用任何 AI 音乐模型做（有 API 就直接生成，没有就给提示词去 Suno、海绵、Mureka 网页生成），skill 自己分人声、逐字对齐、挑最好的一版；画风和背景都能换（暗色电影感、黑板粉笔、发光线条，或者自己的视频、一张图）。用户说「做一个数学说唱视频」「把这个公式做成口诀视频」「AI 说唱讲题」「给这首歌做讲解画面」「口诀讲解视频」，或者想把某个公式、定理、解题方法做成好记的歌加动画时，都用本 skill。只想了解做法、要写歌词的提示词、要给音乐模型的提示词，也用它。
license: MIT
metadata:
  version: "2.0.1"
  author: "Yari-tuber（亚里）"
---

# 口诀说唱讲题视频

一支视频由四样东西拼成：**歌**（AI 音乐模型唱）、**时间表**（每个字第几秒唱）、**画面**（口诀、公式、题目图形）、**背景**。
所有步骤都用一个入口 `scripts/mrv.py`。**每条命令做完都会打印「下一步」的完整命令，照抄就行；不知道做到哪了就跑 `mrv.py next <作品目录>`。**

下面的 `mrv.py` 指本 skill 的 `scripts/mrv.py`（和这份 SKILL.md 在同一个文件夹下）。运行时写完整路径，路径有空格就加引号：
`python "<skill 文件夹>/scripts/mrv.py" <命令> "<作品目录>"`。Windows 上中文乱码时先设环境变量 `PYTHONUTF8=1`。

## 第一次用：检查环境

```
python mrv.py doctor
```

缺什么它会写「怎么办」。对时间要用 torch、transformers、demucs：`mrv.py doctor --fix` 会自动建一个独立环境装好（不碰系统的 Python，约 3 GB，对齐模型第一次用时再下 1.8 GB；国内网络先设 `HF_ENDPOINT=https://hf-mirror.com`）。

## 流程

```
1 new 新建 → 2 写口诀和歌词 → lyrics → 3 出歌（先问有没有 API）→ 4 song 对时间
   → 5 写画面（storyboard.json + graphics.py）→ 6 check 看预览图 → 7 render 出片 → 8 交付
```

第 2 步写完歌词、第 6 步出了预览图，都**先给用户看，用户点头再往下**。

### 1. 新建作品

```
python mrv.py new <作品目录> --example gougu       # 照「勾股定理」样例（发光线条画风，不用下素材库）
python mrv.py new <作品目录>                       # 照「数线段」样例（暗色电影感画风）
python mrv.py new <作品目录> --blank               # 空白模板
```

### 2. 写口诀和歌词

照 `prompts/写词.md` 写（这份提示词也可以原样交给别的 AI）：先验算每个数字、写清口诀成立的前提、想好评论区会挑什么刺，再写歌词。90 BPM，一句一小节，每句 11–15 字，一韵到底。存成作品目录的 `lyrics.md`（格式见样例：`## [Verse 1]` 下面一行一句 `1. 歌词`，句号从 1 连续编到最后）。

```
python mrv.py lyrics <作品目录>
```

它做两件事：歌词体检（字数、押韵、容易听错的写法，比如「是五」会被听成「十五」）；生成**送唱版**（数字写成汉字、去掉括号，`唱词.md`）和各平台的提示词（`给音乐模型/` 里的 Suno.md、海绵音乐.md、Mureka.md、通用.md，歌词已经填好）。
多音字唱错了就在作品目录写 `读音替换.json`（`{"原词": "同音字"}`，只影响唱的那份，字幕照旧）。

### 3. 出歌：先问用户「你有没有音乐模型的 API？」

- **有**（现在支持 ElevenLabs，Starter 档起）：请用户给密钥，保存后直接生成。**生成会花用户的额度，先告诉用户大概多少**（一首 70 秒约 1000 额度）。
  ```
  python mrv.py key elevenlabs              # 粘贴密钥（不显示）；或 --file 存密钥的文件
  python mrv.py music <作品目录> --api elevenlabs --takes 2
  ```
  密钥只存在用户自己电脑上（`~/.math-rap-video/keys.json`），不要写进作品目录、不要打印出来。
- **没有**（只用 Suno、海绵、Mureka 等网页）：把 `给音乐模型/` 里用户那个平台的文件给用户，让他照着生成 2–3 首、下载 mp3 回来。原理一样，歌词和风格词都已经排好了。

### 4. 对时间、挑一版

```
python mrv.py song <作品目录> --song 第一首.mp3 第二首.mp3      # 用接口生成的不用写 --song，自动用 歌/ 里的
```

它对每一版：分人声 → 按送唱版逐字强制对齐 → 算节拍 → 查「哪句可能没唱、字挤成一团、人声晚进」→ 自动挑最好的一版写成 `timing.json`。
Suno 的 mp3 里嵌着歌词时，没有 `lyrics.md` 也能直接用（它会读出来写成草稿，记得核对）。

**退出码 3 = 这版音频建议换，不是程序错误：不要改代码，也不要改歌词去迁就。** 告诉用户哪几句有问题，再生成一两版，或者用户接受。换版本：`mrv.py pick <作品目录> 生成_02`。

### 5. 写画面

改作品目录里两个文件（先读 `references/visuals.md`，再照样例改，不要从零写）：

- `storyboard.json`：画风 `style`、口诀横幅 `banner`、公式 `formulas`、弹字 `keywords`、箭头、背景。
- `graphics.py`：本题的图形，`setup(ctx)` 算时间，`draw(canvas, t, ctx)` 每帧画。

**时间一律写成相对歌词的表达式，不写死秒数**：`L(6)` 第 6 句开始、`W(9,'四')` 第 9 句唱到「四」、`B` 一拍。这样换一版歌，画面自动跟上。
最重要的两条：图形要大（主图形占画面一半以上，线宽 ≥ 9，字 ≥ 44）；每一句都要有画面变化。

**画风和背景**（`python mrv.py styles` 看全部）：

| 画风 | 样子 | 背景 |
|---|---|---|
| `cinema` | 暗色电影感，蓝色图形、黄色结果、白字黑底字幕 | 素材库里的 AI 生成镜头（没装素材库会先用暗色纯色底，`python scripts/install.py --get-library` 装） |
| `chalk` | 黑板粉笔 | 墨绿黑板，不用素材库 |
| `glow` | 发光线条，粗宋体口诀 | 深蓝网格，不用素材库 |

背景还能换成自己的：`storyboard.json` 写 `"backgrounds": {"source": "folder", "path": "我的视频文件夹"}`，或 `{"source": "image", "path": "图.jpg"}`，或 `{"source": "color", "color": "#101820", "texture": "grid"}`。自己做画风见 `references/styles.md`。

### 6. 检查

```
python mrv.py check <作品目录>
```

分镜问题、渲染出错、版面提醒（压字、压横幅、图形太小、画面空着）都会报出来，精确到第几句。它会先把背景铺好（约 1 分钟），所以预览图每一格垫的就是那一刻真实的背景镜头。**能看图就打开 `分镜预览.jpg` 和 `分镜预览_p1.jpg`… 逐句对照**：图形对不对、字有没有压住、背景镜头和图形搭不搭；看不了图就按报告改，改到「版面提醒 0 类」。例题的数字自己再验算一遍。

### 7. 出片

```
python mrv.py render <作品目录> --part 20 30      # 先出 10 秒看看
python mrv.py render <作品目录> [--vertical]       # 全片（6–12 分钟，放后台跑）；--vertical 再出一条竖屏
```

### 8. 交付

`成片.mp4`（和竖屏版）。告诉用户：画面和时间都检查过，**声音要人听一遍**，尤其 `状态.json` 里 `listen_lines` 那几句（口诀所在的句子）。

## 参考文件

| 文件 | 什么时候读 |
|---|---|
| `prompts/写词.md` | 写口诀和歌词（也可以直接交给别的 AI） |
| `prompts/音乐模型/` | 给各平台的写法模板（`mrv.py lyrics` 会自动填好歌词放进作品目录） |
| `references/visuals.md` | 写 storyboard.json 和 graphics.py 之前 |
| `references/audio.md` | 出歌、对时间、挑版本出问题时 |
| `references/styles.md` | 换画风、换背景、自己做画风 |
| `references/troubleshooting.md` | 任何一步报错 |
| `references/teaching.md` | 用户想了解原理、教别人做、不写代码（剪映）的做法 |
| `examples/gougu/` | 完整样例：勾股定理（含拼图证明的动画） |
| `examples/shuxianduan/` | 完整样例：数线段 |
