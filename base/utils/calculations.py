import hashlib
from typing import List, Dict


def total_sum(data_value: None, recipients: None):
    total_records = len(data_value)

    engement_rateSum = [engRate['engegmentRate']
                        for engRate in data_value]
    scrolledUser_sum = [scrUsr['scrolledUser'] for scrUsr in data_value]
    screenViews_sum = [screenViews['screenViews']
                       for screenViews in data_value]
    userEng_sum = [userEng['userEngegment'] for userEng in data_value]
    avgSession_sum = [avgSession['avgSessionDuration']
                      for avgSession in data_value]
    bounceRate_sum = [avgSession['bounceRate']
                      for avgSession in data_value]

    total_engagement_rate = sum(engement_rateSum)
    total_scrolled_user = sum(scrolledUser_sum)
    total_screen_views = sum(screenViews_sum)
    total_user_engegment = sum(userEng_sum)
    total_avg_session = sum(avgSession_sum)
    total_bounce_rate = sum(bounceRate_sum)

    average_bounce_rate = total_bounce_rate / total_records
    average_engagement_rate = total_engagement_rate / total_records
    average_session = total_avg_session / total_records
    # Format percentage values to show only two digits
    formatted_engagement_rate, formatted_bounce_rate = [float('{:.1%}'.format(
        value).rstrip('%')) for value in [average_bounce_rate, average_engagement_rate]]

    total_sum_object = {'engegment_rate_total': formatted_engagement_rate, 'scrolled_user_total': total_scrolled_user, 'screen_views_total': total_screen_views, 'user_engegment_total': total_user_engegment,
                        'avg_session_total': average_session, 'bounceRate': formatted_bounce_rate}

    return total_sum_object


def calculate_overall_performance(final_data: None, recipients: None):

    try:
        # Assign weights to each metric
        bounce_rate_weight = 0.3  # Adjust based on importance
        engagement_rate_weight = 0.4  # Adjust based on importance
        total_views_weight = 0.3
        scrolled_users_weight = 0.2
        user_engagement_weight = 0.3
        total_views_weight = 0.5

        # Normalize values to be between 0 and 1
        max_possible_scrolled_users = 100
        max_possible_user_engagement = 100
        max_possible_total_views = 100

        normalized_bounce_rate = final_data['bounceRate'] / 100
        normalized_engagement_rate = final_data['engegment_rate_total'] / 100
        normalized_scrolled_users = final_data['scrolled_user_total'] / \
            max_possible_scrolled_users
        normalized_user_engagement = final_data['user_engegment_total'] / \
            max_possible_user_engagement
        normalized_total_views = final_data['screen_views_total'] / \
            max_possible_total_views

        # Calculate the weighted average
        overall_performance = (
            bounce_rate_weight * normalized_bounce_rate +
            engagement_rate_weight * normalized_engagement_rate +
            scrolled_users_weight * normalized_scrolled_users +
            user_engagement_weight * normalized_user_engagement +
            total_views_weight * normalized_total_views

        ) / recipients

        # Convert the result to a percentage

        overall_performance_percentage = float('{:.2%}'.format(
            overall_performance).rstrip('%'))
        print('CALCULATE:', overall_performance_percentage, overall_performance)
        return overall_performance_percentage
    except Exception as e:
        return str(e)


def calculate_avg_performance(data_entry: List[Dict[str, any]]) -> Dict[str, float]:
    # Initialize variables to store sums
    total_engagement_rate = 0
    total_user_engagement = 0
    total_scrolled_users = 0
    total_session_duration = 0
    print("CALCULATION", data_entry)
    # Loop through each entry in the data
    for entry in data_entry:

        # Increment sums with values from each day
        total_engagement_rate += entry.get("engegmentRate", 0)
        total_user_engagement += entry.get("userEngegment", 0)
        total_scrolled_users += entry.get("scrolledUser", 0)
        total_session_duration += entry.get("avgSessionDuration", 0)

    # Calculate averages
    num_days = len(data_entry)
    avg_engagement_rate = total_engagement_rate / num_days if num_days > 0 else 0
    avg_user_engagement = total_user_engagement / num_days if num_days > 0 else 0
    avg_scrolled_users = total_scrolled_users / num_days if num_days > 0 else 0
    avg_session_duration = total_session_duration / num_days if num_days > 0 else 0
    # Return averages as a dictionary
    return {
        "average_engagement_rate": avg_engagement_rate,
        "average_user_engagement": avg_user_engagement,
        "average_scrolled_users": avg_scrolled_users,
        "average_session_duration": avg_session_duration
    }


def format_number(value):
    print(value)
    if value >= 1000000:  # 1M or more
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1000:  # 1K or more
        return f"{value / 1000:.1f}k"
    return str(value)


def clicks_rate(clicks=None, sends=None):
    print(clicks, sends)
    if clicks > 0 and sends > 0:
        click_rate = clicks/sends
        final_click_rate = float('{:.2%}'.format(
            click_rate).rstrip('%'))
        return final_click_rate
    else:
        return 0


def calculate_deliveribility(delivered=None, sends=None):
    if sends === 0:
        return 0
    final_division = delivered/sends

    formated_value = float('{:.2%}'.format(
        final_division).rstrip('%'))
    return formated_value
