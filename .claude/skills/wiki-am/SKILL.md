---
name: wiki-am
description: 프로젝트에 아직 없는 지식 베이스 폴더 wiki-{service}/ (raw/ + wiki/) 를 새로 만드는 스킬. Karpathy 의 LLM Wiki 개념(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 기반. **생성 전용이다** — 폴더 자체를 새로 만들어 달라는 요청("위키 만들어줘", "지식 베이스 세팅", "wiki 초기화", "프로젝트 지식을 쌓아두는 곳 만들어줘", "wiki-xxx 생성")에만 쓴다. 기존 위키가 있으면 절대 덮어쓰지 않고 중단한다. **이미 존재하는 위키 안에서 벌어지는 일은 무엇이든 이 스킬의 일이 아니다** — 그런 요청은 그 위키의 wiki/CLAUDE.md 규칙을 따라 직접 처리한다. 요청이 기존 wiki-*/ 경로나 그 안의 파일을 가리키면 쓰지 않는다. 루트 CLAUDE.md 를 코딩 가이드(빌드 명령·컨벤션)로 작성·초기화하는 요청(init 의 일), 문서 사이트 도구 세팅, wikipedia 등 외부 위키 API 코드 작성, 이 스킬 자체의 수정·튜닝·평가에도 쓰지 않는다.
---

# wiki-am

프로젝트에 Karpathy LLM Wiki 개념 기반의 지식 베이스(`wiki-{service}/`)를 새로 만드는 스킬이다.
LLM Wiki의 핵심: **raw 소스는 사람이 관리하고, wiki는 LLM이 전적으로 작성·유지하는 영속적·복리적(compounding) 지식 베이스**다. 개념 상세는 `references/llm-wiki-concept.md`를 읽는다.

이 스킬은 **생성 전용**이다. 기존 위키를 수정·확장하는 요청이면 이 스킬을 쓰지 말고, 해당 위키의 `wiki/CLAUDE.md` 규칙을 따라 직접 작업한다.

생성물은 `raw/`·`wiki/` 에 더해 데이터 규칙 정본 `SCHEMA.md`, 페이지 템플릿 `templates/`, 검증 도구 `scripts/lint.py` 를 포함한다. 규칙을 강제할 도구까지 위키 안에 두어야 이 스킬이 없어져도 위키가 스스로 검증할 수 있기 때문이다.

## 절대 규칙: 덮어쓰기 금지

기존에 위키가 존재하면 어떤 파일도 덮어쓰지 않는다. 위키는 축적된 지식 자산이라 덮어쓰면 복구 불가능한 손실이 나기 때문이다. 존재 확인은 생성 작업을 시작하기 **전에** 한다.

## 워크플로우

### Step 1. 기존 위키 스캔

사용자에게 질문하거나 무언가를 만들기 **전에**, 프로젝트 루트(스킬을 실행한 작업 디렉터리)에서 기존 위키를 찾는다:

```bash
ls -d wiki-*/ 2>/dev/null
```

- 대상은 `wiki-` 접두 + 하이픈 패턴의 폴더만이다. `wiki/`, `docs/`, `wiki_old/` 처럼 패턴에 맞지 않는 폴더는 이 스킬이 다루는 위키가 아니므로 **무시하고 진행한다** — 그런 폴더가 있다는 이유로 멈추거나 질문하지 않는다.
- 결과를 기억해 두고 Step 2 로 간다. 여기서는 아직 중단하지 않는다 (서비스명이 확정되지 않았다).

### Step 2. 프로젝트 유형·서비스명 확인 → 같은 이름이 있으면 중단

폴더를 만들기 전에 사용자에게 지금 프로젝트가 어떤 형태인지 확인을 요청한다. 유형에 따라 위키의 페이지 분류, `wiki/CLAUDE.md` 내용, 루트 CLAUDE.md 연결 문구가 달라지기 때문이다.

- **프로젝트 유형**: `msa service` / `monolithic service` / `batch` / `research` / `library/tool` / `skill·prompt 개발` 중 선택. 그 외 유형이면 자유 입력. 유형별 위키 설계 지침은 `references/claude-md-templates.md` 에 있다.
- **서비스명** (`{service}`): 프로젝트 디렉터리명 등에서 추정한 값을 제시하고 확인받는다. 소문자-kebab-case를 권장한다.
- Step 1 에서 다른 이름의 `wiki-*` 가 발견됐으면 질문에 그 사실을 함께 알리고, 추가 위키를 만드는 것이 맞는지 확인한다 (같은 프로젝트에 위키가 이미 있을 수 있다).

질문은 **반드시 AskUserQuestion 도구로** 한다 (일반 텍스트 질문 금지 — 프로젝트 hook 이 이 규칙을 강제 주입한다). 선택지는 4개까지이므로 유형은 `msa service` / `monolithic service` / `batch` / `research` 를 선택지로 두고, 질문 설명에 "library/tool, skill·prompt 개발, 그 외 유형은 Other 로 입력" 을 적는다. AskUserQuestion 도구를 쓸 수 없는 환경에서만 대화로 묻는다. 사용자가 이미 대화에서 유형과 이름을 밝혔다면 다시 묻지 말고 그 값을 쓴다.

서비스명이 확정되면 Step 1 결과와 대조한다:

- `wiki-{service}/`가 **이미 존재하면 여기서 중단**한다. 아무것도 생성·수정하지 않고, 사용자에게 "이미 `wiki-{service}/`가 존재합니다. 덮어쓰지 않습니다. 다른 서비스명으로 만들거나, 기존 위키를 계속 사용하세요."라고 알린다.

### Step 3. `wiki-{service}/wiki/CLAUDE.md` 생성

Step 2의 답변(프로젝트 유형)을 기준으로, 그 유형에 맞는 위키 운영 프롬프트를 `wiki-{service}/wiki/CLAUDE.md`로 작성한다. 이 파일이 위키의 **행동 규칙** — 이후 모든 LLM 세션이 위키를 어떻게 읽고 쓰고 유지할지 정의하는 문서다. 데이터 규칙(계층·ID·프론트매터)은 Step 3b 의 `SCHEMA.md` 가 맡는다.

작성 방법:
1. `references/llm-wiki-concept.md`를 읽고 LLM Wiki의 구조·워크플로우(ingest/query/lint)·원칙을 파악한다.
2. `references/claude-md-templates.md`를 읽고 공통 골격 + 프로젝트 유형별 조정 지침을 확인한다.
3. `references/schema-and-templates.md` 의 §1·§2·§9 를 읽고, 계층 참조 방향·시점형 페이지 고정(freeze)·lint 실행 규칙을 CLAUDE.md 의 원칙·Lint 절에 넣는다 (§9 문장을 그대로 써도 된다).
4. 세 문서를 바탕으로 **이 프로젝트 유형에 맞게 구체화된** CLAUDE.md를 작성한다. 템플릿을 그대로 복사하지 말고, 유형별 페이지 분류·엔티티 정의·ingest 대상(코드 변경, 배포 문서, 논문 등)을 실제 프로젝트에 맞게 채운다.
5. `## 구조` 절에서 하위 폴더는 **한 줄에 하나씩** `` - `폴더명/` — 역할 `` 형식으로 적는다. 이 목록이 Step 3b 의 `SCHEMA.md` `pages` 와 1:1 이어야 한다 — 정본은 SCHEMA.md 이고 Step 6 의 lint 가 그것을 기준으로 실제 구조를 검증한다.

### Step 3b. `SCHEMA.md`·`templates/`·`scripts/` 생성

`references/schema-and-templates.md` 를 끝까지 읽고 다음을 만든다. 셋 다 `wiki-{service}/` 바로 아래, `wiki/` 의 형제다.

1. `SCHEMA.md` — §6 골격대로. `pages` 는 Step 3 `## 구조` 절의 하위 폴더와 1:1 이며, 폴더마다 `prefix·type·layer·kind` 네 값을 §5 표에서 가져온다. 공통 `sources/`(SRC, frozen)·`analyses/`(ANA, frozen)는 항상 포함한다.
2. `scripts/lint.py` — **이 SKILL.md 와 같은 폴더에 있는 `scripts/lint.py` 를 그대로 복사**한다 (`cp <스킬 폴더>/scripts/lint.py wiki-{service}/scripts/lint.py`. 스킬 폴더는 보통 `.claude/skills/wiki-am/` 또는 `~/.claude/skills/wiki-am/`). 위키별로 고치지 않는다. 규칙은 스크립트가 아니라 SCHEMA.md 에 있다.
3. `templates/{type}.md` — `pages` 의 type 마다 하나. §7 공통 골격 + 유형별 섹션. frozen 템플릿에는 `updated` 줄이 없다. 자리표시자는 `{{ }}` 만 쓴다.
4. `templates/examples/{중심 엔티티 type}.md` — 자리표시자 없이 실제처럼 채운 예시 1건(`id: {PREFIX}-000`). `templates/README.md` 에 "템플릿 복사 → `next-id` → 자리표시자 교체 → `lint`" 4줄.
5. 확인: `python3 wiki-{service}/scripts/lint.py check wiki-{service}/templates/examples/*.md` 가 전부 ✓ 여야 Step 4 로 간다.

### Step 4. 폴더 구조 생성

Step 3b 의 `SCHEMA.md` `pages` 에 선언된 폴더 **그대로** 폴더와 초기 파일을 만든다. 구조의 정본은 SCHEMA.md 이고 `wiki/CLAUDE.md` `## 구조` 절은 그 설명이다 — 셋(SCHEMA.md·CLAUDE.md·실제 폴더)이 어긋나면 이후 세션이 혼란을 겪고 Step 6 lint 가 `SCHEMA_DIR` 로 실패한다.

기본 골격 (유형별 하위 폴더는 SCHEMA.md `pages` 를 따른다):

```
wiki-{service}/
├── SCHEMA.md         # 데이터 규칙 정본 — 계층·접두어·프론트매터 (Step 3b)
├── templates/        # 페이지 유형별 템플릿 + examples/ + README.md (Step 3b)
├── scripts/lint.py   # 검증·ID 발급·백링크 파생 (Step 3b, 스킬에서 복사)
├── raw/              # 불변 원본 소스 (사람이 넣는 곳, LLM은 읽기만)
│   └── assets/
└── wiki/             # LLM이 작성·유지하는 지식 베이스
    ├── CLAUDE.md     # 위키 운영 규칙 (Step 3에서 생성)
    ├── index.md      # 전체 페이지 카탈로그 (허브)
    ├── log.md        # append-only 작업 이력
    ├── overview.md   # 종합 개요
    └── (유형별 하위 폴더: sources/, entities/, concepts/, analyses/ 등)
```

- `index.md`: 초기 상태로 카테고리 골격 + "아직 페이지 없음" 표시를 넣는다.
- `log.md`: 첫 항목으로 `## [YYYY-MM-DD] init | wiki-{service} 위키 생성` 을 기록한다 (날짜는 오늘 날짜).
- `overview.md`: 프로젝트 한 줄 소개와 "소스가 ingest되면 채워짐" 안내를 넣는다.
- 빈 하위 폴더에는 `.gitkeep`을 넣어 구조가 유지되게 한다.

### Step 5. 프로젝트 루트 CLAUDE.md 연결

프로젝트 루트의 `CLAUDE.md`가 이후 세션들이 위키의 존재를 알게 하는 유일한 연결 고리다. **이 단계는 생략할 수 없다.** description 의 "루트 CLAUDE.md 작성·초기화 금지(init 의 일)"는 위키와 무관한 코딩 가이드 작성 요청을 배제하는 조항이며, 여기서 추가하는 위키 연결 1줄에는 적용되지 않는다.

**프로젝트 루트**는 스킬을 실행한 작업 디렉터리(cwd)다. git 루트나 상위 레포 루트가 따로 있어 판단이 갈리면 AskUserQuestion 으로 후보 경로(cwd / git 루트)를 선택지로 제시해 어느 쪽인지 확인한다.

**대상 파일은 루트의 `CLAUDE.md` 하나로 고정한다.** Claude Code 는 `.claude/CLAUDE.md` 도 프로젝트 지시 파일로 읽지만, 위키 연결 줄은 **거기에 쓰지 않는다**. `.claude/CLAUDE.md` 가 이미 있고 다른 위키를 가리키는 `**Project knowledge:**` 줄을 담고 있더라도 — 그런 줄은 다른 프로젝트에서 `.claude/` 를 복사해 오면서 딸려온 것일 수 있다 — 그 파일을 판정 근거나 기록 대상으로 삼지 말고 루트 `CLAUDE.md` 를 만들거나 갱신한다. `.claude/CLAUDE.md` 에 낡은 위키를 가리키는 줄이 있으면 **고치지 말고 완료 보고에서 알리기만** 한다.
> 2026-09-09 wiki-dba 실행이 이 함정에 빠졌다. 루트 `CLAUDE.md` 는 없고 `.claude/CLAUDE.md` 에 다른 위키(`wiki-am/wiki/`)를 가리키는 줄이 남아 있어서, 스킬이 그 파일에 줄을 덧붙이고 루트 `CLAUDE.md` 를 만들지 않았다.

**추가할 줄은 위키 연결 1줄이다.** `{지식 문구}` 는 Step 2 의 프로젝트 유형에 따라 고른다:

| Step 2 유형 | `{지식 문구}` |
|---|---|
| `msa service` · `monolithic service` · `batch` | 도메인 지식·상태머신·배포 선행조건 |
| `research` | 소스 요약·개념·엔티티·종합 분석 |
| `library/tool` | 공개 API·설계 결정·호환성 이력 |
| `skill·prompt 개발` | 스킬별 트리거 범위·설계 패턴·평가 이력 |
| 그 외 | 축적된 프로젝트 지식(배경·설계 결정·이력) |

```markdown
**Project knowledge:** 이 프로젝트의 {지식 문구}은 `wiki-{service}/wiki/` 에 있다. 허브는 `wiki-{service}/wiki/index.md`, 위키 작성 규칙은 `wiki-{service}/wiki/CLAUDE.md`(이 파일과 별개 — 대상이 다르다).
```

이 줄 **외에는 아무것도 추가하지 않는다.** 위키와 무관한 행동 지시(예: 이전 버전이 넣던 `**Tradeoff:** … bias toward caution …` 줄)는 사용자 프로젝트의 판단 성향을 바꾸는 것이라 이 스킬의 범위가 아니다. 이전 실행이 남긴 `**Tradeoff:**` 줄이 이미 있어도 건드리지 않는다.

절차:

1. 루트에 `CLAUDE.md`가 **없으면** — `.claude/CLAUDE.md` 의 존재 여부와 **무관하게** 루트에 위 1줄로 새로 생성하고 3번으로 간다.
2. 루트에 `CLAUDE.md`가 **이미 있으면** — 파일을 읽은 뒤, 추가 여부는 아래 명령 하나로만 판정한다:

   ```bash
   grep -q 'wiki-{service}/wiki/' CLAUDE.md          # 실패(=없음)면 Project knowledge 줄을 추가
   ```

   - **본문에 위키·`wiki/` 언급이 있다는 이유로 건너뛰지 않는다.** 정확히 위 패턴만 근거로 삼는다. 기존 CLAUDE.md가 위키 폴더를 여러 번 언급하더라도, 패턴이 없으면 추가한다.
   - 기존 내용은 한 글자도 수정하지 않고 파일 **맨 끝**에 줄을 덧붙인다.
   - 패턴이 이미 있으면 파일을 바꾸지 않는다.
3. 반영 결과를 확인한다. 실패하면 원인을 해결하고 다시 한다:

   ```bash
   grep -q 'wiki-{service}/wiki/' CLAUDE.md && echo "root-link OK"
   ```

Project knowledge 줄은 위키당 1회다. 위키가 두 개 이상인 프로젝트의 루트 CLAUDE.md 예시:

```markdown
**Project knowledge:** ... `wiki-order/wiki/` ...
**Project knowledge:** ... `wiki-payment/wiki/` ...
```

### Step 6. 완료 검증과 보고

보고하기 **전에** 필수 산출물이 실제로 있는지, 그리고 `SCHEMA.md` 가 선언한 폴더·템플릿이 실제로 만들어졌는지 생성한 lint 로 확인한다. 하나라도 실패하면 해당 Step 으로 돌아가 만들고 다시 검증한다 — 검증을 통과하기 전에는 완료 보고를 하지 않는다.

```bash
S=wiki-{service}
# 1) 필수 산출물 + 루트 연결
test -f $S/SCHEMA.md && test -f $S/scripts/lint.py && test -d $S/templates/examples \
  && test -f $S/wiki/CLAUDE.md && test -f $S/wiki/index.md && test -f $S/wiki/log.md \
  && grep -q "$S/wiki/" CLAUDE.md && echo "$S files OK"
# 2) 스키마↔구조↔템플릿 일치 (SCHEMA_DIR·NO_TEMPLATE 등 ERROR 0 이어야 통과. exit 0)
python3 $S/scripts/lint.py lint --severity error
# 3) 예시 페이지가 스키마를 통과하는가 (전부 ✓)
python3 $S/scripts/lint.py check $S/templates/examples/*.md
```

통과하면 사용자에게 생성된 구조를 트리로 보여주고, 다음 사용법을 안내한다:
- 원본 문서는 `wiki-{service}/raw/`에 넣으면 된다.
- "raw에 넣은 문서 ingest해줘"라고 하면 위키가 채워진다. 새 페이지는 `templates/{type}.md` 를 복사해 시작하고 ID 는 `python3 wiki-{service}/scripts/lint.py next-id {PREFIX}` 로 발급한다.
- 점검은 `python3 wiki-{service}/scripts/lint.py lint`. 위키 운영 규칙은 `wiki-{service}/wiki/CLAUDE.md`, 데이터 규칙은 `wiki-{service}/SCHEMA.md` 에 있다.
