# 用 Mureka 生成（国内站 mureka.cn / 国际站 mureka.ai）

> 按 Mureka 的标签规则和社区经验整理，没有逐项实测。免费档用的是旧模型，下载要会员；付费档可以商用。

## 1. 选「自定义」模式

## 2. 歌曲描述（风格）框：整段复制（300 字以内）

```
Mandarin Chinese rap, melodic chant flow, {{bpm}} BPM, male vocal, two-note sing-song melody, each line ends on the root note, one line per bar, crisp clear diction, lyrics sung exactly as written, short intro, light trap drums, soft piano, clean mix, educational, 说唱, 口诀, 吐字清楚
```

## 3. 歌词框：整段复制

```
{{lyrics_mureka}}
```

（已经按 Mureka 的规矩改好：`[Hook]` 换成了 `[Chorus]`，标签里只有段落名，没有 `[End]`。）

## 4. 挑选

1. 先在网页上听：前奏别太长；{{n_lines}} 句一句不少；口诀那两处听得清。
2. 下载 2–3 首 MP3，丢回给 AI：`mrv.py song <作品目录> --song 第一首.mp3 第二首.mp3`。
3. Mureka 也有 API（platform.mureka.ai）。有密钥的话可以让 AI 直接生成（见 SKILL.md「出歌」）。
