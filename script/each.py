"""
台本とラベルファイルで音素が違うものを検出して人力で修正する。
FIXME: つもりだったけど、ラベルファイル側の誤りが多いため、ほとんどのものを無視する。
"""

import argparse
from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import List

from acoustic_feature_extractor.data.phoneme import OjtPhoneme
from tqdm import tqdm


@dataclass
class PhonemeInfo:
    phoneme: str
    accent_start: str
    accent_end: str
    accent_phrase_start: str
    accent_phrase_end: str


def copy_phoneme_info(phoneme_info: PhonemeInfo, phoneme: str):
    return PhonemeInfo(
        phoneme,
        phoneme_info.accent_start,
        phoneme_info.accent_end,
        phoneme_info.accent_phrase_start,
        phoneme_info.accent_phrase_end,
    )


def _load_split(file_name: str):
    return [
        s.strip().split()
        for s in Path(f"{file_name}.txt").read_text().strip().splitlines()
    ]


def _create_phoneme_infos(name: str):
    return [
        [
            PhonemeInfo(
                phoneme,
                accent_start,
                accent_end,
                accent_phrase_start,
                accent_phrase_end,
            )
            for (
                phoneme,
                accent_start,
                accent_end,
                accent_phrase_start,
                accent_phrase_end,
            ) in zip(*info_lists)
        ]
        for info_lists in zip(
            _load_split(f"{name}_phonemes"),
            _load_split(f"{name}_accent_starts"),
            _load_split(f"{name}_accent_ends"),
            _load_split(f"{name}_accent_phrase_starts"),
            _load_split(f"{name}_accent_phrase_ends"),
        )
    ]


def process(labs_path: Path, base_phoneme_info_list: List[PhonemeInfo], force: bool):
    labs = OjtPhoneme.load_julius_list(labs_path)
    labs[0].phoneme = labs[-1].phoneme = "sil"

    base_phoneme_list = [
        phoneme_info.phoneme for phoneme_info in base_phoneme_info_list
    ]
    each_phoneme_list = [lab.phoneme for lab in labs]

    # 有声・無声を無視
    base_phoneme_list = [
        p if p not in ["A", "I", "U", "E", "O"] else p.lower()
        for p in base_phoneme_list
    ]
    each_phoneme_list = [
        p if p not in ["A", "I", "U", "E", "O"] else p.lower()
        for p in each_phoneme_list
    ]

    each_phoneme_info_list: List[PhonemeInfo] = []

    unexpcted = False

    for tag, i1, i2, j1, j2 in SequenceMatcher(
        None, base_phoneme_list, each_phoneme_list
    ).get_opcodes():
        bp = base_phoneme_list[i1:i2]
        ep = each_phoneme_list[j1:j2]

        if tag == "equal":
            each_phoneme_info_list += base_phoneme_info_list[i1:i2]

        # いう→ゆう
        elif (
            tag == "replace"
            and i2 - i1 == 1
            and j2 - j1 == 2
            and bp == ["i"]
            and ep == ["y", "u"]
            and base_phoneme_list[i2] == "u"
            and each_phoneme_list[j2] == "u"
        ):
            each_phoneme_info_list += [
                copy_phoneme_info(base_phoneme_info_list[i1], ep[0]),
                copy_phoneme_info(base_phoneme_info_list[i1], ep[1]),
            ]

        # 無音が消された
        elif tag == "delete" and i2 - i1 == 1 and bp == ["pau"]:
            pass

        # 無音が足された
        elif tag == "insert" and j2 - j1 == 1 and ep == ["pau"]:
            each_phoneme_info_list += [PhonemeInfo("pau", "0", "0", "0", "0")]

        # 一文字だけ違う
        elif tag == "replace" and i2 - i1 == 1 and j2 - j1 == 1:
            each_phoneme_info_list += [
                copy_phoneme_info(base_phoneme_info_list[i1], ep[0])
            ]

            unexpcted = True

        # 予期せず消された
        elif tag == "delete":
            if not force:
                phoneme_info_lists = deepcopy(base_phoneme_info_list[i1:i2])
                for phoneme_info_list in phoneme_info_lists:
                    phoneme_info_list.phoneme = "?"
                each_phoneme_info_list += phoneme_info_lists

            unexpcted = True

        # 予期せず足された
        elif tag == "insert":
            if not force:
                each_phoneme_info_list += [
                    PhonemeInfo(p, "?", "?", "?", "?") for p in ep
                ]
            else:
                each_phoneme_info_list += [
                    copy_phoneme_info(base_phoneme_info_list[i1], p) for p in ep
                ]

            unexpcted = True

        # 予期せず違った
        elif tag == "replace":
            if not force:
                each_phoneme_info_list += [
                    PhonemeInfo(p, "?", "?", "?", "?") for p in ep
                ]
            else:
                each_phoneme_info_list += [
                    copy_phoneme_info(base_phoneme_info_list[i1], p) for p in ep
                ]

            unexpcted = True

        else:
            raise ValueError(f"{tag}, {bp}, {ep}")

    return each_phoneme_info_list, unexpcted


