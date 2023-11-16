from djoser.email import PasswordResetEmail


class CustomPasswordResetConfirmationEmail(PasswordResetEmail):
    def get_context_data(self):
        print('Test?')
        context = super().get_context_data()
        print(context)
        context['domain'] = 'sendit-frontend-production.up.railway.app'
        # context['domain'] = 'localhost:3000'
        context['protocol'] = 'https'

        return context
