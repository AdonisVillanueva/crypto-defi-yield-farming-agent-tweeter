from flask import Flask, request

app = Flask(__name__)

@app.route('/callback')
def callback():
    """Handle incoming requests (if needed)."""
    # This endpoint can be used for other purposes, but not for OAuth
    return "Callback received! You can close this window."

if __name__ == "__main__":
    app.run(port=8000) 