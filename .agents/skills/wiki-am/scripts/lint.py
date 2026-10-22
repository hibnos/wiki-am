#!/usr/bin/env python3
"""wiki-{service} 검증 도구. wiki-am 스킬이 위키를 만들 때 `scripts/lint.py` 로 복사해 둔다.
표준 라이브러리만 쓴다. 루트(wiki-{service}/)는 이 파일의 상위 폴더로 자동 결정한다.

  python3 scripts/lint.py lint [--severity error|warning|info] [--stale-days 180]
  python3 scripts/lint.py next-id PAT              # 다음 ID 출력 (PAT-004)
  python3 scripts/lint.py backlinks                # '참조됨' 파생 블록을 각 페이지 끝에 갱신 (쓰기)
  python3 scripts/lint.py check <file>...          # 파일 단위 프론트매터·자리표시자 검사 (templates/examples 용)
  공통 옵션: --root <wiki-{service} 경로>

규칙의 정본은 SCHEMA.md 의 첫 ```yaml 블록이다. 이 스크립트는 그 블록을 읽어 검사할 뿐 규칙을 갖고 있지 않다.
"""
import os
import re
import sys
from datetime import date, datetime

FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ID_RE = re.compile(r"^[A-Z]{2,5}-\d{3,}$")
PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YAML_BLOCK_RE = re.compile(r"```yaml[ \t]*\n(.*?)\n```", re.S)
MAP_ITEM_RE = re.compile(r"^[A-Za-z_][\w-]*:(\s|$)")
BL_START, BL_END = "<!-- backlinks:start -->", "<!-- backlinks:end -->"
BL_RE = re.compile(re.escape(BL_START) + r".*?" + re.escape(BL_END) + r"\n?", re.S)


# ---------- YAML 부분집합 파서 ----------
def parse_yaml_subset(text, inline_comments=False):
    """`key: value`, `[a, b]`, 들여쓴 `- item`(항목이 매핑이면 `- k: v` + 이어지는 줄)만 읽는다."""
    items = []
    for raw in text.split("\n"):
        s = raw.rstrip()
        if not s.strip() or s.strip().startswith("#"):
            continue
        if inline_comments and " #" in s:
            s = s[: s.index(" #")].rstrip()
        items.append([len(s) - len(s.lstrip(" ")), s.strip()])
    pos = [0]

    def scalar(v):
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            return [] if not inner else [x.strip().strip("'\"") for x in inner.split(",")]
        v = v.strip("'\"")
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if v in ("true", "false"):
            return v == "true"
        return v

    def block():
        if pos[0] >= len(items):
            return None
        ind, s = items[pos[0]]
        return lst(ind) if s.startswith("- ") else mp(ind)

    def mp(indent):
        d = {}
        while pos[0] < len(items):
            ind, s = items[pos[0]]
            if ind < indent or s.startswith("- "):
                break
            if ind > indent:
                raise ValueError(f"들여쓰기 오류: {s!r}")
            if ":" not in s:
                raise ValueError(f"`key: value` 형식이 아님: {s!r}")
            key, _, val = s.partition(":")
            pos[0] += 1
            if val.strip() == "":
                if pos[0] < len(items) and items[pos[0]][0] > indent:
                    d[key.strip()] = block()
                else:
                    d[key.strip()] = None
            else:
                d[key.strip()] = scalar(val)
        return d

    def lst(indent):
        out = []
        while pos[0] < len(items):
            ind, s = items[pos[0]]
            if ind < indent or not s.startswith("- "):
                break
            if ind > indent:
                raise ValueError(f"들여쓰기 오류: {s!r}")
            rest = s[2:].strip()
            if MAP_ITEM_RE.match(rest):  # `- key: v` 만 매핑. `- https://…` 같은 값은 스칼라
                items[pos[0]] = [indent + 2, rest]  # 대시 줄을 매핑의 첫 줄로 바꿔 mp 에 맡긴다
                out.append(mp(indent + 2))
            else:
                pos[0] += 1
                out.append(scalar(rest))
        return out

    return block() or {}


def parse_front_matter(text):
    m = FM_RE.match(text)
    if not m:
        return None, text
    try:
        fm = parse_yaml_subset(m.group(1), inline_comments=True)
    except ValueError as e:
        return {"__error__": str(e)}, text[m.end():]
    if not isinstance(fm, dict):
        return {"__error__": "프론트매터가 매핑이 아님"}, text[m.end():]
    return fm, text[m.end():]


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [str(v)] if str(v).strip() else []


