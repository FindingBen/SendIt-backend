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

    formatted_engagement_rate = [
        '{:.2%}'.format(rate) for rate in engement_rateSum]
    formatted_bounce_rate = ['{:.2%}'.format(rate) for rate in bounceRate_sum]

    total_sum_object = {'engegment_rate_total': sum(formatted_engagement_rate), 'scrolled_user_total': sum(scrolledUser_sum), 'screen_views_total': sum(screenViews_sum), 'user_engegment_total': sum(userEng_sum),
                        'avg_session_total': sum(avgSession_sum), 'bounceRate': sum(formatted_bounce_rate)}

    # print(total_sum_object)
    return total_sum_object


def calculate_overall_performance(final_data: None):

    # Assign weights to each metric
    bounce_rate_weight = 0.1
    engagement_rate_weight = 0.2
    scrolled_users_weight = 0.15
    user_engagement_weight = 0.2
    total_views_weight = 0.15
    # total_clicks_weight = 0.15
    # total_sends_weight = 0.1

    # Normalize values to be between 0 and 1
    max_possible_scrolled_users = 1000  # Replace with your maximum value
    max_possible_user_engagement = 300  # Replace with your maximum value
    # Replace with your maximum value
    max_possible_total_views = 50
    # max_possible_total_clicks = 1000  # Replace with your maximum value
    # Replace with your maximum value
    # max_possible_total_sends = final_data.total_sends

    normalized_bounce_rate = final_data['bounceRate'] / 100
    normalized_engagement_rate = final_data['engegment_rate_total'] / 100
    normalized_scrolled_users = final_data['scrolled_user_total'] / \
        max_possible_scrolled_users
    normalized_user_engagement = final_data['user_engegment_total'] / \
        max_possible_user_engagement
    normalized_total_views = final_data['screen_views_total'] / \
        max_possible_total_views
    # normalized_total_clicks = final_data.total_clicks / max_possible_total_clicks
    # normalized_total_sends = final_data.total_sends / max_possible_total_sends

    # Calculate the weighted average
    overall_performance = (
        bounce_rate_weight * normalized_bounce_rate +
        engagement_rate_weight * normalized_engagement_rate +
        scrolled_users_weight * normalized_scrolled_users +
        user_engagement_weight * normalized_user_engagement +
        total_views_weight * normalized_total_views
        # total_clicks_weight * normalized_total_clicks +
        # total_sends_weight * normalized_total_sends
    )

    # Convert the result to a percentage
    overall_performance_percentage = overall_performance * 100

    return overall_performance_percentage


# Example usage:
# overall_performance = calculate_overall_performance(
#     bounce_rate=10,
#     engagement_rate=80,
#     scrolled_users=1000,
#     user_engagement=120,
#     total_views=5000,
#     total_clicks=200,
#     total_sends=10000
# )
