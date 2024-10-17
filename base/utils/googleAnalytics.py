import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from sms.models import Sms
from base.models import AnalyticsData, CustomUser, Message
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    FilterExpression,
    Filter
)
from datetime import datetime, timedelta


def get_all_dates_in_range(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    date_list = [start + timedelta(days=x)
                 for x in range(0, (end-start).days + 1)]
    return set(date.strftime("%Y-%m-%d") for date in date_list)


def sample_run_report(property_id="400824086", record_id=None, start_date=None, end_date=None, recipients=None):
    page_specified = f'/view/{record_id}'
    sms_model = Sms.objects.get(message_id=record_id)
    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    print('RECORD:', record_id)
    property_id = "400824086"
    credentials_path = os.path.abspath('base/utils/credentials.json')
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    client = BetaAnalyticsDataClient()

    # start_date = (datetime.now() - timedelta(days=1)).date()
    end_date = datetime.now().date()
    date_range = DateRange(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pagePath"),
                    Dimension(name='date')],
        metrics=[

            Metric(name='engagementRate'),
            Metric(name='screenPageViews'),
            Metric(name='userEngagementDuration'),
            Metric(name='scrolledUsers'),
            Metric(name='averageSessionDuration'),
            Metric(name='bounceRate')],

        date_ranges=[date_range],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(value=page_specified),
            )
        ),
    )
    response = client.run_report(request)

    existing_dates = set(datetime.strptime(
        row.dimension_values[1].value, "%Y%m%d").strftime("%Y-%m-%d") for row in response.rows)

    date_range_list = get_all_dates_in_range(
        date_range.start_date, date_range.end_date)

    merged_set = existing_dates.union(date_range_list)
    final_data = []
    for date in merged_set:
        formatted_date = datetime.strptime(
            date, "%Y-%m-%d").strftime("%m-%d")
        # Check if the date is in existing_dates
        for row in response.rows:
            if date == datetime.strptime(row.dimension_values[1].value, "%Y%m%d").strftime("%Y-%m-%d"):
                row_obj = {"date": formatted_date, "engegmentRate": float(row.metric_values[0].value), "screenViews": int(row.metric_values[1].value), "userEngegment": float(row.metric_values[2].value),
                           "scrolledUser": int(row.metric_values[3].value), "avgSessionDuration": float(row.metric_values[4].value), "bounceRate": float(row.metric_values[5].value)}
                final_data.append(row_obj)
                break
        else:
            # If it doesn't exist, just append the date
            row_obj = {"date": formatted_date, "engegmentRate": 0, "screenViews": 0, "userEngegment": 0,
                       "scrolledUser": 0, "avgSessionDuration": 0, 'bounceRate': 0}
            final_data.append(row_obj)
    sorted_final_data = sorted(final_data, key=lambda x: x["date"])[:7]

    final_analysis_data = get_total_values(sorted_final_data, recipients)
    sms_model.update_from_values(final_analysis_data, record_id)
    analytics_data = AnalyticsData.objects.get(custom_user=sms_model.user.id)

    if final_analysis_data['sorted_total_data']['screen_views_total'] > sms_model.total_views:
        # Calculate the difference
        new_views_to_add = final_analysis_data['sorted_total_data']['screen_views_total'] - \
            sms_model.total_views

        # Increment the total views by the difference
        analytics_data.total_views += new_views_to_add
        analytics_data.save()

    return final_analysis_data, sorted_final_data


def get_total_values(values: None, recipients: None):
    from .calculations import total_sum, calculate_overall_performance

    summed_data = total_sum(values, recipients)

    overall_perf = calculate_overall_performance(summed_data)
    final_analysis_data = {'sorted_data': values,
                           'sorted_total_data': summed_data,
                           'overall_perf': overall_perf}
    return final_analysis_data
