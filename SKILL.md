---
name: math-rap-video
description: 把一个知识点（数学为主，其他学科也行）做成"口诀 + 图形演示"的讲解短视频，风格类似抖音「Rap&科学」：暗色电影感背景、顶部常驻口诀、中间蓝色图形逐步演示、白字公式加黄色结果、底部逐句字幕，画面跟着唱词或配音卡点。音频由用户或客户自带（任何 AI 音乐平台生成的歌、真人说唱、普通配音都行），背景从自带素材库里按用途自动挑，画面由脚本逐帧绘制后用 ffmpeg 合成，可另出竖屏版。用户说"做一个数学说唱视频""把这个知识点做成口诀视频""复刻 Rap&科学 那种视频""教学说唱 MV""给这段配音/这首歌做讲解画面""口诀讲解视频"，或想把某个公式、定理、解题方法做成好记的歌加动画时，都应使用本 skill，即使没有明确说"说唱"。只想了解做法、选音乐工具、或教别人做时，也用本 skill 里的说明回答。
---

# 口诀讲解视频（数学说唱）

把一个知识点做成约 1 分钟的讲解视频。它好记，是因为三层东西叠在一起，并且都跟着同一条音频走：

- **耳朵**：固定节奏，一句歌词一小节，一韵到底，所以顺口
- **语言**：8–10 字的口诀，唱 2–3 次，屏幕顶部常驻
- **眼睛**：唱到哪个字，图形就走到哪一步，学生能看到"为什么对"

叙事固定为：**抛问题 → 设陷阱（笨办法会乱）→ 给口诀 → 示范 → 讲原理 → 收尾**。

## 分工：谁提供什么

| 部分 | 谁来做 | 说明 |
|---|---|---|
| 口诀、歌词、分镜 | 你（AI）写，用户确认 | 规则见 `references/lyrics.md` |
| **音频（人声 + 音乐）** | **用户或客户自己提供** | 用哪家模型、谁的声音，由他们定。把 `references/audio.md` 里"发给客户的要求"给他们。本 skill 不替用户选平台，也不默认花钱生成 |
| 字幕时间 | 脚本算 | 任何工具导出的 SRT 都行，有错别字也行 |
| 背景画面 | 素材库自动挑 | `assets/backgrounds/`，按用途打了标签；可以自己加 |
| 图形、口诀、公式、字幕 | 脚本逐帧画 | 你只写本题的 `storyboard.json` 和 `graphics.py` |

## 环境

第一次使用先运行自检，它会逐项告诉你缺什么、怎么装：

```bash
python $SKILL/scripts/check_env.py
```

需要的是：Python 3.10+（`pip install pillow numpy librosa pypinyin`）、`ffmpeg` / `ffprobe`、一个中文粗体字体（常见系统自带的会自动找到）、背景素材库。素材库按这个顺序找：环境变量 `MATH_RAP_LIBRARY` → 本 skill 的 `assets/backgrounds/` → 共享位置 `~/.math-rap-video/backgrounds/`。缺素材库时运行 `python $SKILL/scripts/install.py --library <素材库压缩包.zip>`。

下文 `$SKILL` 指本 skill 所在目录（就是这份 SKILL.md 所在的文件夹）。它不是现成的环境变量：运行命令时把它换成实际路径，或者先设一次（bash：`export SKILL="/路径/math-rap-video"`；PowerShell：`$SKILL="C:\路径\math-rap-video"`）。路径里有空格或中文时要加引号。所有脚本都是普通命令行程序（都支持 `--help`），任何能跑命令的 AI 或人都可以照着做，不依赖特定工具。

## 流程

```
1 写词和分镜 ──→ 2 用户交音频 ──→ 3 prepare_audio 算时间并验收
                                        │
4 写 storyboard.json + graphics.py ←────┘
        │
5 check + 预览图（看图确认）──→ 6 build_video 出片 ──→ 7 检查并交付
```

每一步做完，把结果简短告诉用户。第 1 步和第 5 步要等用户确认后再往下走。

**用户带着现成的歌词和音频来**（歌词已经定稿、音频已经按它做好）时：歌词一个字都不改，否则画面和唱词对不上。第 1 步只做三件事：新建作品、把歌词原样放进 `lyrics.md`、在末尾补上分镜表；`check_lyrics.py` 的结果只作参考，不据此改词。然后直接从第 3 步继续。

### 1. 新建作品，写口诀、歌词、分镜表

```bash
python $SKILL/scripts/new_project.py <作品目录>          # 复制样例（数线段）作为起点
python $SKILL/scripts/new_project.py <作品目录> --blank  # 或从空白模板开始
```

按 `references/lyrics.md` 写 `lyrics.md`：一句 = 一小节，每句 11–15 字（原理段 9–11 字），一韵到底；结构是 Verse 1（14 句）+ Hook（2 句，口诀单独念）+ Verse 2（8 句）。

