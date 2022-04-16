import multiprocessing
import re
import urllib.request
from difflib import SequenceMatcher, ndiff
from pathlib import Path
from typing import Union

from julius4seg.sp_inserter import kata2hira
from openjtalk_label_getter import FullContextLabel, OutputType, openjtalk_label_getter
from tqdm import tqdm

from data import mora2yomi, moraend_list, pause_list, yomi2mora


def get_text(line: str):
    string = line.strip().split(":")[1].split(",")[0]
    return re.sub(r"\(.*?\)", "", string)


def get_yomi(line: str):
    katakana = line.strip().split(",")[1]
    return kata2hira(katakana)


def text2phoneme(text: str):
    text = text.replace("づ", "ず").replace("ぢ", "じ").replace("を", "お").replace("ゔ", "う゛")
    text = text.replace("ふゅ", "ひゅ").replace("しぃ", "しい")
    for yomi, (consonant, vowel) in yomi2mora.items():
        text = text.replace(yomi, f"{consonant} {vowel} ")

    # 伸ばし棒
    text = text.replace("ー", "ー ")
    text = " ".join(
        phoneme if phoneme != "ー" else text.split()[i - 1]
        for i, phoneme in enumerate(text.split())
    )
    return text.strip()


def decide(jul_phones: list[str], ojt_labels: list[FullContextLabel], verbose=False):
    ojt_phones = [l.phoneme for l in ojt_labels]

    labels: list[Union[FullContextLabel, str]] = []  # FullContextLabelが無かった場合は音素だけが入る
    for tag, s1, e1, s2, e2 in SequenceMatcher(
        None, jul_phones, ojt_phones
    ).get_opcodes():
        if tag == "equal":
            labels += ojt_labels[s2:e2]
            continue

        # print(tag, jul_phones[s1:e1], ojt_phones[s2:e2])

        i1, i2 = s1, s2
        while i1 < e1 or i2 < e2:
            p1 = jul_phones[i1] if i1 < len(jul_phones) else None
            p2 = ojt_phones[i2] if i2 < len(ojt_phones) else None
            l2 = ojt_labels[i2] if i2 < len(ojt_labels) else None

            pp1 = jul_phones[i1 - 1 : i1 + 1] if i1 > 0 else None
            pp2 = ojt_phones[i2 - 1 : i2 + 1] if i2 > 0 else None

            np1 = jul_phones[i1 : i1 + 2] if i1 < len(jul_phones) - 1 else None
            np2 = ojt_phones[i2 : i2 + 2] if i2 < len(ojt_phones) - 1 else None

            inc1 = inc2 = 1

            if i1 == e1:
                inc1 = 0
                inc2 = e2 - i2

            elif p1 == p2:
                labels += [l2]

            elif p2 == "pau":
                inc1 = 0

            elif (p1 == "i" and p2 == "I") or (p1 == "u" and p2 == "U"):
                labels += [l2]

            elif (pp1 == ["o", "u"] and pp2 == ["o", "o"]) or (
                pp1 == ["e", "i"] and pp2 == ["e", "e"]
            ):
                labels += [l2]

            elif np1 == ["j", "i"] and np2 == ["d", "i"]:
                labels += [l2]

            elif np1 == ["j", "u"] and np2 == ["d", "u"]:
                labels += [l2]

            elif np1 == ["ch", "i"] and np2 == ["t", "i"]:
                labels += [l2]

            else:
                labels += list(jul_phones[i1:e1])
                inc1 = e1 - i1
                inc2 = e2 - i2

                if verbose:
                    print(list(ndiff(jul_phones[i1:], ojt_phones[i2:])))

            i1 += inc1
            i2 += inc2

    return labels


def alignment(args: tuple[str, str], verbose=False):
    text, yomi = args

    yomi = (
        yomi.replace("？", "、")
        .replace("。", "、")
        .replace("、、", "、")
        .strip("、")
        .replace("、", " sp ")
    )

    jul_phones = text2phoneme(yomi).replace("q", "cl").replace("sp", "pau").split()
    ojt_labels = [
        label.label
        for label in openjtalk_label_getter(
            text, output_type=OutputType.full_context_label
        )[1:-1]
    ]

    labels = decide(jul_phones=jul_phones, ojt_labels=ojt_labels, verbose=verbose)
    # breakpoint()
    assert len(labels) == len(jul_phones), args

    if verbose:
        print(" ".join(map(label_to_phone, labels)))
        # print("\n".join([str(label) for label in labels]))
        print("------------------------")

    return ["sil"] + labels + ["sil"]


def label_to_phone(label: Union[FullContextLabel, str]):
    if isinstance(label, str):
        return label
    return label.phoneme


# アクセント情報が書かれた読みを返す
def make_memo(labels: list[Union[FullContextLabel, str]]):
    memo = ""

    for label in labels:
        phone = label_to_phone(label)

        if phone in pause_list:
            memo += "|" + phone + "|"
            continue

        if phone in ["A", "I", "U", "E", "O"]:
            phone = phone.lower()

        if not isinstance(label, FullContextLabel):
            memo += phone + "?"
            continue

        a1, a3 = (label.contexts["a1"], label.contexts["a3"])

        # if a2 == "1":
        #     memo += "|"

        memo += phone

        if a1 == "0" and phone in moraend_list:
            memo += "'"

        if a3 == "1" and phone in moraend_list:
            memo += "|"

    memo = re.sub(r"\|+", "|", memo)
    memo = re.sub(r"^\|", "", memo)
    memo = re.sub(r"\|$", "", memo)

    old_memo = memo
    memos = []
    for m in old_memo.split("|"):
        if "?" in m:
            m = m.replace("?", "")
            m += "?"
        memos += [m]
    memo = "|".join(memos)

    for mora, yomi in mora2yomi.items():
        memo = memo.replace(mora, yomi)

    # print(memo)
    return memo


def main():
    rohan_url = "https://raw.githubusercontent.com/mmorise/rohan4600/main/Rohan4600_transcript_utf8.txt"
    with urllib.request.urlopen(rohan_url) as response:
        rohan_string: str = response.read().decode()

    output_phoneme_path = Path("rohan4600_phoneme_openjtalk.txt")
    output_memo_path = Path("rohan4600_memo_openjtalk.txt")

    texts: list[str] = list(map(get_text, rohan_string.splitlines()))
    yomis: list[str] = list(map(get_yomi, rohan_string.splitlines()))

    # texts = texts[:20]
    # yomis = yomis[:20]
    # labels_list = [
    #     alignment((text, yomi), verbose=True) for text, yomi in zip(texts, yomis)
    # ]

    with multiprocessing.Pool(processes=16) as pool:
        it = pool.imap(alignment, zip(texts, yomis), chunksize=32)
        labels_list = list(tqdm(it, total=len(texts)))

    output_phoneme_path.write_text(
        "\n".join(" ".join(map(label_to_phone, labels)) for labels in labels_list)
    )

    memo = ""
    for text, labels in zip(texts, labels_list):
        memo += text + "\n"
        memo += make_memo(labels[1:-1]) + "\n"
        memo += "\n"
    output_memo_path.write_text(memo)


if __name__ == "__main__":
    main()
