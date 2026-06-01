# AI Git Commit & PR Generator

Git 저장소의 `git status`와 `git diff`를 AI API에 전달해 커밋 메시지와 Pull Request 제목/본문 초안을 터미널에 출력하는 Python CLI 도구입니다. 생성 결과는 자동 적용되지 않으며, 사용자가 검토한 뒤 복사해 사용합니다.

## Requirements

- Python 3.10 이상
- Git CLI
- AI API Key 환경변수

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Environment

API Key는 코드에 저장하지 않고 환경변수로만 설정합니다.

```sh
export AI_API_KEY="<YOUR_API_KEY>"
```

기본 endpoint는 OpenAI 호환 Chat Completions 형식입니다. 다른 호환 서버나 테스트 서버를 사용할 때는 아래처럼 바꿀 수 있습니다.

```sh
export AI_API_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
```

## Usage

이 도구는 Git 프로젝트 루트에서 실행해야 합니다.

```sh
python main.py commit --model gemini-3.5-flash --temperature 0.2 --max-tokens 700 --safe-mode
```

```sh
python main.py pr --model gemini-3.5-flash --temperature 0.2 --max-tokens 900 --safe-mode
```

API 호출 없이 Git 수집과 safe-mode 적용 상태만 확인하려면 dry-run을 사용합니다.

```sh
python main.py commit --dry-run --safe-mode
```

## Output Examples

커밋 메시지 출력 예시:

```text
[INFO] Git status 수집 완료: 3개 파일 변경 감지
[INFO] Git diff 수집 완료: 128줄
[INFO] AI API 요청 중...
[INFO] AI API 호출 횟수: 1
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat: generate commit messages from Git changes
----------------------
```

PR 초안 출력 예시:

```text
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: add AI Git summary CLI

--- PR Body ---
## Why
- Reduce manual effort when writing commit messages and PR descriptions.

## What
- Collect git status and git diff from the current repository.
- Generate commit and PR drafts through an AI API request.

## How to Test
- Run python main.py commit --safe-mode.
- Run python main.py pr --safe-mode.
```

## Safe Mode And Cost

`--safe-mode`는 기본으로 켜져 있으며 diff를 API로 보내기 전에 다음 처리를 수행합니다.

- 이메일, API key, token, password, secret 패턴을 `<MASKED_TOKEN>`으로 마스킹
- 기본 최대 10개 파일, 200줄까지만 diff 전송
- `--max-files`, `--max-diff-lines`로 제한값 조정 가능
- `--no-safe-mode`로 비활성화 가능하지만 민감정보가 API 요청에 포함될 수 있습니다

비용 방지를 위해 `commit`과 `pr` 명령은 각각 AI API를 1회만 호출하며, 실행 출력에 `AI API 호출 횟수`를 표시합니다.

## Error Handling

API Key가 없으면 아래처럼 원인과 설정 예시를 출력합니다.

```text
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다. 예) export AI_API_KEY="YOUR_KEY"
```

API 호출 실패나 인증 실패가 발생하면 HTTP 상태 또는 네트워크 오류 원인을 출력합니다.

## Validate Output

생성된 출력 형식을 다시 검사할 수 있습니다.

```sh
python main.py validate-output < sample-output.txt
```

검증 기준:

- 커밋 제목은 최대 72자
- 커밋 메시지는 제목 한 줄만 허용
- PR 제목은 최대 80자
- PR 본문은 `Why`, `What`, `How to Test` 섹션과 각 섹션 1개 이상 불릿 포함

## 보너스 증빙: 실제 PR 적용

실제 적용 PR: [codyssey-b2-2-team-mission/git-flow-utility-lab#30](https://github.com/codyssey-b2-2-team-mission/git-flow-utility-lab/pull/30)

아래 초안은 [codyssey-b2-2-team-mission/git-flow-utility-lab.git](https://github.com/codyssey-b2-2-team-mission/git-flow-utility-lab.git) 저장소의 `feature/sangheonlee-member-initials` 브랜치 변경분을 대상으로 이 프로그램을 실행해 생성한 결과입니다. 실제 출력 원문은 [logs/bonus-commit-output.txt](logs/bonus-commit-output.txt), [logs/bonus-pr-output.txt](logs/bonus-pr-output.txt)에 저장했습니다.

추천 커밋 메시지:

```text
Add member_initials function to team_utils
```

추천 PR 제목:

```text
Add member_initials function to extract initials from normalized names
```

추천 PR 본문:

```text
## Why
- Capture the reason for the current Git changes.

## What
- Update README.md
- Update src/team_utils.py

## How to Test
- Run the project checks for this change.
```

## 최종 커밋, PR


최종 커밋 메시지:

```text
feat: add member initials helper
```

최종 PR 제목:

```text
Add member initials helper and README examples
```

최종 PR 본문:

```text
## What
- Add `member_initials()` to return initials from a normalized member name.
- Print the new helper result from `src/team_utils.py`.
- Update the README improvement history, expected output, and check examples.

## Why
- Member-name utilities now cover both slug generation and initials extraction.
- Reusing `normalize_member_name()` keeps whitespace cleanup and capitalization consistent.
- README examples should match the behavior users see when they run the script.

## How to Test
- Run `python3 src/team_utils.py`.
- Confirm the output includes `member_initials: SL`.
- Check that `member_initials("  sangheon   lee ") == "SL"` matches the README example.
```

변경점과 이유:

- 초안 커밋 메시지는 함수명을 말했지만 Conventional Commit 형식이 아니어서 `feat:` prefix를 붙여 기능 추가임을 분명히 했습니다.
- `member_initials`는 코드 식별자라 커밋 제목에서는 `member initials helper`처럼 사람이 읽기 쉬운 표현으로 다듬었습니다.
- PR 제목은 함수 추가만 말하지 않고 README 예시 갱신까지 포함해 실제 변경 범위를 반영했습니다.
- PR 본문 `What`에는 코드 변경, 실행 출력 변경, README 문서 변경을 각각 분리해 리뷰어가 빠르게 확인할 수 있게 했습니다.
- PR 본문 `Why`에는 새 helper가 기존 이름 유틸리티 흐름을 확장한다는 목적을 추가했습니다.
- `normalize_member_name()` 재사용을 명시해 공백 정리와 대소문자 처리 일관성이 유지된다는 점을 설명했습니다.
- 초안의 `Run the project checks`는 너무 추상적이라 실제 실행 명령인 `python3 src/team_utils.py`로 바꿨습니다.
- `member_initials: SL`과 README 확인 예시를 검증 항목에 넣어 이번 변경의 성공 기준을 구체화했습니다.
