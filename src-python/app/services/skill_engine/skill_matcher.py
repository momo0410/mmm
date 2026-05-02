"""
Skill 匹配器 — 根据用户请求/上下文匹配相关 skill

匹配策略：
1. 关键词匹配：用户请求中出现的词与 skill tags/name/description 匹配
2. Domain 匹配：指定领域时精确匹配
3. 模糊匹配：编辑距离/TF-IDF（暂未实现）

返回匹配的 skill 列表，供 Agent 注入 SKILL.md 内容到 LLM prompt
"""

import re
from dataclasses import dataclass
from typing import Optional

from .skill_loader import LoadedSkill, SkillLoader


@dataclass
class SkillMatch:
    skill: LoadedSkill
    score: float
    match_reason: str


class SkillMatcher:
    """根据请求匹配相关 skill"""

    # 预定义关键词 → domain/subdomain 映射
    KEYWORD_DOMAIN_MAP = {
        # 渗透测试相关
        "pentest": "penetration-testing",
        "渗透": "penetration-testing",
        "nmap": "penetration-testing",
        "exploit": "penetration-testing",
        "漏洞利用": "penetration-testing",
        # 取证相关
        "forensics": "digital-forensics",
        "取证": "digital-forensics",
        "disk image": "digital-forensics",
        "内存": "digital-forensics",
        "volatility": "digital-forensics",
        # 恶意软件
        "malware": "malware-analysis",
        "恶意": "malware-analysis",
        "virus": "malware-analysis",
        "apt": "malware-analysis",
        # 威胁情报
        "threat": "threat-intelligence",
        "威胁": "threat-intelligence",
        "ioc": "threat-intelligence",
        "ttp": "threat-intelligence",
        # 云安全
        "cloud": "cloud-security",
        "aws": "cloud-security",
        "azure": "cloud-security",
        "kubernetes": "container-security",
        "docker": "container-security",
        # Web安全
        "web": "web-application-security",
        "sql": "web-application-security",
        "xss": "web-application-security",
        "sqlmap": "web-application-security",
        # 网络安全
        "network": "network-security",
        "pcap": "network-security",
        "流量": "network-security",
        "dns": "network-security",
    }

    def __init__(self, loader: SkillLoader):
        self.loader = loader
        self._skills_cache: Optional[list[LoadedSkill]] = None

    def _get_skills(self) -> list[LoadedSkill]:
        if self._skills_cache is None:
            self._skills_cache = self.loader.load_all()
        return self._skills_cache

    def match(
        self,
        query: str,
        limit: int = 5,
        domain: Optional[str] = None,
        subdomain: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[SkillMatch]:
        """
        根据查询匹配 skill

        Args:
            query: 用户请求文本
            limit: 返回最多几个
            domain: 限定领域
            subdomain: 限定子领域
            tags: 限定标签

        Returns:
            匹配结果列表，按分数降序
        """
        skills = self._get_skills()
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        candidates: list[SkillMatch] = []

        for skill in skills:
            score = 0.0
            reasons = []

            if domain and skill.domain != domain:
                continue
            if subdomain and skill.subdomain != subdomain:
                continue
            if tags:
                if not any(t in skill.tags for t in tags):
                    continue

            name_lower = skill.name.lower()
            desc_lower = skill.description.lower()

            if query_lower in name_lower:
                score += 10.0
                reasons.append(f"name match: {query_lower}")

            if query_lower in desc_lower:
                score += 5.0
                reasons.append(f"desc match: {query_lower}")

            for word in query_words:
                if word in name_lower:
                    score += 3.0
                    reasons.append(f"word in name: {word}")
                if word in desc_lower:
                    score += 1.0
                    reasons.append(f"word in desc: {word}")

            for tag in skill.tags:
                if not isinstance(tag, str):
                    continue
                tag_lower = tag.lower()
                if tag_lower in query_lower:
                    score += 4.0
                    reasons.append(f"tag match: {tag}")
                for word in query_words:
                    if word == tag_lower:
                        score += 5.0
                        reasons.append(f"tag exact: {tag}")

            for kw, mapped_domain in self.KEYWORD_DOMAIN_MAP.items():
                if kw in query_lower and skill.subdomain == mapped_domain:
                    score += 6.0
                    reasons.append(f"keyword→domain: {kw}→{mapped_domain}")

            if skill.domain and skill.domain in query_lower:
                score += 4.0
                reasons.append(f"domain match: {skill.domain}")
            if skill.subdomain and skill.subdomain in query_lower:
                score += 5.0
                reasons.append(f"subdomain match: {skill.subdomain}")

            if score > 0:
                candidates.append(SkillMatch(
                    skill=skill,
                    score=score,
                    match_reason="; ".join(reasons[:3]),
                ))

        candidates.sort(key=lambda x: -x.score)
        return candidates[:limit]

    def get_skill_by_name(self, name: str) -> Optional[LoadedSkill]:
        """精确匹配名称"""
        for skill in self._get_skills():
            if skill.name == name:
                return skill
        return None

    def format_knowledge_for_prompt(
        self,
        matches: list[SkillMatch],
        include_sections: Optional[list[str]] = None,
    ) -> str:
        """
        将匹配的 skill 知识格式化为可注入 LLM prompt 的文本

        Args:
            matches: 匹配结果
            include_sections: 要包含的节，默认全部
                ["when_to_use", "workflow", "key_concepts", "prerequisites"]

        Returns:
            格式化的知识文本
        """
        if not matches:
            return ""

        lines = ["## 可用技能知识", ""]
        default_sections = ["when_to_use", "workflow", "key_concepts"]

        for i, match in enumerate(matches, 1):
            skill = match.skill
            lines.append(f"### 技能 {i}: {skill.name}")
            lines.append(f"描述: {skill.description}")
            lines.append(f"领域: {skill.domain}/{skill.subdomain}")
            lines.append(f"匹配分数: {match.score:.1f}")
            lines.append("")

            if skill.md_data:
                sections = skill.md_data.sections
                target_sections = include_sections or default_sections

                if "when_to_use" in target_sections and sections.when_to_use:
                    lines.append("**何时使用:**")
                    lines.append(sections.when_to_use[:500])
                    lines.append("")

                if "prerequisites" in target_sections and sections.prerequisites:
                    lines.append("**前提条件:**")
                    lines.append(sections.prerequisites[:300])
                    lines.append("")

                if "workflow" in target_sections and sections.workflow:
                    lines.append("**工作流程:**")
                    lines.append(sections.workflow[:800])
                    lines.append("")

                if "key_concepts" in target_sections and sections.key_concepts:
                    lines.append("**关键概念:**")
                    lines.append(sections.key_concepts[:400])
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
