---
name: wiki-am
description: 새 wiki-{service}/ 지식 베이스를 생성한다. 위키 만들기·지식 베이스 세팅·wiki 초기화 요청에 사용한다. 기존 위키의 ingest·수정·질의, 일반 코딩 가이드 초기화, 문서 사이트 구축에는 사용하지 않는다.
---

# wiki-am

사람이 관리하는 불변 원본 `raw/`와 LLM이 작성·유지하는 `wiki/`를 갖춘 지식 베이스를 만든다. 사용자와 한국어로 소통하되 명시한 언어가 있으면 따른다. 이 스킬은 생성 전용이다. 기존 위키 작업은 해당 위키의 운영 지침을 읽고 별도로 수행한다.

## 1. 대상 확정과 충돌 확인

- 작업 디렉터리의 `wiki-*/`를 먼저 확인한다. `wiki/`, `docs/`, `wiki_old/`는 충돌로 취급하지 않는다.
- 프로젝트 유형과 서비스명을 확인한다. 대화에서 이미 지정한 값은 다시 묻지 않는다. 유형은 `msa service`, `monolithic service`, `batch`, `research`, `library/tool`, `skill·prompt 개발` 또는 사용자 지정이다. 서비스명은 소문자 kebab-case로 제안하고 경로 구분자·`..`를 허용하지 않는다.
- 값이 빠졌으면 프로젝트에서 추정한 후보를 제시해 질문한다. 다른 `wiki-*`가 있으면 함께 알리고 추가 생성 의도를 확인한다. 사용자가 이미 별도 위키 생성을 명시했다면 재확인하지 않는다.
- 질문은 현재 환경·모드에서 사용 가능한 사용자 입력 도구를 우선한다. `request_user_input`을 현재 환경·모드에서 허용할 때 우선 사용한다. 사용할 수 없으면 `request_user_input_async`로 질문하고 답에 의존하지 않는 조사만 계속한다. 사용할 수 있는 도구가 없으면 일반 대화로 묻는다. 필수 답변을 기다리는 동안 임의 값으로 위키를 생성하지 않는다.
- 루트는 사용자가 지정한 프로젝트 경로, 미지정 시 cwd다. cwd와 git 루트 중 대상이 실제로 모호하면 확인한다.
- 확정한 `wiki-{service}` 경로에 파일·디렉터리·심볼릭 링크가 이미 있으면 아무것도 수정하지 않고 중단한다. 다른 이름 또는 기존 위키 사용을 안내한다. 생성 직전 다시 확인하고 기존 경로를 재사용하지 않는다.

## 2. 운영 지침과 스키마 설계

다음 자료를 읽는다:

- [LLM Wiki 개념](references/llm-wiki-concept.md): raw/wiki 역할과 ingest/query/lint 원칙.
- [AGENTS.md 작성 가이드](references/agents-md-templates.md): 공통 골격과 확정된 프로젝트 유형의 분류·워크플로우.
- [스키마와 템플릿](references/schema-and-templates.md): 계층, ID, living/frozen, 템플릿과 검증 규칙. 생성 전에 전체를 읽는다.

`wiki-{service}/wiki/AGENTS.md`를 프로젝트에 맞게 구체화한다. 구조 절에는 하위 폴더를 한 줄에 하나씩 `- 폴더명/ — 역할` 형식으로 나열한다. 위키 작업 전 이 파일을 명시적으로 읽도록 루트 연결에도 적는다.

`wiki-{service}/SCHEMA.md`는 데이터 규칙의 정본이다. 첫 YAML 블록의 `pages`와 운영 지침의 폴더 목록을 일치시킨다. 각 폴더의 prefix/type/layer/kind는 참고 표에 따른다. `sources`(SRC, frozen)와 `analyses`(ANA, frozen)는 항상 포함한다. `hubs`는 `[index.md, overview.md, log.md, AGENTS.md]`로 선언한다.

raw 불변, 출처 추적, 모순 표시, 상위→하위 참조 및 같은 계층 참조, frozen 대체 체인, append-only 로그 규칙을 유지한다. frozen 본문은 바꾸지 않으며 도구가 생성한 backlinks 블록만 파생 뷰로 갱신한다. 스키마·템플릿은 ingest 중 임의로 바꾸지 않는다.

## 3. 생성

