import os
import sqlite3
from flask import Flask, request, render_template_string

app = Flask(__name__)
FLAG = os.environ.get("FTCR_FLAG", "FTCR{sqli_classic_auth_bypass_2026}")

def init_db():
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.execute("CREATE TABLE users (id INT, username TEXT, password TEXT, role TEXT);")
    c.execute("INSERT INTO users VALUES (1, 'admin', 'SuperSecureSecretAdminPass99!', 'administrator');")
    c.execute("INSERT INTO users VALUES (2, 'guest', 'guest', 'user');")
    conn.commit()
    return conn

db = init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Internal Corp Portal - Secure Authentication</title>
    <style>
        body { font-family: monospace; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { background: #1e293b; padding: 30px; border-radius: 8px; border: 1px solid #334155; width: 350px; }
        input { width: 90%; padding: 8px; margin: 8px 0; background: #0f172a; border: 1px solid #475569; color: #38bdf8; }
        button { background: #0284c7; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 4px; }
        .msg { margin-top: 15px; padding: 10px; border-radius: 4px; }
        .success { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; }
        .error { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
    </style>
</head>
<body>
    <div class="box">
        <h2>🔒 Corp Gateway v2.4</h2>
        <form method="POST">
            <label>Username:</label><br>
            <input type="text" name="username" placeholder="admin" required><br>
            <label>Password:</label><br>
            <input type="password" name="password" placeholder="••••••••" required><br>
            <button type="submit">Authenticate</button>
        </form>
        {% if message %}
        <div class="msg {{ 'success' if success else 'error' }}">
            {{ message }}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    message = None
    success = False
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Intentionally vulnerable raw string concatenation
        query = f"SELECT username, role FROM users WHERE username = '{username}' AND password = '{password}'"
        c = db.cursor()
        try:
            c.execute(query)
            user = c.fetchone()
            if user:
                success = True
                message = f"Welcome, {user[0]}! Target Flag: {FLAG}"
            else:
                message = "Invalid authentication credentials."
        except Exception as e:
            message = f"Database Error: {str(e)}"

    return render_template_string(HTML_TEMPLATE, message=message, success=success)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

