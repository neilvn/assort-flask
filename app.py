import os
import json
import logging

from dotenv import load_dotenv
from flask import Flask, request, Response
from flask_socketio import SocketIO, emit
from openai import get_ai_response
from script import script
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
        action=f'{request.url_root}process-call',
        method='POST',           
        language='en-US',        
        speechTimeout='auto',    
        enhanced=True            
    )

    gather.pause(length=3)
    gather.say("Hello, this is Assort Health")
    response.append(gather)
    response.gather(speechTimeout=4)
    
    return str(response)


@app.route('/process-call', methods=["POST"])
def process_call():
    logger.info('Processing call...')
    
    speech_result = request.values.get('SpeechResult', '')
    call_sid = request.values.get('CallSid', '')
    logger.info(f'Speech result: {speech_result}')
    
    current_question_index = int(request.values.get('question_index', 0))
    
    response = VoiceResponse()
    
    if current_question_index < len(script):
        curr_script = script[current_question_index]
        if speech_result and current_question_index > 0:
            prev_question = script[current_question_index - 1]
            logger.info(f"Answer to '{prev_question}': {speech_result}")
        
        response.pause(length=1)
        
        ai_query = get_ai_response(curr_script)
        
        response.say(ai_query)
        
        gather = Gather(
            input='speech',
            action=f'/process-call?question_index={current_question_index + 1}',
            method='POST',
            speechTimeout='auto',
            enhanced=True
        )
        
        response.append(gather)
        response.redirect(f'/process-call?question_index={current_question_index}')
    else:
        response.pause(length=1)
        response.say("Thank you for answering all our questions. Have a great day!")
        response.hangup()
    
    return str(response)


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
