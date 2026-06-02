"""Shared constants for the AI Git generator."""

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_CONFIG_FILE = ".ai-gitgen.yml"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 700
MIN_MAX_TOKENS = 50
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_DIFF_LINES = 200
DEFAULT_API_TIMEOUT = 30.0
DEFAULT_SAFE_MODE = True

AI_API_KEY_ENV = "AI_API_KEY"
AI_API_BASE_URL_ENV = "AI_API_BASE_URL"
AI_MODEL_ENV = "AI_MODEL"

COMMAND_COMMIT = "commit"
COMMAND_PR = "pr"
COMMAND_VALIDATE_OUTPUT = "validate-output"

CLI_PROG = "main.py"

EXIT_SUCCESS = 0
EXIT_API_ERROR = 1
EXIT_USAGE_ERROR = 2
ZERO_API_CALLS = 0
INITIAL_API_CALL_COUNT = 0
API_CALL_INCREMENT = 1
FIRST_API_RESPONSE_CHOICE_INDEX = 0
INITIAL_COUNT = 0
COUNT_INCREMENT = 1

MOCK_URL_PREFIX = "mock://"
MOCK_ERROR_URL_PREFIX = "mock://error"
MOCK_PR_URL_PREFIX = "mock://pr"

MASKED_TOKEN = "<MASKED_TOKEN>"

COMMIT_TITLE_LIMIT = 72
PR_TITLE_LIMIT = 80
DEFAULT_FALLBACK_TARGET = "project"
FALLBACK_COMMIT_PREFIX = "chore"
FALLBACK_PR_PREFIX = "chore"
MAX_FALLBACK_WHAT_FILES = 3

DEFAULT_WHY_BULLET = "- Capture the reason for the current Git changes."
DEFAULT_WHAT_BULLET = "- Summarize the implementation changes."

STRIP_LABEL_PATTERN = r"^(#+\s*)?(-\s*)?(commit message|commit title|pr title|title)\s*[:：-]\s*"
PR_HEADING_PATTERN = r"^##\s+(.+?)\s*$"
WHITESPACE_PATTERN = r"\s+"
PR_SECTION_PATTERN_TEMPLATE = r"(?ms)^##\s+{section}\s*$.*?(?=^##\s+|\Z)"
PR_BULLET_PATTERN = r"(?m)^-\s+\S+"
HEADING_SUFFIX_CHARS = ":："

SECRET_ASSIGNMENT_PATTERN = r"(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)([^\s'\"`]+)"
OPENAI_SECRET_PATTERN = r"\bsk-[A-Za-z0-9_-]{12,}\b"
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
AWS_ACCESS_KEY_PATTERN = r"\bAKIA[0-9A-Z]{16}\b"

COMMIT_OUTPUT_HEADER = "--- Commit Message ---"
COMMIT_OUTPUT_FOOTER = "----------------------"
PR_TITLE_MARKER = "--- PR Title ---"
PR_BODY_MARKER = "--- PR Body ---"
DRY_RUN_SUMMARY_MARKER = "--- Dry Run Summary ---"

MARKDOWN_HEADING_PREFIX = "##"
BULLET_PREFIX = "- "
TITLE_ELLIPSIS = "…"
TITLE_ELLIPSIS_WIDTH = 1
FIRST_LINE_INDEX = 0
MAX_COMMIT_MESSAGE_LINES = 1

PROMPT_MODE_COMMIT = COMMAND_COMMIT
PROMPT_MODE_PR = COMMAND_PR
PROMPT_SYSTEM_ROLE = "system"
PROMPT_USER_ROLE = "user"

GIT_EXECUTABLE = "git"
GIT_REV_PARSE_ROOT_ARGS = ("rev-parse", "--show-toplevel")
GIT_STATUS_SHORT_ARGS = ("status", "--short")
GIT_BRANCH_CURRENT_ARGS = ("branch", "--show-current")
GIT_STAGED_DIFF_ARGS = ("diff", "--cached", "--no-ext-diff", "--")
SHORT_STATUS_PATH_OFFSET = 3
GIT_RENAME_SEPARATOR = " -> "
GIT_RENAME_SPLIT_MAX = 1
GIT_RENAME_TARGET_INDEX = 1
GIT_DIFF_FILE_PREFIX = "diff --git "
DETACHED_BRANCH_NAME = "detached"
PROCESS_SUCCESS_RETURN_CODE = 0

HTTP_ENCODING = "utf-8"
HTTP_ERROR_ENCODING = "replace"
HTTP_METHOD_POST = "POST"
HTTP_AUTHORIZATION_HEADER = "Authorization"
HTTP_CONTENT_TYPE_HEADER = "Content-Type"
HTTP_RETRY_AFTER_HEADER = "Retry-After"
HTTP_JSON_CONTENT_TYPE = "application/json"
HTTP_BEARER_PREFIX = "Bearer"

HTTP_STATUS_HINTS = {
    400: "요청 형식이 잘못되었습니다. 모델명, temperature, max_tokens 같은 요청 값을 확인하세요.",
    401: "인증에 실패했습니다. AI_API_KEY 값이 올바른지 확인하세요.",
    403: "API 키 권한, 프로젝트 권한, 결제 설정 또는 모델 접근 권한을 확인하세요.",
    404: "API URL 또는 모델명을 찾을 수 없습니다. --api-base-url과 --model 값을 확인하세요.",
    408: "요청 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
    413: "요청이 너무 큽니다. --max-files 또는 --max-diff-lines 값을 줄여 diff 크기를 낮추세요.",
    429: "요청 제한 또는 할당량을 초과했습니다. 잠시 후 다시 시도하거나 API 쿼터를 확인하세요.",
    500: "AI 제공자 서버 오류입니다. 잠시 후 다시 시도하세요.",
    502: "AI 제공자 게이트웨이 오류입니다. 잠시 후 다시 시도하세요.",
    503: "AI 서비스가 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도하세요.",
    504: "AI 제공자 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.",
}

API_RESPONSE_CHOICES_KEY = "choices"
API_RESPONSE_MESSAGE_KEY = "message"
API_RESPONSE_CONTENT_KEY = "content"
API_PAYLOAD_MODEL_KEY = "model"
API_PAYLOAD_MESSAGES_KEY = "messages"
API_PAYLOAD_TEMPERATURE_KEY = "temperature"
API_PAYLOAD_MAX_TOKENS_KEY = "max_tokens"
API_ERROR_KEY = "error"
API_ERROR_MESSAGE_KEY = "message"
API_ERROR_DETAIL_KEY = "detail"
API_ERROR_DESCRIPTION_KEY = "error_description"
API_ERROR_CODE_KEY = "code"
API_ERROR_STATUS_KEY = "status"
EMPTY_ERROR_RESPONSE = "empty error response"

DRY_RUN_STATUS_PREVIEW_LINES = 20
MARKER_SPLIT_MAX = 1
PR_TITLE_CONTENT_LINE_INDEX = 1
SECRET_ASSIGNMENT_PATTERN_INDEX = 0
ADDITIONAL_SECRET_PATTERNS_START_INDEX = 1
PR_HEADING_TEXT_GROUP = 1
FULL_MATCH_GROUP = 0
SECRET_NAME_GROUP = 1
SECRET_SEPARATOR_GROUP = 2
