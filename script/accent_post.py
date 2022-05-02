import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Union

from data import conso_list, other_list, pause_list, vowel_list, yomi2mora


def yomi_to_phones(text: str):
    text = text.replace("づ", "ず").replace("ぢ", "じ").replace("を", "お").replace("ゔ", "う゛")
    text = text.replace("ふゅ", "ひゅ").replace("しぃ", "しい")

    text = text.replace("'", "").replace("|", "")
    for yomi, phones in yomi2mora.items():
        text = text.replace(yomi, " " + " ".join(phones) + " ")
    text = re.sub(r"\s+", " ", text)
    return text.split()


def modify_phonemes(yomi_phones: list[str], ojt_phones: list[str]):
    # 無声化・「おう」や「えい」が「おお」「ええ」になっていない場合に修正する
    new_phones: list[str] = []
    for tag, s1, e1, s2, e2 in SequenceMatcher(
        None, yomi_phones, ojt_phones
    ).get_opcodes():
        if tag == "equal":
            new_phones += ojt_phones[s2:e2]
            continue

        i1, i2 = s1, s2
        while i1 < e1 or i2 < e2:
            p1 = yomi_phones[i1] if i1 < len(yomi_phones) else None
            p2 = ojt_phones[i2] if i2 < len(ojt_phones) else None

            pp1 = yomi_phones[i1 - 1 : i1 + 1] if i1 > 0 else None
            pp2 = ojt_phones[i2 - 1 : i2 + 1] if i2 > 0 else None

            inc1 = inc2 = 1

            if i1 == e1:
                inc1 = 0
                inc2 = e2 - i2

            elif p1 == p2:
                new_phones += [p2]

            elif (p1 == "i" and p2 == "I") or (p1 == "u" and p2 == "U"):
                new_phones += [p2]

            elif (pp1 == ["o", "u"] and pp2 == ["o", "o"]) or (
                pp1 == ["e", "i"] and pp2 == ["e", "e"]
            ):
                new_phones += [p2]

            i1 += inc1
            i2 += inc2

    return new_phones


def yomi_to_accents(text: str):
    for yomi, phones in yomi2mora.items():
        text = text.replace(yomi, " " + " ".join(phones) + " ")
    text = text.replace("|", " | ").replace("'", " ' ")
    text = re.sub(r"\s+", " ", text)

    phrases = [t.strip().split() for t in text.split("|")]

    starts: list[str] = []
    ends: list[str] = []
    phrase_starts: list[str] = []
    phrase_ends: list[str] = []

    for phrase in phrases:
        if phrase == ["pau"]:
            starts += ["0"]
            ends += ["0"]
            phrase_starts += ["0"]
            phrase_ends += ["0"]
            continue

        assert sum(p == "'" for p in phrase) == 1

        moras: list[Union[tuple[str], tuple[str, str]]] = []
        for prev, cent in zip([""] + phrase[:-1], phrase):
            if cent not in conso_list:
                if prev in conso_list:
                    moras += [(prev, cent)]
                else:
                    moras += [(cent,)]

        pos = next(filter(lambda x: x[1] == ("'",), enumerate(moras)))[0]
        moras = list(filter(lambda x: x != ("'",), moras))

        mora_phrase_starts = ["1"] + ["0"] * (len(moras) - 1)
        mora_phrase_ends = ["0"] * (len(moras) - 1) + ["1"]

        if pos == 1:
            mora_starts = ["1"] + ["0"] * (len(moras) - 1)
        else:
            mora_starts = ["0", "1"] + ["0"] * (len(moras) - 2)

        mora_ends = ["0"] * (pos - 1) + ["1"] + ["0"] * (len(moras) - pos)

        for mora_start, mora_end, mora_phrase_start, mora_phrase_end, mora in zip(
            mora_starts, mora_ends, mora_phrase_starts, mora_phrase_ends, moras
        ):
            starts += [mora_start] * len(mora)
            ends += [mora_end] * len(mora)
            phrase_starts += [mora_phrase_start] * len(mora)
            phrase_ends += [mora_phrase_end] * len(mora)

    return (
        starts,
        ends,
        phrase_starts,
        phrase_ends,
    )


