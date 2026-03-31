# Letterbox Overlay

보더리스 창모드에서 모니터보다 낮은 해상도로 게임을 실행할 때 남는 영역을 검정으로 채워주는 프로그램.

캡처가 아닌 순수 오버레이 방식이라 입력 지연이 없습니다.

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
python -m PyInstaller --onefile --noconsole --icon=activated.ico --add-data "activated.ico;." --add-data "deactivated.ico;." --name letterbox letterbox.py
```
