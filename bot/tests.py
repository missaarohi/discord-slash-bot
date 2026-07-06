from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class SignupViewTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newadmin",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

        user = get_user_model().objects.get(username="newadmin")
        self.assertTrue(user.check_password("StrongPass123!"))
