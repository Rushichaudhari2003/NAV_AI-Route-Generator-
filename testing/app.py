from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send-location', methods=['POST'])
def receive_location():
    data = request.get_json()
    print("Received location:", data)
    return jsonify({
        "message": "Location received successfully",
        "your_location": {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude")
        }
    })

if __name__ == '__main__':
    app.run(debug=True)
