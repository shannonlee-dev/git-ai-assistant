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

## Team Convention

프로젝트 루트의 `.ai-gitgen.yml`로 커밋/PR 생성 규칙을 커스터마이징할 수 있습니다. 기본 경로 대신 다른 파일을 쓰려면 `--config`를 전달합니다.

```sh
python main.py pr --config .ai-gitgen.yml
```

현재 예시는 `codyssey-b2-2-team-mission/git-flow-utility-lab`의 히스토리와 `docs/CONTRIBUTING.md`에서 확인한 팀 컨벤션을 반영합니다.

```yml
commit:
  prefixes:
    - feat
    - fix
    - docs
    - test
    - chore
  scope_required: false
  subject_max_length: 72

branch:
  patterns:
    - feature/<name>-<topic>
    - chore/<name>-<topic>

pr:
  sections:
    - What
    - Why
    - How
  tone: concise, factual, and review-focused
  issue_reference: "Include Closes #<issue_number> or Fixes #<issue_number>."
  checklist:
    - Latest main reflected before merge
    - Conflicts resolved
    - Validation or test result recorded
    - Review comments resolved
```

설정된 prefix, scope 필수 여부, 브랜치 패턴, PR 섹션, 이슈 참조, checklist는 AI 프롬프트와 출력 검증에 함께 반영됩니다.

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
