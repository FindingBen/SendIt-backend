from djoser.email import PasswordResetEmail, ActivationEmail
from django.core.mail import send_mail
from base.models import CustomUser
from django.template.loader import get_template
from django.conf import settings


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context['domain'] = 'spplane.app'
        # context['domain'] = 'localhost:3000'
        context['protocol'] = 'https'

        return context


def send_confirmation_email(email, token_id, user_id):
    user_obj = CustomUser.objects.get(id=user_id)

    send_mail(
        subject=f'[SENDPERPLANE] Hi {user_obj.first_name}, we need to confirm your email',
        message=f"""
        Please confirm your email by clicking on the link below:

        https://spplane.app/activate_email/{token_id}/{user_id}/
        """,
        from_email='benarmys4@gmail.com',
        recipient_list=[email],
        fail_silently=True
    )


def send_welcome_email(email: None, user_object: None):

    send_mail(
        subject='Welcome to Sendperplane - Your SMS Marketing Platform',
        message=f'''Dear,

                    Welcome to Sendperplane - the platform that empowers you to supercharge your SMS marketing efforts! 🚀

                    We're thrilled to have you on board! Here's a quick rundown of what you can achieve with Sendperplane:

                    1. Import Contacts: Easily import and organize your contact lists for targeted campaigns.
                    2. Create Compelling Content: Craft engaging SMS messages with our user-friendly editor. Personalize your content to make a lasting impression.
                    3. Send Messages Effortlessly: With a few clicks, you can send SMS messages to your contacts, ensuring your messages reach the right audience at the right time.

                    Get started now and elevate your SMS marketing game!

                    If you have any questions or need assistance along the way, our support team is here to help. Simply reply to this email, and we'll be happy to assist you.

                    Thanks for choosing Sendperplane. Let's make your SMS marketing journey a success!

                    Best regards,
                    The Sendperplane Team''',
        from_email='benarmys4@gmail.com',  # Replace with your sender email address
        recipient_list=[email],  # Use the user's email address
        fail_silently=False,
    )


def send_email_notification(user_id):
    try:
        # Retrieve user email from request
        user_obj = CustomUser.objects.get(id=user_id)
        subject = "Scheduled SMS Failed"
        message = f"Sorry, one of your recent messages has failed."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user_obj.email]
        send_mail(subject, message, from_email, recipient_list)
    except Exception as e:
        print("Error sending email notification:", str(e))


def send_confirmation_email_account_close(email):
    email_sent = False
    send_mail(
        subject=f'[SENDPERPLANE] We were honored to have you with us!',
        message=f"""
        Thank you for using our service, we hope to see you back some day, hopefully soon!
        
        Your account is now closed and all of the data we had is deleted as per our privacy policy rules which you can
        check out here: https://spplane.app/privacy-policy .

        Have a good one!
        """,
        from_email='benarmys4@gmail.com',
        recipient_list=[email],
        fail_silently=True
    )
    email_sent = True
    return email_sent
