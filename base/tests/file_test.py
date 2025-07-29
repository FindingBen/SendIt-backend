
from base.models import CustomUser, Contact
from utils.helpers import Utils

util = Utils()

recipients = Contact.objects.filter(users=31)
user = CustomUser.objects.get(id=31)


run = util.flag_recipients(recipients_queryset=recipients, user=user)

print(run)
