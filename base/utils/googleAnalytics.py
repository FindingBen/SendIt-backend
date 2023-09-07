import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    FilterExpression,
    Filter
)


def sample_run_report(property_id="400824086", record_id=None):
    page_specified = f'/message_view/{record_id}'
    #page_specified = f'/message_view/14'
    # print("ID", record_id)
    # Using a default constructor instructs the client to use the credentials
    # specified in GOOGLE_APPLICATION_CREDENTIALS environment variable.
    property_id = "400824086"
    credentials_path = os.path.abspath('base/utils/credentials.json')
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pagePath"),
                    Dimension(name='date')],
        metrics=[

                 Metric(name='engagementRate'),
                 Metric(name='screenPageViews'),
                 Metric(name='userEngagementDuration'),
                 Metric(name='scrolledUsers'),
                 Metric(name='averageSessionDuration')],
        date_ranges=[DateRange(start_date="2020-07-31", end_date="today")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(value=page_specified),
            )
        ),
    )
    response = client.run_report(request)

    print("Report result:")
    print(response)
    for row in response.rows:
        print(row.dimension_values[0].value, row.dimension_values[1].value,
              row.metric_values[0].value, row.metric_values[1].value)

    return response


sample_run_report(14)
