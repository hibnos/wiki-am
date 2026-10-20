# 스키마·템플릿·검증 계층 작성 가이드 (Step 3b)

`wiki/CLAUDE.md` 가 **행동 규칙**(원칙·워크플로우·답해야 하는 질문)이라면, 여기서 만드는 세 가지는 그 규칙이 실제로 지켜지게 하는 장치다. 스킬이 삭제되어도 위키가 스스로 검증할 수 있도록 **셋 다 생성물 안에** 둔다.

| 산출물 | 역할 | 소유 |
|---|---|---|
| `wiki-{service}/SCHEMA.md` | **데이터 규칙** 정본 — 계층, 폴더↔접두어, 페이지 종류, 프론트매터 필드, 상태값 | 사람+LLM 합의 (스키마 계층) |
| `wiki-{service}/templates/` | 페이지 유형별 템플릿 + 검증을 통과한 예시 1건 | 스키마 계층. ingest 중 LLM 이 임의 수정하지 않는다 |
| `wiki-{service}/scripts/lint.py` | SCHEMA.md 를 읽어 위키를 검사. ID 발급, 백링크 파생 | 스킬 `scripts/lint.py` 를 **그대로 복사**. 위키별 수정 금지 |

## 1. 계층과 참조 방향

| 계층 | 폴더 | 내용 | 참조할 수 있는 대상 |
|---|---|---|---|
| L0 `raw` | `../raw/` | 불변 원본. 프론트매터 없음 | — |
| L1 `sources` | `sources/` | 소스 하나의 요약 | raw 만 |
| L2 `entities` | 유형별 엔티티·개념 폴더 | 여러 소스를 종합한 **사실** | raw, sources, 같은 계층 |
| L3 `analyses` | `analyses/`·`decisions/`·`evals/` | 사실 위의 **해석·판단·평가** | 전부 |

- **참조는 상위 → 하위 방향으로만** 건다 (`related` ID 와 본문 링크 모두). 하위 페이지가 상위 페이지를 가리키면 소스 요약이 분석의 해석에 물든다 — 이것이 "역방향 오염" 이고 `lint.py` 가 `DIRECTION` 으로 잡는다.
- 역방향 탐색("이 소스를 어느 분석이 썼나")은 손으로 쓰지 않는다. `python3 scripts/lint.py backlinks` 가 각 페이지 끝에 `<!-- backlinks:start -->` … `<!-- backlinks:end -->` 블록을 **생성물로** 써넣는다. 이 블록은 파생 뷰라 오염이 아니며, 손으로 고치지 않는다.
- 허브(`index.md`·`overview.md`·`log.md`·`CLAUDE.md`)는 계층이 없다. 어디서든 링크할 수 있고, 허브는 어디든 링크한다.

## 2. 페이지 종류: living 과 frozen

| kind | 뜻 | 갱신 방식 | 예 |
|---|---|---|---|
| `living` | 현재 상태를 말하는 페이지 | **제자리 갱신**. `updated` 를 올린다 | 엔티티(서비스·모듈·잡·API·스킬), 개념, 패턴, 운영 절차 |
| `frozen` | 어느 시점의 요약·판단 | **만든 뒤 본문을 고치지 않는다.** 내용이 바뀌면 새 페이지를 만들고 `supersedes: <옛 ID>` 로 잇는다 | 소스 요약, 분석, 결정, 평가 기록 |

