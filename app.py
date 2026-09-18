from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import aiohttp
import requests
import json
import like_pb2
import uid_generator_pb2
import visit_count_pb2
from google.protobuf.message import DecodeError
from collections import OrderedDict

app = Flask(__name__)

# ✅ Valid API keys
VALID_API_KEYS = {
    "UDIT"  # don't change warna api nhi chalega
}

# 🔢 Like limit tracking
daily_limit = 200
used_count = 0


def load_tokens(region):
    try:
        if region == "IND":
            with open("token_ind.json", "r") as f:
                tokens = json.load(f)
        elif region in {"BR", "US", "SAC", "NA"}:
            with open("token_br.json", "r") as f:
                tokens = json.load(f)
        elif region == "PK":  # 🇵🇰 PK Server support added
            with open("token_pk.json", "r") as f:
                tokens = json.load(f)
        else:
            with open("token_bd.json", "r") as f:
                tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens for region {region}: {e}")
        return None


def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None


def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None


async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB55"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None


async def send_multiple_requests(uid, region, url):
    try:
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            return None
        tokens = load_tokens(region)
        if tokens is None:
            return None
        tasks = []
        for i in range(300):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        app.logger.error(f"Error in send_multiple_requests: {e}")
        return None


@app.route('/like', methods=['GET', 'POST'])
def handle_like():
    api_key = request.args.get('key') or request.headers.get('Authorization')
    if not api_key or api_key not in VALID_API_KEYS:
        return jsonify({"status": "error", "message": "Invalid API Key"}), 401

    uid = request.args.get('uid')
    region = request.args.get('region', 'IND').upper()
    
    if not uid:
        return jsonify({"status": "error", "message": "UID is required"}), 400

    # Define your game endpoint URL here based on region/version
    url = "https://client.freefiremobile.com/LikeProfile" # Replace with your target endpoint if different

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(send_multiple_requests(uid, region, url))

    if results is None:
        return jsonify({"status": "error", "message": "Failed to process request or load tokens."}), 500

    return jsonify({
        "status": "success",
        "message": "Requests sent successfully",
        "region": region,
        "uid": uid,
        "total_tasks": len(results)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

