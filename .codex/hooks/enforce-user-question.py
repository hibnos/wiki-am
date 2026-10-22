#!/usr/bin/env python3
"""Codex project skill question guidance; stdin hook JSON -> additionalContext.

UserPromptSubmit: explicit $skill-name mentions (also legacy /skill-name).
PostToolUse: shell reads mentioning a project SKILL.md path. This is a
best-effort read detector, not a complete skill activation or enforcement API.
"""
import json
from pathlib import Path
import re
import sys

RULE = (
    "[프로젝트 스킬 질문 규칙] {names} 실행 중 질문·확인·선택이 필요한 경우, "
    "현재 환경과 모드에서 사용 가능한 사용자 입력 도구를 우선 사용한다. "
    "request_user_input_async가 있으면 사용하고, request_user_input은 현재 모드에서 허용할 때만 사용한다. "
    "도구 스키마에 맞게 간결한 선택지를 구성하고 권장안을 먼저 둔다. "
    "입력 도구를 사용할 수 없으면 일반 대화로 질문한다. 이미 받은 답이나 승인은 다시 묻지 않는다. "
    "스킬이 요구하는 필수 입력값이 빠졌으면 답을 기다리며, 임의 추정으로 의존 작업을 진행하지 않는다. "
    "이 규칙은 불필요한 질문이나 추가 승인을 요구하지 않는다."
)


def installed_skills(root):
    return {p.parent.name: p for p in (root / '.agents/skills').glob('*/SKILL.md')}


def matching_skills(data, root):
    skills = installed_skills(root)
    event = data.get('hook_event_name')
    if event == 'UserPromptSubmit':
        prompt = data.get('prompt')
        if not isinstance(prompt, str):
            return []
        names = set(re.findall(r'(?<![\w$\\])\$([a-z0-9]+(?:-[a-z0-9]+)*)(?![\w-])', prompt))
        legacy = re.match(r'^\s*/([a-z0-9]+(?:-[a-z0-9]+)*)(?=\s|$)', prompt)
        if legacy:
            names.add(legacy.group(1))
        return sorted(names & skills.keys())
    if event == 'PostToolUse' and data.get('tool_name') in ('Bash', 'exec_command', 'shell_command', 'shell'):
        args = data.get('tool_input')
        if not isinstance(args, dict):
            return []
        command = args.get('command', args.get('cmd', ''))
        if isinstance(command, list):
            command = ' '.join(x for x in command if isinstance(x, str))
        if not isinstance(command, str) or not re.search(r'\b(cat|sed|head|tail|rg|less|more)\s', command):
            return []
        # Require a path token, rather than a bare skill name or tool output.
        cwd = Path(data.get('cwd') or root)
        tokens = re.findall(r'[^\s\x22\x27;|&()]+', command)
        found = []
        for name, path in skills.items():
            for token in tokens:
                if token.endswith('/SKILL.md'):
                    candidate = Path(token)
                    if not candidate.is_absolute():
                        candidate = cwd / candidate
                    if candidate.resolve() == path.resolve():
                        found.append(name)
                        break
        return sorted(found)
    return []


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError('hook input must be an object')
    except (ValueError, UnicodeError) as exc:
        print(f'Invalid hook input: {exc}', file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[2]
    names = matching_skills(data, root)
    if names:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': data['hook_event_name'],
            'additionalContext': RULE.format(names=', '.join(names)),
        }}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
