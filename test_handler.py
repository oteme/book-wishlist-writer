"""Simple test handler for Lambda."""
import json


def lambda_handler(event, context):
    """Simple test handler."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'success',
            'message': 'Test handler working!',
            'event': event
        })
    }