# ---------- 스키마 ----------
class Schema:
    def __init__(self, root):
        self.root = root
        self.errors = []
        self.pages = {}        # folder -> def
        self.by_type = {}      # type -> def
        self.layers, self.hubs = [], []
        self.fields, self.status, self.confidence = {}, {}, []
        path = os.path.join(root, "SCHEMA.md")
        if not os.path.exists(path):
            self.errors.append(("NO_SCHEMA", "SCHEMA.md 가 없습니다"))
            return
        m = YAML_BLOCK_RE.search(open(path, encoding="utf-8").read())
        if not m:
            self.errors.append(("BAD_SCHEMA", "SCHEMA.md 에 ```yaml 블록이 없습니다"))
            return
        try:
            d = parse_yaml_subset(m.group(1), inline_comments=True)
        except ValueError as e:
            self.errors.append(("BAD_SCHEMA", f"yaml 블록 파싱 실패: {e}"))
            return
        self.layers = as_list(d.get("layers"))
        self.hubs = as_list(d.get("hubs")) or ["index.md", "overview.md", "log.md", "AGENTS.md"]
        self.fields = d.get("fields") or {}
        self.status = d.get("status") or {}
        self.confidence = as_list(d.get("confidence"))
        for p in d.get("pages") or []:
            if not isinstance(p, dict):
                self.errors.append(("BAD_SCHEMA", f"pages 항목이 매핑이 아님: {p!r}"))
                continue
            missing = [k for k in ("folder", "prefix", "type", "layer", "kind") if not p.get(k)]
            if missing:
                self.errors.append(("BAD_SCHEMA", f"pages[{p.get('folder')}] 에 {missing} 없음"))
                continue
            if p["layer"] not in self.layers:
                self.errors.append(("BAD_SCHEMA", f"pages[{p['folder']}].layer={p['layer']} 가 layers 에 없음"))
            if p["kind"] not in ("living", "frozen"):
                self.errors.append(("BAD_SCHEMA", f"pages[{p['folder']}].kind 는 living|frozen"))
            if p["folder"] in self.pages:
                self.errors.append(("BAD_SCHEMA", f"folder {p['folder']} 중복"))
            self.pages[p["folder"]] = p
            self.by_type[p["type"]] = p
        if not self.pages:
            self.errors.append(("BAD_SCHEMA", "pages 가 비어 있습니다"))

    def rank(self, layer):
        return self.layers.index(layer) if layer in self.layers else -1

    def required(self, kind):
        return as_list(self.fields.get("common")) + as_list(self.fields.get(kind))

    def allowed_status(self, kind):
        return as_list(self.status.get(kind))


# ---------- 페이지 수집 ----------
class Page:
    __slots__ = ("rel", "full", "folder", "fm", "body", "pdef", "id", "out_ids", "out_pages", "text")


def collect(root, schema):
    wiki = os.path.join(root, "wiki")
    pages, warnings = [], []
    for base, dirs, files in os.walk(wiki):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(base, fn)
            rel = os.path.relpath(full, wiki).replace(os.sep, "/")
            if "/" not in rel and fn in schema.hubs:
                continue
            p = Page()
            p.rel, p.full = rel, full
            p.folder = rel.split("/")[0] if "/" in rel else ""
            p.text = open(full, encoding="utf-8", errors="replace").read()
            p.fm, body = parse_front_matter(p.text)
            p.body = BL_RE.sub("", body)  # 백링크 파생 블록은 본문이 아니다
            p.pdef = schema.pages.get(p.folder)
            p.id = str(p.fm.get("id")) if p.fm and p.fm.get("id") else None
            pages.append(p)
    return pages


def mentions(text, token):
    """token 이 단어 단위로 들어 있는가. SRC-001 이 SRC-0010 에 매치되지 않게 한다."""
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", text) is not None


def body_links(page, wiki):
    """본문 상대 링크 → (원문, 절대경로). http/mailto/anchor 는 제외."""
    out = []
    base = os.path.dirname(page.full)
    for link in LINK_RE.findall(page.body):
        link = link.split("#")[0].strip()
        if not link or link.startswith(("http://", "https://", "mailto:")):
            continue
        out.append((link, os.path.normpath(os.path.join(base, link))))
    return out


