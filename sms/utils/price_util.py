import math
import requests
import phonenumbers
from phonenumbers import geocoder


def vonage_api_pricing(query_params):
    response = requests.get(
        "https://rest.nexmo.com/account/get-full-pricing/outbound/sms", query_params)

    data = response.json()
    countries = data.get("countries", [])

    # Simplify into a mapping for quick lookup
    simplified_countries = {
        country["countryCode"]: float(country.get("defaultPrice", 0))
        for country in countries
    }

    return simplified_countries


def calculate_sms_segments(message_text):
    # Basic GSM vs Unicode check
    if any(ord(char) > 127 for char in message_text):
        return (len(message_text) + 69) // 70  # Unicode limit
    return (len(message_text) + 159) // 160


def get_price_per_segment(contacts, message_text, query_params, fallback_country_code='US'):
    country_prices = vonage_api_pricing(query_params)
    total_cost = 0.0
    segments_per_contact = []

    for contact in contacts:
        phone_number = str(contact.phone_number)
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number

        parsed = phonenumbers.parse(phone_number)
        country_code = geocoder.region_code_for_number(parsed)

        price = country_prices.get(
            country_code, country_prices.get(fallback_country_code, 0))
        segments = calculate_sms_segments(message_text)
        cost = price * segments
        total_cost += cost

        segments_per_contact.append({
            "phone": phone_number,
            "country": country_code,
            "segments": segments,
            "segment_price": price,
            "total_price": round(cost, 6)
        })

    return {
        "total_cost": round(total_cost, 6),
        "recipients": len(contacts),
        "details": segments_per_contact
    }


def estimate_credits_required(message_text, country_code, credit_unit=0.01):
    segments = calculate_sms_segments(message_text)
    cost = segments * get_price_per_segment(country_code)
    return math.ceil(cost / credit_unit)
