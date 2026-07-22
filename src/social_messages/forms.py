from django.contrib.auth.forms import AuthenticationForm
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

class CustomAdminAuthenticationForm(AuthenticationForm):
    captcha = ReCaptchaField(widget=ReCaptchaV3)