# ---------- lint ----------
def lint(root, severity=None, stale_days=180):
    findings = []

    def add(sev, code, msg):
        findings.append((sev, code, msg))

    schema = Schema(root)
    for code, msg in schema.errors:
        add("ERROR", code, msg)
    wiki = os.path.join(root, "wiki")
    if not os.path.isdir(wiki):
        add("ERROR", "NO_SCHEMA", "wiki/ 폴더가 없습니다")
    if schema.errors or not os.path.isdir(wiki):
        return report(findings, severity, 0)

    # 스키마 ↔ 구조
    for folder, pdef in schema.pages.items():
        if not os.path.isdir(os.path.join(wiki, folder)):
            add("ERROR", "SCHEMA_DIR", f"SCHEMA.md 가 선언한 폴더가 없습니다: wiki/{folder}/")
        tpl = os.path.join(root, "templates", f"{pdef['type']}.md")
        if not os.path.exists(tpl):
            add("ERROR", "NO_TEMPLATE", f"templates/{pdef['type']}.md 가 없습니다 (pages[{folder}])")
    index_path = os.path.join(wiki, "index.md")
    index_text = open(index_path, encoding="utf-8").read() if os.path.exists(index_path) else None
    if index_text is None:
        add("ERROR", "NO_INDEX", "wiki/index.md 가 없습니다")

    pages = collect(root, schema)
    by_id, path_to_page = {}, {}
    for p in pages:
        path_to_page[os.path.normpath(p.full)] = p
        if PLACEHOLDER_RE.search(p.text):
            add("ERROR", "PLACEHOLDER", f"{p.rel}: 자리표시자 {{{{ }}}} 가 남아 있습니다")
        if p.fm is None:
            add("ERROR", "NO_ID", f"{p.rel}: 프론트매터가 없습니다")
            continue
        if "__error__" in p.fm:
            add("ERROR", "MISSING_FIELD", f"{p.rel}: 프론트매터 파싱 실패 — {p.fm['__error__']}")
            continue
        if p.pdef is None:
            add("WARNING", "UNKNOWN_FOLDER", f"{p.rel}: SCHEMA.md 에 선언되지 않은 위치입니다 (검사 생략)")
            continue
        kind = p.pdef["kind"]
        if not p.id:
            add("ERROR", "NO_ID", f"{p.rel}: id 가 없습니다")
        else:
            if not ID_RE.match(p.id):
                add("ERROR", "BAD_ID", f"{p.rel}: id 형식 위반 ({p.id}) — PREFIX-NNN")
            elif p.id.split("-")[0] != p.pdef["prefix"]:
                add("ERROR", "BAD_ID", f"{p.rel}: 접두어 {p.id.split('-')[0]} 는 wiki/{p.folder}/ 의 {p.pdef['prefix']} 와 다릅니다")
            by_id.setdefault(p.id, []).append(p)
        if str(p.fm.get("type", "")) != p.pdef["type"]:
            add("ERROR", "BAD_TYPE", f"{p.rel}: type={p.fm.get('type')} — wiki/{p.folder}/ 는 {p.pdef['type']}")
        for f in schema.required(kind):
            if f not in p.fm:
                add("ERROR", "MISSING_FIELD", f"{p.rel}: 필수 필드 {f} 없음 ({kind})")
        allowed = schema.allowed_status(kind)
        if allowed and str(p.fm.get("status")) not in allowed:
            add("ERROR", "BAD_STATUS", f"{p.rel}: status={p.fm.get('status')} — {kind} 은 {allowed}")
        if schema.confidence and p.fm.get("confidence") and str(p.fm["confidence"]) not in schema.confidence:
            add("ERROR", "BAD_STATUS", f"{p.rel}: confidence={p.fm['confidence']} — {schema.confidence}")
        for f in ("created", "updated"):
            if f in p.fm and not DATE_RE.match(str(p.fm[f])):
                add("WARNING", "BAD_DATE", f"{p.rel}: {f}={p.fm[f]} — YYYY-MM-DD")
        if kind == "frozen" and "updated" in p.fm:
            add("WARNING", "FROZEN_UPDATED", f"{p.rel}: frozen 페이지에 updated 가 있습니다 — 본문을 고쳤다면 새 페이지 + supersedes 가 맞습니다")
        if kind == "living" and ("supersedes" in p.fm or "superseded_by" in p.fm):
            add("ERROR", "CHAIN", f"{p.rel}: living 페이지는 supersede 체인을 갖지 않습니다 (제자리 갱신)")
        if not as_list(p.fm.get("sources")):
            add("WARNING", "NO_SOURCES", f"{p.rel}: sources 가 비어 있습니다")
        stem = os.path.splitext(os.path.basename(p.rel))[0]
        if ID_RE.match(stem):
            add("WARNING", "ID_FILENAME", f"{p.rel}: 파일명이 ID 입니다 — 파일명은 슬러그(내용을 말하는 이름), ID 는 프론트매터에만 둡니다")

    for did, ps in by_id.items():
        if len(ps) > 1:
            add("ERROR", "DUP_ID", f"중복 ID {did}: " + ", ".join(x.rel for x in ps))
    head = {did: ps[0] for did, ps in by_id.items()}

    # 엣지: related(ID) + 본문 링크(페이지)
    in_edges = {p.id: set() for p in pages if p.id}
    for p in pages:
        p.out_ids, p.out_pages = set(), set()
        if not p.fm or "__error__" in p.fm or p.pdef is None:
            continue
        for r in as_list(p.fm.get("related")):
            if r not in head:
                add("ERROR", "MISSING_REF", f"{p.rel}: related 의 {r} 문서가 없습니다")
                continue
            p.out_ids.add(r)
        for link, target in body_links(p, wiki):
            if not os.path.exists(target):
                add("ERROR", "BROKEN_LINK", f"{p.rel}: 끊어진 링크 → {link}")
                continue
            q = path_to_page.get(target)
            if q is not None and q.id:
                p.out_pages.add(q.id)
        for tid in p.out_ids | p.out_pages:
            q = head.get(tid)
            if q is None or q.pdef is None:
                continue
            if tid in in_edges:
                in_edges[tid].add(p.id)
            if schema.rank(q.pdef["layer"]) > schema.rank(p.pdef["layer"]):
                add("ERROR", "DIRECTION", f"{p.rel} ({p.pdef['layer']}) → {tid} ({q.pdef['layer']}): 하위 계층이 상위 계층을 참조합니다 (역방향 오염)")

    # supersede 체인
    superseders = {}
    for p in pages:
        if not p.fm or p.pdef is None or p.pdef["kind"] != "frozen" or not p.id:
            continue
        sup = p.fm.get("supersedes")
        if sup:
            sup = str(sup)
            superseders.setdefault(sup, []).append(p.id)
            old = head.get(sup)
            if old is None:
                add("ERROR", "CHAIN", f"{p.rel}: supersedes={sup} 문서가 없습니다")
            else:
                if str(old.fm.get("status")) != "superseded":
                    add("ERROR", "CHAIN", f"{old.rel}: {p.id} 가 대체했는데 status 가 superseded 가 아닙니다")
                if str(old.fm.get("superseded_by", "")) != p.id:
                    add("ERROR", "CHAIN", f"{old.rel}: superseded_by 가 {p.id} 를 가리키지 않습니다 (현재 {old.fm.get('superseded_by')})")
        if str(p.fm.get("status")) == "superseded":
            nb = p.fm.get("superseded_by")
            if not nb:
                add("ERROR", "CHAIN", f"{p.rel}: status=superseded 인데 superseded_by 가 없습니다")
            else:
                nb = str(nb)
                new = head.get(nb)
                if new is None:
                    add("ERROR", "CHAIN", f"{p.rel}: superseded_by={nb} 문서가 없습니다")
                else:
                    if str(new.fm.get("supersedes", "")) != p.id:
                        add("ERROR", "CHAIN", f"{new.rel}: supersedes 가 {p.id} 를 가리키지 않습니다")
                    if mentions(p.body, nb) or (new.id in p.out_pages):
                        add("ERROR", "DIRECTION", f"{p.rel}: 옛 판 본문이 새 판 {nb} 를 언급합니다 (시간 방향 오염) — 프론트매터 두 필드만 허용")
        elif p.fm.get("superseded_by"):
            add("ERROR", "CHAIN", f"{p.rel}: superseded_by 가 있으면 status 는 superseded 여야 합니다")
    for old, news in superseders.items():
        if len(news) > 1:
            add("ERROR", "CHAIN", f"{old} 를 대체하는 페이지가 둘 이상입니다: {', '.join(news)} (head 는 하나)")

    # index 절 분해 (정책 C: superseded 는 `## 대체된 페이지` 절에만)
    sup_section, other_sections = "", ""
    if index_text is not None:
        cur_h, parts = "", {}
        for ln in index_text.splitlines():
            if ln.startswith("## "):
                cur_h = ln[3:].strip()
                continue
            parts[cur_h] = parts.get(cur_h, "") + ln + "\n"
        for h, body in parts.items():
            if "대체된 페이지" in h or "superseded" in h.lower():
                sup_section += body
            else:
                other_sections += body

    # 고아 · index · stale
    today = date.today()
    for p in pages:
        if not p.id or p.pdef is None or p.id not in head or head[p.id] is not p:
            continue
        if not (p.out_ids | p.out_pages) and not in_edges.get(p.id):
            add("WARNING", "ORPHAN", f"{p.id}: 어떤 페이지와도 연결되지 않았습니다 ({p.rel})")
        if index_text is not None and not mentions(index_text, p.id) and not mentions(index_text, p.rel):
            add("WARNING", "NOT_IN_INDEX", f"{p.id}: index.md 에 없습니다 ({p.rel})")
        elif index_text is not None and p.pdef["kind"] == "frozen" and str(p.fm.get("status")) == "superseded":
            in_other = mentions(other_sections, p.id) or mentions(other_sections, p.rel)
            in_sup = mentions(sup_section, p.id) or mentions(sup_section, p.rel)
            if in_other:
                add("WARNING", "INDEX_SUPERSEDED", f"{p.id}: 대체된 페이지가 index 카테고리 절에 남아 있습니다 — `## 대체된 페이지` 절로 옮기십시오 ({p.rel})")
            elif not in_sup:
                add("WARNING", "INDEX_SUPERSEDED", f"{p.id}: 대체된 페이지가 `## 대체된 페이지` 절에 없습니다 ({p.rel})")
        if p.pdef["kind"] == "living" and DATE_RE.match(str(p.fm.get("updated", ""))):
            d = datetime.strptime(str(p.fm["updated"]), "%Y-%m-%d").date()
            if (today - d).days > stale_days:
                add("INFO", "STALE", f"{p.id}: {(today - d).days}일간 갱신 없음 (updated={p.fm['updated']})")
    if index_text is not None:
        n = len(re.findall(r"^\s*-\s*\[", index_text, re.M))
        if n > 200:
            add("INFO", "BIG_INDEX", f"index.md 항목 {n}개 — 영역별 index 분리를 검토하십시오")
    return report(findings, severity, len(pages))


