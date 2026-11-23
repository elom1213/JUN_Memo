# JUN_Memo

Windows 10 · 11 의 **스티커 메모(Sticky Notes)** 처럼 쓰는 독립 실행 메모 앱 (PySide6).
노트 하나하나가 **바탕화면에 붙는 작은 색 창**이고, 노트 목록에서 골라 다시 연다.

![preview](icon/JUN_Memo.png)

- **버전**: `app/config/version.py` (v01.01 — 목록 창 색 · Pin, 공유(GitHub) / 이 PC 노트, 시작 메뉴 · 작업 표시줄) · 변경 기록 [`CHANGELOG.md`](CHANGELOG.md)
- **필요한 것**: Python 3.9+ · `pip install -r requirements.txt` (PySide6)
- **실행**: `Run_JUN_Memo.bat` 더블클릭(콘솔 창 없이) 또는 `pythonw launch.py`

---

## 1. 화면

```
 노트 목록                                  노트 (스티커)
┌───────────────────────────┐            ┌─────────────────────────────┐
│ Sticky Notes  [+][Pin][…] │            │ +                Pin  …  ✕  │ ← 색 띠: 잡고 끌면 이동
│ [Search...              ] │            │ Today                       │
│ ┌───────────────────────┐ │  클릭 →    │  • Rig review 2pm           │
│ │              10:25    │ │            │  • Fix A00630 hover         │
│ │ Today                 │ │            │ Buy coffee beans            │
│ │ Rig review 2pm        │ │            │                             │
│ └───────────────────────┘ │            │ B  I  U  S  •            ◢ │ ← 서식 · 크기 손잡이
│ 3 note(s)                 │            └─────────────────────────────┘
└───────────────────────────┘
```

### 노트 목록
- **`+`** (Ctrl+N) — 새 노트. 기본 색은 스티커 메모와 같은 **노랑**. 필터가 `Shared` 면 공유 노트로 만든다.
- **`Pin`** — 목록 창을 늘 맨 위에(켜지면 `Pinned` · 연한 빨강).
- **`…`** — 목록 창 **색**(7색 견본 · `Custom list color...`) · `Reload shared notes` · **`Add to Start Menu`** · `Pin to Taskbar` (4장).
  목록 창은 모든 부분(배경 · 글자 · 검색칸)을 고른 색으로 칠한다 — 윈도우 다크 모드에서도 글자가 보인다. 색 · Pin · 자리는 기억.
- **All / Shared / This PC** — 범위로 거르기(3장). 카드 왼쪽 위에 범위 표시.
- **Search** — 적은 낱말이 **모두** 들어 있는 노트만(대소문자 무시).
- 카드 = 노트의 색 · 앞부분 3줄 · 마지막으로 고친 시각(오늘이면 시:분), 📌 = Pin.
- **카드를 클릭하면 그 노트가 스티커 창으로 열린다.** 이미 열려 있으면 앞으로 나온다.
- 우클릭 — Open · Color(7색) · Delete.
- 최근에 고친 노트가 위.

### 노트 (스티커 창)
| 자리 | 동작 |
|------|------|
| 위쪽 색 띠 | 잡고 끌면 창이 움직인다 |
| `+` (Ctrl+N) | 이 노트 옆(오른쪽 아래로 조금)에 새 노트 |
| **`Pin`** | **늘 다른 창 위에**. 켜지면 `Pinned` · 연한 빨강. 다시 누르면 해제 |
| `…` | **색 견본 7개**(Yellow · Green · Pink · Purple · Blue · Gray · Charcoal) · `Custom color...`(아무 색) · **`Shared (GitHub)`** 켜고 끄기 · Notes list · Delete note |
| 띠 왼쪽 `Shared` / `This PC` | 이 노트의 범위 (3장) |
| `✕` | 닫기 — 노트는 목록에 남는다. **빈 노트는 닫을 때 지운다** |
| 아래 `B I U S •` | 굵게 (Ctrl+B) · 기울임 (Ctrl+I) · 밑줄 (Ctrl+U) · 취소선 (Ctrl+T) · 글머리표 (Ctrl+Shift+L, 다시 누르면 해제) |
| 오른쪽 아래 ◢ | 끌어서 크기 |

- 붙여 넣기는 **글자만** 들어온다 — 웹 · 워드에서 복사한 배경색 · 큰 글꼴이 색 노트를 깨지 않게.
- 사용자 색: 띠는 조금 어둡게, 글자는 바탕 밝기에 따라 검정 / 흰색이 저절로 정해진다.

## 2. 저장

- 이 PC 노트 · 공유 노트가 따로 저장된다 — 3장.
- **자동 저장** — 글을 칠 때마다가 아니라 멈추고 0.5초 뒤, 그리고 노트를 닫을 때 · 앱을 끌 때 바로.
- 파일: **`%APPDATA%\JUN_Memo\notes.json`**(이 PC 노트의 내용 · 색 · 만든 / 고친 시각) + **`state.json`**(모든 노트의 열림 · 창 자리 · 크기 · Pin, 목록 창 색 · Pin · 자리).
  쓰기는 임시 파일 → 한 번에 바꾸기라 쓰다 꺼져도 깨지지 않고, 직전 파일을 `notes.json.bak` 으로 하나 남긴다(깨졌으면 그것을 읽는다).
