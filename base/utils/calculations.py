import hashlib


def total_sum(data_value: None):

    engement_rateSum = [engRate['engegmentRate'] for engRate in data_value]
    scrolledUser_sum = [scrUsr['scrolledUser'] for scrUsr in data_value]
    screenViews_sum = [screenViews['screenViews']
                       for screenViews in data_value]
    userEng_sum = [userEng['userEngegment'] for userEng in data_value]
    avgSession_sum = [avgSession['avgSessionDuration']
                      for avgSession in data_value]
    bounceRate_sum = [avgSession['bounceRate']
                      for avgSession in data_value]
    total_sum_object = {'engegment_rate_total': sum(engement_rateSum), 'scrolled_user_total': sum(scrolledUser_sum), 'screen_views_total': sum(screenViews_sum), 'user_engegment_total': sum(userEng_sum),
                        'avg_session_total': sum(avgSession_sum), 'bounceRate': sum(bounceRate_sum)}
    # print(total_sum_object)
    return total_sum_object


def generate_hash(phone_number):
    # Create a hashlib object
    sha256 = hashlib.sha256()

    # Update the hash object with the phone number as bytes
    sha256.update(str(phone_number).encode('utf-8'))

    # Get the hexadecimal representation of the hash
    hashed_phone = sha256.hexdigest()

    return hashed_phone
