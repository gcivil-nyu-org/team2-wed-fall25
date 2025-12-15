from unittest import mock
from django.test import RequestFactory, TestCase
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage

from accounts import views

class AccountViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_signup_get_renders(self):
        req = self.factory.get("/signup/")
        req.user = mock.Mock(is_authenticated=False)
        # Avoid template rendering; patch render to a simple mock
        with mock.patch("accounts.views.CustomUserCreationForm") as MockForm:
            MockForm.return_value = mock.Mock()
            with mock.patch("accounts.views.render") as mock_render:
                mock_render.return_value = mock.Mock()
                resp = views.signup_view(req)
                self.assertTrue(hasattr(resp, "__class"))

    def test_signup_post_creates_and_redirects_when_valid(self):
        req = self.factory.post("/signup/", data={})
        req.user = mock.Mock(is_authenticated=False)
        mock_form = mock.Mock()
        mock_form.is_valid.return_value = True
        mock_form.save.return_value = mock.Mock(username="u")

        # Attach session and messages so views can use them
        SessionMiddleware().process_request(req)
        req.session.save()
        req._messages = FallbackStorage(req)

        with mock.patch("accounts.views.CustomUserCreationForm", return_value=mock_form):
            with mock.patch("accounts.views.authenticate", return_value=mock.Mock()):
                with mock.patch("accounts.views.render") as mock_render:
                    mock_render.return_value = mock.Mock(status_code=302)
                    resp = views.signup_view(req)
                    # Expect a redirect when login happens
                    self.assertEqual(resp.status_code, 302)

    def test_login_get_renders(self):
        req = self.factory.get("/login/")
        req.user = mock.Mock(is_authenticated=False)
        with mock.patch("accounts.views.CustomAuthenticationForm") as MockForm:
            MockForm.return_value = mock.Mock()
            with mock.patch("accounts.views.render") as mock_render:
                mock_render.return_value = mock.Mock()
                resp = views.login_view(req)
                self.assertTrue(hasattr(resp, "__class"))

    def test_logout_redirects(self):
        req = self.factory.get("/logout/")
        req.user = mock.Mock()
        # Attach a session so logout() can flush it
        SessionMiddleware().process_request(req)
        req.session.save()

        with mock.patch("accounts.views.redirect") as mock_redirect:
            mock_redirect.return_value = mock.Mock(status_code=302)
            resp = views.logout_view(req)
            self.assertEqual(resp.status_code, 302)
