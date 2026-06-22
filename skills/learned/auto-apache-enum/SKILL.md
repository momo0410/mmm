---
name: auto-apache-enum
description: 自动学习的 apache-enum exploit 技能。未成功。目标: ajp13 Apache Jserv (Protocol v1.3):8009
domain: penetration-testing
subdomain: auto-learned
tags:
  - apache-enum
  - web-enum
  - auto-learned
  - medium
version: '1.0'
metadata:
  generated_at: 2026-06-22T13:28:25.183702
  target: 192.168.136.137
  success: False
  elapsed_seconds: 8.9
  difficulty: medium
  category: web-enum
  evidence: []
---

# Auto-Learned Skill: apache-enum

## When to Use
当检测到 **ajp13 Apache Jserv (Protocol v1.3)** 服务 (端口 8009) 时自动触发。
类别: web-enum | 难度: medium | 状态: 未成功

## Prerequisites
- Kali Linux with metasploit-framework
- 目标端口 8009 开放

## Workflow

### 执行步骤 (耗时 8.9s)

#### Step 1
```bash
nikto -h 192.168.136.137:8009 -C all 2>&1 | tail -20
```

#### Step 2
```bash
nmap --script http-vuln*,http-enum -p 8009 192.168.136.137 2>/dev/null
```

## Optimization Notes
- 实际耗时: 8.9s
- 难度评级: medium
- 可靠性: 低

## Key Concepts
| 属性 | 值 |
|------|-----|
| 目标服务 | ajp13 Apache Jserv (Protocol v1.3) |
| 目标端口 | 8009 |
| 攻击类别 | web-enum |
| 成功状态 | 未成功 |
| 耗时 | 8.9s |
