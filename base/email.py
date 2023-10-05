from djoser.email import PasswordResetEmail


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    def get_context_data(self):
        context = super().get_context_data()
        context['domain'] = 'https://sendit-frontend-production.up.railway.app'
        context['protocol'] = 'https'

        return context