frozen 페이지의 체인 규칙 (`lint.py` 가 `CHAIN` 으로 검사):
- 새 페이지: `supersedes: ANA-002`.
- 옛 페이지: 프론트매터 **두 필드만** 바꾼다 — `status: superseded`, `superseded_by: ANA-004`. 본문은 그대로 두고, **본문에 새 페이지를 언급하지 않는다** (시간 방향 오염. `DIRECTION` 으로 검사).
- 한 페이지를 대체하는 페이지는 하나다 (head 가 둘이면 ERROR).
- **index 노출 (정책 C)**: 대체된 페이지는 index 의 카테고리 절에서 빼고, index 맨 아래 `## 대체된 페이지` 절에 `- [옛 ID 제목](경로) → 새 ID` 한 줄로 옮긴다. 현행을 찾는 세션은 상단만 읽고, 이력을 묻는 세션만 하단을 본다. `lint.py` 가 `INDEX_SUPERSEDED` 로 검사한다 (카테고리 절에 남아 있거나 대체된 절에 없으면 WARNING).
- **모순 표기**는 페이지 종류를 가리지 않고 `> ⚠️ 모순:` 블록 하나다 — 양쪽 주장·출처·상태(미해결/해결)를 반드시 적는다. frozen 페이지의 내용이 새 증거와 어긋나면 그 페이지를 고치지 않고 관련 living 페이지에 블록을 두거나 새 분석 페이지를 만든다. 별도 "충돌 기록" 절이나 프론트매터 필드는 쓰지 않는다.
- 이 규칙의 이름은 **"시점형 페이지 고정(freeze)"** 이다. wiki-am 의 절대 규칙 "덮어쓰기 금지"(기존 위키 폴더를 건드리지 않음)와는 다른 규칙이다.

## 3. ID 와 파일명

- ID 는 프론트매터에만 있다. 형식 `PREFIX-NNN` (접두어 대문자 2~5자 + 3자리 이상 숫자, 예 `PAT-003`). 접두어는 SCHEMA.md 의 `pages[].prefix` 로 폴더에 1:1 대응한다.
- **파일명은 슬러그**(`patterns/negative-triggers.md`)다. 사람이 `ls` 로 찾고, Karpathy 원형·기존 위키와 호환된다. `PAT-003.md` 처럼 ID 를 파일명으로 쓰지 않는다 (`lint.py` 가 `ID_FILENAME` WARNING). 템플릿 README 와 CLAUDE.md 에 이 규칙을 적지 않으면 LLM 은 ID 를 파일명으로 쓴다 — 2026-09-15 ingest 평가에서 6/6 페이지가 그랬다.
- ID 는 한 번 발급하면 바꾸지 않고 재사용하지 않는다. 발급은 `python3 scripts/lint.py next-id PAT` 로 한다 (LLM 이 세지 않는다).
- **`related` 에는 ID 만 적는다.** 경로를 적지 않는다 — 파일을 옮겨도 ID 는 안 깨진다. 경로 링크는 본문에서 쓴다 (`BROKEN_LINK` 검사 대상).

## 4. 프론트매터 필드

```yaml
---
id: PAT-003
type: pattern
title: description 에 negative 트리거 명시
status: current
created: 2026-09-03
updated: 2026-09-14
sources:
  - ../../SKILL.md
related:
  - SKL-001
---
```

실제 페이지 프론트매터에는 **주석(`#`)을 쓰지 않는다.** 필드 설명은 아래 표에 둔다.

| 필드 | 값 |
|---|---|
| `type` | SCHEMA.md `pages[].type` 과 일치 |
| `status` | living: `current`\|`stale` / frozen: `current`\|`superseded` |
| `updated` | living 만. frozen 에는 없다 |
| `sources` | raw 경로 또는 코드 경로(URL 가능). 비어 있으면 WARNING |
| `related` | ID 만. 방향 규칙 적용 |
| `supersedes` / `superseded_by` | frozen 전용 (선택). 예 `ANA-002` / `ANA-004` |
| `confidence` | 공통 선택. `verified`\|`assumed` (직접 읽은 사실 \| 의도·이유를 역산한 추정) |
| `summary` | 공통 선택. 한 줄 요약 (index 항목 원천) |
| `aliases` | 공통 선택. `[옛 ID, 다른 이름]` — 위키 밖 문서를 이관할 때 옛 ID 보존. lint 는 검사하지 않는다 |

필드는 공통 7 + kind 별 1 을 넘기지 않는다. 필드가 많으면 지켜지지 않는다.

