#!/usr/bin/env python3
"""Generate expanded, block-aligned Korean notes for T210 chapters 1-10."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from dhammapada_manual_ko_3_10 import MANUAL


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "불교_경전"
CACHE = ROOT / ".cache" / "buddist-sutra-builder"
XML = CACHE / "8980644a8f36aeec-T04n0210.xml"
GAIJI = CACHE / "262237f7c9196fb3-cbeta_gaiji.json"

CHAPTERS = {
    1: ("무상품", "無常品", "무상", "법구경_제1품_무상품_문장별_풀이_해설.md"),
    2: ("교학품", "教學品", "배움", "법구경_제2품_교학품_문장별_풀이_해설.md"),
    3: ("다문품", "多聞品", "많이 듣고 배우는 지혜", "법구경_제3품_다문품_문장별_풀이_해설.md"),
    4: ("독신품", "篤信品", "검증된 믿음", "법구경_제4품_독신품_문장별_풀이_해설.md"),
    5: ("계신품", "戒慎品", "계율과 삼감", "법구경_제5품_계신품_문장별_풀이_해설.md"),
    6: ("유념품", "惟念品", "호흡과 마음챙김", "법구경_제6품_유념품_문장별_풀이_해설.md"),
    7: ("자인품", "慈仁品", "자비와 불살생", "법구경_제7품_자인품_문장별_풀이_해설.md"),
    8: ("언어품", "言語品", "바른 말", "법구경_제8품_언어품_문장별_풀이_해설.md"),
    9: ("쌍요품", "雙要品", "마음과 업의 두 갈래", "법구경_제9품_쌍요품_문장별_풀이_해설.md"),
    10: ("방일품", "放逸品", "방일하지 않는 정진", "법구경_제10품_방일품_문장별_풀이_해설.md"),
}

TOPICS = [
    ("무상", "無常|老|死|命|病|衰", "조건 지어진 것은 생겨나고 변하며 사라진다는 무상의 통찰", "변화를 부정하지 말고 지금 할 수 있는 선한 행동을 미루지 않는 것", "무상을 허무주의나 생명 경시로 오해하지 않아야 한다"),
    ("마음과 업", "心|意|善惡|罪|福|行業", "의도를 지닌 생각·말·행동이 습관과 결과를 만든다는 업의 원리", "행동 직전의 의도와 행동 뒤의 마음을 관찰하여 해로운 반복을 끊는 것", "업을 고정된 운명이나 외부의 상벌로만 이해하지 않아야 한다"),
    ("배움과 지혜", "多聞|聞|學|智慧|解義|明哲", "듣고 성찰하고 실천하는 세 과정이 함께할 때 지혜가 성숙한다는 가르침", "배운 내용을 하루의 구체적 선택 하나에 적용하고 결과를 다시 성찰하는 것", "많이 아는 것과 실제로 번뇌가 줄어드는 것을 혼동하지 않아야 한다"),
    ("믿음", "信|慚|愧", "믿음이 맹신이 아니라 바른 행위를 시작하고 지속하게 하는 신뢰라는 뜻", "가르침을 삶에서 시험하며 탐욕·성냄·어리석음이 실제로 줄어드는지 확인하는 것", "권위에 대한 복종을 바른 믿음으로 착각하지 않아야 한다"),
    ("계율", "戒|慎|護|攝|禁|律", "계율이 처벌 규정이 아니라 자신과 타인의 괴로움을 예방하는 보호선이라는 뜻", "몸과 말의 행동을 돌아보고 해가 예상되는 행동 앞에서 한 번 멈추는 것", "계율을 남을 평가하거나 우월감을 세우는 도구로 사용하지 않아야 한다"),
    ("정념과 선정", "惟念|念|出息|入息|定|思惟|覺", "현재의 몸과 마음을 잊지 않고 관찰하여 산란과 혼침을 알아차리는 수행", "호흡을 바꾸려 하지 말고 들고나는 과정을 차분히 알아차리는 것", "집중에서 생긴 고요함 자체를 최종 해탈로 여기지 않아야 한다"),
    ("자비와 불살생", "慈|仁|不殺|殺|害|怨|忍", "모든 존재가 고통을 싫어한다는 공감에서 폭력을 멈추는 자비의 윤리", "분노가 일어날 때 즉시 보복하지 않고 상대와 자신의 고통을 함께 살피는 것", "자비를 무조건적인 순응이나 부당함의 묵인으로 오해하지 않아야 한다"),
    ("바른 말", "言|語|口|辭|罵|詈|說", "말도 의도를 지닌 행위이므로 진실성·유익함·때와 방식까지 살펴야 한다는 정어의 가르침", "말하기 전에 사실인지, 필요한지, 해를 줄이는 방식인지 점검하는 것", "침묵만을 선으로 여기거나 거친 진실을 정당화하지 않아야 한다"),
    ("정진과 불방일", "精進|放逸|勤|務|健", "선한 마음을 꾸준히 기르고 해로운 습관을 방치하지 않는 불방일의 태도", "작더라도 매일 반복할 수 있는 수행을 정하고 중단했을 때 다시 시작하는 것", "정진을 과도한 긴장·자기학대·성과 경쟁으로 바꾸지 않아야 한다"),
    ("열반", "泥洹|不死|滅度|解脫|彼岸", "탐욕·성냄·어리석음의 불길이 꺼져 생사의 속박에서 벗어나는 열반의 방향", "집착이 느슨해질 때 생기는 자유와 평안을 일상에서 세밀하게 확인하는 것", "열반을 육체의 영생이나 단순한 죽음과 동일시하지 않아야 한다"),
]

CHAPTER_CONTEXT = {
    1: "이 품은 죽음을 겁주기보다 유한한 삶을 분명히 보아 집착을 줄이게 한다.",
    2: "이 품은 배움의 가치를 암송량이 아니라 행위의 변화와 계율의 성숙으로 판단한다.",
    3: "이 품의 다문은 정보를 많이 모으는 일이 아니라 듣고 분별하여 법답게 행하는 능력이다.",
    4: "이 품의 믿음은 지혜와 부끄러움과 계행을 낳는 실천적 신뢰이며 맹목적 확신과 다르다.",
    5: "이 품은 계율을 자유를 억압하는 명령보다 후회와 해침을 미리 막는 울타리로 제시한다.",
    6: "이 품은 들숨과 날숨을 잊지 않는 안반념을 통해 몸과 마음의 변화를 직접 관찰하게 한다.",
    7: "이 품은 불살생을 소극적인 금지에 그치지 않고 모든 존재의 안녕을 바라는 적극적 자비로 확장한다.",
    8: "이 품은 말이 관계와 마음의 업을 동시에 만든다는 점을 밝히며 진실하고 부드러운 표현을 권한다.",
    9: "이 품은 선과 악, 청정과 오염의 결과를 짝지어 보여 주며 그 갈림이 마음에서 시작됨을 강조한다.",
    10: "이 품은 방일을 살아 있으나 깨어 있지 못한 상태로 보고, 지속적인 정진을 죽음 없는 길이라 부른다.",
}


def load_builder():
    path = ROOT / "scripts" / "generate_full_sutra_readings.py"
    spec = importlib.util.spec_from_file_location("sutra_builder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sutra_builder"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def extract_chapters() -> dict[int, list[str]]:
    m = load_builder()
    gaiji = m.load_gaiji(GAIJI.read_bytes(), {})
    blocks = m.extract_juan(XML.read_bytes(), gaiji)[1]
    starts = []
    for index, block in enumerate(blocks):
        if index == 4 and block.startswith("無常品"):
            starts.append(index)
        elif "品法句經" in block[:20]:
            starts.append(index)
    starts.append(len(blocks))
    return {number: blocks[starts[number - 1] : starts[number]] for number in range(1, 11)}


def load_existing() -> dict[str, tuple[str, str]]:
    result = {}
    for number in (1, 2):
        path = OUT / CHAPTERS[number][3]
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"\*\*원문\*\*  (.*?)\n\n\*\*우리말 풀이\*\*  (.*?)\n\n\*\*해설\*\*  (.*?)(?=\n\n## |\n\n## 편집 확인)",
            re.S,
        )
        for source, translation, note in pattern.findall(text):
            result[source.strip()] = (translation.strip(), note.strip())
    return result


def topic_for(source: str):
    for topic in reversed(TOPICS):
        if any(keyword in source for keyword in topic[1].split("|")):
            return topic
    return TOPICS[2]


def expanded_note(number: int, source: str, old_note: str = "") -> str:
    chapter_topic = {
        1: (0, "無常|老|死|命|衰|壞"),
        2: (2, "學|教|聞|解|智"),
        3: (2, "多聞|聞|學|智"),
        4: (3, "信|慚|愧"),
        5: (4, "戒|慎|律|護"),
        6: (5, "念|息|定|思惟|覺"),
        7: (6, "慈|仁|不殺|殺|害|忍"),
        8: (7, "言|語|口|辭|說"),
        9: (1, "心|意|善|惡|罪|福|行"),
        10: (8, "放逸|精進|勤|務|健"),
    }
    topic_index, keywords = chapter_topic[number]
    selected = TOPICS[topic_index] if any(k in source for k in keywords.split("|")) else topic_for(source)
    name, _, doctrine, practice, caution = selected
    if " 이 구절은" in old_note:
        old_note = old_note.split(" 이 구절은", 1)[0]
    lead = old_note.rstrip(".") + ". " if old_note else ""
    return (
        f"{lead}이 구절은 {name}의 관점과 연결된다. 교학적으로 살피면 핵심 내용은 ‘{doctrine}’이다. "
        f"{CHAPTER_CONTEXT[number]} 수행에서는 {practice}이 핵심이며, "
        f"그 과정에서 {caution}. 따라서 문자상의 보상과 처벌만 좇기보다 이 가르침이 지금의 의도·말·행동을 어떻게 바꾸는지 확인해야 한다."
    )


def title_translation(number: int, index: int, source: str) -> str | None:
    ko, _, _, _ = CHAPTERS[number]
    if index == 1:
        if number == 1:
            return "법구경 제1품 무상품이며 모두 스물한 장이다."
        return f"법구경 제{number}품 {ko}이다."
    if index == 2 and re.search(r"第|章", source):
        nums = {1: "스물한", 2: "스물아홉", 3: "열아홉", 4: "열여덟", 5: "열여섯", 6: "열두", 7: "열아홉", 8: "열두", 9: "스물두", 10: "스물"}
        return f"제{number}품, 모두 {nums[number]} 장으로 이루어져 있다."
    return None


def main() -> None:
    chapters = extract_chapters()
    existing = load_existing()

    for number, blocks in chapters.items():
        ko, hanja, theme, filename = CHAPTERS[number]
        lines = [
            f"# 법구경 제{number}품 {ko}({hanja}) — 확장 해설본",
            "",
            "> 저본: CBETA T04 No.210 《法句經》 권상. 원전 단락을 빠짐없이 순서대로 싣고 각 단락에 우리말 풀이와 확장 해설을 대응시켰다.",
            ">",
            f"> 해설 방향: {theme}. 교리적 의미, 수행 적용, 오해하기 쉬운 지점을 함께 설명한다.",
            "",
        ]
        for index, source in enumerate(blocks, 1):
            manual = existing.get(source)
            translated = MANUAL[number][index - 1] if number in MANUAL else (
                title_translation(number, index, source) or manual[0]
            )
            note = expanded_note(number, source, manual[1] if manual else "")
            lines += [
                f"## {index}", "", f"**원문**  {source}", "",
                f"**우리말 풀이**  {translated}", "", f"**해설**  {note}", "",
            ]
        lines += [
            "## 편집 확인", "",
            f"- T210 권상 제{number}품의 원문 단락 {len(blocks)}개를 순서대로 수록했다.",
            f"- 원문·우리말 풀이·확장 해설이 각각 {len(blocks)}개로 일대일 대응한다.",
            "- 원문의 이체자와 문장부호를 보존했다.", "",
        ]
        (OUT / filename).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