def report(findings, severity, npages):
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    findings.sort(key=lambda x: (order[x[0]], x[1], x[2]))
    counts = {k: 0 for k in order}
    for s, _, _ in findings:
        counts[s] += 1
    shown = [f for f in findings if not severity or order[f[0]] <= order[severity.upper()]]
    print(f"검사 페이지: {npages}개")
    cur = None
    for s, code, msg in shown:
        if s != cur:
            print(f"\n=== {s} ===")
            cur = s
        print(f"  [{code}] {msg}")
    print(f"\n합계  ERROR {counts['ERROR']}  WARNING {counts['WARNING']}  INFO {counts['INFO']}")
    return 1 if counts["ERROR"] else 0


# ---------- next-id ----------
def next_id(root, prefix):
    schema = Schema(root)
    prefix = prefix.upper()
    if schema.errors:
        for code, msg in schema.errors:
            print(f"[{code}] {msg}", file=sys.stderr)
        return 1
    if prefix not in {p["prefix"] for p in schema.pages.values()}:
        print(f"접두어 {prefix} 는 SCHEMA.md pages 에 없습니다: {sorted(p['prefix'] for p in schema.pages.values())}", file=sys.stderr)
        return 1
    mx, width = 0, 3
    for p in collect(root, schema):
        if p.id and p.id.startswith(prefix + "-"):
            num = p.id.split("-", 1)[1]
            if num.isdigit():
                mx, width = max(mx, int(num)), max(width, len(num))
    print(f"{prefix}-{mx + 1:0{width}d}")
    return 0