- **`confidence` 부여·승격**: 소스·시스템에서 직접 읽은 사실은 `verified`, 의도·이유를 역산한 것은 `assumed`. `assumed` → `verified` 는 `sources` 에 확인 근거(raw 또는 코드 경로)를 추가할 때만 올린다. 이 문장은 §9 로 CLAUDE.md 에 내려간다 — 필드만 있고 규칙이 없으면 아무도 쓰지 않는다.
- **`aliases`**: 위키 밖에서 만든 기존 문서를 이관할 때 옛 ID·옛 이름을 보존하는 자리다. ID 변경은 이관 시점이 마지막 기회이며 이관 뒤에는 바꾸지 않는다.

## 5. 유형별 pages 표

공통(모든 유형): `sources/` SRC `source` L1 frozen · `analyses/` ANA `analysis` L3 frozen.

| 프로젝트 유형 | folder | prefix | type | layer | kind |
|---|---|---|---|---|---|
| msa service | services / concepts / operations | SVC / CON / OPS | service / concept / operation | entities | living |
| monolithic service | modules / concepts / operations | MOD / CON / OPS | module / concept / operation | entities | living |
| batch | jobs / dataflows / operations | JOB / FLW / OPS | job / dataflow / operation | entities | living |
| research | entities / concepts | ENT / CON | entity / concept | entities | living |
| library/tool | api / concepts / **decisions** | API / CON / **DEC** | api / concept / **decision** | entities / entities / **analyses** | living / living / **frozen** |
| skill·prompt 개발 | skills / patterns / **evals** | SKL / PAT / **EVL** | skill / pattern / **eval** | entities / entities / **analyses** | living / living / **frozen** |

"그 외 유형" 은 가장 가까운 유형에서 출발해 폴더를 바꾸되, 폴더마다 prefix·type·layer·kind 네 값을 반드시 정한다. kind 는 폴더 단위다 — 한 폴더에 living 과 frozen 이 섞이면 폴더를 나눈다 (예: 장애 회고는 `operations/` 가 아니라 `analyses/`).

## 6. SCHEMA.md 골격

`lint.py` 는 이 파일의 **첫 번째 ```yaml 블록만** 읽는다. 블록 안에서 쓸 수 있는 문법은 `key: value`, 인라인 목록 `[a, b]`, 들여쓴 `- item` 목록(항목이 매핑이면 `- key: v` 다음 줄부터 같은 깊이로 이어 쓴다)뿐이다. 앵커·따옴표 문자열·여러 줄 값은 쓰지 않는다.

````markdown
# wiki-{service} 스키마

이 파일은 **데이터 규칙**(계층·ID·프론트매터·상태값)의 정본이다. 행동 규칙(원칙·워크플로우)은 `wiki/CLAUDE.md` 에 있다.
`scripts/lint.py` 가 아래 첫 yaml 블록을 읽어 위키를 검사한다. 블록을 바꾸면 `python3 scripts/lint.py lint` 를 돌려 깨진 곳이 없는지 확인하고 `wiki/log.md` 에 `schema` 로 기록한다.

```yaml
version: 1
service: {service}
layers: [sources, entities, analyses]
hubs: [index.md, overview.md, log.md, CLAUDE.md]
pages:
  - folder: sources
    prefix: SRC
    type: source
    layer: sources
    kind: frozen
  - folder: {엔티티 폴더}
    prefix: {PFX}
    type: {type}
    layer: entities
    kind: living
  - folder: analyses
    prefix: ANA
    type: analysis
    layer: analyses
    kind: frozen
fields:
  common: [id, type, title, status, created, sources, related]   # 모든 페이지 필수
  living: [updated]                                             # living 추가 필수
  frozen: []                                                    # frozen 추가 필수 없음
  optional: [supersedes, superseded_by, confidence, summary, aliases]  # supersede 두 필드는 frozen 전용
status:
  living: [current, stale]
  frozen: [current, superseded]
