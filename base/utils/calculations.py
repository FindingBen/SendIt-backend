

def total_sum(data_value: None):

    engement_rateSum = [engRate['engegmentRate'] for engRate in data_value]
    scrolledUser_sum = [scrUsr['scrolledUser'] for scrUsr in data_value]
    screenViews_sum = [screenViews['screenViews']
                       for screenViews in data_value]
    userEng_sum = [userEng['userEngegment'] for userEng in data_value]
    avgSession_sum = [avgSession['avgSessionDuration']
                      for avgSession in data_value]
    print(sum(engement_rateSum))
    total_sum_object = {'engegment_rate_total': sum(engement_rateSum), 'scrolled_user_total': sum(scrolledUser_sum), 'screen_views_total': sum(screenViews_sum), 'user_engegment_total': sum(userEng_sum),
                        'avg_session_total': sum(avgSession_sum)}
    # print(total_sum_object)
    return total_sum_object
