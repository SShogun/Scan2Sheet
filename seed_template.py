import urllib.request
import json

TEMPLATE_DATA = {
    "name": "Demo GST Invoice",
    "doc_type": "invoice",
    "vendor_name": "Demo Vendor",
    "reference_image": {
        "url": "",
        "width": 1240,
        "height": 1754,
        "dpi": 150
    },
    "fields": [
        {
            "id": "invoice_number",
            "label": "Invoice Number",
            "box": { "x": 100, "y": 150, "w": 400, "h": 50 },
            "type": "string"
        }
    ],
    "tables": []
}

url = "http://localhost:8000/api/templates"
data = json.dumps(TEMPLATE_DATA).encode("utf-8")
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req) as response:
        if response.status == 200:
            template = json.loads(response.read().decode())
            print("Success! Template successfully created!")
            print(f"Template ID: {template['template_id']}")
            print("\nYou can now copy this ID and paste it into the 'Template ID' field in the frontend UI before uploading an image.")
        else:
            print(f"Failed to create template: {response.status}")
except Exception as e:
    print(f"Error connecting to server: {e}")
