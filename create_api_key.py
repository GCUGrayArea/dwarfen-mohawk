import asyncio
import os
import secrets
import bcrypt
from datetime import datetime, timezone
import boto3

async def create_api_key():
    # Generate a secure API key
    api_key = secrets.token_urlsafe(48)[:64]  # 64-character key

    # Hash the key
    key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Connect to DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
    table = dynamodb.Table('zapier-api-keys-production')

    # Create the key record
    import uuid
    key_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    table.put_item(Item={
        'key_id': key_id,
        'key_hash': key_hash,
        'status': 'active',
        'rate_limit': 100,
        'user_email': 'admin@example.com',
        'role': 'admin',
        'created_at': timestamp,
        'last_used_at': timestamp
    })

    print(f"\nAPI Key created successfully!")
    print(f"\nKey ID: {key_id}")
    print(f"Plaintext API Key: {api_key}")
    print(f"\nSAVE THIS KEY NOW! It will never be displayed again.\n")
    print(f"Use it in your requests:")
    print(f'  Authorization: Bearer {api_key}\n')

    return api_key

if __name__ == '__main__':
    asyncio.run(create_api_key())
