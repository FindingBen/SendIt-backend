from .test_setup import TestSmsSetup, TestInsufficientSmsSetup, TestScheduleInvalidDateSetup, TestScheduleSmsSetup, TestScheduleInsufficientSmsSetup


class TestSms(TestSmsSetup):

    def test_send_sms(self):
        """Create-Send sms successfully"""
        res = self.client.post(self.create_sms, self.sms_data, format='json')

        self.assertEqual(res.status_code, 200)


class testInsufficientSms(TestInsufficientSmsSetup):

    def test_send_insufficient_sms(self):

        res = self.client.post(self.create_sms, self.sms_data, format='json')

        self.assertEqual(res.status_code, 405)


class TestScheduleSms(TestScheduleSmsSetup):

    def test_schedule_sms(self):
        res = self.client.post(self.schedule_sms, self.sms_data, format='json')
        print(res.data)
        self.assertEqual(res.status_code, 200)


class TestScheduleInsufficientSms(TestScheduleInsufficientSmsSetup):

    def test_schedule_insufficient_sms(self):
        res = self.client.post(self.schedule_sms, self.sms_data, format='json')
        self.assertEqual(res.status_code, 405)


class TestScheduleWrongDateSms(TestScheduleInvalidDateSetup):

    def test_schedule_invalid_date_sms(self):
        res = self.client.post(self.schedule_sms, self.sms_data, format='json')
        print(res.data)
        self.assertEqual(res.status_code, 400)
