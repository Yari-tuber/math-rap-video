# 用 Suno 生成（网页 suno.com，Custom 模式）

> 这份写法按 Suno v6 官方文档和社区实测整理，**作者没有 Suno 会员，没有亲自实测**。用下来哪里不对，欢迎在 GitHub 提 issue。
> 注意：v6 只给 Pro / Premier；免费号只有 v6-mini，而且 2026-09 之后注册的免费号基本不能下载，免费档做的歌也不能商用。

## 1. 设置

| 设置 | 怎么选 |
|---|---|
| 模式 | Custom |
| 模型 | v6 |
| Variety（多样性） | 拉到 0（Off）：完全照风格词走 |
| Weirdness、Style Influence | 先不动（默认 50） |
| Vocal Gender | Male（想要女声就选 Female，风格词里的 male 改成 female） |
| Duration | Auto |
| 魔法棒、Persona | 不用（魔法棒会改写你的风格词） |

## 2. Style（风格）框：三选一，先用 A

**A 念唱（最像口诀说唱）**

```
Mandarin Chinese melodic rap, sing-song chant flow, {{bpm}} BPM, 4/4, minor key, mid-high male rap vocal, the melody moves between only two or three notes and returns to the root note at the end of every line, one lyric line per bar, steady on-beat delivery with three to four syllables per beat, every syllable clearly enunciated, lyrics sung exactly as written and in order, dry upfront lead vocal, light autotune, sparse trap drums, crisp hi-hats, soft piano loop, clean mix
```

**B 吐字最清楚（旋律最少，保底）**

```
Mandarin Chinese boom bap rap, {{bpm}} BPM, 4/4, head-nodding groove, male rap vocal with a calm confident teacher tone, rhythmic near-spoken delivery with very little melody, pitch stays close to one note and drops to the root at the end of each line, one lyric line per bar, every syllable crisp and clear, lyrics sung exactly as written and in order, dry vocal loud in the mix, punchy kick and snare, simple drum break, warm bassline, light piano sample, clean mix
```

**C 主歌念清楚、口诀带旋律**

```
Mandarin Chinese hip-hop with a catchy chant hook, {{bpm}} BPM, 4/4, minor key, mid-high male vocal, verses rapped clearly and evenly on the beat, one lyric line per bar, the hook is chanted on a simple two-note sing-song melody with strong emphasis so every word of the hook is easy to understand and remember, every line ends back on the root note, lyrics sung exactly as written and in order, vocal-forward mix, light autotune, trap hi-hats, warm 808, soft piano, clean bright mix
```

## 3. Exclude styles（排除）框

```
ad-libs, backing vocals, choir, vocal harmonies, humming, spoken intro, fade out, Cantonese
```

## 4. Lyrics（歌词）框：整段复制

```
{{lyrics_suno}}
```

写法规矩（已经替你做好了）：只有要唱的字和方括号标签；没有圆括号（圆括号里的字会被唱成和声）；数字写成汉字；一句一行，段内不空行。

## 5. 生成和挑选

1. 点 Create 两次，一共 4 首。先在网页上听，**别急着下载**（Pro 每月只有 20 次下载）。
2. 挑的时候看：人声大约 {{intro_sec}} 秒进（两小节前奏）；{{n_lines}} 句一句不少；口诀那两处不看歌词也能听清；没有 yeah、uh 这类垫词。
3. 歌曲编辑器（Song Editor）底部会显示 BPM，在 {{bpm_lo}}–{{bpm_hi}} 之间最好；显示一半或两倍说明它当成了半速 / 倍速。
4. 挑 2–3 首下载 MP3，丢回给 AI：`mrv.py song <作品目录> --song 第一首.mp3 第二首.mp3`，它会自己量哪一首最合适。
5. 只有一两句唱错：用 Replace Section 框住那一两小节重做，不用整首重来。
