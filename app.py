from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import insta_fetch

app = Flask(__name__)
app.secret_key = "change_this_secret_for_production"

# ------Pages------ #
@app.route("/")
def index():
    # If user is logged in, redirect to home page
    if session.get("user"):
        return redirect(url_for("home_page"))
    return redirect(url_for("login"))

@app.route("/login")
def login():
    # Simple login page
    return render_template("login.html")  # create this template

@app.route("/home")
def home_page():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("home.html", username=session["user"])

@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["user"])

@app.route("/reports")
def reports():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("reports.html", username=session["user"])

@app.route("/help")
def help_page():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("help.html", username=session["user"])

@app.route("/settings")
def settings():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("settings.html", username=session["user"])

@app.route('/logout')
def logout():
    session.clear()  # remove all session data
    return render_template("logout.html", message="You have successfully logged out.")

@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='icons/favicon.ico'))

# -------------------------------
# Example login action (for demonstration)
# -------------------------------
@app.route("/do_login", methods=["POST"])
def do_login():
    username = request.form.get("username", "Guest")
    session["user"] = username
    # Redirect to Home page after login
    return redirect(url_for("home_page"))

# -------------------------------
# APIs
# -------------------------------
@app.route("/get_comments")
def get_comments():
    try:
        comments = insta_fetch.fetch_and_moderate_comments()
        return jsonify({"comments": comments})
    except Exception as e:
        return jsonify({"error": str(e), "comments": []}), 500

@app.route("/set_preview_mode", methods=["POST"])
def set_preview_mode():
    data = request.get_json() or {}
    enabled = data.get("previewMode", True)
    insta_fetch.PREVIEW_MODE = bool(enabled)
    return jsonify({"success": True, "previewMode": insta_fetch.PREVIEW_MODE})

@app.route("/get_preview_mode")
def get_preview_mode():
    return jsonify({"previewMode": insta_fetch.PREVIEW_MODE})

@app.route("/reports_data")
def reports_data():
    try:
        data = insta_fetch.get_report_stats()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
