from djoser.email import PasswordResetEmail, ActivationEmail
from django.core.mail import send_mail
from base.models import CustomUser
from django.template.loader import render_to_string
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    template_name = 'email/password_reset_email.html'

    def get_context_data(self):
        context = super().get_context_data()
        context['domain'] = 'spplane.app'
        # context['domain'] = 'localhost:3000'
        context['protocol'] = 'https'

        return context


def send_confirmation_email(email, token_id, user_id):
    user_obj = CustomUser.objects.get(id=user_id)

    subject = f'[SENDPERPLANE] Hi {user_obj.first_name}, please confirm your email'
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [email]

    context = {
        'first_name': user_obj.first_name or 'there',
        'token_id': token_id,
        'user_id': user_id,
    }

    html_content = render_to_string('email/activation_email.html', context)
    text_content = f"Hi {user_obj.first_name},\n\nPlease confirm your email by clicking the link below:\nhttps://spplane.app/activate_email/{token_id}/{user_id}/"

    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_welcome_email(email: None, user_object: None):
    subject = 'Welcome to Sendperplane - Your SMS Marketing Platform'
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = [email]

    # Render email HTML
    html_content = render_to_string('email/welcome_email.html', {
        'first_name': user_object.first_name or 'there'
    })

    # Optional plain-text fallback
    text_content = "Welcome to Sendperplane! Visit spplane.app to start sending messages."

    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    msg.send()


def send_email_notification(user_id):
    try:
        user_obj = CustomUser.objects.get(id=user_id)
        subject = "Scheduled SMS Failed"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [user_obj.email]

        context = {
            'first_name': user_obj.first_name or 'there'
        }

        html_content = render_to_string(
            'email/sms_failure_notification.html', context)
        text_content = (
            f"Dear {user_obj.first_name},\n\n"
            "IMPORTANT NOTIFICATION: One of your scheduled messages has failed.\n"
            "Please visit https://spplane.app to check your dashboard.\n"
        )

        msg = EmailMultiAlternatives(
            subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception as e:
        print("Error sending email notification:", str(e))


def send_confirmation_email_account_close(email):
    try:
        subject = '[SENDPERPLANE] We were honored to have you with us!'
        from_email = 'benarmys4@gmail.com'
        to_email = [email]

        html_content = render_to_string('email/account_closure.html', {})
        text_content = (
            "Thank you for using our service. Your account is now closed and your data has been deleted.\n\n"
            "You can review our privacy policy here: https://spplane.app/privacy-policy\n\n"
            "We hope to see you back someday."
        )

        msg = EmailMultiAlternatives(
            subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print("Error sending account closure email:", str(e))
        return False
