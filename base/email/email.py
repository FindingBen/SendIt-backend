from djoser.email import PasswordResetEmail, ActivationEmail
from django.core.mail import send_mail
from django.template.loader import get_template


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context['domain'] = 'sendit-frontend-production.up.railway.app'
        # context['domain'] = 'localhost:3000'
        context['protocol'] = 'https'

        return context


def send_confirmation_email(email, token_id, user_id):
    # data = {
    #     "token_id": token_id,
    #     "user_id": str(user_id)
    # }
    send_mail(
        subject=f'[SENDPERPLANE] Hi [], we need to confirm your email',
        message=f""""
        Please confirm your email by clicking on the link below:

        https://sendit-frontend-production.up.railway.app/activate_email/{token_id}/{user_id}/
        """,
        from_email='benarmys4@gmail.com',
        recipient_list=[email],
        fail_silently=True
    )


def send_welcome_email(email: None, user_object: None):
    print('AAA', email)
    print(user_object)
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
