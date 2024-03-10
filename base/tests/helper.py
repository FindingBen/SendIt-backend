from django.urls import reverse
from base.models import PackagePlan, CustomUser


class RegisterLoginUser:

    def __init__(self) -> None:
        self.register_url = reverse('register')
        self.login_url = reverse('token_obtain_pair')
        self.login_data = {
            "username": "test",
            "password": "Dusica123!"
        }
        self.user_data = {
            "custom_email": "test@gmail.com",
            "username": "test",
            "password": "Dusica123!",
            "re_password": "Dusica123!",
            "user_type": "Independent",
            "is_active": "false",
            "sms_count": 6
        }
