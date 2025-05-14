import os
import json
import logging
import base64

from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
from twilio.rest import Client
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

active_calls = {}

@app.route('/make-call', methods=['POST'])
def make_call():
    """Endpoint to initiate a call using Twilio's API"""
    try:
        data = request.get_json()
        to_number = data.get('to_number')
        
        if not to_number:
            return {'error': 'Missing destination phone number'}, 400
            
        call = client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{request.url_root}handle-call", 
        )
        
        active_calls[call.sid] = {'status': 'initiated', 'transcription': []}
        
        return {'message': f'Call initiated with SID: {call.sid}', 'call_sid': call.sid}
    
    except Exception as e:
        logger.error(f"Error making call: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/handle-call', methods=['POST'])
def handle_call():
    """Webhook that Twilio calls when the call connects"""
    response = VoiceResponse()
    
    start = Start()
    
    stream = Stream(
        url=f"wss://{request.host}/audio-stream",
        track='both_tracks'
    )
    
    stream.parameter(name='speechResult', value='true')
    
    start.append(stream)
    
    response.append(start)
    
    response.say("This call is being transcribed in real-time.")
    
    response.pause(length=120)  # Keep connection for 2 minutes
    
    return Response(str(response), mimetype='text/xml')

@app.route('/call-status', methods=['POST'])
def call_status():
    """Webhook for call status updates"""
    call_sid = request.values.get('CallSid')
    call_status = request.values.get('CallStatus')
    
    if call_sid in active_calls:
        active_calls[call_sid]['status'] = call_status
        
    response = VoiceResponse()
    return Response(str(response), mimetype='text/xml')

@app.route('/get-transcription/<call_sid>', methods=['GET'])
def get_transcription(call_sid):
    """Endpoint to retrieve the current transcription for a call"""
    if call_sid not in active_calls:
        return {'error': 'Call not found'}, 404
        
    return {
        'call_sid': call_sid,
        'status': active_calls[call_sid]['status'],
        'transcription': active_calls[call_sid]['transcription']
    }

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info('WebSocket client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info('WebSocket client disconnected')

@socketio.on('message')
def handle_message(message):
    """Process WebSocket messages from Twilio"""
    try:
        data = json.loads(message)
        
        if data.get('event') == 'connected':
            logger.info('Connected to Twilio Media Stream')
            
        elif data.get('event') == 'start':
            logger.info(f"Media stream started for call {data.get('start', {}).get('callSid')}")
            
        elif data.get('event') == 'media':
            process_media(data)
            
        elif data.get('event') == 'stop':
            logger.info(f"Media stream stopped for call {data.get('stop', {}).get('callSid')}")
            
        elif data.get('event') == 'transcription':
            process_transcription(data)
            
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {str(e)}")

def process_media(data):
    """Process media data from the WebSocket"""
    call_sid = data.get('streamSid')
    payload = data.get('media', {}).get('payload')
    
    logger.debug(f"Received media chunk for call {call_sid}")

def process_transcription(data):
    """Process transcription results from Twilio"""
    call_sid = data.get('streamSid')
    transcript = data.get('transcription', {}).get('text')
    
    if call_sid and transcript:
        if call_sid in active_calls:
            active_calls[call_sid]['transcription'].append(transcript)
        
        socketio.emit('transcription_update', {
            'call_sid': call_sid,
            'text': transcript
        })
        
        logger.info(f"Transcription for {call_sid}: {transcript}")

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
