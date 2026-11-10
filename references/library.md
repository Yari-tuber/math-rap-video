# 背景素材库

素材库是一个文件夹：整理好的背景片段（1920×1080、30fps、无声、每段约 8 秒）加一份 `library.json`。出片时 `build_video.py` 按分镜里的"用途"自动挑片段，所以做新视频一般不用再生成背景。

## 位置

查找顺序：`storyboard.json` 的 `backgrounds.library` → 环境变量 `MATH_RAP_LIBRARY` → 本 skill 的 `assets/backgrounds/`。

素材库和 skill 可以分开发放：把素材库压缩包解压到 `assets/backgrounds/`（里面直接是 `library.json` 和 mp4），或解压到任意位置再设置环境变量。

```bash
python $SKILL/scripts/library_tool.py list     # 每种用途有哪些片段（带 * 的是"安静"片段）
python $SKILL/scripts/library_tool.py check    # 文件是否齐全、每种用途是否至少 2 段
python $SKILL/scripts/library_tool.py sheet    # 生成 library_overview.jpg
```

## 9 种用途

| 用途 | 对应段落 | 适合的画面 |
|---|---|---|
| `problem` | 抛问题 | 黑板、桌上的物件、一个待解的东西 |
| `trap` | 陷阱 / 苦恼 | 抱头、踱步、揉纸、沙漏 |
| `reveal` | 给口诀 | 老师站在黑板前、灯亮起、书写 |
| `demo` | 示范计算 | 手部特写：写字、拨算盘、画图、摆木块 |
| `transition` | 过渡 | 人群剪影、走路、翻书、空镜 |
| `hook` | 口诀大字 | 画面简单、中间留空的镜头（大字要压在上面） |
| `principle` | 讲原理 | 抽象线条、齿轮、星空、书页图形 |
| `aha` | 恍然大悟 | 抬头微笑、点头、灯亮 |
| `outro` | 收尾 | 放下粉笔、转身微笑、晨光 |

一段片段可以有多个用途。

## "安静"和"热闹"

每段片段还有一个标记：

- **安静**：画面暗，没有亮的人脸特写，也没有发光的大块。上面压图形和文字最清楚
- **热闹**：有亮的人脸特写、强光源或很多细节。适合画面上东西少的句子（给口诀、收尾）

分镜的背景计划里，在用途后加 `:quiet`（如 `"demo:quiet"`）就只挑安静的。示范和原理这些图形多的句子建议都加。

```bash
python $SKILL/scripts/library_tool.py tag BG07_Professor --busy          # 改标记（--busy / --quiet）
python $SKILL/scripts/library_tool.py tag BG22_Gears --roles principle,hook   # 改用途
python $SKILL/scripts/library_tool.py remove BG17_Crumple                # 删掉一段
```

## 加新片段

任何来源都行（Google Flow / Veo、可灵、即梦、海螺、Runway、实拍），只要：横屏、整体偏暗、没有可读的文字、没有水印、时长 5 秒以上。

```bash
python $SKILL/scripts/library_tool.py add 新片段.mp4 --id BG30_Rain --roles trap,transition --desc "雨夜窗边的台灯"
python $SKILL/scripts/library_tool.py add 新片段.mp4 --id BG31_Smile --roles aha --busy --desc "学生抬头微笑"   # 人脸特写标成热闹
```

脚本会自动去掉上下黑边、放大 6% 裁掉边框、统一规格、去掉声音。

### 生成提示词模板

```
Cinematic [景别：close-up / medium shot / wide shot], [主体 + 一个简单动作],
dark moody [场景], single warm light source, deep black shadows,
desaturated teal and amber grade, heavy vignette, film grain, slow [运镜].
No readable text, no subtitles, no watermark.
```

要点：
- 每段只写**一个主体、一个动作**，动作要慢。画面越简单，上面的图形和字越清楚
- 统一写"暗、单一暖光、深阴影、低饱和、暗角、胶片颗粒"，整库风格才一致
- 一定写 `No readable text`：背景里的字会和口诀、公式打架
- 人物写成年人、不指定真实人物；年代感（1920s 西装、烛光、黑板）让不同片段看起来像同一部片子
- 生成后**一定抽帧看一眼再入库**：是不是你要的画面（生成工具偶尔会交回别的视频或半成品）、有没有文字、够不够暗、主体是不是在中间挡住图形的位置（偏左或偏右更好）

`library.json` 里每段都记了当时用的提示词，可以照着改。

### 换风格

想做另一种风格（比如明亮的卡通教室、科幻实验室）：新建一个素材库文件夹，按同样的 9 种用途各生成 2–3 段，用 `--lib` 指向它；出片时在分镜里写 `backgrounds.library`，并把 `backgrounds.grade` 改成合适的调色（明亮风格可以写 `"eq=brightness=-0.05"`，少压暗一点）。

## 挑得不合适时

- 换一套：改 `backgrounds.seed`
- 人脸或亮处压住了文字：给那一句的用途加 `:quiet`
- 固定某一段：在 `plan` 里把用途换成片段名，如 `["L(9)", "BG05_Candle"]`
- 看分配结果：`build_video.py <目录> bg` 会打印每段用了哪个片段，并写到 `背景分配.json`