**分镜表写在 `lyrics.md` 末尾的 `## 分镜表` 小节里**（一个表格：句号、画面动作、唱到哪个字触发）。它是给用户确认用的，也是第 4 步写代码的依据；脚本不读它。

写完运行歌词体检，把"必须改"的都改掉，"建议"逐条看一下：

```bash
python $SKILL/scripts/check_lyrics.py <作品目录>     # 结构、每句字数、押韵、容易听错的写法
```

**例题的每个数字自己验算一遍**（脚本查不了数学）。然后把口诀、歌词、分镜表给用户确认。

### 2. 用户提供音频

把确认后的歌词和 `references/audio.md` 里的"发给客户的要求"交给用户。他们可以用任何方式做音频：AI 音乐平台、真人说唱、TTS 或真人配音加伴奏。交回来的东西是：

- 一个或几个音频文件（mp3 / wav），带人声。AI 生成的建议一次给 2–3 版，方便挑
- 最好再给字幕文件（SRT）。没有的话，用手头任何语音识别工具对音频识别一遍，导出 SRT 即可

如果用户明确要求你代为生成歌曲，并且提供了 ElevenLabs 的 API Key，可以用 `scripts/gen_music.py`（用法见 `references/audio.md`）。这是可选的，每版都要花用户的额度，生成前先说明。

### 3. 处理音频：算时间，并判断这版能不能用

```bash
python $SKILL/scripts/prepare_audio.py <作品目录> --audio 歌.mp3 --srt 识别.srt --bpm 90 --intro-bars 2
```

它把识别结果按字对到歌词上（错别字、断句不同都没关系），检测速度和节拍，写出 `timing.json`，并把音频复制一份到作品目录（出片时从这里读，所以作品目录里会多出音频文件，属于正常）。最后一行给出**结论**：

- **可用**：继续。有"匹配率低"的句子时，记下来，交付时提醒用户听这几句
- **建议换一版**（退出码 3）：会列出原因，常见的是漏唱了某一句、人声进晚了、整体被挤压。换一版音频，不要硬用

有几版音频时，每版写到不同的文件再比较，选定后复制成 `timing.json`：

```bash
python $SKILL/scripts/prepare_audio.py <目录> --audio 生成_01.mp3 --srt 01.srt --bpm 90 --intro-bars 2 --out timing_01.json
python $SKILL/scripts/prepare_audio.py <目录> --audio 生成_02.mp3 --srt 02.srt --bpm 90 --intro-bars 2 --out timing_02.json
cp <目录>/timing_02.json <目录>/timing.json
```

怎么挑见 `references/audio.md` 第三节。简单说：先排除"建议换一版"的，再选**口诀那两句匹配率最高**的，最后才看节奏整不整齐。两条冲突时**口诀清楚优先于节奏整齐**：观众记的是口诀。

其他情况：纯讲解配音、没有节拍的音频加 `--no-beat`；没有 SRT 时的退路是 `--grid --entry <人声进入秒数>`，按一句一小节推算；`--intro-bars` 写和客户约定的前奏小节数（上面例子里的 2 是我们给客户的默认要求），没有约定过就不要写。Windows 的 PowerShell 里 `cp` 也能用；在 cmd 里换成 `copy`。

**换音频只需重跑这一步**，分镜不用改。

### 4. 写分镜和题目图形

读 `references/visuals.md`，然后改作品目录里的两个文件：

- **`storyboard.json`**：口诀横幅、公式、弹字、箭头、背景切换计划
- **`graphics.py`**：本题专用的图形，实现 `setup(ctx)` 和 `draw(canvas, t, ctx)`

最重要的一条规则：**时间一律写成相对歌词的表达式，不写死秒数。**

| 写法 | 含义 |
|---|---|
| `L(6)` / `E(6)` | 第 6 句的起点 / 终点 |
| `W(9,'四')` / `W(9,'四',2)` | 第 9 句里"四"字（第 2 个"四"）唱出来的时间 |
| `B`、`L(6)+2*B` | 一拍；第 6 句开始后 2 拍 |

这样画面真的卡在唱词上，而且客户换一版音频，重跑第 3 步就能直接出片。

图形是最花功夫的一步。引擎已经提供了常用的画法（点、线、弧、扇形角、直角符号、数字方块、括线、一行多色算式、整块旋转平移、沿路线移动、等距排开），先在 `references/visuals.md` 第 4 节找现成的，不要从零造。写一小段就出图看一眼（见下一步），不要全写完再看。

实测里最常见的两个毛病，写的时候就避开：

- **图形画得太小太细**。这是给手机看的：主图形要占到画面宽度的一半以上（宽 ≥ 800 或高 ≥ 400），一排元素用 `ctx.spread(n)` 铺满宽度，线宽 ≥ 9，字号 ≥ 44。尺寸参考见 `references/visuals.md` 第 1 节
- **每一句都要有画面**。图形、弹字、公式至少有一样在画面中间，不要让某一句只剩背景和字幕

### 5. 检查和预览

