# Copyright 2013 Concentric Sky, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
from django.contrib import auth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils.decorators import method_decorator
from django.utils.http import is_safe_url
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.generic import CreateView, FormView, RedirectView, TemplateView
from django.utils.translation import ugettext_lazy as _
from sky_visitor.models import InvitedUser
from sky_visitor.backends import auto_login
from sky_visitor.forms import RegisterForm, LoginForm, PasswordResetForm, SetPasswordForm, PasswordChangeForm, InvitationStartForm, InvitationCompleteForm
from sky_visitor.views.mixins import SendTokenEmailMixin, TokenValidateMixin, LoginRequiredMixin


class RegisterView(CreateView):
    model = auth.get_user_model()
    form_class = RegisterForm
    template_name = 'sky_visitor/register.html'
    success_message = _("Successfully registered and logged in")
    auto_login_on_success = True

    def form_valid(self, form):
        response = super(RegisterView, self).form_valid(form)
        user = self.object
        if self.auto_login_on_success:
            auto_login(self.request, user)
        messages.success(self.request, self.success_message)
        return response

    def get_success_url(self):
        return settings.LOGIN_REDIRECT_URL


# Originally from: https://github.com/stefanfoulis/django-class-based-auth-views/blob/develop/class_based_auth_views/views.py
class LoginView(FormView):
    """
    This is a class based version of django.contrib.auth.views.login.

    Usage:
        in urls.py:
            url(r'^login/$',
                LoginView.as_view(
                    form_class=MyVisitorFormClass,
                    success_url='/my/custom/success/url/),
                name="login"),

    """
    redirect_field_name = auth.REDIRECT_FIELD_NAME
    success_url_overrides_redirect_field = False
    template_name = 'sky_visitor/login.html'
    form_class = LoginForm

    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, *args, **kwargs):
        return super(LoginView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        """
        The user has provided valid credentials (this was checked in AuthenticationForm.is_valid()). So now we
        can log them in.
        """
        auth.login(self.request, form.get_user())
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        """
        This will default to the "next" field if available, unless success_url_overrides_redirect_field is True, then it will default to that.
        """
        redirect_to = self.request.REQUEST.get(self.redirect_field_name, '')

        # Ensure the user-originating redirection url is safe.
        if not is_safe_url(url=redirect_to, host=self.request.get_host()):
            redirect_to = resolve_url(settings.LOGIN_REDIRECT_URL)

        if self.success_url and (self.success_url_overrides_redirect_field or not redirect_to):
            redirect_to = self.success_url

        return redirect_to

    def set_test_cookie(self):
        self.request.session.set_test_cookie()

    def check_and_delete_test_cookie(self):
        if self.request.session.test_cookie_worked():
            self.request.session.delete_test_cookie()
            return True
        return False

    def get(self, request, *args, **kwargs):
        """
        Same as django.views.generic.edit.ProcessFormView.get(), but adds test cookie stuff
        """
        self.set_test_cookie()
        return super(LoginView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Same as django.views.generic.edit.ProcessFormView.post(), but adds test cookie stuff
        """
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            self.check_and_delete_test_cookie()
            return self.form_valid(form)
        else:
            self.set_test_cookie()
            return self.form_invalid(form)


class LogoutView(RedirectView):
    permanent = False
    redirect_field_name = auth.REDIRECT_FIELD_NAME
    redirect_url_overrides_redirect_field = False
    success_message = _("Successfully logged out.")

    def get(self, request, *args, **kwargs):
        auth.logout(request)
        messages.success(request, self.success_message, fail_silently=True)
        return super(LogoutView, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        """
        Order of priority:
        * self.success URL (if success_url_overrides_redirect_field is an override)
        * a "next" paramater specified in the logout URL
        * the login URL
        """
        if self.redirect_url_overrides_redirect_field:
            return super(LogoutView, self).get_redirect_url(**kwargs)

        redirect_to = reverse('login')

        if self.redirect_field_name in self.request.REQUEST:
            redirect_to = self.request.REQUEST[self.redirect_field_name]
            # Security check -- don't allow redirection to a different host.
            if not is_safe_url(url=redirect_to, host=self.request.get_host()):
                redirect_to = self.request.path

        return redirect_to


class ForgotPasswordView(SendTokenEmailMixin, FormView):
    form_class = PasswordResetForm
    template_name = 'sky_visitor/forgot_password_start.html'
    email_template = 'visitor-forgot-password'
    token_view_name = 'reset_password'

    def form_valid(self, form):
        # Copied behavior from django.contrib.auth.forms.PasswordResetForm
        UserModel = get_user_model()
        email = form.cleaned_data["email"]
        active_users = UserModel._default_manager.filter(
            email__iexact=email, is_active=True)
        for user in active_users:
            # Make sure that no email is sent to a user that actually has
            # a password marked as unusable
            if not user.has_usable_password():
                continue

            self.send_email(user)

        return super(ForgotPasswordView, self).form_valid(form)  # Do redirect

    def get_success_url(self):
        return reverse('forgot_password_check_email')


class ForgotPasswordCheckEmailView(TemplateView):
    template_name = 'sky_visitor/forgot_password_check_email.html'


class ResetPasswordView(TokenValidateMixin, FormView):
    form_class = SetPasswordForm
    template_name = 'sky_visitor/reset_password.html'
    invalid_token_message = _("Invalid reset password link. Please reset your password again.")
    auto_login_on_success = True
    success_message = _("Succesfully reset password.")

    def get_form_kwargs(self):
        kwargs = super(ResetPasswordView, self).get_form_kwargs()
        kwargs['user'] = self.token_user  # Form expects this
        return kwargs

    def get_form(self, form_class):
        if self.is_token_valid:
            return super(ResetPasswordView, self).get_form(form_class)
        else:
            return None

    def form_valid(self, form):
        if self.is_token_valid:
            form.save()
            messages.success(self.request, self.success_message, fail_silently=True)
            auto_login(self.request, self.token_user)
        return super(ResetPasswordView, self).form_valid(form)

    def get_success_url(self):
        if not self.success_url:
            return resolve_url(settings.LOGIN_REDIRECT_URL)


class ChangePasswordView(LoginRequiredMixin, FormView):
    form_class = PasswordChangeForm
    success_message = _("Succesfully changed password.")
    template_name = 'sky_visitor/change_password.html'

    def get_form_kwargs(self):
        kwargs = super(ChangePasswordView, self).get_form_kwargs()
        kwargs['user'] = self.request.user  # Form expects this
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, self.success_message, fail_silently=True)
        return super(ChangePasswordView, self).form_valid(form)

    def get_success_url(self):
        if not self.success_url:
            # If the user hasn't specific a path or overriddene this method, then return back to the change password form
            return self.request.path
        else:
            return super(ChangePasswordView, self).get_success_url()


class InvitationStartView(SendTokenEmailMixin, CreateView):
    form_class = InvitationStartForm
    template_name = 'sky_visitor/invitation_start.html'
    success_message = _("Invitation successfully delivered.")
    email_template = 'invitation_complete'

    def get_user_object(self):
        """
        Allows you to override to specify a custom way to grab the user that will be emailed

        Useful for more dynamic ways of adding a user (like when you have two forms on the same page.

        Defaults to self.object assuming that the primary form on the view is a user form.
        """
        return self.object

    def form_valid(self, form):
        redirect = super(InvitationStartView, self).form_valid(form)
        self.send_email(self.get_user_object())
        return redirect

    def get_success_url(self):
        messages.success(self.request, self.success_message, fail_silently=True)
        return self.request.path


class InvitationCompleteView(TokenValidateMixin, CreateView):
    """
    Invitations create an InviteUser. Once an invitation is completed, a standard user object is created.

    If the token is invalid, `invalid_token_message` is displayed and the user is redirected to `get_invalid_token_redirect_url()`
    """
    model = auth.get_user_model()
    form_class = InvitationCompleteForm
    auto_login_on_success = True
    template_name = 'sky_visitor/invitation_complete.html'
    invalid_token_message = _("This one-time use invitation URL has already been used. This means you have likely already created an account. Please try to login or use the forgot password form.")
    success_message = _("Account successfully created.")
    # Since this is an UpdateView, the default success_url will be the user's get_absolute_url(). Override if you'd like different behavior

    def get_user_model_class(self):
        """
        Used for token validation. We're faking a real user with the InvitedUser so we can use django core's token validation code.
        """
        return InvitedUser

    def get_invited_user(self):
        return self.token_user

    def get_form_kwargs(self):
        kwargs = super(InvitationCompleteView, self).get_form_kwargs()
        kwargs['invited_user'] = self.get_invited_user()
        return kwargs

    def form_valid(self, form):
        response = super(InvitationCompleteView, self).form_valid(form)  # Save and generate redirect
        if self.auto_login_on_success:
            auto_login(self.request, self.object)
        messages.success(self.request, self.success_message)
        return response

    def get_context_data(self, **kwargs):
        context_data = super(InvitationCompleteView, self).get_context_data(**kwargs)
        context_data['invited_user'] = self.get_invited_user()
        context_data['is_token_valid'] = self.is_token_valid
        return context_data
