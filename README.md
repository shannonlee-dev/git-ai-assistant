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

모델은 `--model`로 직접 지정하거나 `AI_MODEL` 환경변수로 기본값을 바꿀 수 있습니다.

```sh
export AI_MODEL="gpt-4.1-mini"
```

## Usage

이 도구는 Git 프로젝트 루트에서 실행해야 합니다.

```sh
python main.py commit --temperature 0.2 --max-tokens 700 --safe-mode
```

```sh
python main.py pr --temperature 0.2 --max-tokens 900 --safe-mode
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

## Team Convention

프로젝트 루트 또는 도구 설치 루트의 `.ai-gitgen.yml`만으로 커밋/PR 생성 규칙을 커스터마이징할 수 있습니다. 이 앱은 보통 대상 저장소로 이동한 뒤 다른 경로에 있는 도구 파일을 실행하는 방식으로 사용합니다.

```sh
TOOL=/home/shh921shh4393/.dev/git-ai-assistant/main.py
python3 "$TOOL" commit --safe-mode
python3 "$TOOL" pr --safe-mode
```

기본 설정 파일 탐색 순서는 다음과 같습니다.

- 현재 실행 중인 Git 저장소 루트의 `.ai-gitgen.yml`
- 도구가 설치된 `git-ai-assistant` 루트의 `.ai-gitgen.yml`

대상 저장소별로 다른 규칙을 쓰고 싶으면 대상 저장소 루트에 `.ai-gitgen.yml`을 두면 되고, 특정 파일을 직접 지정하려면 `--config`를 전달합니다.

```sh
python3 "$TOOL" pr --config /path/to/.ai-gitgen.yml
```

현재 설정은 이전 미션 저장소 `codyssey-b2-2-team-mission/git-flow-utility-lab`의 README, `docs/CONTRIBUTING.md`, 커밋 히스토리에서 확인한 스타일을 반영합니다.

분석한 팀 컨벤션:

- 브랜치는 `main`에서 `feature/<name>-<topic>` 형식으로 분기하고 PR로만 병합합니다.
- 커밋은 `feat:`, `fix:`, `docs:`, `test:` 예시를 기본으로 쓰며, 히스토리에 있는 `chore:`도 운영성 변경에 허용합니다.
- scope는 기존 커밋에서 필수 패턴이 아니므로 선택 사항입니다.
- PR 본문은 `What`, `Why`, `How` 섹션을 반드시 포함하고 각 섹션은 불릿으로 씁니다.
- 병합 전 최신 `main` 반영, 충돌 해결, 검증 기록, 리뷰 대화 해결을 체크리스트로 남깁니다.

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

pr:
  title_max_length: 80
  sections:
    - What
    - Why
    - How
  tone: concise, factual, review-focused, and action-oriented
  checklist:
    - Latest main reflected before merge
    - Conflicts resolved
    - Validation or test result recorded
    - Review comments resolved
```

설정된 prefix, scope 필수 여부, 브랜치 패턴, PR 제목 길이, PR 섹션, checklist는 모두 `.ai-gitgen.yml`에서만 가져오며 AI 프롬프트, 출력 정규화, `validate-output` 검증에 함께 반영됩니다. 예를 들어 AI가 `Add config loading`처럼 prefix 없는 커밋 제목을 반환해도 도구는 YML의 prefix 목록에 맞춰 `chore: Add config loading`처럼 보정한 뒤 검증합니다.

적용 전/후 예시:

```text
Before
Add member_initials function to team_utils

After
feat: add member initials helper
```

```text
Before
## Why
- Capture the reason for the current Git changes.

## What
- Update README.md

## How to Test
- Run the project checks for this change.

After
## What
- Add `member_initials()` to return initials from a normalized member name.

## Why
- Extend the team utility examples with one more small name helper.

## How
- Run `python3 src/team_utils.py`.

## Checklist
- [ ] Latest main reflected before merge
- [ ] Conflicts resolved
- [ ] Validation or test result recorded
- [ ] Review comments resolved
```

## 로그 결과 비교: 1차 vs 2차

같은 대상 브랜치(`feature/sangheonlee-member-initials`)와 같은 변경량(2개 파일, diff 51줄)을 기준으로, 팀 컨벤션 적용 전 로그 2개와 적용 후 로그 2개를 비교했습니다.