# ---------- backlinks ----------
def backlinks(root):
    schema = Schema(root)
    if schema.errors:
        for code, msg in schema.errors:
            print(f"[{code}] {msg}", file=sys.stderr)
        return 1
    wiki = os.path.join(root, "wiki")
    pages = [p for p in collect(root, schema) if p.fm and "__error__" not in p.fm]
    head = {}
    for p in pages:
        if p.id and p.id not in head:
            head[p.id] = p
    path_to_page = {os.path.normpath(p.full): p for p in pages}
    incoming = {p.id: set() for p in pages if p.id}
    for p in pages:
        if not p.id:
            continue
        targets = set(as_list(p.fm.get("related")))
        for _, t in body_links(p, wiki):
            q = path_to_page.get(t)
            if q and q.id:
                targets.add(q.id)
        for t in targets:
            if t in incoming and t != p.id:
                incoming[t].add(p.id)
    changed = 0
    for p in pages:
        if not p.id:
            continue
        srcs = sorted(incoming[p.id])
        stripped = BL_RE.sub("", p.text).rstrip("\n")
        if srcs:
            lines = [BL_START, "## 참조됨 (scripts/lint.py backlinks 가 생성 — 손으로 고치지 않는다)"]
            for sid in srcs:
                q = head[sid]
                relp = os.path.relpath(q.full, os.path.dirname(p.full)).replace(os.sep, "/")
                lines.append(f"- [{sid} {q.fm.get('title', '')}]({relp})")
            lines.append(BL_END)
            new = stripped + "\n\n" + "\n".join(lines) + "\n"
        else:
            new = stripped + "\n"
        if new != p.text:
            open(p.full, "w", encoding="utf-8").write(new)
            changed += 1
    print(f"백링크 갱신: {changed}개 페이지 변경 (전체 {len(pages)})")
    return 0


