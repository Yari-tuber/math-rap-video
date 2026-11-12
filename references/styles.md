# 画风和背景

长相和题目分开：同一个作品（同一份歌词、分镜、图形），`storyboard.json` 里改一个词就换一套长相。

## 换画风

```json
"style": "glow"
```

`python mrv.py styles` 列出全部画风。自带三套：

| 画风 | 长什么样 | 背景从哪来 | 适合 |
|---|---|---|---|
| `cinema` | 暗色电影感：蓝色图形、黄色结果数字、白字黑底字幕 | 素材库里 26 段 AI 生成的暗色镜头，按用途挑 | 最像抖音上那种口诀说唱，什么题都行 |
| `chalk` | 黑板粉笔：粉笔色线条（白、粉蓝、粉黄），字幕不加底框 | 墨绿黑板（代码生成，带擦过的粉笔痕） | 几何、作图题；不想下素材库 |
| `glow` | 发光线条：青色发光图形、粗宋体口诀 | 深蓝夜色 + 淡网格（代码生成） | 想要高级感、有氛围 |

只想改一两处，在 `storyboard.json` 里写同名的键覆盖，别的照画风：

```json
"style": "glow",
"colors": {"result": "#FF8A3D"},
"subtitles": {"size": 60},
"glow": null
```

## 换背景

`storyboard.json` 写 `backgrounds`（画风里的是默认值）：

| 写法 | 效果 |
|---|---|
| `{"source": "library", "plan": [["T0","problem"], ["L(3)","trap"], …]}` | 自带素材库，按用途挑（problem 抛问题、trap 陷阱、reveal 给口诀、demo 示范、hook 口诀大字、principle 讲原理、aha 恍然大悟、outro 收尾；加 `:quiet` 只挑没有亮人脸的安静片段）。素材库没装时自动先用暗色纯色底 |
| `{"source": "folder", "path": "D:/我的素材"}` | 自己的视频文件夹，轮流用；不写 plan 就每 4 句换一段；写了 plan 就在那些时间点换 |
| `{"source": "image", "path": "背景.jpg"}` | 一张图慢慢推近；`"motion": "none"` 不动 |
| `{"source": "color", "color": "#101820", "color2": "#05080C", "texture": "grid"}` | 纯色渐变；`texture` 可以是 `grid` 网格、`chalk` 黑板、`noise` 颗粒、`none` |

所有来源都会再过一道调色 `grade`（ffmpeg 滤镜，默认压暗、降饱和、加暗角），保证图形和字看得清。想原样显示就写 `"grade": "null"`。

## 自己做一个画风

1. 复制 `styles/cinema/` 到 `~/.math-rap-video/styles/<新名字>/`（放在这里各家 AI 工具都能用，skill 更新也不会被覆盖）。
2. 改 `style.json`：

```jsonc
{
  "name": "给人看的名字",
  "desc": "一句话：长什么样、适合什么题",
  "palette": {                // 颜色用语义名，图形代码里写 "primary"、"result"……就跟着画风变
    "text": "#FFFFFF",        // 正文、横幅
    "primary": "#4C8DFF",     // 主图形（旧名字 blue）
    "primary_dark": "#285CC8", "primary_light": "#82B9FF",
    "highlight": "#EC546A",   // 正在讲的、错的（旧名字 red）
    "result": "#FFD84A",      // 结果数字（旧名字 yellow）
    "accent": "#FF6030", "ok": "#5CD68C", "muted": "#9696A0", "line": "#E6ECFF",
    "stroke": "#000000"       // 字的描边
  },
  "fonts": {"heavy": ["字体文件路径"], "subtitle": ["字体文件路径"]},   // 找不到就用系统里的粗体
  "banner": {"y": 78, "size": 84, "color": "text", "stroke": 3},       // 顶部口诀
  "formula": {"y": 830},                                               // 公式那一行
  "subtitles": {"y": 1010, "size": 64, "color": "text", "box": true, "box_color": "#000000", "box_alpha": 165, "radius": 0, "stroke": 0},
  "glow": {"radius": 16, "strength": 0.9},                             // 图形发光；null 不发光（发光会让出片慢一些）
  "backgrounds": {"source": "color", "color": "#0B1A2C", "texture": "grid", "grade": "vignette=PI/3.6"}
}
```

3. 作品里写 `"style": "<新名字>"`，跑 `mrv.py check` 看预览图。

旧作品写的颜色名（white blue red yellow orange green gray）照样能用，会自动对到语义名上。