비교 대상:

- 로그1 커밋: [logs/bonus-commit-output.txt](logs/bonus-commit-output.txt)
- 로그1 PR: [logs/bonus-pr-output.txt](logs/bonus-pr-output.txt)
- 로그2 커밋: [logs/bonus2-commit-output.txt](logs/bonus2-commit-output.txt)
- 로그2 PR: [logs/bonus2-pr-output.txt](logs/bonus2-pr-output.txt)

| 구분 | 로그1 결과 | 로그2 결과 | 비교 |
| --- | --- | --- | --- |
| 커밋 메시지 | `Add member_initials function to team_utils` | `feat: add member_initials function` | 로그2는 `.ai-gitgen.yml`의 Conventional Commit prefix 규칙이 반영되어 `feat:`가 붙었습니다. |
| PR 제목 | `Add member_initials function to extract initials from normalized names` | `Add member_initials utility to team_utils` | 로그1은 동작 설명이 더 구체적이고, 로그2는 변경 위치와 유틸리티 성격을 더 짧게 표현합니다. |
| PR 섹션 | `Why`, `What`, `How to Test` | `What`, `Why`, `How`, `Checklist` | 로그2는 팀 컨벤션의 섹션 순서와 `How` 명칭, 체크리스트를 반영했습니다. |
| 테스트 표현 | `Run the project checks for this change.` | `Run the project checks for this change.` | 두 버전 모두 실제 명령까지는 추론하지 못해 테스트 항목은 여전히 추상적입니다. |
| 컨벤션 반영도 | 기본 PR 템플릿에 가까움 | 팀 설정 파일 기반 형식에 가까움 | 로그2가 커밋 prefix, PR 섹션, 체크리스트 측면에서 팀 규칙에 더 잘 맞습니다. |

요약하면 로그1은 변경 내용을 자연어로 설명하는 데 집중했고, 로그2는 팀 컨벤션을 출력 형식에 더 강하게 반영했습니다. 특히 커밋 메시지의 `feat:` prefix와 PR 본문의 `Checklist` 추가는 설정 파일 기반 보정이 실제 결과에 반영된 부분입니다.

다만 두 버전 모두 `Run the project checks for this change.`처럼 테스트 방법이 추상적으로 남아 있습니다. 최종 제출용으로는 실제 실행 명령인 `python3 src/team_utils.py`와 기대 출력(`member_initials: SL`)을 사람이 한 번 더 보강하는 편이 좋습니다.

## Safe-mode 마스킹 관측 결과

`.env.example`에 이메일, API key, token, password 형태의 더미 값을 추가한 뒤 같은 변경 사항을 대상으로 safe-mode 적용 여부만 바꿔 커밋 메시지를 생성했습니다.

safe-mode를 끈 실행:

```bash
./main.py commit --model gpt-4.1-mini --no-safe-mode --temperatur 0
```

결과:

```text
chore: update .env.example with new demo credentials and secrets
```

safe-mode를 켠 실행:

```bash
./main.py commit --model gpt-4.1-mini --temperature 0
```

결과:

```text
chore: update .env.example with additional masked tokens and password p…
```

비교하면 `--no-safe-mode`에서는 diff 원문에 포함된 더미 credential 값을 모델이 그대로 읽을 수 있어 `demo credentials and secrets`처럼 값의 의도를 비교적 자연스럽게 요약했습니다. 반면 safe-mode 기본 실행에서는 민감정보 패턴 4건이 `<MASKED_TOKEN>`으로 치환되어 모델이 실제 값을 볼 수 없었고, 그 영향으로 `masked tokens`라는 표현이 커밋 메시지에 직접 나타났습니다.

즉 safe-mode는 단순히 로그의 마스킹 횟수만 바꾸는 것이 아니라, AI에 전달되는 diff의 의미 정보도 줄이기 때문에 생성되는 커밋 메시지의 표현까지 달라질 수 있습니다. 이 실험에서는 safe-mode 적용 시 `마스킹 4건`이 발생했고, 그 결과가 커밋 메시지 문구 차이로 관측되었습니다.