confidence: [verified, assumed]
```

## 계층과 참조 방향
(§1 표를 이 위키의 폴더 이름으로 옮겨 적는다. 4~6줄)

## 페이지 종류
(§2 의 living/frozen 과 체인 규칙을 4~6줄로)

## 변경 이력
- {오늘} v1 — wiki-am 생성
````

`pages[].folder` 는 `wiki/CLAUDE.md` `## 구조` 절의 폴더 목록과 **같아야** 한다. Step 6 의 lint 가 SCHEMA.md 기준으로 폴더 존재를 검사하므로, CLAUDE.md 쪽 목록은 사람을 위한 설명이고 SCHEMA.md 가 정본이다.

## 7. templates/ 작성법

페이지 유형(`pages[].type`)마다 `templates/{type}.md` 하나. 공통 골격에 유형별 섹션을 끼운다. 원본 파일을 유형 수만큼 들고 있지 않고 **여기 표에서 조합**한다.

공통 골격:
````markdown
---
id: {{id}}
type: {type}
title: {{title}}
status: current
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}          <- living 만. frozen 템플릿에서는 이 줄을 뺀다
sources:
  - {{raw 또는 코드 경로}}
related: []
---

# {{title}}

{{한 줄 요약 — 이 페이지가 답하는 질문}}

## {유형별 섹션…}

## 출처
- {{경로}} — {{이 페이지의 어느 주장을 뒷받침하는지}}
````

유형별 섹션:

| type | 섹션 |
|---|---|
| source | 원문 정보(파일·날짜·저자) / 핵심 주장 / 인용할 만한 구절 / 의문·미해결 |
| service · module · job · api · entity | 책임(한 줄) / 인터페이스·계약(입출력) / 의존(upstream·downstream, 선행·후행) / 규칙·상태 / 운영 주의 / 이력 |
| concept | 정의 / 규칙·상태머신 / 적용되는 곳 / 흔한 오해·반례 |
| operation | 절차 / 선행조건 / 실패 시 영향과 복구 / 이력 |
| dataflow | 출발 → 도착 / 변환 / 계보(어느 잡이 만들고 누가 쓰나) |
| analysis | 질문 / 근거(하위 페이지 링크) / 결론 / 한계 / 후속 |
| decision | Context / Decision / Alternatives(대안과 탈락 사유 — 이 섹션이 존재 이유) / Trade-off / Consequence |
| skill | 목적 / 트리거 범위(발동·미발동·인접 경계) / 구조 / 버전 이력 / 약점 |
| pattern | 언제 쓰나 / 왜 / 적용된 스킬 / 반례 |
| eval | 프롬프트 세트 / 기대 vs 실제 / 실패 분석 / 그로 인한 변경 |

규칙:
- 자리표시자는 `{{...}}` 하나로 통일한다. `lint.py` 가 `wiki/` 안에 남은 `{{` 를 `PLACEHOLDER` ERROR 로 잡는다. `XXX`·`YYYY-MM-DD` 같은 다른 표기는 쓰지 않는다.
- **예시 1건**을 `templates/examples/{중심 엔티티 type}.md` 로 둔다. 자리표시자 없이 실제 값처럼 채운 페이지이며 `id` 는 `{PREFIX}-000` 이다. `python3 scripts/lint.py check templates/examples/*.md` 를 통과해야 한다 — 빈 골격만 있으면 첫 페이지부터 검증에 걸린다.
- `templates/README.md` 에 "새 페이지 = 템플릿 복사(파일명은 슬러그) → `next-id` 로 ID 발급 → 자리표시자 전부 교체 → `lint`" 4줄을 적는다. 명령은 **프로젝트 루트 기준** `python3 wiki-{service}/scripts/lint.py …` 로 적는다 — `../scripts/` 같은 상대 경로는 templates/ 와 wiki/{folder}/ 에서 서로 달라 헷갈린다.

## 8. scripts/lint.py

스킬 폴더의 `scripts/lint.py` 를 `wiki-{service}/scripts/lint.py` 로 복사한다. 표준 라이브러리만 쓰며, 루트는 스크립트 위치에서 자동으로 찾는다.

