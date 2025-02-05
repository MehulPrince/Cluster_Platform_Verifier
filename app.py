from flask import Flask, request, jsonify, send_from_directory
import json
import os

app = Flask(__name__)

# Serve the static index.html file
@app.route('/')
def serve_frontend():
    return send_from_directory('', 'index.html')

# Endpoint to update the Config.json file
@app.route('/update_config', methods=['POST'])
def update_config():
    try:
        # Get the JSON data from the request
        new_data = request.get_json()

        # Write the data to Config.json
        with open('Config.json', 'w') as config_file:
            json.dump(new_data, config_file, indent=4)

        return jsonify({"message": "Config.json updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to retrieve the latest saved content from Config.json
@app.route('/get_config', methods=['GET'])
def get_config():
    try:
        # Read the data from Config.json
        with open('Config.json', 'r') as config_file:
            config_data = json.load(config_file)

        return jsonify(config_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to retrieve the content of output.txt
@app.route('/get_output', methods=['GET'])
def get_output():
    try:
        # Check if output.txt exists
        if not os.path.exists('output.txt'):
            return jsonify({"error": "output.txt file not found!"}), 404

        # Read the content of output.txt
        with open('output.txt', 'r') as output_file:
            output_data = output_file.read()

        return jsonify({"output": output_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# New endpoint to fetch PCI devices (mocked for now)
@app.route('/api/get-pci-devices', methods=['GET'])
def get_pci_devices():
    try:
        # In a real-world scenario, you would use a library like `psutil` or other tools
        # to scan for actual PCI devices. For now, we are returning a mocked list of PCI devices
        pci_devices = [
            {"device_id": "0000:00:1f.2", "device_name": "Ethernet Controller", "vendor_id": "8086"},
            {"device_id": "0000:00:1b.0", "device_name": "Audio Device", "vendor_id": "8086"},
            {"device_id": "0000:00:03.0", "device_name": "Storage Controller", "vendor_id": "8086"},
            {"device_id": "0000:00:0d.0", "device_name": "Graphics Controller", "vendor_id": "1002"}
        ]

        return jsonify({"pciDevices": pci_devices}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to execute Platform.py script (mocked for now)
@app.route('/execute_platform', methods=['POST'])
def execute_platform():
    try:
        # In a real-world scenario, you'd execute Platform.py here.
        # For now, returning a success response.
        return jsonify({"message": "Platform.py executed successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
