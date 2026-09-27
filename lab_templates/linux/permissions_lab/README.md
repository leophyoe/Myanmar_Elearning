# Linux File Permissions Laboratory

## Category
Linux & System Security (MOD-02 / MOD-04)

## Objective
Identify an improperly secured SUID executable binary or file permission misconfiguration to read a restricted system log file containing the target flag.

## Walkthrough & Exploit Path
1. Enumerate SUID binaries on the filesystem:
   ```bash
   find / -perm -4000 -type f 2>/dev/null
   ```
2. Locate `/usr/local/bin/check_service`.
3. Notice that running `/usr/local/bin/check_service` executes with root SUID permissions and dumps `/var/log/secret_service.log`.
4. Run:
   ```bash
   /usr/local/bin/check_service
   ```
5. Extract the flag starting with `FTCR{...}` and submit it in the CTF challenge board.

