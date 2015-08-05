from allauth.account import app_settings
from allauth.account.adapter import get_adapter
from allauth.account.utils import user_pk_to_url_str, user_username
from allauth.utils import build_absolute_uri
import datetime
from calendar import monthrange
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django_countries import countries
import floppyforms
import allauth.account.forms as allauth_forms
from localflavor.us.forms import USStateField
from localflavor.us.us_states import STATE_CHOICES
from artists.forms import ArtistAddForm
from events import forms as event_forms
from events.forms import Formset
from events.models import Recording

User = get_user_model()

STATE_CHOICES_WITH_EMPTY = (('', ''),) + STATE_CHOICES
COUNTRIES_WITH_EMPTY = (('', ''),) + tuple(countries)


class ToggleRecordingStateForm(forms.ModelForm):
    class Meta:
        model = Recording
        fields = ('state',)


class EventEditForm(event_forms.EventEditForm):
    class Meta(event_forms.EventEditForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        super(EventEditForm, self).__init__(*args, **kwargs)
        del self.fields['state']
        del self.fields['start']
        del self.fields['end']
        self.helper[3] = Formset('artists', template='form_widgets/formset_layout.html', admin=False)


class ArtistInfoForm(forms.ModelForm):
    state = USStateField(widget=floppyforms.Select(choices=STATE_CHOICES_WITH_EMPTY), required=False)
    country = floppyforms.ChoiceField(choices=COUNTRIES_WITH_EMPTY)
    payout_method = forms.ChoiceField(
        choices=User.PAYOUT_CHOICES,
        widget=forms.RadioSelect()
    )
    paypal_email_again = floppyforms.EmailField(required=False)

    class Meta:
        fields = ('first_name', 'last_name', 'address_1', 'address_2', 'city', 'zip', 'state', 'country',
                  'payout_method', 'paypal_email', 'paypal_email_again', 'taxpayer_id')
        model = User

    def __init__(self, *args, **kwargs):
        super(ArtistInfoForm, self).__init__(*args, **kwargs)
        for field in self.Meta.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
        self.fields['state'].widget.attrs['class'] = 'form-control selectpicker'
        self.fields['country'].widget.attrs['class'] = 'form-control selectpicker'
        # default to US if nothing is set, initial not working as the form is bound
        if not self.initial['country']:
            self.initial['country'] = 'US'

    def clean(self):
        cleaned_data = super(ArtistInfoForm, self).clean()
        if cleaned_data.get('payout_method') == User.PAYOUT_CHOICES.PayPal:
            msg = u"This field is required."
            if not cleaned_data.get('paypal_email'):
                self.add_error('paypal_email', msg)
            if not cleaned_data.get('paypal_email_again'):
                self.add_error('paypal_email_again', msg)
            if cleaned_data.get('paypal_email') != cleaned_data.get('paypal_email_again'):
                raise forms.ValidationError(u'The two email addresses must match.')

        if cleaned_data.get('country') == 'US':
            state = cleaned_data.get('state')
            if not state:
                self.add_error('state', 'You must select a valid US state or territory.')
            taxpayer_id = cleaned_data.get('taxpayer_id')
            if not taxpayer_id:
                self.add_error('taxpayer_id', 'You must enter a valid taxpayer ID as a US citizen.')
            self.fields['state'].clean(state)
            self.fields['taxpayer_id'].clean(state)
        else:
            cleaned_data['state'] = ''
            cleaned_data['taxpayer_id'] = ''
        return cleaned_data


class EditProfileForm(ArtistAddForm):
    def __init__(self, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        for field in self.Meta.fields:
            self.fields[field].widget.attrs['class'] = self.fields[field].widget.attrs.get('class', '') + ' form-control'
        self.fields['salutation'].widget.attrs['class'] = 'form-control selectpicker'
        self.fields['website'].widget.attrs['placeholder'] = 'http://www.yourwebsite.com'


class ArtistResetPasswordForm(allauth_forms.ResetPasswordForm):
    def save(self, request, **kwargs):
        # c/p from parent class, only needed to change the URL in the email
        email = self.cleaned_data["email"]
        token_generator = kwargs.get("token_generator",
                                     default_token_generator)

        for user in self.users:

            temp_key = token_generator.make_token(user)

            # save it to the password reset model
            # password_reset = PasswordReset(user=user, temp_key=temp_key)
            # password_reset.save()

            current_site = Site.objects.get_current()

            # send the password reset email
            path = reverse("artist_dashboard:reset_password_from_key",
                           kwargs=dict(uidb36=user_pk_to_url_str(user),
                                       key=temp_key))
            url = build_absolute_uri(request, path,
                                     protocol=app_settings.DEFAULT_HTTP_PROTOCOL)
            context = {"site": current_site,
                       "user": user,
                       "password_reset_url": url}
            if app_settings.AUTHENTICATION_METHOD \
                    != app_settings.AuthenticationMethod.EMAIL:
                context['username'] = user_username(user)
            get_adapter().send_mail('account/email/password_reset_key',
                                    email,
                                    context)
        return self.cleaned_data["email"]


class MetricsPayoutForm(forms.Form):
    period_start = forms.DateField(required=True, input_formats=["%B // %Y"])
    period_end = forms.DateField(required=True, input_formats=["%B // %Y"])
    revenue = forms.DecimalField(required=True)
    operating_cost = forms.DecimalField(required=True)
    final_calculation = forms.BooleanField(required=False)

    def clean_period_start(self):
        start = self.cleaned_data['period_start']
        start = start.replace(day=1)
        return start

    def clean_period_end(self):
        end = self.cleaned_data['period_end']
        end = end.replace(day=monthrange(end.year, end.month)[1])
        return end
