"""音乐模型的接口插件：一个平台一个文件。

每个插件提供：
    NAME        平台名（命令行里用的，小写英文）
    TITLE       给人看的名字
    KEY_HELP    去哪拿密钥（一句话 + 网址）
    COST_HELP   大概多少钱 / 额度
    generate(work, sections, bpm, takes, key, preset, dry) -> [生成的音频路径]
        sections: [{name, lines: [唱的歌词…]}]（已经是送唱版：数字写汉字、没有编号）

想加一家：照 elevenlabs.py 写一个 <平台>.py，在下面 PROVIDERS 里加一行。
"""
from importlib import import_module

PROVIDERS = {
    "elevenlabs": "music_api.elevenlabs",
}


def get(name):
    name = (name or "").lower()
    if name not in PROVIDERS:
        raise SystemExit(f"错误：还不支持「{name}」的接口。现在支持：{', '.join(PROVIDERS)}。"
                         "没有接口的平台用网页生成：打开作品目录的 给音乐模型/ 照着做，生成好把音频丢回来")
    return import_module(PROVIDERS[name])


def names():
    return list(PROVIDERS)