# ---------- check ----------
def check(root, files):
    schema = Schema(root)
    if schema.errors:
        for code, msg in schema.errors:
            print(f"[{code}] {msg}")
        return 1
    bad = 0
    for f in files:
        errs = []
        text = open(f, encoding="utf-8").read()
        fm, _ = parse_front_matter(text)
        if PLACEHOLDER_RE.search(text):
            errs.append("PLACEHOLDER 자리표시자 {{ }} 잔존")
        if fm is None:
            errs.append("NO_ID 프론트매터 없음")
        elif "__error__" in fm:
            errs.append(f"MISSING_FIELD 파싱 실패 — {fm['__error__']}")
        else:
            pdef = schema.by_type.get(str(fm.get("type")))
            if pdef is None:
                errs.append(f"BAD_TYPE type={fm.get('type')} 가 SCHEMA.md 에 없음")
            else:
                kind = pdef["kind"]
                for k in schema.required(kind):
                    if k not in fm:
                        errs.append(f"MISSING_FIELD {k} ({kind})")
                pid = str(fm.get("id", ""))
                if not ID_RE.match(pid):
                    errs.append(f"BAD_ID {pid}")
                elif pid.split("-")[0] != pdef["prefix"]:
                    errs.append(f"BAD_ID 접두어 {pid.split('-')[0]} ≠ {pdef['prefix']}")
                allowed = schema.allowed_status(kind)
                if allowed and str(fm.get("status")) not in allowed:
                    errs.append(f"BAD_STATUS {fm.get('status')} — {allowed}")
                if kind == "frozen" and "updated" in fm:
                    errs.append("FROZEN_UPDATED frozen 에 updated")
                for k in ("created", "updated"):
                    if k in fm and not DATE_RE.match(str(fm[k])):
                        errs.append(f"BAD_DATE {k}={fm[k]}")
        rel = os.path.relpath(f, root)
        if errs:
            bad += 1
            print(f"✗ {rel}")
            for e in errs:
                print(f"    {e}")
        else:
            print(f"✓ {rel}")
    return 1 if bad else 0


def main(argv):
    args = list(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--root" in args:
        i = args.index("--root")
        root = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "lint":
        sev, stale = None, 180
        if "--severity" in rest:
            i = rest.index("--severity") + 1
            sev = rest[i].lower() if i < len(rest) else ""
            if sev not in ("error", "warning", "info"):
                print("--severity 는 error|warning|info 중 하나입니다", file=sys.stderr)
                return 2
        if "--stale-days" in rest:
            stale = int(rest[rest.index("--stale-days") + 1])
        return lint(root, sev, stale)
    if cmd == "next-id":
        if not rest:
            print("사용법: next-id PREFIX", file=sys.stderr)
            return 2
        return next_id(root, rest[0])
    if cmd == "backlinks":
        return backlinks(root)
    if cmd == "check":
        if not rest:
            print("사용법: check <file>...", file=sys.stderr)
            return 2
        return check(root, rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
