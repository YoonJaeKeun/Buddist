# 경전 전문 한자음 대조본

CBETA 대정신수대장경의 기본 본문 전체를 권별로 나누고, 각 한자 바로 아래에 한국 한자음을 배치한 대조본이다.

## 읽는 방법

각 표의 첫째 줄은 원문이고 셋째 줄은 같은 열의 한자를 읽는 한글 음이다. 문장부호에는 독음이 없으므로 아래 칸이 비어 있다.

## 수록 범위

| 경전 | 대장경 번호 | 권수 | 한자 수 | 바로가기 |
|---|---:|---:|---:|---|
| 금강반야바라밀경 | T0235 | 1 | 5,191 | [금강경](./금강경/README.md) |
| 반야바라밀다심경 | T0251 | 1 | 1,097 | [반야심경](./반야심경/README.md) |
| 유마힐소설경 | T0475 | 3 | 27,229 | [유마경](./유마경/README.md) |
| 불설무량수경 | T0360 | 2 | 17,423 | [무량수경](./무량수경/README.md) |
| 불설관무량수불경 | T0365 | 1 | 7,967 | [관무량수경](./관무량수경/README.md) |
| 불설아미타경 | T0366 | 1 | 2,107 | [아미타경](./아미타경/README.md) |
| 묘법연화경 | T0262 | 7 | 71,841 | [법화경](./법화경/README.md) |
| 대방광불화엄경 | T0279 | 80 | 593,039 | [화엄경](./화엄경/README.md) |

## 본문 범위 원칙

- 경전 본문, 권 제목, 번역자 표시, 품 제목, 게송, 다라니를 포함한다.
- CBETA 기본 본문에서 채택한 글자(교감 장치의 `lem`)를 사용한다.
- 교감 각주, 다른 판본의 이문, 대정장 페이지·행 번호, 편집자 발음 주는 본문이 아니므로 대조표에서 제외한다.
- 희귀 글자는 CBETA 외자 데이터베이스의 유니코드 글자 또는 통용자로 복원한다.
- 한자음은 CC0 한자음 데이터에 불교 관용 독음 보정표를 적용했다. 다라니·음역어·고유명사는 전통과 판본에 따라 다르게 읽을 수 있다.

## 출처와 재생성

- [CBETA XML P5a](https://github.com/cbeta-git/xml-p5a)
- [CBETA 외자 데이터](https://github.com/cbeta-org/cbeta_gaiji)
- [한자-한글 데이터(CC0)](https://github.com/masoris/hanja_hangul) · [라이선스](https://github.com/masoris/hanja_hangul/blob/main/LICENSE)
- [번체자 단어 분리 사전](https://github.com/ldkrsi/jieba-zh_TW) · [MIT 라이선스](https://github.com/ldkrsi/jieba-zh_TW/blob/master/LICENSE)
- 생성 명령: `python3 scripts/generate_full_sutra_readings.py`
- 원문 및 추출 결과의 SHA-256과 문자 수는 [`manifest.json`](./manifest.json)에 기록한다.
