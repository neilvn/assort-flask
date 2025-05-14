import os
import json
import logging

from dotenv import load_dotenv
from flask import Flask, request, Response
from flask_socketio import SocketIO, emit
from openai import get_ai_response
from twilio.twiml.voice_response import Gather, VoiceResponse, Start, Stream
from twilio.rest import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
OPENAI_KEY = os.getenv("OPENAI_KEY")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

active_calls = {}

@app.route('/make-call', methods=['POST'])
def make_call():
    """Endpoint to initiate a call using Twilio's API"""
    logger.info("Initiating outgoing call")

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
    '''Webhook that Twilio calls when the call connects'''
    response = VoiceResponse()

    gather = Gather(
        input='speech',          
        action=f'{request.url_root}process_speech',
        method='POST',           
        language='en-US',        
        speechTimeout='auto',    
        enhanced=True            
    )

    gather.say("Hello, this is Assort Health")
    response.gather(speechTimeout=4)
    
    return Response(str(response), mimetype='text/xml')


@app.route('/process-call', methods=["POST"])
def process_call():
    speech_result = request.values.get('SpeechResult', '')
    response = VoiceResponse()
    response.say(f"I heard you say: {speech_result}")


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
