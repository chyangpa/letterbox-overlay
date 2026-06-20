# Letterbox Overlay

보더리스 창모드에서 모니터보다 낮은 해상도로 게임을 실행할 때 남는 영역을 검정으로 채워주는 프로그램.

순수 오버레이 방식이라 입력 지연이 없습니다.

## 사용법

1. `letterbox.exe` 실행 (시스템 트레이에 상주)
2. 대상 창에 포커스 → `Ctrl+Alt+D`로 활성화
3. 다시 `Ctrl+Alt+D`로 비활성화

## 동작

- 대상 창이 있는 모니터 전체를 검정 오버레이로 덮고, 대상 창만 그 위에 표시
- 대상 창이 포커스를 잃으면 오버레이 자동 숨김, 다시 받으면 복원
- 대상 창이 닫히면 자동 비활성화

## 빌드

```
python -m PyInstaller --onefile --noconsole --uac-admin --icon=activated.ico --add-data "activated.ico;." --add-data "deactivated.ico;." --name letterbox letterbox.py
```

`--uac-admin` 옵션은 exe에 "관리자 권한 요구" 매니페스트를 심어, 어떤 방식으로 실행하든 항상 관리자 권한으로 뜨게 합니다. 코드 자체에도 self-elevation이 있어 매니페스트 없이도 시작 시 권한이 없으면 UAC로 승격 재실행합니다.

## 자동 실행 / 관리자 권한

- **작업 스케줄러로 자동 실행 시**: 작업 속성 → 일반 탭에서 **"가장 높은 수준의 권한으로 실행"** 체크. 이래야 로그온 시 UAC 프롬프트 없이 관리자 권한으로 실행됩니다.
- **시작 메뉴 검색에 등록**: `letterbox.exe` 바로가기를 `%APPDATA%\Microsoft\Windows\Start Menu\Programs` 폴더에 넣으면 검색에 노출됩니다.
