# -*- coding: utf-8 -*-
# JUN_Memo - 버전 기록
# 01.00  첫 버전 (2026-11-23) - 윈도우 스티커 메모 같은 독립 실행 PySide6 앱. 노트 목록(검색 · 클릭하면 노트 창) +
#        스티커 노트 창(테두리 없는 색 창, 위쪽 띠로 이동, 서식 B/I/U/S/글머리표, 오른쪽 아래로 크기).
#        색 = 스티커 메모 7색(기본 노랑) + 사용자 색, Pin = 늘 맨 위. %APPDATA%/JUN_Memo/notes.json 자동 저장,
#        다시 켜면 열려 있던 노트를 그 자리에, 빈 노트는 닫을 때 지움, 한 번만 실행(두 번째 실행 = 목록 창을 앞으로).

# 01.01  (2026-11-23) 노트 목록 창 색(노트와 같은 7색 + 사용자 색) - 창의 모든 부분을 그 팔레트로 칠한다(윈도우 다크 모드에서
#        흰 글자 + 밝은 배경으로 안 보이던 것) · 목록 창 Pin · 노트 범위 Shared(GitHub, 저장소 shared/notes/<id>.json) /
#        This PC(%APPDATA%) - 공유 파일엔 내용만, 창 자리 · Pin · 열림은 이 PC 의 state.json · Reload shared notes ·
#        시작 메뉴 추가 · 작업 표시줄 고정(0110_JUN_Video_Tool 의 shell_integration 을 옮겨 맞춤). v01.00 notes.json 이어 읽기.

# 01.02  (2026-11-23) 목록 창의 All / Shared / This PC 라디오 버튼이 안 보이던 것 - 창을 통째로 칠하며 다크 모드 스타일의
#        동그라미가 묻혔다. 동그라미를 직접 그린다: 안 고름 = 빈 원, 고름 = 원 안의 점 + 굵은 글자, 창 색을 따른다.

VERSION = "01.02"
APP_NAME = "JUN Memo"
APP_USER_MODEL_ID = "JUN.Memo"
LAST_UPDATE = "2026-11-23"
