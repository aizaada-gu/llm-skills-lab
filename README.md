# Skills

Each folder holds a `SKILL.md`: expert instructions the model follows when you pick
that skill in the guarded LLM page (Skill dropdown).

These 6 defensive Linux/security skills are copied from the community collection
https://github.com/mukul975/Anthropic-Cybersecurity-Skills (Apache-2.0, see LICENSE).

| Skill | Use it for |
|---|---|
| hardening-linux-endpoint-with-cis-benchmark | Securing a new Linux server (SSH, users, services, permissions) |
| detecting-port-scanning-with-fail2ban | Blocking SSH brute force and port scans with fail2ban |
| analyzing-linux-audit-logs-for-intrusion | Finding suspicious activity in auditd logs |
| analyzing-persistence-mechanisms-in-linux | Finding backdoors: cron, systemd, .bashrc, authorized_keys |
| detecting-privilege-escalation-attempts | Spotting attempts to become root |
| scanning-network-with-nmap-advanced | Scanning your own lab network with nmap |

## Add a new skill
1. Make a folder `skills/<skill-name>/`
2. Put a `SKILL.md` inside (a `name:` and `description:` header between `---` lines, then the instructions)
3. Restart `bash start.sh` and it appears in the dropdown
