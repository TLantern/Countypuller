#!/usr/bin/env python3
import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

# Add the scripts directory to Python path
scripts_path = os.path.join(os.path.dirname(__file__), '../../../../Chatbot/cc-frontend/scripts')
sys.path.insert(0, scripts_path)

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("address_enrichment_pipeline", 
                                                  os.path.join(scripts_path, "address_enrichment_pipeline.py"))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        enrich_address = module.enrich_address
    else:
        raise ImportError("Could not load module")
except (ImportError, AttributeError, FileNotFoundError):
    def enrich_address(address):
        return {
            'canonical_address': address,
            'attomid': None,
            'est_balance': None,
            'available_equity': None,
            'ltv': None,
            'error': 'Address enrichment pipeline not available'
        }

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Get content length
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Read the request body
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            # Extract address from request
            address = data.get('address', '')
            
            if not address:
                self.send_error(400, "Address is required")
                return
            
            # Process the address
            result = enrich_address(address)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = json.dumps(result)
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# For Vercel
def handler_function(request):
    if request.method == 'POST':
        try:
            data = request.get_json()
            address = data.get('address', '')
            
            if not address:
                return {'error': 'Address is required'}, 400
            
            result = enrich_address(address)
            return result
            
        except Exception as e:
            return {'error': f'Internal server error: {str(e)}'}, 500
    
    return {'error': 'Method not allowed'}, 405 