```text
wiki-{service}/
├── SCHEMA.md
├── templates/
│   ├── {type}.md
│   ├── examples/{중심 엔티티 type}.md
│   └── README.md
├── scripts/lint.py
├── raw/assets/
└── wiki/
    ├── AGENTS.md
    ├── index.md
    ├── log.md
    ├── overview.md
    └── {SCHEMA.md pages에 선언한 폴더들}/
```

- 이 스킬의 [scripts/lint.py](scripts/lint.py)를 생성할 위키의 `scripts/lint.py`로 그대로 복사한다. 설치된 스킬 경로를 기준으로 찾고, 프로젝트별 규칙은 스크립트가 아닌 스키마에 둔다. Python 표준 라이브러리만 필요하다.
- type별 템플릿을 만든다. 자리표시자는 `{{...}}`만 쓰고 frozen에는 `updated`를 넣지 않는다.
- 중심 엔티티 예시 1건을 `{PREFIX}-000`으로 채운다. 예시는 실제 프로젝트 사실로 오인되지 않도록 가상 예시임을 밝힌다.
- 템플릿 README에 “슬러그 파일명으로 템플릿 복사 → next-id → 자리표시자 교체 → lint” 사용법을 프로젝트 루트 기준 명령으로 적는다.
- index는 카테고리별 “아직 페이지 없음”, overview는 프로젝트 소개와 ingest 후 채워진다는 안내로 시작한다.
- log의 첫 항목은 실제 오늘 날짜의 `## [YYYY-MM-DD] init | wiki-{service} 위키 생성`이다.
- 빈 폴더에는 `.gitkeep`을 둔다.

## 4. 프로젝트 루트 연결

루트 `AGENTS.md`를 읽고 정확한 문자열 `wiki-{service}/wiki/`가 없으면 다음 연결 한 줄을 끝에 추가한다. 파일이 없으면 이 줄로 생성한다. 기존 내용은 보존하고 다른 지시 파일을 대신 수정하지 않는다. `AGENTS.override.md` 등 우선 지침 때문에 연결이 가려지는 환경이면 사용자에게 그 사실을 알린다.

```markdown
**Project knowledge:** 이 프로젝트의 {지식 문구}은 `wiki-{service}/wiki/`에 있다. 허브는 `wiki-{service}/wiki/index.md`이며, 위키 작업 전 `wiki-{service}/wiki/AGENTS.md`를 읽고 운영 규칙을 따른다.
```

지식 문구는 서비스형이면 “도메인 지식·상태머신·배포 선행조건”, research면 “소스 요약·개념·엔티티·종합 분석”, library/tool이면 “공개 API·설계 결정·호환성 이력”, skill·prompt 개발이면 “스킬별 트리거 범위·설계 패턴·평가 이력”, 그 외는 “축적된 프로젝트 지식”을 사용한다. 조사(은/는)는 자연스럽게 조정한다.

`rg -F 'wiki-{service}/wiki/' AGENTS.md`로 정확한 연결을 확인한다. 다른 위키의 연결이 있다는 이유로 생략하지 않는다.

## 5. 검증과 완료 보고

프로젝트 루트에서 실제 서비스명으로 실행한다:

```bash
python3 wiki-{service}/scripts/lint.py lint --severity error
python3 wiki-{service}/scripts/lint.py check wiki-{service}/templates/examples/*.md
```

필수 파일, raw/assets, 모든 선언 폴더·템플릿, 루트 연결을 별도로 확인한다. lint는 운영 지침의 폴더 목록이나 루트 연결까지 검사하지 않으므로 직접 대조한다. ERROR 0과 예시 전부 통과를 확인한 뒤 완료를 보고한다. 실패는 이번에 만든 산출물에서 수정하고 재검증한다. 권한 등으로 해결할 수 없으면 미완료 항목을 정확히 알린다.

완료 시 생성 경로·구조와 검증 결과를 간단히 보여주고 다음 사용법을 안내한다:
- 원본은 `wiki-{service}/raw/`에 넣고 “raw에 넣은 문서 ingest해줘”라고 요청한다.
- 새 ID는 `python3 wiki-{service}/scripts/lint.py next-id {PREFIX}`로 얻는다. 이 명령은 ID를 예약하지 않으므로 페이지를 저장한 후 다음 ID를 얻는다.
- 점검은 `python3 wiki-{service}/scripts/lint.py lint`로 한다.
- 운영 규칙은 `wiki/AGENTS.md`, 데이터 규칙은 `SCHEMA.md`에 있다.
