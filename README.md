# Letterbox Overlay

활성 창 외 영역을 검정으로 채우는 Windows용 오버레이 프로그램.

## 사용법

1. `letterbox.exe` 실행
2. 시스템 트레이에 아이콘 표시
3. 대상 창에 포커스 후 `Ctrl+Alt+D`로 활성화
4. 다시 `Ctrl+Alt+D`로 비활성화

## 동작

- 활성화하면 대상 창이 있는 모니터 전체를 검정 오버레이로 덮음
- 대상 창은 오버레이 위에 표시
- 대상 창이 포커스를 잃으면 오버레이 자동 숨김, 다시 포커스 받으면 복원
- 대상 창이 닫히면 자동 비활성화

## 트레이 아이콘

- 아이콘 색상으로 활성/비활성 상태 확인
- 마우스 올리면 대상 창 이름과 키 바인딩 표시
- 우클릭 메뉴에서 종료

## 기술 스택

- Python + ctypes (Win32 API 직접 호출)
- 외부 의존성 없음

## 빌드

```
python -m PyInstaller --onefile --noconsole --icon=activated.ico --add-data "activated.ico;." --add-data "deactivated.ico;." --name letterbox letterbox.py
```
