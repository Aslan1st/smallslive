import floppyforms as forms
from allauth.account.forms import SignupForm


class UserSignupForm(SignupForm):
    email = forms.EmailField(max_length=80, required=True,
                             label="E-mail",
                             widget=forms.TextInput(attrs={
                                 'placeholder': 'Your e-mail address',
                                 'class': 'form-control'
                             }))
    first_name = forms.CharField(max_length=50, required=False,
                                 label="First name",
                                 widget=forms.TextInput(attrs={
                                     'placeholder': 'Your first name',
                                     'class': 'form-control'
                                 }))
    last_name = forms.CharField(max_length=50, required=False,
                                label="Last name",
                                widget=forms.TextInput(attrs={
                                    'placeholder': 'Your last name',
                                    'class': 'form-control'
                                }))
    terms_of_service = forms.BooleanField(required=True)

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
