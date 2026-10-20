#!/usr/bin/env python3
"""설치된 프로젝트 skill 실행 시 사용자 질문은 AskUserQuestion 으로만 하도록 지시를 주입하는 hook.

- PostToolUse(Skill): Claude 가 Skill 도구로 skill 을 불러온 직후
- UserPromptSubmit: 사용자가 /<skill-name> 으로 skill 을 직접 호출했을 때
"""
import json
import os
import sys
from pathlib import Path

RULE = (
    "[필수 규칙] skill '{name}' 실행 중 사용자에게 질문·확인·선택을 요청해야 하면 "
    "반드시 AskUserQuestion 도구를 사용한다. 도구를 사용할 수 있는데 일반 텍스트로 질문하고 턴을 끝내지 않는다. "
    "질문 전에 선택지(최대 4개, 권장안은 첫 번째에 '(Recommended)' 표기)를 구성하고, "
    "선택지에 없는 값은 사용자가 Other 로 입력하도록 안내한다. "
    "AskUserQuestion 을 사용할 수 있으면 skill 문서의 다른 질문 방식보다 우선한다. "
    "도구를 사용할 수 없는 환경(비대화형 실행·권한 차단 등)에서는 skill 문서의 대안 절차를 따르고, "
    "필수 입력값을 추정해서 진행하지 않는다."
)


def installed_skills() -> set[str]:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "skills"
    return {p.parent.name for p in root.glob("*/SKILL.md")}


def emit(event: str, name: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": RULE.format(name=name),
        }
    }, ensure_ascii=False))


def main() -> None:
    data = json.load(sys.stdin)
    event = data.get("hook_event_name")
    skills = installed_skills()

    if event == "PostToolUse":
        name = (data.get("tool_input") or {}).get("skill", "")
        name = name.split(":")[-1]
        if name in skills:
            emit(event, name)
    elif event == "UserPromptSubmit":
        prompt = data.get("prompt", "").lstrip()
        if prompt.startswith("/"):
            name = prompt[1:].split(maxsplit=1)[0] if len(prompt) > 1 else ""
            if name in skills:
                emit(event, name)


if __name__ == "__main__":
    main()
