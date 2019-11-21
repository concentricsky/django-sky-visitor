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
# limitations under the License.
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.http import base36_to_int, int_to_base36
from django.utils.translation import ugettext_lazy as _

from emailtemplates.utils import send_email_template


class LoginRequiredMixin(object):
    """Ensures that user must be authenticated in order to access view."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)


class SendTokenEmailMixin(object):
    email_template = None
    token_view_name = None

    def get_email_context_data(self, user, **kwargs):
        token_view_name = kwargs.get('token_view_name', self.token_view_name)
        if not token_view_name:
            raise ImproperlyConfigured("No token_view_name defined.")

        site = Site.objects.get_current()
        token = default_token_generator.make_token(user)
        uidb36 = int_to_base36(user.id)

        static_url = settings.STATIC_URL

        token_url = reverse(token_view_name, kwargs={'uidb36': uidb36, 'token': token})
        if hasattr(self, 'request'):
            token_url = self.request.build_absolute_uri(token_url)
            if '://' not in static_url:
                static_url = self.request.build_absolute_uri(static_url)
        else:
            token_url = 'http://%s%s' % (site.domain, token_url)

        return {
            'user': user,
            'uid': uidb36,
            'token': token,
            'token_url': token_url,
            'site': site,
            'static_url': static_url,
        }

    def send_email(self, user, **kwargs):
        to_address = getattr(user, 'email', None)
        if not to_address:
            return False
        template_name = kwargs.get('template_name', self.email_template)
        if not template_name:
            raise ImproperlyConfigured("No email_template defined.")

        context = self.get_email_context_data(user, **kwargs)
        return send_email_template(template_name, [to_address],
            context=context,
            attachments=kwargs.get('attachments', None),
            headers=kwargs.get('headers', None))


class TokenValidateMixin(object):
    """
    If the token is invalid, `invalid_token_message` is displayed and the user is redirected to `get_invalid_token_redirect_url()`
    """
    token_generator = default_token_generator
    display_message_on_invalid_token = True
    is_token_valid = False
    invalid_token_message = _("This one-time use URL has already been used. Try to login or use the forgot password form.")

    def get_token_generator(self):
        return self.token_generator

    def get_user_model_class(self):
        return get_user_model()

    @cached_property
    def token_user(self):
        uidb36 = self.kwargs.get('uidb36')
        assert uidb36 is not None
        UserModel = self.get_user_model_class()
        if not hasattr(self, '_token_user'):
            try:
                uid_int = base36_to_int(uidb36)
                self._token_user = UserModel._default_manager.get(id=uid_int)
            except (ValueError, OverflowError, UserModel.DoesNotExist):
                self._token_user = None
        return self._token_user

    def dispatch(self, request, *args, **kwargs):
        token = kwargs['token']
        assert token is not None  # checked by URLconf
        self.is_token_valid = (self.token_user is not None and self.get_token_generator().check_token(self.token_user, token))
        if not self.is_token_valid:
            return self.token_invalid(request, *args, **kwargs)
        return super(TokenValidateMixin, self).dispatch(request, *args, **kwargs)

    def token_invalid(self, request, *args, **kwargs):
        if self.display_message_on_invalid_token:
            messages.error(request, self.invalid_token_message, fail_silently=True)
        return HttpResponseRedirect(self.get_invalid_token_redirect_url())

    def get_invalid_token_redirect_url(self):
        """
        Redirecting away from this page is recommended, so the user doesn't have any opportunity to see the invitation completion form if their token is invalid.
        """
        return resolve_url(settings.LOGIN_URL)
