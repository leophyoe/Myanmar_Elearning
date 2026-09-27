# SQL Injection Basics Laboratory

## Category
Web Application Security & OWASP Top 10 (MOD-07)

## Objective
Bypass the web login form by injecting classic SQL syntax into the username field to authenticate as the administrator without knowing the password.

## Exploit Walkthrough
1. Access the web interface at port 5000.
2. In the username field, input the standard SQL injection payload:
   ```sql
   admin' OR 1=1 --
   ```
3. Enter any arbitrary text in the password field.
4. Submit the form. The underlying SQL query resolves to:
   ```sql
   SELECT username, role FROM users WHERE username = 'admin' OR 1=1 --' AND password = '...'
   ```
5. The administrator session will be granted, revealing the dynamic `FTCR{...}` flag.

