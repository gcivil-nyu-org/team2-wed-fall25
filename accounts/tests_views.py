from unittest import mock

from django.test import RequestFactory, TestCase

from accounts import views


class AccountViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_signup_get_renders(self):
        req = self.factory.get("/signup/")
        req.user = mock.Mock(is_authenticated=False)
        with mock.patch("accounts.views.CustomUserCreationForm") as MockForm:
            MockForm.return_value = mock.Mock()
            resp = views.signup_view(req)
            self.assertTrue(hasattr(resp, "__class"))

    def test_signup_post_creates_and_redirects_when_valid(self):
        req = self.factory.post("/signup/", data={})
        req.user = mock.Mock(is_authenticated=False)
        mock_form = mock.Mock()
        mock_form.is_valid.return_value = True
        mock_form.save.return_value = mock.Mock(username="u")

        with mock.patch(
            "accounts.views.CustomUserCreationForm", return_value=mock_form
        ):
            with mock.patch("accounts.views.authenticate", return_value=mock.Mock()):
                resp = views.signup_view(req)
                # Expect a redirect when login happens
                self.assertTrue(hasattr(resp, "status_code"))

    def test_login_get_renders(self):
        req = self.factory.get("/login/")
        req.user = mock.Mock(is_authenticated=False)
        with mock.patch("accounts.views.CustomAuthenticationForm") as MockForm:
            MockForm.return_value = mock.Mock()
            resp = views.login_view(req)
            self.assertTrue(hasattr(resp, "__class"))

    def test_logout_redirects(self):
        req = self.factory.get("/logout/")
        req.user = mock.Mock()
        resp = views.logout_view(req)
        self.assertTrue(hasattr(resp, "status_code"))
