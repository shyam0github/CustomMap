from flask import Flask, request, jsonify, send_file, render_template_string
import google.generativeai as genai
import json
import re
import requests
import urllib.parse
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("MAPS_API_KEY")

app = Flask(__name__)
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-pro-exp')

HTML_TEMPLATE = '''
<form method="post" action="/get-coordinates">
    <h2>Location Prompt</h2>
    <input type="text" name="prompt" value="{{ prompt }}" style="width:400px;" placeholder="Enter a location-based prompt">
    <input type="submit" value="Generate Map">
</form>
{% if places %}
<hr>
<div style="display:flex; gap:40px;">
    <div>
        <h3>Generated Map</h3>
        <label style="position:absolute; top:10px; right:20px;">
            <input type="checkbox" id="toggleLabels" checked onchange="updateMap()"> ✅ Show extracted location names
        </label><br><br>
        <img id="mapImage" src="/map.png?labels=1" alt="Map Image" style="border:1px solid #ccc;"><br><br>
    </div>
    <div>
        <h3>Historical Facts</h3>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr><th>Location</th><th>Historical Fact</th></tr>
            {% for p in places %}
            <tr><td>{{ p.name }}</td><td>{{ p.fact }}</td></tr>
            {% endfor %}
        </table>
    </div>
</div>
<script>
    function updateMap() {
        const show = document.getElementById('toggleLabels').checked ? 1 : 0;
        document.getElementById('mapImage').src = '/map.png?labels=' + show + '&t=' + new Date().getTime();
    }
</script>
<br>
<a href="/download-json">⬇️ Download JSON</a>
{% endif %}
'''

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE, prompt="", places=None)

@app.route('/get-coordinates', methods=['POST'])
def get_coordinates():
    prompt = request.form.get("prompt")

    full_prompt = f"""
You are an AI assistant. Given a user prompt that may mention one or more locations, extract each distinct place and return a JSON list.

Each item must contain:
- "name" (name of the location),
- "latitude",
- "longitude",
- "fact" (one historical fact about that location),
- "type" (either "country", "city", or "region")

Only return the raw JSON array.
Prompt: \"\"\"{prompt}\"\"\"
"""

    try:
        response = model.generate_content(full_prompt)
        cleaned = re.sub(r"```(?:json)?|```", "", response.text).strip()
        coords = json.loads(cleaned)

        with open("coordinates.json", "w") as f:
            json.dump(coords, f)

        return render_template_string(HTML_TEMPLATE, prompt=prompt, places=coords)

    except Exception as e:
        return jsonify({
            "error": "Could not parse response from Gemini",
            "details": str(e),
            "raw_response": response.text if 'response' in locals() else "No response"
        }), 500

@app.route('/download-json')
def download_json():
    return send_file("coordinates.json", as_attachment=True)

@app.route('/map.png')
def map_png():
    show_labels = request.args.get("labels", "1") == "1"
    try:
        with open("coordinates.json", "r") as f:
            places = json.load(f)
    except Exception as e:
        return jsonify({"error": "Could not load coordinates", "details": str(e)}), 500

    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    marker_params = []

    for place in places:
        lat = place["latitude"]
        lng = place["longitude"]
        name = urllib.parse.quote(place["name"])
        marker = f"markers=color:red%7Clabel:%7C{lat},{lng}"
        if show_labels:
            marker += f"&markers=label:{name}%7C{lat},{lng}"
        marker_params.append(marker)

    markers = "&".join(marker_params)

    types = set([p.get("type", "").lower() for p in places])
    border_type = "country" if "country" in types else "province"

    style = (
        "style=element:labels|visibility:off"
        "&style=feature:road|visibility:off"
        "&style=feature:transit|visibility:off"
        "&style=feature:poi|visibility:off"
        "&style=feature:landscape|visibility:simplified"
        "&style=feature:water|visibility:simplified"
        f"&style=feature:administrative.{border_type}|visibility:on"
    )

    map_url = f"{base_url}?size=800x600&{markers}&{style}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(map_url)

    with open("map.png", "wb") as f:
        f.write(response.content)

    return send_file("map.png", mimetype="image/png")

if __name__ == '__main__':
    app.run(debug=True)