```bash
python $SKILL/scripts/overlay_engine.py <作品目录> check          # 必须：分镜问题 0 个、渲染出错 0 处；"版面提醒"逐条核对
python $SKILL/scripts/overlay_engine.py <作品目录> sheet          # 分镜预览.jpg：每句一格的总览
python $SKILL/scripts/overlay_engine.py <作品目录> sheet --pages  # 再加 分镜预览_p1.jpg…：大图分页，看文字有没有压边（总览图也会一起更新）
python $SKILL/scripts/overlay_engine.py <作品目录> frames "L(18)" "L(19)" 0.2   # 分镜逐帧.jpg：把一段动画逐帧排开
```

**自己把图打开看**，逐格对照分镜表：

- 总览图：每句该出现的东西出现了没有，有没有哪一格是空的
- 大图分页：文字有没有互相压住、有没有顶到口诀横幅或字幕、图形够不够粗够不够大
- 有移动、旋转、飞入的地方，用 `frames` 看途中有没有撞到别的东西
- `check` 的"版面提醒"指出的时间点，逐个看一眼（它会报：顶到横幅、压到字幕、和公式重叠、碰到边缘、图形偏小、画面中间是空的、文字互相压住）
- `check` 查不出的：文字压在线条或色块上看不清、图形画错了数量、颜色不够醒目。这些只能看大图发现

有问题就改第 4 步再看。没问题后把总览图给用户确认，再出片。

### 6. 出片

```bash
python $SKILL/scripts/build_video.py <作品目录> bg            # 挑背景并拼接，打印每段用了哪个素材
python $SKILL/scripts/build_video.py <作品目录> final 20 30   # 可选：先出 10 秒片段看效果
python $SKILL/scripts/build_video.py <作品目录> final         # 全片，约 6–12 分钟（看电脑快慢），放后台跑
python $SKILL/scripts/build_video.py <作品目录> sheet         # 成片_总览.jpg
python $SKILL/scripts/make_vertical.py <作品目录> --title "标题"   # 可选：竖屏版（抖音、快手、视频号）
```

`bg` 会自动判断每一段中间有没有题目图形，有的话只挑"安静"片段（没有亮的人脸特写），并在打印出来的清单里注明。预览都看过以后，也可以用 `build_video.py <作品目录> all` 一条命令完成 check + bg + final + 总览图。竖屏版是把横屏成片放在 1080×1920 画面的中间，上方加标题、下方加小字、背景用模糊放大的画面填满；它不会把图形重新排成竖版。竖屏标题不写 `--title` 时，会读 `storyboard.json` 里的 `vertical.title`，再没有就用歌词文件的标题。

### 7. 检查并交付

看 `成片_总览.jpg`：背景够不够暗、图形和字清不清楚、有没有背景里的亮脸正好压在弹字或说明文字后面（有的话在背景计划里给那一句加 `:quiet` 或指定片段，重跑 `bg` 和 `final`）。然后把 `成片.mp4` 交给用户，并说明：

- 画面和时间是脚本验证过的，但**声音需要人来听**：请重点看口诀弹出、结果数字出现时，和唱词是不是同一下
- 第 3 步里匹配率低的句子，请专门听一下

## 参考文件

| 文件 | 什么时候读 |
|---|---|
| `references/lyrics.md` | 写口诀、歌词、分镜表之前 |
| `references/audio.md` | 用户问"用什么做音乐/配音"时；要把音频要求发给客户时；验收和挑选音频时 |
| `references/visuals.md` | 写 storyboard.json 和 graphics.py 之前（版式、字段、画图工具、常见题型画法） |
| `references/library.md` | 要给素材库加片段、生成新背景，或背景挑得不合适时 |
| `references/troubleshooting.md` | 任何一步报错或效果不对时 |
| `references/teaching.md` | 用户想了解原理、教别人做、或不想写代码（剪映做法）时 |
| `references/compatibility.md` | 用户问"别的 AI / 别的模型能不能做"时；要把 skill 交给别人用时 |
| `examples/shuxianduan/` | 完整样例：歌词、分镜、图形。写新题目前先看一遍 |

## 脚本一览

| 脚本 | 作用 |
|---|---|
| `check_env.py` | 环境自检 |
| `new_project.py` | 新建作品目录 |
| `check_lyrics.py` | 歌词体检 |
| `prepare_audio.py` | 音频 + 字幕 → `timing.json`，并给出可用 / 换一版的结论 |
| `overlay_engine.py` | 检查、预览、渲染叠加层 |
| `build_video.py` | 挑背景、合成成片、出总览图 |
| `make_vertical.py` | 横屏成片 → 竖屏版 |
| `library_tool.py` | 管理背景素材库（加、删、改标签、总览图） |
| `gen_music.py` | 可选：用 ElevenLabs 生成歌曲 |
| `install.py` | 把本 skill 装进其他 AI 工具（Codex、Gemini CLI、opencode 等），安放素材库 |
| `chat_pack.py` | 给只能聊天的 AI 生成提示包（写歌词 / 写画面 / 按检查结果修改） |
