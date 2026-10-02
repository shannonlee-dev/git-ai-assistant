# AI Git 도구 사용법과 출력 계약

## 변경 수집

도구 실행 시 현재 디렉토리의 Git 루트를 찾습니다. 스테이징 상태를 확인하고 필요한 변경을 먼저 스테이징합니다.

```bash
git status --short
git diff --cached
uv run --frozen git-ai commit --dry-run --safe-mode
uv run --frozen git-ai pr --dry-run --safe-mode
```

다른 저장소에서 사용하려면 먼저 `uv tool install /절대/경로/git-ai-assistant`로 설치한 뒤 대상 저장소에서 `git-ai`를 실행합니다. `.ai-gitgen.yml`은 대상 저장소의 파일을 우선 사용하고 없으면 도구의 기본 설정을 사용합니다. `--config`로 직접 지정할 수도 있습니다.

## 실제 생성

```bash
uv run --frozen git-ai commit --temperature 0.2 --max-tokens 700 --safe-mode
uv run --frozen git-ai pr --temperature 0.2 --max-tokens 900 --safe-mode
```

`--model`, `--api-base-url`로 공급자 설정을 재정의합니다. 인증 키는 환경 변수 `AI_API_KEY`에서 읽습니다. 호출 결과는 터미널에 출력하며 적용 작업은 사용자가 수행합니다.

## 안전 모드

기본적으로 켜져 있습니다. `--max-files`는 diff 파일 수와 파일 목록·Git status의 각 행 수를 제한하고, `--max-diff-lines`는 diff 행 수를 제한합니다. 기본값은 각각 10과 200이며 세 입력 모두 패턴 마스킹을 적용합니다. 프롬프트의 고정 설명과 팀 규칙은 이 Git 입력 행 제한에 포함하지 않습니다. `--no-safe-mode`는 마스킹과 크기 제한을 해제하므로 요청 내용을 확인한 후 사용합니다. 마스킹 결과만으로 비밀정보가 모두 제거되었다고 판단하지 않습니다.

## 출력 형식

커밋 제목은 한 줄이며 기본 설정의 최대 길이는 100자입니다. PR 제목은 기본 최대 80자이며 본문에 설정한 `What`, `Why`, `How` 섹션과 각각 하나 이상의 불릿이 필요합니다. 섹션명·검증 규칙은 `.ai-gitgen.yml`과 구현의 계약을 유지합니다.

```bash
uv run --frozen git-ai validate-output < .runtime/sample-output.txt
```

입력 파일에는 생성기의 출력 구분자를 포함한 원문을 저장합니다. 형식을 검증하는 명령이며 실제 변경의 적절성을 평가하는 코드 리뷰를 대신하지 않습니다.

## 오류와 로컬 검증

설정·Git 사용 오류와 API 실패는 종료 코드로 구분합니다. `make smoke`는 `mock://` 응답과 임시 Git 저장소를 사용해 실제 API 비용 없이 실행합니다.