```bash
python3 scripts/lint.py lint                 # 전체 검사. ERROR 가 있으면 exit 1
python3 scripts/lint.py lint --severity error
python3 scripts/lint.py next-id PAT          # 다음 ID 출력 (PAT-004)
python3 scripts/lint.py backlinks            # '참조됨' 파생 블록 갱신 (파일을 쓴다)
python3 scripts/lint.py check <file>...      # 파일 단위 프론트매터·자리표시자 검사
```

| 심각도 | 코드 |
|---|---|
| ERROR | `NO_SCHEMA` `BAD_SCHEMA` `SCHEMA_DIR` `NO_TEMPLATE` `NO_INDEX` `NO_ID` `BAD_ID` `DUP_ID` `BAD_TYPE` `MISSING_FIELD` `BAD_STATUS` `MISSING_REF` `BROKEN_LINK` `DIRECTION` `CHAIN` `PLACEHOLDER` |
| WARNING | `UNKNOWN_FOLDER` `NO_SOURCES` `BAD_DATE` `FROZEN_UPDATED` `ID_FILENAME` `ORPHAN` `NOT_IN_INDEX` `INDEX_SUPERSEDED` |
| INFO | `STALE` `BIG_INDEX` |

ERROR 는 반드시 해소한다. WARNING 은 사유가 있으면 남기고 그 사유를 페이지에 적는다 — 억지로 0건을 만들려고 의미 없는 링크를 만들지 않는다. 보고할 때 스크립트 출력을 그대로 붙이지 말고 건수·원인·조치로 정리한다.

## 9. wiki/CLAUDE.md 에 넣을 규칙 (그대로 써도 된다)

원칙 절에:
- 페이지의 계층·ID·프론트매터 규칙은 `../SCHEMA.md` 가 정본이다. 새 페이지는 `../templates/{type}.md` 를 복사해 시작하고, ID 는 `python3 ../scripts/lint.py next-id {PREFIX}` 로 발급한다. `{{ }}` 자리표시자는 전부 채운다. 파일명은 내용을 말하는 슬러그(`concepts/attention-budgeting.md`)로 짓고 ID 는 프론트매터에만 둔다.
- 참조는 상위 계층 → 하위 계층 방향으로만 건다 (분석 → 엔티티 → 소스). 하위가 상위를 링크하지 않는다. 역방향은 `lint.py backlinks` 가 만드는 "참조됨" 블록으로 본다.
- 시점형(frozen) 페이지는 만든 뒤 본문을 고치지 않는다. 바뀌면 새 페이지를 만들고 `supersedes:` 로 잇고, 옛 페이지는 `status: superseded`·`superseded_by:` 두 필드만 바꾼다. index 에서는 옛 페이지를 카테고리 절에서 빼고 맨 아래 `## 대체된 페이지` 절에 `→ 새 ID` 와 함께 한 줄로 옮긴다.
- 모순을 발견하면 숨기지 않고 그 페이지에 `> ⚠️ 모순:` 블록으로 양쪽 주장·출처·상태(미해결/해결)를 적는다. 최신 정보가 항상 옳지는 않으므로 조용히 덮어쓰지 않는다.
- `confidence` 는 소스·시스템에서 직접 읽은 사실이면 `verified`, 의도·이유를 역산한 것이면 `assumed` 다. `assumed` → `verified` 승격은 `sources` 에 확인 근거 경로를 추가할 때만 한다.

Lint 절은 이렇게 바꾼다:
1. `python3 ../scripts/lint.py lint` — ERROR 는 해소, WARNING 은 사유를 남긴다.
2. 스크립트가 못 보는 것을 사람이 본다: 모순, 낡은 주장, 출처와 어긋나는 서술.
3. `python3 ../scripts/lint.py backlinks` 로 파생 블록을 갱신하고 log 에 `lint` 로 기록한다.

log 작업종류에 `schema`(SCHEMA.md·templates 변경)를 추가한다.
