from djoser.email import PasswordResetEmail


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context['domain'] = 'https://sendit-backend-production.up.railway.app'
        # context['domain'] = 'http://localhost:8000'
        context['protocol'] = 'https'

        return context