- **다시 켜면 열려 있던 노트가 그 자리 · 크기 · 색 · Pin 그대로 다시 열린다.** 저장된 자리가 지금 어느 화면에도 없으면(모니터를 뺐을 때) 주 화면으로.
- **한 번만 실행** — 이미 떠 있을 때 다시 실행하면 새로 뜨지 않고, 떠 있는 앱의 노트 목록이 앞으로 나온다.
- 모든 창(목록 · 노트)을 닫으면 앱이 끝난다.

## 3. 공유 노트 (GitHub) / 이 PC 노트 (v01.01)

| 범위 | 내용이 있는 곳 | 누가 본다 |
|------|----------------|-----------|
| **Shared** | 저장소 안 **`shared/notes/<id>.json`** (노트 하나 = 파일 하나) | git 으로 올리고 받은 모든 PC |
| **This PC** | `%APPDATA%\JUN_Memo\notes.json` | 이 컴퓨터만 |

- 노트 `…` > `Shared (GitHub)` 로 바꾼다(파일이 옮겨진다). 목록 카드와 노트 띠에 표시.
- **창 자리 · 크기 · 열림 · Pin 은 공유하지 않는다** — PC 마다 화면이 달라서 `%APPDATA%\JUN_Memo\state.json` 에 둔다.
  그래서 창을 옮기거나 Pin 해도 공유 파일은 바뀌지 않는다(git 에 쓸데없는 변경이 안 생긴다). 공유 파일 = 내용 · 색 · 만든 / 고친 시각.
- 노트마다 파일이 따로라 **두 PC 가 다른 노트를 고치면 git 충돌이 없다.** 같은 노트를 두 곳에서 고쳤을 때만 충돌한다.
- 올리기 / 받기는 git 으로 한다 (앱이 git 을 직접 부르지는 않는다):
  ```
  cd JUN_Memo
  git pull                      # 다른 PC 의 공유 노트 받기 → 앱의 … > Reload shared notes
  git add shared && git commit -m "notes" && git push
  ```
- `Reload shared notes` 는 열어 둔 공유 노트는 손대지 않는다(고치는 중인 글이 바뀌지 않게) — 닫고 다시 읽으면 바뀐다.
- **주의**: 공유 노트는 GitHub 저장소에 그대로 올라간다. 저장소가 공개면 누구나 본다 — 개인적인 것은 This PC 로.

## 4. 시작 메뉴 · 작업 표시줄 (v01.01)

목록 창 `…` 메뉴 (`0110_JUN_Video_Tool` 과 같은 방식):

- **`Add to Start Menu`** — 시작 메뉴 `모든 앱` 에 **JUN Memo** 바로가기를 만들고(pythonw 로 실행 = 콘솔 창 없음, 아이콘 · 앱 ID 포함) 시작 화면 고정을 시도한다.
  고정이 안 보이면 시작 > 모든 앱 > JUN Memo 우클릭 > `시작 화면에 고정`. **폴더를 옮겼으면 다시 누른다**(경로 갱신).
- **`Pin to Taskbar`** — 고정을 시도하고, Windows 10 1809+ / 11 처럼 프로그램이 스스로 고정하는 것을 막는 곳이면
  "작업 표시줄의 JUN Memo 버튼 우클릭 → 작업 표시줄에 고정" 을 안내한다. 그 버튼은 python 이 아니라 JUN Memo 를 실행한다.

## 5. 구조

```
JUN_Memo/
├── launch.py              # 실행 · 한 번만 실행(QLocalServer) · 작업 표시줄 아이콘(AppUserModelID) · 아이콘 그리기
├── Run_JUN_Memo.bat       # pythonw 로 실행
├── app/config/version.py
├── app/core/store.py      # 노트 저장소(이 PC + 공유) · 색 팔레트 · 미리보기 (Qt 비의존)
├── app/core/shell_integration.py  # 시작 메뉴 바로가기 · 고정 · 창 재실행 정보 (Video Tool 에서 옮김)
├── app/ui/note_window.py  # 스티커 창
├── app/ui/list_window.py  # 노트 목록 창
├── app/ui/controller.py   # 목록 · 노트 창 · 저장 잇기 (자동 저장, 빈 노트 지우기, 다시 열기)
├── icon/JUN_Memo.ico · .png
├── shared/notes/          # 공유 노트 (<id>.json, git 으로 올라간다)
└── tests/test_memo.py · test_scope_list.py   # 오프스크린 시험
```

## 6. 시험

`python tests/test_memo.py` · `python tests/test_scope_list.py` — **44 + 30항목**. 공유 폴더는 시험 동안 임시 폴더(`JUN_MEMO_SHARED`). test_memo(오프스크린 PySide6): 저장소(내용 · 순서 · 검색 · 저장/다시 읽기 · 깨진 파일 → 백업 · 팔레트),
노트 창(자리 · 색 · Pin 플래그 · 굵게 · 글머리표 켜고 끄기 · 붙여 넣기 글자만), 앱 흐름(새 노트 · 자동 저장 · 빈 노트 지움 · 닫아도 목록에 남음 ·
목록 클릭 = 그대로 다시 열기 · 검색 · 색 바꾸기 · 다시 켜면 다시 열림 · 화면 밖 자리 → 주 화면 · 삭제), 한 번만 실행.

**실제 화면 확인은 아직** — 창 끌기 · 크기 손잡이 · Pin 이 다른 앱 위에 남는지 · 작업 표시줄 아이콘.

## 7. 원본과의 관계

Microsoft 스티커 메모의 **쓰임새(색 · 목록 · 붙는 창)** 를 따라 새로 만든 것이다 — 그 앱의 코드 · 그림은 쓰지 않았다.
색 값은 스티커 메모의 7색에 가깝게 골랐다.
