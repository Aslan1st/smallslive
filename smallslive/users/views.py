from allauth.account import app_settings
from allauth.account.forms import SetPasswordForm
from allauth.account.views import SignupView as AllauthSignupView, ConfirmEmailView as CoreConfirmEmailView
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from .forms import UserSignupForm, ChangeEmailForm, EditProfileForm


class SignupView(AllauthSignupView):
    form_class = UserSignupForm

signup_view = SignupView.as_view()


def user_settings_view(request):
    # if this is a POST request we need to process the form data
    if 'edit_profile' in request.POST:
        # create a form instance and populate it with data from the request:
        edit_profile_form = EditProfileForm(data=request.POST, user=request.user)
        # check whether it's valid:
        if edit_profile_form.is_valid():
            edit_profile_form.save()
            return HttpResponseRedirect('/')
    # if a GET (or any other method) we'll create a blank form
    else:
        edit_profile_form = EditProfileForm(user=request.user)

    if 'change_email' in request.POST:
        change_email_form = ChangeEmailForm(data=request.POST, user=request.user)
        if change_email_form.is_valid():
            change_email_form.save(request)
            return HttpResponseRedirect(reverse('account_email_verification_sent'))
    else:
        change_email_form = ChangeEmailForm(user=request.user)

    if 'change_password' in request.POST:
        change_password_form = SetPasswordForm(data=request.POST, user=request.user)
        if change_password_form.is_valid():
            change_password_form.save()
            return HttpResponseRedirect('/')
    else:
        change_password_form = SetPasswordForm(user=request.user)

    return render(request, 'account/user_settings.html', {
        'change_email_form': change_email_form,
        'change_profile_form': edit_profile_form,
        'change_password_form': change_password_form,
    })


class ConfirmEmailView(CoreConfirmEmailView):
    def login_on_confirm(self, confirmation):
        """
        Redirects the user to the user settings page only after successfully confirming the email address.
        """
        resp = super(ConfirmEmailView, self).login_on_confirm(confirmation)
        if resp:
            if app_settings.EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL:
                return HttpResponseRedirect(app_settings.EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL)
            else:
                return HttpResponseRedirect('/')

confirm_email = ConfirmEmailView.as_view()
