import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from django.conf import settings
from django.db import transaction
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    FilterExpression,
    Filter
)
from datetime import datetime, timedelta
from google.oauth2 import service_account


def get_all_dates_in_range(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    date_list = [start + timedelta(days=x)
                 for x in range(0, (end-start).days + 1)]
    return set(date.strftime("%Y-%m-%d") for date in date_list)


def sample_run_report(property_id="400824086", record_id=None, start_date=None, end_date=None):
    page_specified = f'/message_view/{record_id}'

    # page_specified = f'/message_view/44'
    # print("ID", record_id)
    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    property_id = "400824086"
    credentials_path = os.path.abspath('base/utils/credentials.json')

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    client = BetaAnalyticsDataClient()
    if start_date is None or end_date is None:
        start_date = (datetime.now() - timedelta(days=1)).date().isoformat()
        end_date = datetime.now().date().isoformat()
        date_range = DateRange(start_date=start_date, end_date=end_date)
    else:
        date_range = DateRange(start_date=start_date,
                               end_date=end_date)
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
        # Check if the date is in existing_dates
        for row in response.rows:
            if date == datetime.strptime(row.dimension_values[1].value, "%Y%m%d").strftime("%Y-%m-%d"):
                row_obj = {"date": date, "engegmentRate": float(row.metric_values[0].value), "screenViews": int(row.metric_values[1].value), "userEngegment": float(row.metric_values[2].value),
                           "scrolledUser": int(row.metric_values[3].value), "avgSessionDuration": float(row.metric_values[4].value), "bounceRate": float(row.metric_values[5].value)}
                final_data.append(row_obj)
                break
        else:
            # If it doesn't exist, just append the date
            row_obj = {"date": date, "engegmentRate": 0, "screenViews": 0, "userEngegment": 0,
                       "scrolledUser": 0, "avgSessionDuration": 0, 'bounceRate': 0}
            final_data.append(row_obj)
    sorted_final_data = sorted(final_data, key=lambda x: x["date"])

    final_analysis_data = get_total_values(sorted_final_data)

    get_values_for_sms(final_analysis_data, record_id)

    return final_analysis_data


def get_total_values(values: None):
    from .calculations import total_sum, calculate_overall_performance

    summed_data = total_sum(values)

    overall_perf = calculate_overall_performance(summed_data)
    final_analysis_data = {'sorted_data': values,
                           'sorted_total_data': summed_data,
                           'overall_perf': overall_perf}
    print("final_ana_data", summed_data)
    return final_analysis_data


def get_values_for_sms(values: None, record_id: None):
    from sms.models import Sms
    sms_model = Sms.objects.get(message_id=record_id)
    print("FOR SMS:", values['sorted_total_data'])
    with transaction.atomic():
        sms_model.total_bounce_rate = values['sorted_total_data']['bounceRate']
        sms_model.total_views = values['sorted_total_data']['screen_views_total']
        sms_model.total_overall_rate = values['overall_perf']
        sms_model.save()
        print('done')
# sample_run_report(14)