def accent_check(
    phones: list[str],
    accent_starts: list[bool],
    accent_ends: list[bool],
    accent_phrase_starts: list[bool],
    accent_phrase_ends: list[bool],
):
    # 最初はアクセント句開始
    expected_is_start = True

    for i in range(len(phones)):
        # 無音にアクセント句区切りは来ない
        if phones[i] in pause_list:
            assert not accent_phrase_starts[i]
            assert not accent_phrase_ends[i]

        # # アクセント句開始と終了は同時に来ない
        # assert not accent_phrase_start[i] or not accent_phrase_end[i]

        # 母音でかつ手前が子音のとき、アクセント句区切りラベルは一致する
        if phones[i] in vowel_list:
            if phones[i - 1] in conso_list:
                assert accent_phrase_starts[i] == accent_phrase_starts[i - 1]
                assert accent_phrase_ends[i] == accent_phrase_ends[i - 1]

        # 子音のとき、後ろとアクセント句区切りラベルが一致する
        if phones[i] in conso_list:
            assert accent_phrase_starts[i] == accent_phrase_starts[i + 1]
            assert accent_phrase_ends[i] == accent_phrase_ends[i + 1]

        if phones[i] in (vowel_list + other_list):
            # アクセント句開始後に開始は来ない
            if accent_phrase_starts[i]:
                assert expected_is_start
                expected_is_start = False

            # アクセント句終了後に終了は来ない
            if accent_phrase_ends[i]:
                assert not expected_is_start
                expected_is_start = True

            # # アクセント句終了は連続しない
            # if accent_phrase_ends[i]:
            #     assert not accent_phrase_ends[i + 1]

    # アクセントはアクセント句外で来ない
    in_accent_phrase = False
    for i in range(len(phones)):
        if phones[i] not in (vowel_list + other_list):
            continue

        if accent_phrase_starts[i]:
            in_accent_phrase = True

        if accent_starts[i] or accent_ends[i]:
            assert in_accent_phrase

        if accent_phrase_ends[i]:
            in_accent_phrase = False

    # 最後はアクセント句終了
    assert expected_is_start

    # アクセント句開始と終了の数は一緒
    a = sum(
        accent_phrase_starts[i]
        for i in range(len(phones))
        if phones[i] in (vowel_list + other_list)
    )
    b = sum(
        accent_phrase_ends[i]
        for i in range(len(phones))
        if phones[i] in (vowel_list + other_list)
    )
    assert a == b


def main():
    phoneme_path = Path("rohan4600_phoneme.txt")
    modified_path = Path("rohan4600_memo.txt")

    accent_starts_path = Path("rohan4600_accent_starts.txt")
    accent_ends_path = Path("rohan4600_accent_ends.txt")
    accent_phrase_starts_path = Path("rohan4600_accent_phrase_starts.txt")
    accent_phrase_ends_path = Path("rohan4600_accent_phrase_ends.txt")

    phone_text_list = phoneme_path.read_text().splitlines()
    yomis = modified_path.read_text().splitlines()[1::3]

    accent_start_text = ""
    accent_end_text = ""
    accent_phrase_start_text = ""
    accent_phrase_end_text = ""

    # phone_text_list = phone_text_list[:10]
    # yomis = yomis[:10]
    for phone_text, yomi in zip(phone_text_list, yomis):
        print(yomi)

        phones = (
            ["sil"]
            + modify_phonemes(yomi_to_phones(yomi), phone_text.split()[1:-1])
            + ["sil"]
        )
        assert phone_text.lower() == " ".join(phones).lower()

        (
            accent_starts,
            accent_ends,
            accent_phrase_starts,
            accent_phrase_ends,
        ) = yomi_to_accents(yomi)

        accent_starts = ["0"] + accent_starts + ["0"]
        accent_ends = ["0"] + accent_ends + ["0"]
        accent_phrase_starts = ["0"] + accent_phrase_starts + ["0"]
        accent_phrase_ends = ["0"] + accent_phrase_ends + ["0"]

        # print(phones)
        # print(accent_starts)
        # print(accent_ends)
        # print(accent_phrase_starts)
        # print(accent_phrase_ends)

        accent_check(
            phones=phones,
            accent_starts=[bool(int(a)) for a in accent_starts],
            accent_ends=[bool(int(a)) for a in accent_ends],
            accent_phrase_starts=[bool(int(a)) for a in accent_phrase_starts],
            accent_phrase_ends=[bool(int(a)) for a in accent_phrase_ends],
        )

        accent_start_text += " ".join(accent_starts) + "\n"
        accent_end_text += " ".join(accent_ends) + "\n"
        accent_phrase_start_text += " ".join(accent_phrase_starts) + "\n"
        accent_phrase_end_text += " ".join(accent_phrase_ends) + "\n"

    accent_starts_path.write_text(accent_start_text)
    accent_ends_path.write_text(accent_end_text)
    accent_phrase_starts_path.write_text(accent_phrase_start_text)
    accent_phrase_ends_path.write_text(accent_phrase_end_text)


if __name__ == "__main__":
    main()
