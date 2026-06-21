"""
SkillGenerator — 从渗透测试结果中自动生成可复用的 SKILL.md 技能文件

输入: 渗透完成后的 State 对象
输出: 按 service/vulnerability 类型生成 SKILL.md 到 skills/learned/ 目录

生成策略:
  - 成功的 exploit 路径 → 完整 exploit skill (检测+利用+验证)
  - 发现漏洞但未利用 → recon skill (仅检测步骤)
  - 失败的尝试 → 不生成
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Optional


# 已知服务 → 标准化 service tag
SERVICE_TAG_MAP = {
    "ftp": "ftp", "ssh": "ssh", "telnet": "telnet", "smtp": "smtp",
    "http": "http", "https": "https", "apache": "http", "nginx": "http",
    "tomcat": "tomcat", "smb": "smb", "microsoft-ds": "smb", "netbios-ssn": "smb",
    "mysql": "mysql", "postgres": "postgresql", "postgresql": "postgresql",
    "vnc": "vnc", "irc": "irc", "distcc": "distcc", "rmi": "java-rmi",
    "bindshell": "shell", "backdoor": "backdoor",
    "shell": "shell", "login": "login", "exec": "exec",
}


def _normalize_service_tag(service: str) -> str:
    lowered = str(service or "").strip().lower()
    for key, tag in SERVICE_TAG_MAP.items():
        if key in lowered:
            return tag
    return lowered.split()[0] if lowered else "unknown"


def _sanitize_name(text: str) -> str:
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:64] or "unnamed"


class SkillGenerator:
    """从渗透测试 State 中自动生成 SKILL.md 技能文件"""

    def __init__(self, skills_root: str):
        self.skills_root = skills_root
        self.learned_dir = os.path.join(skills_root, "learned")

    def generate_from_state(self, state) -> list[str]:
        """
        从完成的渗透状态中提取经验，生成 skill 文件。

        Returns:
            生成的 skill 文件路径列表
        """
        os.makedirs(self.learned_dir, exist_ok=True)

        data = state.data if hasattr(state, "data") else state
        findings = data.get("findings", [])
        actions = data.get("actions_taken", [])
        credentials = data.get("credentials", [])
        vulnerabilities = data.get("vulnerabilities", [])
        targets = data.get("targets", [])
        sessions = data.get("sessions", [])

        generated_files: list[str] = []

        # 1. 按 service 聚类成功的攻击路径
        attack_paths = self._extract_attack_paths(
            findings, actions, credentials, vulnerabilities, sessions, targets
        )

        # 2. 每条攻击路径生成一个 skill
        for path in attack_paths:
            skill_content = self._render_skill_md(path)
            filename = f"{_sanitize_name(path['name'])}.md"
            filepath = os.path.join(self.learned_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(skill_content)
            generated_files.append(filepath)

        # 3. 生成汇总 skill
        if attack_paths:
            summary = self._render_summary_skill(attack_paths, targets)
            summary_path = os.path.join(self.learned_dir, "pentest-summary.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            generated_files.append(summary_path)

        return generated_files

    def _extract_attack_paths(
        self,
        findings: list[dict],
        actions: list[dict],
        credentials: list[dict],
        vulnerabilities: list[dict],
        sessions: list[dict],
        targets: list[str],
    ) -> list[dict]:
        """从渗透结果中提取成功的攻击路径"""
        paths: list[dict] = []

        # 按 port+service 聚类 findings
        service_map: dict[tuple[int, str], dict] = {}
        for f in findings:
            if not isinstance(f, dict):
                continue
            port = f.get("port")
            if isinstance(port, str) and port.isdigit():
                port = int(port)
            if not isinstance(port, int):
                continue
            service = str(f.get("service", "")).strip()
            ip = str(f.get("ip", "")).strip() or (targets[0] if targets else "")
            key = (port, _normalize_service_tag(service))
            if key not in service_map:
                service_map[key] = {
                    "port": port,
                    "service": service,
                    "ip": ip,
                    "tag": _normalize_service_tag(service),
                }

        # 找出每个 service 相关的成功 action
        successful_actions = [
            a for a in actions
            if isinstance(a, dict) and a.get("status") == "completed"
            and a.get("tool") not in {"_doctor", "_llm_wait", "_token_usage", "_done", "_skip", "_llm_error"}
        ]

        # 找出有 exploit 成功证据的 action
        exploit_actions = [
            a for a in successful_actions
            if self._has_exploit_evidence(a)
        ]

        # 为每个高价值 service 生成攻击路径
        for (port, tag), svc_info in service_map.items():
            # 找与此 service 相关的成功 action
            related_actions = [
                a for a in successful_actions
                if self._action_targets_port(a, port) or self._action_targets_service(a, svc_info["service"])
            ]
            if not related_actions:
                continue

            # 找相关的 credential
            related_creds = [
                c for c in credentials
                if isinstance(c, dict) and self._cred_matches_service(c, tag)
            ]

            # 找相关的 vulnerability
            related_vulns = [
                v for v in vulnerabilities
                if isinstance(v, dict) and self._vuln_matches_port(v, port)
            ]

            # 找是否有 exploit 成功
            exploit_success = any(
                self._action_targets_port(a, port) and self._has_exploit_evidence(a)
                for a in exploit_actions
            )

            # 找成功的命令
            successful_commands = [
                {"tool": a.get("tool", ""), "args": a.get("args", ""), "result": (a.get("result", "") or "")[:200]}
                for a in related_actions
                if a.get("tool") not in {"_doctor", "_llm_wait", "_token_usage", "_done", "_skip", "_llm_error"}
            ]

            path = {
                "name": f"exploit-{tag}-{port}" if exploit_success else f"recon-{tag}-{port}",
                "port": port,
                "service": svc_info["service"],
                "tag": tag,
                "ip": svc_info["ip"],
                "exploit_success": exploit_success,
                "credentials": related_creds,
                "vulnerabilities": related_vulns,
                "commands": successful_commands,
                "sessions": [s for s in sessions if isinstance(s, dict)],
            }
            paths.append(path)

        # 按 exploit 成功优先排序
        paths.sort(key=lambda p: (not p["exploit_success"], p["port"]))
        return paths

    def _has_exploit_evidence(self, action: dict) -> bool:
        text = " ".join(str(action.get(k, "")) for k in ("result", "error", "full_stdout")).lower()
        indicators = [
            "uid=0(", "root@", "meterpreter session", "command shell session",
            "shell opened", "session opened", "login successful", "access granted",
            "interactive_session_connected", "nt authority\\system",
        ]
        return any(ind in text for ind in indicators)

    def _action_targets_port(self, action: dict, port: int) -> bool:
        explicit_ports = {
            int(p) for p in (action.get("ports") or [])
            if isinstance(p, int) or str(p).isdigit()
        }
        if port in explicit_ports:
            return True
        args = str(action.get("args", ""))
        return bool(re.search(rf"(?:^|\D){port}(?:\D|$)", args))

    def _action_targets_service(self, action: dict, service: str) -> bool:
        if not service:
            return False
        args = str(action.get("args", "")).lower()
        surface = str(action.get("surface", "")).lower()
        svc_lower = service.lower()
        return svc_lower in args or svc_lower in surface

    def _cred_matches_service(self, cred: dict, tag: str) -> bool:
        source = str(cred.get("source", "")).lower()
        kind = str(cred.get("kind", "")).lower()
        return tag in source or tag in kind or not source

    def _vuln_matches_port(self, vuln: dict, port: int) -> bool:
        vuln_port = vuln.get("port")
        if isinstance(vuln_port, int):
            return vuln_port == port
        if isinstance(vuln_port, str) and vuln_port.isdigit():
            return int(vuln_port) == port
        target = str(vuln.get("target", ""))
        return str(port) in target

    def _render_skill_md(self, path: dict) -> str:
        """渲染单个攻击路径为 SKILL.md"""
        tag = path["tag"]
        port = path["port"]
        service = path["service"]
        exploit_success = path["exploit_success"]
        name = path["name"]

        # YAML frontmatter
        tags = [tag, f"port-{port}"]
        if exploit_success:
            tags.append("exploit")
        else:
            tags.append("recon")
        if path["vulnerabilities"]:
            tags.append("vulnerability")

        description = (
            f"{'成功利用' if exploit_success else '检测到'} {service} 服务 (端口 {port})"
        )
        if path["credentials"]:
            creds_desc = ", ".join(f"{c.get('username','?')}" for c in path["credentials"][:3])
            description += f"，凭据: {creds_desc}"

        lines = [
            "---",
            f"name: {name}",
            f"description: '{description}'",
            f"domain: penetration-testing",
            f"subdomain: {tag}",
            f"tags: [{', '.join(tags)}]",
            f"version: '1.0'",
            f"source: auto-generated",
            "---",
            "",
            f"# {service.upper()} 端口 {port} {'利用' if exploit_success else '检测'} Skill",
            "",
            "## When to Use",
            f"- 目标开放端口 {port}/{service}",
            f"- nmap 服务指纹匹配 `{service}`",
            "",
            "## Prerequisites",
            f"- 目标可达，端口 {port} 开放",
        ]

        if path["credentials"]:
            lines.append("- 需要以下凭据:")
            for c in path["credentials"][:3]:
                lines.append(f"  - 用户名: `{c.get('username', '?')}` / 密码: `{c.get('password', '?')}`")

        lines.append("")
        lines.append("## Workflow")

        if exploit_success:
            lines.append(f"### 步骤 1: 确认服务")
            lines.append(f"```")
            lines.append(f"nmap -Pn -sV -p {port} TARGET")
            lines.append(f"```")
            lines.append("")

            if path["commands"]:
                lines.append("### 步骤 2: 利用")
                for i, cmd in enumerate(path["commands"][:5], start=1):
                    lines.append(f"```")
                    lines.append(f"# {cmd.get('tool', '?')}: {cmd.get('args', '?')[:120]}")
                    lines.append(f"```")
                lines.append("")

            if path["credentials"]:
                lines.append("### 步骤 3: 凭据利用")
                for c in path["credentials"][:3]:
                    lines.append(f"- `{c.get('username', '?')}` / `{c.get('password', '?')}` ({c.get('source', '?')})")
                lines.append("")

            lines.append("### 验证")
            lines.append("```")
            lines.append("id; whoami; uname -a")
            lines.append("```")
        else:
            lines.append(f"### 检测")
            lines.append(f"```")
            lines.append(f"nmap -Pn -sC -sV -p {port} TARGET")
            lines.append(f"```")
            if path["vulnerabilities"]:
                lines.append("")
                lines.append("### 发现的漏洞")
                for v in path["vulnerabilities"][:5]:
                    lines.append(f"- [{v.get('severity', '?')}] {v.get('name', '?')}")

        if path["sessions"]:
            lines.append("")
            lines.append("## 注意事项")
            lines.append(f"- 已获得 {len(path['sessions'])} 个会话")

        lines.append("")
        return "\n".join(lines)

    def _render_summary_skill(self, paths: list[dict], targets: list[str]) -> str:
        """渲染汇总 skill"""
        exploit_paths = [p for p in paths if p["exploit_success"]]
        recon_paths = [p for p in paths if not p["exploit_success"]]
        target_str = ", ".join(targets[:3]) if targets else "unknown"

        lines = [
            "---",
            f"name: pentest-summary",
            f"description: '渗透测试汇总: {len(exploit_paths)} 个成功利用, {len(recon_paths)} 个检测'",
            f"domain: penetration-testing",
            f"subdomain: summary",
            f"tags: [summary, pentest, {'exploit' if exploit_paths else 'recon'}]",
            f"version: '1.0'",
            f"source: auto-generated",
            "---",
            "",
            f"# 渗透测试汇总报告",
            "",
            f"## 目标",
            f"- {target_str}",
            "",
            f"## 成功利用 ({len(exploit_paths)})",
        ]

        for p in exploit_paths:
            creds = ""
            if p["credentials"]:
                creds = f" (凭据: {p['credentials'][0].get('username', '?')})"
            lines.append(f"- 端口 {p['port']}/{p['tag']}{creds}")

        if recon_paths:
            lines.append("")
            lines.append(f"## 已检测 ({len(recon_paths)})")
            for p in recon_paths:
                lines.append(f"- 端口 {p['port']}/{p['tag']}")

        lines.append("")
        return "\n".join(lines)
