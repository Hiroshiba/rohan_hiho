# rohan_hiho

## 内容物

* rohan4600_phoneme_openjtalk.txt
    * OpenJTalk用音素列
    * phoneme.pyを実行して取得
* rohan4600_memo_openjtalk.txt
    * アクセント情報を手修正するためのテキストファイル
    * script/phoneme.pyを実行して取得したものを手修正
* rohan4600_accent_*_openjtalk.txt
    * [./rohan4600_memo_openjtalk.txt]のアクセント情報をonehotベクトルで使いやすいように加工したテキストファイル
    * script/accent_post.pyを実行して取得

## 謝辞

- [ROHAN4600：モーラバランス型日本語コーパス](https://github.com/mmorise/rohan4600)

## ライセンス

* rohan4600_*.txtファイル　･･･　CC0 1.0 Universal（元データのライセンスを継承）
* それ以外　･･･　[MIT LICENSE](./MIT_LICENSE)