def phoneme_info_list_memo(name: str, stem: str, phoneme_info_list: List[PhonemeInfo]):
    memo_text = ""
    memo_text += name + " " + stem + "\n"
    memo_text += "\t".join([pi.phoneme for pi in phoneme_info_list]) + "\n"
    memo_text += "\t".join([pi.accent_start for pi in phoneme_info_list]) + "\n"
    memo_text += "\t".join([pi.accent_end for pi in phoneme_info_list]) + "\n"
    memo_text += "\t".join([pi.accent_phrase_start for pi in phoneme_info_list]) + "\n"
    memo_text += "\t".join([pi.accent_phrase_end for pi in phoneme_info_list]) + "\n"
    return memo_text


def each(root_dir: Path, memo_path: Path, force: bool):
    rohan4600_phoneme_info_lists = _create_phoneme_infos("rohan4600")

    memo_dict = {}
    if memo_path.exists():
        memo_lines = memo_path.read_text().strip().splitlines()
        memo_dict = {
            tuple(name_and_stem.split()): [
                PhonemeInfo(*infos)
                for infos in zip(*[info_text.split() for info_text in info_texts])
            ]
            for name_and_stem, *info_texts in zip(
                memo_lines[0::6],
                memo_lines[1::6],
                memo_lines[2::6],
                memo_lines[3::6],
                memo_lines[4::6],
                memo_lines[5::6],
            )
        }

    memo_text = ""
    for speaker, style in [["zundamon", "normal"]]:
        target = f"{speaker}-{style}"
        print(target)

        (Path(target) / "phoneme").mkdir(exist_ok=True, parents=True)
        (Path(target) / "accent_start").mkdir(exist_ok=True, parents=True)
        (Path(target) / "accent_end").mkdir(exist_ok=True, parents=True)
        (Path(target) / "accent_phrase_start").mkdir(exist_ok=True, parents=True)
        (Path(target) / "accent_phrase_end").mkdir(exist_ok=True, parents=True)

        phoneme_info_lists = rohan4600_phoneme_info_lists
        labs_paths = sorted((root_dir / speaker / target / "label").glob("*.lab"))

        assert len(phoneme_info_lists) == len(labs_paths)

        for phoneme_info_list, labs_path in tqdm(zip(phoneme_info_lists, labs_paths)):
            stem = labs_path.stem

            # メモに存在
            if (target, stem) in memo_dict:
                each_phoneme_info_list = memo_dict[(target, stem)]
                unexpcted = False

                each_phoneme_info_list_before, _ = process(
                    labs_path=labs_path,
                    base_phoneme_info_list=phoneme_info_list,
                    force=True,
                )

                assert [pi.phoneme for pi in each_phoneme_info_list] == [
                    pi.phoneme for pi in each_phoneme_info_list_before
                ], (
                    stem,
                    [pi.phoneme for pi in each_phoneme_info_list],
                    [pi.phoneme for pi in each_phoneme_info_list_before],
                )

            # メモにないとき
            else:
                each_phoneme_info_list, unexpcted = process(
                    labs_path=labs_path,
                    base_phoneme_info_list=phoneme_info_list,
                    force=force,
                )

            # メモに追加
            if unexpcted:
                memo_text += phoneme_info_list_memo(
                    name=target, stem=stem, phoneme_info_list=each_phoneme_info_list
                )

            # 書き出し
            else:
                path = Path(target) / "phoneme" / f"{stem}.txt"
                path.write_text(" ".join([pi.phoneme for pi in each_phoneme_info_list]))

                path = Path(target) / "accent_start" / f"{stem}.txt"
                path.write_text(
                    " ".join([pi.accent_start for pi in each_phoneme_info_list])
                )

                path = Path(target) / "accent_end" / f"{stem}.txt"
                path.write_text(
                    " ".join([pi.accent_end for pi in each_phoneme_info_list])
                )

                path = Path(target) / "accent_phrase_start" / f"{stem}.txt"
                path.write_text(
                    " ".join([pi.accent_phrase_start for pi in each_phoneme_info_list])
                )

                path = Path(target) / "accent_phrase_end" / f"{stem}.txt"
                path.write_text(
                    " ".join([pi.accent_phrase_end for pi in each_phoneme_info_list])
                )

    if len(memo_text) > 0:
        memo_path.write_text(memo_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", type=Path)
    parser.add_argument("--memo_path", type=Path, default=Path("each_memo.txt"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    each(**vars(args))
