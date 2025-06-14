import time
import pytz
import requests
import phonenumbers
from phonenumbers import geocoder
from django.conf import settings
import math


def calculate_sms_segments(message_text):
    # Basic GSM vs Unicode check
    if any(ord(char) > 127 for char in message_text):
        return (len(message_text) + 69) // 70  # Unicode limit
    return (len(message_text) + 159) // 160


def get_price_per_segment(country_code):
    # You already have a function to pull this dynamically
    # For example purposes, hardcoding some average values:
    return {
        'US': 0.00645,
        'IN': 0.0020,
        'FR': 0.032,
        'DK': 0.052
    }.get(country_code.upper(), 0.01)


def estimate_credits_required(message_text, country_code, credit_unit=0.01):
    segments = calculate_sms_segments(message_text)
    cost = segments * get_price_per_segment(country_code)
    return math.ceil(cost / credit_unit)


def get_price():
    number = "+4552529924"
    parsed = phonenumbers.parse(number)
    country_code = geocoder.region_code_for_number(parsed)

    query_params = {
        "api_key": "33572b56",
        "api_secret": "cq75YEW2e1Z5coGZ",

    }
    response = requests.get(
        "https://rest.nexmo.com/account/get-full-pricing/outbound/sms", query_params)

    data = response.json()
    countries = data.get("countries", [])
    # Clean and return only needed fields
    simplified_countries = [
        {
            "countryName": country["countryName"],
            "countryCode": country["countryCode"],
            "currency": country["currency"],
            "defaultPrice": country.get("defaultPrice")
        }
        for country in countries
    ]

    return simplified_countries


dd = get_price()
print(dd)


# text = "Clara Bichiiiiiin como que Bichiiiin aoraaaa, porfavor sientese queres una servesa"
# country = 'DK'

# segments = calculate_sms_segments(text)
# total_cost = estimate_credits_required(text, country)

# print(total_cost)
